from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .model import SimulationState


class ScenarioStore:
    @staticmethod
    def load(path: str | Path) -> tuple[dict[str, Any], SimulationState]:
        data = json.loads(Path(path).read_text())
        return data["metadata"], SimulationState.from_dict(data["state"])

    @staticmethod
    def save(path: str | Path, metadata: dict[str, Any], state: SimulationState) -> None:
        body = {
            "metadata": metadata,
            "state": state.to_dict(),
        }
        Path(path).write_text(json.dumps(body, indent=2))
