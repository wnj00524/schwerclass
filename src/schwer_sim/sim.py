from __future__ import annotations

from dataclasses import dataclass

from .core import DeterministicEngine
from .model import (
    BunkArrayComponent,
    EccsComponent,
    FailureSeverity,
    LightingComponent,
    MaintenanceState,
    ScenarioEvent,
    SignalingComponent,
    SimulationModel,
    WarpComponent,
)


class ElectricalDomainSolver:
    def solve(self, model: SimulationModel) -> None:
        main = model.domains["main"]
        eccs: EccsComponent = model.ship.systems["eccs"]  # type: ignore[assignment]
        demand = 2.2 if eccs.air_handler_enable else 1.0
        main.electrical_mw = max(0.0, 48.0 - demand * (1.0 - eccs.health))


class ThermalDomainSolver:
    def solve(self, model: SimulationModel) -> None:
        global_rejection = sum(d.thermal_rejection_mw for d in model.domains.values())
        global_load = sum(d.thermal_load_mw for d in model.domains.values())
        if global_load > global_rejection:
            model.alarms.append("GLOBAL_THERMAL_REJECTION_LIMIT")
        eccs: EccsComponent = model.ship.systems["eccs"]  # type: ignore[assignment]
        model.domains["main"].thermal_load_mw = 30.0 + (0.8 if eccs.air_handler_cooling else 0.2)
        eccs.thermal_margin = model.domains["main"].thermal_margin_mw


class AtmosphereDomainSolver:
    def solve(self, model: SimulationModel) -> None:
        eccs: EccsComponent = model.ship.systems["eccs"]  # type: ignore[assignment]
        bas: BunkArrayComponent = model.ship.systems["bas"]  # type: ignore[assignment]
        if not eccs.cassette_enable:
            model.alarms.append("O2_CASSETTE_INTERLOCK_OPEN")
        if not eccs.air_handler_cooling:
            model.alarms.append("AHU_COOLING_OFF")
        if not bas.pressure_hierarchy_preserved:
            model.alarms.append("BAS_PRESSURE_HIERARCHY_FAULT")


class PropellantDomainSolver:
    def solve(self, model: SimulationModel) -> None:
        return


class WarpEnergyDomainSolver:
    def solve(self, model: SimulationModel) -> None:
        warp: WarpComponent = model.ship.systems["warp"]  # type: ignore[assignment]
        thermal_violation = model.domains["warp"].thermal_margin_mw < 0.5
        warp.staged_abort(thermal_violation)
        if warp.stage == "abort_stage_b":
            model.alarms.append("WARP_ABORT_STAGE_B")


class ControlEngine:
    def run(self, model: SimulationModel) -> None:
        for component in model.ship.systems.values():
            component.evaluate_sensors()
            component.evaluate_control()
        lighting: LightingComponent = model.ship.systems["lighting"]  # type: ignore[assignment]
        sdss: SignalingComponent = model.ship.systems["sdss"]  # type: ignore[assignment]
        if lighting.lit_critical_routes < 1:
            model.alarms.append("LIGHTING_CRITICAL_ROUTE_LOSS")
        if not sdss.emergency_visible:
            model.alarms.append("SDSS_SAFETY_PATH_UNAVAILABLE")


class FailureEngine:
    def run(self, model: SimulationModel) -> None:
        for component in model.ship.systems.values():
            component.accumulate_wear()
            component.evaluate_failures()
            if component.failure.severity == FailureSeverity.FAILED:
                model.alarms.append(f"{component.id.upper()}_FAILED")


class MaintenanceEngine:
    def run(self, model: SimulationModel) -> None:
        dt_h = model.dt_seconds / 3600.0
        for component in model.ship.systems.values():
            component.maintenance.tick(dt_h)
            if component.maintenance.state == MaintenanceState.SCHEDULED:
                model.alarms.append(f"{component.id.upper()}_MAINTENANCE_DUE")


class EventEngine:
    def __init__(self, engine: DeterministicEngine, model: SimulationModel) -> None:
        self.engine = engine
        self.model = model
        self.engine.register_handler("scenario_event", self._handle_event)

    def schedule(self, event: ScenarioEvent) -> None:
        self.engine.schedule(event.tick, "scenario_event", event.payload)

    def _handle_event(self, payload: dict[str, object]) -> None:
        event_type = str(payload.get("event_type", ""))
        eccs: EccsComponent = self.model.ship.systems["eccs"]  # type: ignore[assignment]
        if event_type == "eccs_leak":
            eccs.no_leak = False
        elif event_type == "lighting_branch_loss":
            lighting: LightingComponent = self.model.ship.systems["lighting"]  # type: ignore[assignment]
            lighting.failed_branches += 1
        elif event_type == "dsc_failure":
            sdss: SignalingComponent = self.model.ship.systems["sdss"]  # type: ignore[assignment]
            sdss.dsc_online = False
        elif event_type == "maintenance_begin":
            eccs.maintenance.begin()
        elif event_type == "maintenance_complete":
            eccs.maintenance.complete()
        elif event_type == "warp_align":
            warp: WarpComponent = self.model.ship.systems["warp"]  # type: ignore[assignment]
            if warp.authorized():
                warp.stage = "aligned"
        elif event_type == "isolate_interface":
            group = str(payload.get("group", ""))
            for edge in self.model.interfaces:
                if edge.redundancy_group == group and edge.isolation_capability:
                    edge.isolated = True


@dataclass
class SimulationRunner:
    model: SimulationModel
    seed: int = 7

    def __post_init__(self) -> None:
        self.engine = DeterministicEngine(dt_seconds=self.model.dt_seconds, seed=self.seed)
        self.control = ControlEngine()
        self.failure = FailureEngine()
        self.maintenance = MaintenanceEngine()
        self.event = EventEngine(self.engine, self.model)
        self.electrical = ElectricalDomainSolver()
        self.thermal = ThermalDomainSolver()
        self.atmosphere = AtmosphereDomainSolver()
        self.propellant = PropellantDomainSolver()
        self.warp_energy = WarpEnergyDomainSolver()

    def step(self, steps: int = 1) -> None:
        for _ in range(steps):
            self.model.alarms.clear()
            self.engine.step()
            self.control.run(self.model)
            self.thermal.solve(self.model)
            self.electrical.solve(self.model)
            self.atmosphere.solve(self.model)
            self.propellant.solve(self.model)
            self.warp_energy.solve(self.model)
            self.failure.run(self.model)
            self.maintenance.run(self.model)
            self.model.tick += 1


class SchwerSimulation:
    """Compatibility wrapper over V2 SimulationRunner."""

    def __init__(self, seed: int = 7, dt_seconds: float = 1.0, model: SimulationModel | None = None) -> None:
        self.model = model or SimulationModel(dt_seconds=dt_seconds)
        self.runner = SimulationRunner(self.model, seed=seed)
        self.engine = self.runner.engine

    @property
    def state(self) -> SimulationModel:
        return self.model

    def step(self, steps: int = 1) -> None:
        self.runner.step(steps)

    def warp_authorized(self) -> bool:
        warp: WarpComponent = self.model.ship.systems["warp"]  # type: ignore[assignment]
        return warp.authorized()

    def pre_jump_sequence(self) -> bool:
        warp: WarpComponent = self.model.ship.systems["warp"]  # type: ignore[assignment]
        if not warp.authorized():
            warp.stage = "blocked"
            return False
        warp.stage = "aligned"
        return True

    def execute_nucleation(self) -> bool:
        warp: WarpComponent = self.model.ship.systems["warp"]  # type: ignore[assignment]
        if warp.stage != "aligned":
            return False
        warp.stage = "entry"
        return True
