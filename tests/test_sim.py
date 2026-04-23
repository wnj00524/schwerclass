from schwer_sim.model import (
    InterfaceEdge,
    MaintenanceState,
    ResourceType,
    ScenarioEvent,
)
from schwer_sim.sim import SchwerSimulation


def test_deterministic_repeatability_from_seed() -> None:
    a = SchwerSimulation(seed=123)
    b = SchwerSimulation(seed=123)
    for _ in range(200):
        a.step()
        b.step()
    assert a.state.to_dict() == b.state.to_dict()


def test_interlock_o2_cassette_formula() -> None:
    sim = SchwerSimulation()
    eccs = sim.state.ship.systems["eccs"]
    eccs.docked = True
    eccs.latched = True
    eccs.coolant = True
    eccs.safe_headers = True
    eccs.no_leak = True
    eccs.power_ok = True
    sim.step()
    assert eccs.cassette_enable

    eccs.no_leak = False
    sim.step()
    assert not eccs.cassette_enable


def test_failure_ladder_progression_not_binary() -> None:
    sim = SchwerSimulation()
    eccs = sim.state.ship.systems["eccs"]
    eccs.no_freeze_risk = False
    sim.step(1200)
    assert eccs.failure.wear > 0.35
    assert eccs.failure.severity.value in {"degraded", "limited", "failed"}


def test_thermal_derating() -> None:
    sim = SchwerSimulation()
    eccs = sim.state.ship.systems["eccs"]
    sim.state.domains["main"].thermal_rejection_mw = 30.5
    sim.step(2)
    assert eccs.operating_mode in {"derated", "safe"}


def test_isolation_behavior_single_branch_loss_survivable() -> None:
    sim = SchwerSimulation()
    sim.state.interfaces = [
        InterfaceEdge("a", "b", ResourceType.ELECTRICAL, 10.0, redundancy_group="critical_1"),
        InterfaceEdge("a", "c", ResourceType.ELECTRICAL, 10.0, redundancy_group="critical_2"),
    ]
    sim.runner.event.schedule(ScenarioEvent(tick=0, event_type="scenario_event", payload={"event_type": "isolate_interface", "group": "critical_1"}))
    sim.step()
    capacities = [e.transferable_capacity() for e in sim.state.interfaces]
    assert capacities[0] == 0.0
    assert capacities[1] > 0.0


def test_maintenance_state_transitions() -> None:
    sim = SchwerSimulation()
    eccs = sim.state.ship.systems["eccs"]
    eccs.maintenance.service_interval_h = 0.0001
    sim.step(2)
    assert eccs.maintenance.state == MaintenanceState.SCHEDULED

    sim.runner.event.schedule(ScenarioEvent(tick=0, event_type="scenario_event", payload={"event_type": "maintenance_begin"}))
    sim.step()
    assert eccs.maintenance.state == MaintenanceState.IN_PROGRESS

    eccs.maintenance.service_interval_h = 5.0
    sim.runner.event.schedule(ScenarioEvent(tick=0, event_type="scenario_event", payload={"event_type": "maintenance_complete"}))
    sim.step()
    assert eccs.maintenance.state == MaintenanceState.IN_SERVICE


def test_v1_loader_adapter() -> None:
    from schwer_sim.persistence import ScenarioStore
    import json
    import tempfile
    from pathlib import Path

    legacy = {
        "metadata": {"name": "legacy"},
        "state": {
            "nodes": [{"kind": "component", "name": "Legacy ECCS"}],
            "edges": [{"source": "n1", "target": "n2", "traffic": "electrical", "capacity": 2.0}],
            "traffic": [],
        },
    }
    with tempfile.TemporaryDirectory() as td:
        p = Path(td) / "legacy.json"
        p.write_text(json.dumps(legacy))
        _, model = ScenarioStore.load(p)

    assert model.schema_version == 2
    assert model.ship.systems["eccs"].name == "Legacy ECCS"
    assert len(model.interfaces) == 1


def test_lighting_branch_segmentation_survives_single_loss() -> None:
    sim = SchwerSimulation()
    sim.runner.event.schedule(ScenarioEvent(tick=0, event_type="scenario_event", payload={"event_type": "lighting_branch_loss"}))
    sim.step()
    lighting = sim.state.ship.systems["lighting"]
    assert lighting.lit_critical_routes >= 1


def test_sdss_safety_path_independent_from_dsc() -> None:
    sim = SchwerSimulation()
    sim.runner.event.schedule(ScenarioEvent(tick=0, event_type="scenario_event", payload={"event_type": "dsc_failure"}))
    sim.step()
    sdss = sim.state.ship.systems["sdss"]
    assert sdss.emergency_visible


def test_bas_enforces_nonzero_external_airflow() -> None:
    sim = SchwerSimulation()
    bas = sim.state.ship.systems["bas"]
    bas.external_airflow_ratio = 0.0
    sim.step()
    assert not bas.pressure_hierarchy_preserved
    assert "BAS_PRESSURE_HIERARCHY_FAULT" in sim.state.alarms


def test_warp_requires_authorization_and_supports_staged_abort() -> None:
    sim = SchwerSimulation()
    warp = sim.state.ship.systems["warp"]
    warp.auth_command = False
    assert not sim.pre_jump_sequence()
    assert warp.stage == "blocked"

    warp.auth_command = True
    assert sim.pre_jump_sequence()
    sim.state.domains["warp"].thermal_rejection_mw = 6.0
    sim.state.domains["warp"].thermal_load_mw = 8.0
    sim.step()
    assert warp.stage == "abort_stage_b"
