from __future__ import annotations

import json
from pathlib import Path

from scripts.pinescript.validation.models import Scenario, ValidationFixture, Zone


def save_fixture(path: Path, *, scenario: Scenario, zones: list[Zone]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "scenario": scenario.to_dict(),
        "zones": [zone.to_dict() for zone in zones],
    }
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def load_fixture(path: Path) -> ValidationFixture:
    payload = json.loads(path.read_text(encoding="utf-8"))
    scenario = Scenario.from_dict(payload["scenario"])
    zones = [Zone.from_dict(item) for item in payload.get("zones", [])]
    return ValidationFixture(scenario=scenario, zones=zones)
