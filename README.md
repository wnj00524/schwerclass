# SchwerSim

Desktop-first engineering simulation for the Schwer Class Freighter. The app models ship-service systems, propulsion, warp chain readiness, environmental control domains, maintenance-heavy components, and progressive fault/derating ladders.

## Features
- Deterministic fixed-step simulation core (headless-capable).
- Separate energy domains:
  - Main ship power (D-T service reactor abstraction)
  - Sublight propulsion power (dedicated reactor chain)
  - Warp energy chain (antimatter inventory -> conversion -> buffers/projector path)
- Thermal rejection as first-order limiter.
- Warp authorization based on cargo geometry/mass moments, hardware readiness, and thermal/environmental readiness.
- Split ECCS domains (habitat, cargo, process).
- Maintenance/fault simulation for scrubbers, getter cartridges, O2 cassettes, air handlers, lighting/signaling branches.
- Desktop multi-dashboard UI with Operations/Engineering/Maintenance/Sandbox style controls.
- Scenario save/load JSON.

## Run
```bash
python -m venv .venv
source .venv/bin/activate
pip install -e . pytest
python -m schwer_sim.app
```

## Tests
```bash
pytest -q
```

## Scenario files
Located in `scenarios/`:
- `nominal_cruise.json`
- `cargo_imbalance_before_warp.json`
- `radiator_damage_thermal_derating.json`
- `co2_scrubber_underperformance.json`
- `getter_jam_approaching.json`
- `o2_cassette_failure_reroute.json`
- `air_handler_condensate_fault.json`
- `emergency_lighting_transfer_failure.json`
- `propulsion_hot_section_overheating.json`
- `warp_authorization_failed_metrology.json`

## Scope note
The model intentionally uses engineering-style reduced-order approximations rather than CFD/plasma/GR solvers. It emphasizes mechanism, traceability, dependency propagation, and survivability-biased failure behavior.
