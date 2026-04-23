from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class ResourceType(str, Enum):
    ELECTRICAL = "electrical"
    THERMAL = "thermal"
    OXYGEN = "oxygen"
    COOLANT = "coolant"
    PROPELLANT = "propellant"
    WARP_PLASMA = "warp_plasma"


class SignalType(str, Enum):
    COMMAND = "command"
    SENSOR = "sensor"
    AUTHORIZATION = "authorization"
    SAFETY = "safety"


class ServiceClass(str, Enum):
    CRITICAL = "critical"
    MISSION = "mission"
    HABITABILITY = "habitability"
    AUXILIARY = "auxiliary"


class FailureSeverity(str, Enum):
    NOMINAL = "nominal"
    DEGRADED = "degraded"
    LIMITED = "limited"
    FAILED = "failed"


class MaintenanceState(str, Enum):
    IN_SERVICE = "in_service"
    SCHEDULED = "scheduled"
    IN_PROGRESS = "in_progress"
    LOCKED_OUT = "locked_out"


@dataclass
class InterlockRule:
    name: str
    required_true: list[str] = field(default_factory=list)

    def evaluate(self, context: dict[str, bool]) -> bool:
        return all(context.get(k, False) for k in self.required_true)


@dataclass
class DeratingRule:
    name: str
    thermal_margin_min: float
    minimum_factor: float = 0.5

    def factor(self, thermal_margin: float) -> float:
        if thermal_margin >= self.thermal_margin_min:
            return 1.0
        deficit = self.thermal_margin_min - thermal_margin
        return max(self.minimum_factor, 1.0 - deficit / max(self.thermal_margin_min * 2, 1.0))


@dataclass
class FailureProfile:
    wear: float = 0.0
    severity: FailureSeverity = FailureSeverity.NOMINAL
    ladder: tuple[float, float, float] = (0.35, 0.65, 0.9)

    def progress(self, wear_rate: float) -> None:
        self.wear = min(1.0, self.wear + wear_rate)
        low, med, high = self.ladder
        if self.wear >= high:
            self.severity = FailureSeverity.FAILED
        elif self.wear >= med:
            self.severity = FailureSeverity.LIMITED
        elif self.wear >= low:
            self.severity = FailureSeverity.DEGRADED


@dataclass
class MaintenanceProfile:
    state: MaintenanceState = MaintenanceState.IN_SERVICE
    hours_since_service: float = 0.0
    service_interval_h: float = 1500.0

    def tick(self, dt_h: float) -> None:
        if self.state == MaintenanceState.IN_SERVICE:
            self.hours_since_service += dt_h
            if self.hours_since_service >= self.service_interval_h:
                self.state = MaintenanceState.SCHEDULED

    def begin(self) -> None:
        self.state = MaintenanceState.IN_PROGRESS

    def complete(self) -> None:
        self.state = MaintenanceState.IN_SERVICE
        self.hours_since_service = 0.0


@dataclass
class Sensor:
    name: str
    value: float | bool


@dataclass
class Actuator:
    name: str
    command: float | bool


@dataclass
class InterfaceEdge:
    source: str
    target: str
    resource_type: ResourceType
    capacity: float
    loss_model: float = 0.0
    isolation_capability: bool = True
    contamination_barrier: bool = False
    redundancy_group: str = ""
    isolated: bool = False

    def transferable_capacity(self) -> float:
        if self.isolated:
            return 0.0
        return self.capacity * (1.0 - self.loss_model)


@dataclass
class SimComponent:
    id: str
    name: str
    health: float = 1.0
    operating_mode: str = "nominal"
    maintenance: MaintenanceProfile = field(default_factory=MaintenanceProfile)
    failure: FailureProfile = field(default_factory=FailureProfile)
    sensors: dict[str, Sensor] = field(default_factory=dict)
    actuators: dict[str, Actuator] = field(default_factory=dict)

    def evaluate_sensors(self) -> None:
        return

    def evaluate_control(self) -> None:
        return

    def transfer_resources(self) -> None:
        return

    def accumulate_wear(self) -> None:
        return

    def evaluate_failures(self) -> None:
        self.failure.progress(0.0)
        self.health = max(0.0, 1.0 - self.failure.wear)


@dataclass
class DomainModel:
    name: str
    domain_type: str
    electrical_mw: float = 0.0
    thermal_load_mw: float = 0.0
    thermal_rejection_mw: float = 0.0

    @property
    def thermal_margin_mw(self) -> float:
        return self.thermal_rejection_mw - self.thermal_load_mw


@dataclass
class ZoneNode:
    id: str
    zone_type: str


@dataclass
class ComponentNode:
    id: str
    component_id: str


@dataclass
class AssemblyNode:
    id: str
    assembly_name: str


@dataclass
class ControllerNode:
    id: str
    control_domain: str


@dataclass
class StorageNode:
    id: str
    storage_type: ResourceType
    capacity: float


@dataclass
class InterfaceNode:
    id: str
    service_class: ServiceClass


@dataclass
class ScenarioEvent:
    tick: int
    event_type: str
    payload: dict[str, Any] = field(default_factory=dict)


@dataclass
class SystemNode:
    id: str
    name: str


@dataclass
class SubsystemNode:
    id: str
    parent_system_id: str
    name: str


@dataclass
class EccsComponent(SimComponent):
    zone_pressure_ok: bool = True
    no_leak: bool = True
    panel_closed: bool = True
    blower_ok: bool = True
    drain_ok: bool = True
    valve_valid: bool = True
    thermal_margin: float = 4.0
    no_freeze_risk: bool = True
    docked: bool = True
    latched: bool = True
    coolant: bool = True
    safe_headers: bool = True
    power_ok: bool = True
    cassette_enable: bool = True
    air_handler_enable: bool = True
    air_handler_cooling: bool = True

    o2_interlock: InterlockRule = field(
        default_factory=lambda: InterlockRule(
            "o2_cassette_enable",
            ["Docked", "Latched", "Coolant", "SafeHeaders", "NoLeak", "PowerOK"],
        )
    )
    air_handler_interlock: InterlockRule = field(
        default_factory=lambda: InterlockRule(
            "ahu_enable",
            ["PanelClosed", "Blower_OK", "Drain_OK", "No_Leak", "Valve_Valid", "Zone_Pressure_OK"],
        )
    )
    thermal_derating: DeratingRule = field(default_factory=lambda: DeratingRule("ahu_thermal", thermal_margin_min=2.0))

    def evaluate_control(self) -> None:
        self.cassette_enable = self.o2_interlock.evaluate(
            {
                "Docked": self.docked,
                "Latched": self.latched,
                "Coolant": self.coolant,
                "SafeHeaders": self.safe_headers,
                "NoLeak": self.no_leak,
                "PowerOK": self.power_ok,
            }
        )
        self.air_handler_enable = self.air_handler_interlock.evaluate(
            {
                "PanelClosed": self.panel_closed,
                "Blower_OK": self.blower_ok,
                "Drain_OK": self.drain_ok,
                "No_Leak": self.no_leak,
                "Valve_Valid": self.valve_valid,
                "Zone_Pressure_OK": self.zone_pressure_ok,
            }
        )
        self.air_handler_cooling = (
            self.air_handler_enable and self.thermal_margin > 0 and self.no_freeze_risk
        )
        factor = self.thermal_derating.factor(self.thermal_margin)
        self.operating_mode = "safe" if not self.air_handler_enable else ("derated" if factor < 1.0 else "nominal")

    def accumulate_wear(self) -> None:
        wear_rate = 0.0003 if self.air_handler_cooling else 0.0006
        self.failure.progress(wear_rate)

    def evaluate_failures(self) -> None:
        self.health = max(0.0, 1.0 - self.failure.wear)
        if self.failure.severity in (FailureSeverity.LIMITED, FailureSeverity.FAILED):
            self.air_handler_cooling = False


@dataclass
class LightingComponent(SimComponent):
    total_branches: int = 3
    failed_branches: int = 0
    critical_routes: int = 2
    lit_critical_routes: int = 2

    def evaluate_control(self) -> None:
        self.lit_critical_routes = max(1, self.critical_routes - min(self.failed_branches, 1))
        self.operating_mode = "nominal" if self.failed_branches == 0 else "degraded"


@dataclass
class SignalingComponent(SimComponent):
    dsc_online: bool = True
    independent_safety_path: bool = True
    emergency_visible: bool = True

    def evaluate_control(self) -> None:
        self.emergency_visible = self.independent_safety_path or self.dsc_online
        self.operating_mode = "nominal" if self.emergency_visible else "failed"


@dataclass
class BunkArrayComponent(SimComponent):
    external_airflow_ratio: float = 1.0
    pressure_gradient_ok: bool = True
    pressure_hierarchy_preserved: bool = True

    def evaluate_control(self) -> None:
        self.pressure_hierarchy_preserved = self.external_airflow_ratio > 0.0 and self.pressure_gradient_ok
        self.operating_mode = "nominal" if self.pressure_hierarchy_preserved else "safe"


@dataclass
class WarpComponent(SimComponent):
    auth_mass: bool = True
    auth_thermal: bool = True
    auth_hardware: bool = True
    auth_command: bool = True
    stage: str = "idle"

    def authorized(self) -> bool:
        return self.auth_mass and self.auth_thermal and self.auth_hardware and self.auth_command

    def evaluate_control(self) -> None:
        if not self.authorized():
            self.stage = "blocked"
            self.operating_mode = "safe"
        elif self.stage == "idle":
            self.operating_mode = "nominal"

    def staged_abort(self, thermal_violation: bool) -> None:
        if thermal_violation and self.stage in {"aligned", "entry"}:
            self.stage = "abort_stage_b"
            self.operating_mode = "safe"


@dataclass
class ShipModel:
    systems: dict[str, SimComponent] = field(default_factory=dict)


@dataclass
class SimulationModel:
    schema_version: int = 2
    tick: int = 0
    dt_seconds: float = 1.0
    domains: dict[str, DomainModel] = field(
        default_factory=lambda: {
            "main": DomainModel("Main Ship Power Domain", "major", electrical_mw=48.0, thermal_load_mw=30.0, thermal_rejection_mw=38.0),
            "sublight": DomainModel("Sublight Propulsion Domain", "major", electrical_mw=62.0, thermal_load_mw=50.0, thermal_rejection_mw=57.0),
            "warp": DomainModel("Warp Domain", "major", electrical_mw=0.0, thermal_load_mw=8.0, thermal_rejection_mw=14.0),
            "maneuver": DomainModel("Maneuvering/Docking", "minor", electrical_mw=6.0, thermal_load_mw=4.0, thermal_rejection_mw=5.0),
            "survivability": DomainModel("Emergency Survivability", "minor", electrical_mw=4.0, thermal_load_mw=2.0, thermal_rejection_mw=6.0),
        }
    )
    ship: ShipModel = field(
        default_factory=lambda: ShipModel(
            systems={
                "eccs": EccsComponent(id="eccs", name="ECCS / HECS"),
                "lighting": LightingComponent(id="lighting", name="Lighting System"),
                "sdss": SignalingComponent(id="sdss", name="Display Signaling System"),
                "bas": BunkArrayComponent(id="bas", name="Bunk Array System"),
                "warp": WarpComponent(id="warp", name="Warp System"),
            }
        )
    )
    interfaces: list[InterfaceEdge] = field(default_factory=list)
    alarms: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        eccs = self.ship.systems["eccs"]
        lighting = self.ship.systems["lighting"]
        sdss = self.ship.systems["sdss"]
        bas = self.ship.systems["bas"]
        warp = self.ship.systems["warp"]
        return {
            "schema_version": self.schema_version,
            "tick": self.tick,
            "dt_seconds": self.dt_seconds,
            "domains": {k: v.__dict__ for k, v in self.domains.items()},
            "ship": {
                "systems": {
                    "eccs": {
                        "id": eccs.id,
                        "name": eccs.name,
                        "health": eccs.health,
                        "operating_mode": eccs.operating_mode,
                        "maintenance": {
                            "state": eccs.maintenance.state.value,
                            "hours_since_service": eccs.maintenance.hours_since_service,
                            "service_interval_h": eccs.maintenance.service_interval_h,
                        },
                        "failure": {
                            "wear": eccs.failure.wear,
                            "severity": eccs.failure.severity.value,
                            "ladder": list(eccs.failure.ladder),
                        },
                        "states": {
                            "zone_pressure_ok": eccs.zone_pressure_ok,
                            "no_leak": eccs.no_leak,
                            "panel_closed": eccs.panel_closed,
                            "blower_ok": eccs.blower_ok,
                            "drain_ok": eccs.drain_ok,
                            "valve_valid": eccs.valve_valid,
                            "thermal_margin": eccs.thermal_margin,
                            "no_freeze_risk": eccs.no_freeze_risk,
                            "docked": eccs.docked,
                            "latched": eccs.latched,
                            "coolant": eccs.coolant,
                            "safe_headers": eccs.safe_headers,
                            "power_ok": eccs.power_ok,
                            "cassette_enable": eccs.cassette_enable,
                            "air_handler_enable": eccs.air_handler_enable,
                            "air_handler_cooling": eccs.air_handler_cooling,
                        },
                        "lighting": {
                            "failed_branches": lighting.failed_branches,
                            "lit_critical_routes": lighting.lit_critical_routes,
                            "critical_routes": lighting.critical_routes,
                        },
                        "sdss": {
                            "dsc_online": sdss.dsc_online,
                            "independent_safety_path": sdss.independent_safety_path,
                            "emergency_visible": sdss.emergency_visible,
                        },
                        "bas": {
                            "external_airflow_ratio": bas.external_airflow_ratio,
                            "pressure_gradient_ok": bas.pressure_gradient_ok,
                            "pressure_hierarchy_preserved": bas.pressure_hierarchy_preserved,
                        },
                        "warp": {
                            "auth_mass": warp.auth_mass,
                            "auth_thermal": warp.auth_thermal,
                            "auth_hardware": warp.auth_hardware,
                            "auth_command": warp.auth_command,
                            "stage": warp.stage,
                        },
                    }
                }
            },
            "interfaces": [
                {
                    "source": i.source,
                    "target": i.target,
                    "resource_type": i.resource_type.value,
                    "capacity": i.capacity,
                    "loss_model": i.loss_model,
                    "isolation_capability": i.isolation_capability,
                    "contamination_barrier": i.contamination_barrier,
                    "redundancy_group": i.redundancy_group,
                    "isolated": i.isolated,
                }
                for i in self.interfaces
            ],
            "alarms": self.alarms,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "SimulationModel":
        if data.get("schema_version", 1) < 2:
            raise ValueError("V1 data must be loaded through adapter")
        model = cls()
        model.tick = data.get("tick", 0)
        model.dt_seconds = data.get("dt_seconds", 1.0)
        model.domains = {k: DomainModel(**v) for k, v in data.get("domains", {}).items()}

        eccs_data = data.get("ship", {}).get("systems", {}).get("eccs", {})
        eccs = EccsComponent(id=eccs_data.get("id", "eccs"), name=eccs_data.get("name", "ECCS / HECS"))
        maint = eccs_data.get("maintenance", {})
        eccs.maintenance = MaintenanceProfile(
            state=MaintenanceState(maint.get("state", MaintenanceState.IN_SERVICE.value)),
            hours_since_service=maint.get("hours_since_service", 0.0),
            service_interval_h=maint.get("service_interval_h", 1500.0),
        )
        fail = eccs_data.get("failure", {})
        eccs.failure = FailureProfile(
            wear=fail.get("wear", 0.0),
            severity=FailureSeverity(fail.get("severity", FailureSeverity.NOMINAL.value)),
            ladder=tuple(fail.get("ladder", [0.35, 0.65, 0.9])),
        )
        states = eccs_data.get("states", {})
        for key, value in states.items():
            if hasattr(eccs, key):
                setattr(eccs, key, value)
        eccs.health = eccs_data.get("health", 1.0)
        eccs.operating_mode = eccs_data.get("operating_mode", "nominal")

        systems = data.get("ship", {}).get("systems", {})
        lighting_data = systems.get("lighting", {})
        sdss_data = systems.get("sdss", {})
        bas_data = systems.get("bas", {})
        warp_data = systems.get("warp", {})
        lighting = LightingComponent(id="lighting", name="Lighting System")
        lighting.failed_branches = lighting_data.get("failed_branches", 0)
        lighting.lit_critical_routes = lighting_data.get("lit_critical_routes", 2)
        lighting.critical_routes = lighting_data.get("critical_routes", 2)
        sdss = SignalingComponent(id="sdss", name="Display Signaling System")
        sdss.dsc_online = sdss_data.get("dsc_online", True)
        sdss.independent_safety_path = sdss_data.get("independent_safety_path", True)
        sdss.emergency_visible = sdss_data.get("emergency_visible", True)
        bas = BunkArrayComponent(id="bas", name="Bunk Array System")
        bas.external_airflow_ratio = bas_data.get("external_airflow_ratio", 1.0)
        bas.pressure_gradient_ok = bas_data.get("pressure_gradient_ok", True)
        bas.pressure_hierarchy_preserved = bas_data.get("pressure_hierarchy_preserved", True)
        warp = WarpComponent(id="warp", name="Warp System")
        warp.auth_mass = warp_data.get("auth_mass", True)
        warp.auth_thermal = warp_data.get("auth_thermal", True)
        warp.auth_hardware = warp_data.get("auth_hardware", True)
        warp.auth_command = warp_data.get("auth_command", True)
        warp.stage = warp_data.get("stage", "idle")

        model.ship = ShipModel(systems={"eccs": eccs, "lighting": lighting, "sdss": sdss, "bas": bas, "warp": warp})
        model.interfaces = [
            InterfaceEdge(
                source=i["source"],
                target=i["target"],
                resource_type=ResourceType(i["resource_type"]),
                capacity=i["capacity"],
                loss_model=i.get("loss_model", 0.0),
                isolation_capability=i.get("isolation_capability", True),
                contamination_barrier=i.get("contamination_barrier", False),
                redundancy_group=i.get("redundancy_group", ""),
                isolated=i.get("isolated", False),
            )
            for i in data.get("interfaces", [])
        ]
        model.alarms = list(data.get("alarms", []))
        return model


@dataclass
class LegacyNetworkV1:
    nodes: list[dict[str, Any]] = field(default_factory=list)
    edges: list[dict[str, Any]] = field(default_factory=list)
    traffic: list[dict[str, Any]] = field(default_factory=list)


class V1ToV2Adapter:
    @staticmethod
    def adapt(network: LegacyNetworkV1) -> SimulationModel:
        model = SimulationModel()
        provisional_components = [n for n in network.nodes if n.get("kind") == "component"]
        if provisional_components:
            model.ship.systems["eccs"].name = provisional_components[0].get("name", "ECCS / HECS")
        for edge in network.edges:
            resource = edge.get("traffic", "electrical")
            try:
                resource_type = ResourceType(resource)
            except ValueError:
                resource_type = ResourceType.ELECTRICAL
            model.interfaces.append(
                InterfaceEdge(
                    source=edge.get("source", "legacy_a"),
                    target=edge.get("target", "legacy_b"),
                    resource_type=resource_type,
                    capacity=float(edge.get("capacity", 1.0)),
                    loss_model=float(edge.get("loss", 0.0)),
                    isolation_capability=bool(edge.get("isolatable", True)),
                    contamination_barrier=bool(edge.get("barrier", False)),
                    redundancy_group=str(edge.get("redundancy", "legacy")),
                )
            )
        return model
