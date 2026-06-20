from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class Scenario:
    id: str
    name: str
    description: str
    steps: list[dict[str, Any]]
    expected_rules: list[str]


def load_scenario(path: Path) -> Scenario:
    with path.open(encoding="utf-8") as handle:
        data = json.load(handle)
    return Scenario(
        id=data["id"],
        name=data["name"],
        description=data["description"],
        steps=data["steps"],
        expected_rules=data["expected_rules"],
    )

