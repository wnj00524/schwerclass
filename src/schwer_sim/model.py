from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class ResourceDomain:
    name: str
    electrical_mw: float
    thermal_load_mw: float
    thermal_rejection_mw: float
    bus_isolated: bool = False

    @property
    def thermal_margin_mw(self) -> float:
        return self.thermal_rejection_mw - self.thermal_load_mw


@dataclass
class AtmosphereZone:
    name: str
    o2_kpa: float
    co2_kpa: float
    humidity_pct: float
    pressure_kpa: float
    contamination_ppm: float


@dataclass
class ReactorState:
    output_mw: float
    max_mw: float
    derate: float = 1.0
    cryo_ready: bool = True
    isotope_ratio: float = 1.0
    maintenance_due_hours: float = 2000.0


@dataclass
class PropulsionState:
    mode: str = "idle"
    hydrogen_kg: float = 180000.0
    thrust_kn: float = 0.0
    hot_section_temp_c: float = 200.0
    nozzle_health: float = 1.0
    plasma_stability: float = 1.0
    online: bool = True


@dataclass
class ThermalLoop:
    name: str
    load_mw: float
    reject_mw: float
    isolated_segments: int = 0
    total_segments: int = 6

    @property
    def margin(self) -> float:
        reduction = (self.isolated_segments / max(self.total_segments, 1)) * 0.5
        return self.reject_mw * (1 - reduction) - self.load_mw


@dataclass
class CargoState:
    mass_tonnes: float
    centroid_m: float
    pitch_moment: float
    yaw_moment: float
    roll_moment: float
    ballast_state: float = 0.0
    geometry_ok: bool = True


@dataclass
class WarpState:
    antimatter_cartridges: int = 4
    train_ready: bool = True
    conversion_online: bool = True
    bulk_storage_gj: float = 0.0
    pulse_network_ready: bool = True
    bow_nucleation_ready: bool = True
    capture_ring_ready: bool = True
    ring_stations_ready: int = 8
    stage: str = "idle"
    auth_reason: str = ""
    armed: bool = False


@dataclass
class EccsState:
    habitat: AtmosphereZone = field(default_factory=lambda: AtmosphereZone("habitat", 21.1, 0.45, 45.0, 101.2, 20.0))
    cargo: AtmosphereZone = field(default_factory=lambda: AtmosphereZone("cargo", 20.0, 0.5, 55.0, 100.8, 60.0))
    process: AtmosphereZone = field(default_factory=lambda: AtmosphereZone("process", 19.5, 0.7, 60.0, 100.0, 140.0))
    comfort_mode: bool = True
    emergency_mode: bool = False


@dataclass
class ScrubberTrain:
    beds_total: int = 4
    beds_ready: int = 4
    poisoning: float = 0.0
    regen_quality: float = 1.0


@dataclass
class GetterCartridge:
    uptake_capacity: float = 1.0
    used_fraction: float = 0.5
    poisoning: float = 0.0
    pressure_drop: float = 0.1
    jam_risk: float = 0.1
    spring_travel_ok: bool = True


@dataclass
class O2Rack:
    cassette_total: int = 6
    cassette_online: int = 6
    branch_bypass_open: bool = False
    purity: float = 0.995


@dataclass
class AirHandlerModule:
    blower_health: float = 1.0
    condensate_ok: bool = True
    enabled: bool = True


@dataclass
class LightingState:
    egress_routes: int = 3
    lit_egress_routes: int = 3
    emergency_path_independent: bool = True
    branch_failures: int = 0


@dataclass
class DisplaySignalingState:
    dsc_online: bool = True
    emergency_signaling_visible: bool = True


@dataclass
class SeatingState:
    mount_health: float = 1.0
    damper_health: float = 1.0
    restraint_health: float = 1.0


@dataclass
class BunkState:
    branches: int = 8
    blocked_branches: int = 0
    local_co2_rise: float = 0.0


@dataclass
class SimulationState:
    time_s: float = 0.0
    main_power: ResourceDomain = field(default_factory=lambda: ResourceDomain("main", 48.0, 31.0, 39.0))
    propulsion_power: ResourceDomain = field(default_factory=lambda: ResourceDomain("propulsion", 62.0, 50.0, 57.0))
    warp_power: ResourceDomain = field(default_factory=lambda: ResourceDomain("warp", 0.0, 8.0, 14.0))
    main_reactor: ReactorState = field(default_factory=lambda: ReactorState(48.0, 60.0))
    propulsion_reactor: ReactorState = field(default_factory=lambda: ReactorState(62.0, 90.0))
    propulsion: PropulsionState = field(default_factory=PropulsionState)
    thermal_loops: dict[str, ThermalLoop] = field(
        default_factory=lambda: {
            "main": ThermalLoop("main", 31.0, 39.0),
            "propulsion": ThermalLoop("propulsion", 50.0, 57.0),
            "warp": ThermalLoop("warp", 8.0, 14.0),
            "emergency": ThermalLoop("emergency", 0.0, 10.0),
        }
    )
    tritium_inventory_kg: float = 430.0
    tritium_contamination_grams: float = 0.0
    cargo: CargoState = field(default_factory=lambda: CargoState(28000.0, 0.0, 0.0, 0.0, 0.0))
    warp: WarpState = field(default_factory=WarpState)
    eccs: EccsState = field(default_factory=EccsState)
    scrubber: ScrubberTrain = field(default_factory=ScrubberTrain)
    getter: GetterCartridge = field(default_factory=GetterCartridge)
    o2_rack: O2Rack = field(default_factory=O2Rack)
    air_handler: AirHandlerModule = field(default_factory=AirHandlerModule)
    lighting: LightingState = field(default_factory=LightingState)
    signaling: DisplaySignalingState = field(default_factory=DisplaySignalingState)
    seating: SeatingState = field(default_factory=SeatingState)
    bunk: BunkState = field(default_factory=BunkState)
    alarms: list[str] = field(default_factory=list)
    maintenance: dict[str, float] = field(default_factory=dict)
    sandbox: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "time_s": self.time_s,
            "main_power": self.main_power.__dict__,
            "propulsion_power": self.propulsion_power.__dict__,
            "warp_power": self.warp_power.__dict__,
            "main_reactor": self.main_reactor.__dict__,
            "propulsion_reactor": self.propulsion_reactor.__dict__,
            "propulsion": self.propulsion.__dict__,
            "thermal_loops": {k: v.__dict__ for k, v in self.thermal_loops.items()},
            "tritium_inventory_kg": self.tritium_inventory_kg,
            "tritium_contamination_grams": self.tritium_contamination_grams,
            "cargo": self.cargo.__dict__,
            "warp": self.warp.__dict__,
            "eccs": {
                "habitat": self.eccs.habitat.__dict__,
                "cargo": self.eccs.cargo.__dict__,
                "process": self.eccs.process.__dict__,
                "comfort_mode": self.eccs.comfort_mode,
                "emergency_mode": self.eccs.emergency_mode,
            },
            "scrubber": self.scrubber.__dict__,
            "getter": self.getter.__dict__,
            "o2_rack": self.o2_rack.__dict__,
            "air_handler": self.air_handler.__dict__,
            "lighting": self.lighting.__dict__,
            "signaling": self.signaling.__dict__,
            "seating": self.seating.__dict__,
            "bunk": self.bunk.__dict__,
            "alarms": self.alarms,
            "maintenance": self.maintenance,
            "sandbox": self.sandbox,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "SimulationState":
        s = cls()
        s.time_s = data.get("time_s", 0.0)
        s.main_power = ResourceDomain(**data["main_power"])
        s.propulsion_power = ResourceDomain(**data["propulsion_power"])
        s.warp_power = ResourceDomain(**data["warp_power"])
        s.main_reactor = ReactorState(**data["main_reactor"])
        s.propulsion_reactor = ReactorState(**data["propulsion_reactor"])
        s.propulsion = PropulsionState(**data["propulsion"])
        s.thermal_loops = {k: ThermalLoop(**v) for k, v in data["thermal_loops"].items()}
        s.tritium_inventory_kg = data["tritium_inventory_kg"]
        s.tritium_contamination_grams = data["tritium_contamination_grams"]
        s.cargo = CargoState(**data["cargo"])
        s.warp = WarpState(**data["warp"])
        e = data["eccs"]
        s.eccs = EccsState(
            habitat=AtmosphereZone(**e["habitat"]),
            cargo=AtmosphereZone(**e["cargo"]),
            process=AtmosphereZone(**e["process"]),
            comfort_mode=e["comfort_mode"],
            emergency_mode=e["emergency_mode"],
        )
        s.scrubber = ScrubberTrain(**data["scrubber"])
        s.getter = GetterCartridge(**data["getter"])
        s.o2_rack = O2Rack(**data["o2_rack"])
        s.air_handler = AirHandlerModule(**data["air_handler"])
        s.lighting = LightingState(**data["lighting"])
        s.signaling = DisplaySignalingState(**data["signaling"])
        s.seating = SeatingState(**data["seating"])
        s.bunk = BunkState(**data["bunk"])
        s.alarms = list(data.get("alarms", []))
        s.maintenance = dict(data.get("maintenance", {}))
        s.sandbox = data.get("sandbox", False)
        return s
