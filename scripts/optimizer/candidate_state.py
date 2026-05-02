from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class CandidateStateStore:
    def __init__(self, state_path: Path, history_path: Path) -> None:
        self.state_path = state_path
        self.history_path = history_path
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        self.history_path.parent.mkdir(parents=True, exist_ok=True)
        self.state: dict[str, Any] = self._load()

    def _load(self) -> dict[str, Any]:
        if not self.state_path.exists():
            return {"schema_version": 1, "created_at": _now(), "candidates": {}}
        return json.loads(self.state_path.read_text())

    def _save(self) -> None:
        self.state["updated_at"] = _now()
        self.state_path.write_text(json.dumps(self.state, indent=2))

    def transition(
        self,
        symbol: str,
        *,
        validation_passed: bool = False,
        latest_30d_weak: bool = False,
        validation_failed: bool = False,
        failed_cycles: int = 0,
        reasons: list[str] | None = None,
    ) -> str:
        clean = symbol.upper()
        candidates = self.state.setdefault("candidates", {})
        current = candidates.get(clean, {}).get("state", "NEW")
        new_state = current
        if validation_passed and current == "NEW":
            new_state = "ACTIVE"
        elif latest_30d_weak and current == "ACTIVE":
            new_state = "WATCH"
        elif latest_30d_weak and current == "WATCH":
            new_state = "PROBATION"
        elif validation_failed and current == "PROBATION":
            new_state = "BLOCKED"
        elif validation_failed and current == "BLOCKED" and failed_cycles >= 2:
            new_state = "RETIRED"
        elif validation_failed and current in {"NEW", "ACTIVE", "WATCH"}:
            new_state = "PROBATION"
        candidates[clean] = {"state": new_state, "updated_at": _now(), "reasons": reasons or []}
        self._save()
        event = {"timestamp": _now(), "symbol": clean, "from": current, "to": new_state, "reasons": reasons or []}
        with self.history_path.open("a") as handle:
            handle.write(json.dumps(event) + "\n")
        return new_state
