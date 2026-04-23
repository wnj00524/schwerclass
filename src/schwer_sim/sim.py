from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .core import DeterministicEngine
from .model import SimulationState


@dataclass
class SnapshotManager:
    checkpoints: list[dict[str, Any]] = field(default_factory=list)

    def save_checkpoint(self, state: SimulationState) -> None:
        self.checkpoints.append(state.to_dict())
        self.checkpoints = self.checkpoints[-8:]

    def rewind(self, state: SimulationState) -> SimulationState:
        if not self.checkpoints:
            return state
        return SimulationState.from_dict(self.checkpoints[-1])


class SchwerSimulation:
    def __init__(self, seed: int = 7, dt_seconds: float = 1.0, state: SimulationState | None = None) -> None:
        self.state = state or SimulationState()
        self.engine = DeterministicEngine(dt_seconds=dt_seconds, seed=seed)
        self.snapshots = SnapshotManager()
        self._register_handlers()

    def _register_handlers(self) -> None:
        self.engine.register_handler("inject_fault", self._inject_fault)
        self.engine.register_handler("schedule_maintenance", self._schedule_maintenance)

    def step(self, steps: int = 1) -> None:
        for _ in range(steps):
            self.engine.step()
            self.state.time_s += self.engine.dt_seconds
            self._advance_subsystems()
            if self.engine.tick % 60 == 0:
                self.snapshots.save_checkpoint(self.state)

    def _advance_subsystems(self) -> None:
        self.state.alarms.clear()
        self._advance_thermal()
        self._advance_main_power()
        self._advance_tritium()
        self._advance_propulsion()
        self._advance_eccs()
        self._advance_scrubber_and_getter()
        self._advance_o2()
        self._advance_lighting_and_signaling()
        self._advance_hab_modules()
        self._evaluate_warp_authorization()

    def _advance_thermal(self) -> None:
        for name, loop in self.state.thermal_loops.items():
            if name == "propulsion":
                loop.load_mw = 20.0 + self.state.propulsion.thrust_kn / 20.0
            if name == "warp" and self.state.warp.armed:
                loop.load_mw = 12.0 + self.state.warp.bulk_storage_gj / 200.0
            margin = loop.margin
            if margin < 0:
                self.state.alarms.append(f"THERMAL_DERATE_{name.upper()}")

    def _advance_main_power(self) -> None:
        loop_margin = self.state.thermal_loops["main"].margin
        derate = 1.0
        if loop_margin < 2.0:
            derate *= max(0.5, 0.7 + loop_margin / 10.0)
        if self.state.main_reactor.isotope_ratio < 0.95:
            derate *= 0.92
        if self.state.tritium_contamination_grams > 60:
            derate *= 0.85
        self.state.main_reactor.derate = derate
        self.state.main_power.electrical_mw = self.state.main_reactor.max_mw * derate * 0.8
        self.state.main_power.thermal_load_mw = 25 + (1 - derate) * 8

    def _advance_tritium(self) -> None:
        rng = self.engine.rng
        drift = 0.00002 * (1.0 + rng.random() * 0.1)
        self.state.main_reactor.isotope_ratio = max(0.9, self.state.main_reactor.isotope_ratio - drift)
        leak = 0.0 if self.state.getter.used_fraction < 0.8 else 0.003
        self.state.tritium_contamination_grams += leak

    def _advance_propulsion(self) -> None:
        p = self.state.propulsion
        if not p.online:
            p.thrust_kn = 0.0
            return
        mode_to_target = {"departure": 900.0, "cruise": 520.0, "economy": 220.0, "idle": 0.0}
        target = mode_to_target.get(p.mode, 0.0)
        if self.state.thermal_loops["propulsion"].margin < 0 or p.hot_section_temp_c > 920:
            target *= 0.4
            self.state.alarms.append("PROPULSION_DERATE")
        p.thrust_kn += (target - p.thrust_kn) * 0.08
        p.hot_section_temp_c += p.thrust_kn * 0.002 - 0.6
        p.hot_section_temp_c = max(120.0, p.hot_section_temp_c)
        p.hydrogen_kg = max(0.0, p.hydrogen_kg - p.thrust_kn * 0.002)
        if p.hydrogen_kg <= 0.0:
            p.online = False
            self.state.alarms.append("PROP_H2_STARVATION")

    def _advance_eccs(self) -> None:
        e = self.state.eccs
        habitat = e.habitat
        co2_growth = 0.0025 if e.comfort_mode else 0.0012
        o2_drop = 0.0018 if e.comfort_mode else 0.0008
        if e.emergency_mode:
            co2_growth *= 0.7
            o2_drop *= 0.55
        habitat.co2_kpa += co2_growth * (5 - self.state.scrubber.beds_ready) * 0.2
        habitat.o2_kpa -= o2_drop * max(0, 4 - self.state.o2_rack.cassette_online) * 0.2
        # inward bias toward dirtier zones
        habitat.contamination_ppm += max(0.0, (e.process.contamination_ppm - habitat.contamination_ppm) * 0.0003)
        if habitat.co2_kpa > 0.9:
            self.state.alarms.append("HAB_CO2_HIGH")

    def _advance_scrubber_and_getter(self) -> None:
        s = self.state.scrubber
        g = self.state.getter
        s.regen_quality = max(0.6, s.regen_quality - s.poisoning * 0.0001)
        eff_capacity = s.beds_total * s.regen_quality - s.poisoning * 0.5
        s.beds_ready = max(1, int(eff_capacity))

        g.used_fraction = min(1.0, g.used_fraction + 0.0006)
        g.pressure_drop = min(1.0, g.pressure_drop + 0.0004)
        g.jam_risk = min(1.0, g.jam_risk + 0.0008 + g.pressure_drop * 0.0002)
        if g.jam_risk > 0.75:
            self.state.alarms.append("GETTER_JAM_APPROACH")

    def _advance_o2(self) -> None:
        rack = self.state.o2_rack
        if rack.cassette_online < 2 and not rack.branch_bypass_open:
            self.state.eccs.habitat.o2_kpa -= 0.01
        rack.purity = max(0.95, rack.purity - (rack.cassette_total - rack.cassette_online) * 0.0002)

    def _advance_lighting_and_signaling(self) -> None:
        l = self.state.lighting
        l.lit_egress_routes = max(1, l.egress_routes - l.branch_failures)
        if l.lit_egress_routes < 2:
            self.state.alarms.append("EGRESS_MARGIN_LOW")
        s = self.state.signaling
        s.emergency_signaling_visible = (not s.dsc_online and l.emergency_path_independent) or s.dsc_online

    def _advance_hab_modules(self) -> None:
        if not self.state.air_handler.condensate_ok:
            self.state.eccs.habitat.humidity_pct += 0.03
            self.state.alarms.append("AHU_CONDENSATE_FAULT")
        self.state.seating.damper_health = max(0.7, self.state.seating.damper_health - self.state.propulsion.thrust_kn * 0.0000005)
        flow_loss = self.state.bunk.blocked_branches / max(self.state.bunk.branches, 1)
        self.state.bunk.local_co2_rise += flow_loss * 0.0005

    def _evaluate_warp_authorization(self) -> None:
        w = self.state.warp
        c = self.state.cargo
        blockers: list[str] = []
        if not c.geometry_ok:
            blockers.append("cargo_geometry")
        if abs(c.centroid_m) > 1.2 or abs(c.pitch_moment) > 300 or abs(c.yaw_moment) > 300 or abs(c.roll_moment) > 300:
            blockers.append("mass_distribution")
        if self.state.thermal_loops["warp"].margin < 1.0:
            blockers.append("warp_thermal")
        if self.state.tritium_contamination_grams > 80:
            blockers.append("environmental_clearance")
        if not w.train_ready or not w.capture_ring_ready or not w.bow_nucleation_ready:
            blockers.append("hardware_readiness")
        if self.state.main_reactor.isotope_ratio < 0.94:
            blockers.append("cryo_or_fuel_quality")
        w.auth_reason = ",".join(blockers)

    def warp_authorized(self) -> bool:
        return self.state.warp.auth_reason == ""

    def pre_jump_sequence(self) -> bool:
        w = self.state.warp
        if not self.warp_authorized():
            w.stage = "blocked"
            return False
        if w.antimatter_cartridges < 1:
            w.stage = "blocked"
            w.auth_reason = "no_antimatter"
            return False
        w.armed = True
        w.bulk_storage_gj = 600.0
        w.stage = "aligned"
        return True

    def execute_nucleation(self) -> bool:
        w = self.state.warp
        if w.stage != "aligned":
            return False
        # Stage-based abort logic prefers survivability
        if self.state.thermal_loops["warp"].margin < 0:
            w.stage = "abort_stage_b"
            w.bulk_storage_gj *= 0.2
            self.state.alarms.append("WARP_ABORT_STAGE_B")
            return False
        w.stage = "sustainment"
        w.bulk_storage_gj -= 120.0
        return True

    def safe_getter_extraction(self, brute_force: bool = False) -> bool:
        g = self.state.getter
        if brute_force and g.jam_risk > 0.4:
            self.state.alarms.append("GETTER_BREACH_RISK")
            return False
        return g.spring_travel_ok and g.jam_risk < 0.85

    def _inject_fault(self, payload: dict[str, Any]) -> None:
        key = payload.get("key")
        if key == "lighting_branch_loss":
            self.state.lighting.branch_failures += 1
        elif key == "dsc_failure":
            self.state.signaling.dsc_online = False
        elif key == "prop_hot_section":
            self.state.propulsion.hot_section_temp_c = 980
        elif key == "o2_cassette_failure":
            self.state.o2_rack.cassette_online = max(0, self.state.o2_rack.cassette_online - 1)
        elif key == "getter_jam":
            self.state.getter.jam_risk = 0.92
        elif key == "radiator_damage":
            self.state.thermal_loops["main"].isolated_segments += 2

    def _schedule_maintenance(self, payload: dict[str, Any]) -> None:
        system = payload["system"]
        duration_h = payload.get("duration_h", 2)
        self.state.maintenance[system] = self.state.time_s + duration_h * 3600
