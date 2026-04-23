from schwer_sim.sim import SchwerSimulation


def test_deterministic_repeatability_from_seed() -> None:
    a = SchwerSimulation(seed=123)
    b = SchwerSimulation(seed=123)
    for _ in range(200):
        a.step()
        b.step()
    assert a.state.to_dict() == b.state.to_dict()


def test_lighting_branch_loss_keeps_egress_route() -> None:
    sim = SchwerSimulation()
    sim.engine.schedule(0, "inject_fault", {"key": "lighting_branch_loss"})
    sim.step()
    assert sim.state.lighting.lit_egress_routes >= 1


def test_propulsion_loss_not_remove_ship_service_power() -> None:
    sim = SchwerSimulation()
    sim.state.propulsion.online = False
    sim.step(10)
    assert sim.state.main_power.electrical_mw > 0


def test_cargo_imbalance_blocks_warp_authorization() -> None:
    sim = SchwerSimulation()
    sim.state.cargo.centroid_m = 2.5
    sim.step()
    assert not sim.warp_authorized()
    assert "mass_distribution" in sim.state.warp.auth_reason


def test_emergency_atmosphere_preserves_o2_co2_longer_than_comfort() -> None:
    comfort = SchwerSimulation()
    comfort.state.scrubber.beds_ready = 1
    comfort.state.o2_rack.cassette_online = 1
    comfort.state.eccs.comfort_mode = True

    emergency = SchwerSimulation()
    emergency.state.scrubber.beds_ready = 1
    emergency.state.o2_rack.cassette_online = 1
    emergency.state.eccs.comfort_mode = False
    emergency.state.eccs.emergency_mode = True

    comfort.step(400)
    emergency.step(400)

    assert emergency.state.eccs.habitat.co2_kpa <= comfort.state.eccs.habitat.co2_kpa
    assert emergency.state.eccs.habitat.o2_kpa >= comfort.state.eccs.habitat.o2_kpa


def test_o2_cassette_fault_isolates_at_branch_level() -> None:
    sim = SchwerSimulation()
    sim.engine.schedule(0, "inject_fault", {"key": "o2_cassette_failure"})
    sim.step()
    assert sim.state.o2_rack.cassette_online == 5
    assert sim.state.o2_rack.cassette_online > 0


def test_jammed_getter_recovery_refuses_unsafe_brute_extraction() -> None:
    sim = SchwerSimulation()
    sim.state.getter.jam_risk = 0.8
    assert not sim.safe_getter_extraction(brute_force=True)


def test_emergency_signaling_visible_after_dsc_failure() -> None:
    sim = SchwerSimulation()
    sim.engine.schedule(0, "inject_fault", {"key": "dsc_failure"})
    sim.step()
    assert sim.state.signaling.emergency_signaling_visible


def test_thermal_overload_causes_derating_not_collapse() -> None:
    sim = SchwerSimulation()
    sim.state.thermal_loops["main"].isolated_segments = 5
    sim.step(100)
    assert sim.state.main_reactor.derate < 1.0
    assert sim.state.main_power.electrical_mw > 0
