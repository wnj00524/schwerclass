# SchwerSim Architecture Notes

## Simulation approximations
SchwerSim uses reduced-order subsystem models with explicit state variables (capacity, load, margin, wear, contamination, and fault indexes) and deterministic update rules.

- **Power domains** are independent resources: main ship services, propulsion services, and warp chain buffers.
- **Thermal-first gating** derates reactors/propulsion/warp readiness by per-loop rejection margin.
- **Warp chain** enforces staged readiness and stage-based abort behavior.
- **ECCS** keeps habitat/cargo/process atmospheres separate with inward contamination bias.
- **Maintenance-heavy systems** (getter, scrubber beds, O2 cassettes, air handlers) degrade progressively and are recoverable through procedures.

## Core modules
- `schwer_sim.core`: deterministic fixed-step engine + event queue.
- `schwer_sim.model`: dataclasses for subsystem state, resources, and scenario schema.
- `schwer_sim.sim`: system-graph style step logic and dependency propagation.
- `schwer_sim.persistence`: scenario/save JSON IO.
- `schwer_sim.app`: desktop UI (Tkinter engineering panels).

## Save/load JSON shape
- `metadata`: scenario metadata and seed
- `state`: complete graph snapshot with stable IDs-by-field and typed subsystem objects

## Time controls
- Pause
- Step-by-step
- 1x / 10x / 100x

## Replay/checkpoint
Every 60 ticks, simulation snapshots are stored in-memory for rewind to last checkpoint.
