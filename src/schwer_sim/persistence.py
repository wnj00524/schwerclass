from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .model import LegacyNetworkV1, SimulationModel, V1ToV2Adapter


class ScenarioStore:
    @staticmethod
    def load(path: str | Path) -> tuple[dict[str, Any], SimulationModel]:
        data = json.loads(Path(path).read_text())
        metadata = data.get("metadata", {})
        state = data.get("state", data)

        schema = state.get("schema_version", 1)
        if schema >= 2:
            return metadata, SimulationModel.from_dict(state)

        if {"nodes", "edges"}.issubset(state.keys()):
            legacy_network = LegacyNetworkV1(
                nodes=state.get("nodes", []),
                edges=state.get("edges", []),
                traffic=state.get("traffic", []),
            )
            return metadata, V1ToV2Adapter.adapt(legacy_network)

        # legacy flat SimulationState fallback
        legacy_network = LegacyNetworkV1(nodes=[{"kind": "component", "name": "ECCS / HECS"}], edges=[])
        model = V1ToV2Adapter.adapt(legacy_network)
        tritium = state.get("tritium_contamination_grams", 0.0)
        if tritium > 80:
            model.alarms.append("LEGACY_ENV_CLEARANCE_ALERT")
        return metadata, model

    @staticmethod
    def save(path: str | Path, metadata: dict[str, Any], model: SimulationModel) -> None:
        body = {
            "metadata": metadata,
            "state": model.to_dict(),
        }
        Path(path).write_text(json.dumps(body, indent=2))
