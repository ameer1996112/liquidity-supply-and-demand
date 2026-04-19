"""
runtime_state.py — machine-readable optimizer run state and worker event logs.

This helper is intentionally simple and synchronous: the parallel optimizer runs
in a single asyncio process, so small load/modify/write JSON updates are easy to
reason about and do not need an async persistence layer.
"""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _iso_now() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat()


@dataclass
class OptimizerRuntimeState:
    results_dir: Path
    current_status_path: Path = field(init=False)
    restart_history_path: Path = field(init=False)

    def __post_init__(self) -> None:
        self.results_dir.mkdir(parents=True, exist_ok=True)
        self.current_status_path = self.results_dir / "optimizer_status_current.json"
        self.restart_history_path = self.results_dir / "optimizer_restart_history.jsonl"

    def start_run(
        self,
        *,
        args: list[str],
        mode: str,
        workers: int,
        log_file: str,
        optimizer_pid: int,
        desktop_cdp_pid: int | None,
        restart_count: int = 0,
    ) -> dict[str, Any]:
        run_id = f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}"
        payload = {
            "run_id": run_id,
            "state": "starting",
            "started_at": _iso_now(),
            "last_progress_at": _iso_now(),
            "stuck_threshold_seconds": 12 * 60,
            "restart_count": restart_count,
            "optimizer_pid": optimizer_pid,
            "desktop_cdp_pid": desktop_cdp_pid,
            "log_file": log_file,
            "mode": mode,
            "workers": workers,
            "args": args,
            "active_pairs": {},
            "worker_health": {},
        }
        self._write_status(payload)
        return payload

    def load_current_status(self) -> dict[str, Any]:
        return json.loads(self.current_status_path.read_text(encoding="utf-8"))

    def mark_pair_started(self, *, run_id: str, worker_id: int, symbol: str) -> None:
        status = self._load_run_status(run_id)
        worker_key = f"worker-{worker_id}"
        now = _iso_now()
        status["state"] = "running"
        status["active_pairs"][worker_key] = {
            "symbol": symbol,
            "trial": 0,
            "last_event_at": now,
            "status": "running",
        }
        status["worker_health"].setdefault(
            worker_key,
            {
                "status": "healthy",
                "stale_reads": 0,
                "last_results_hash": "",
            },
        )
        status["last_progress_at"] = now
        self._write_status(status)

    def mark_pair_completed(self, *, run_id: str, worker_id: int, symbol: str) -> None:
        status = self._load_run_status(run_id)
        worker_key = f"worker-{worker_id}"
        now = _iso_now()
        prior = status["active_pairs"].get(worker_key, {})
        status["active_pairs"][worker_key] = {
            "symbol": symbol,
            "trial": prior.get("trial", 0),
            "last_event_at": now,
            "status": "completed",
        }
        status["last_progress_at"] = now
        self._write_status(status)

    def mark_worker_unhealthy(
        self,
        *,
        run_id: str,
        worker_id: int,
        stale_reads: int,
        reason: str,
    ) -> None:
        status = self._load_run_status(run_id)
        worker_key = f"worker-{worker_id}"
        previous = status["worker_health"].get(worker_key, {})
        status["worker_health"][worker_key] = {
            "status": "unhealthy",
            "stale_reads": stale_reads,
            "reason": reason,
            "last_results_hash": previous.get("last_results_hash", ""),
        }
        self._write_status(status)

    def record_trial_event(
        self,
        *,
        run_id: str,
        worker_id: int,
        symbol: str,
        trial: int,
        outcome: str,
        params_hash: str,
        results_hash_before: str,
        results_hash_after: str,
        metrics: dict[str, Any] | None = None,
    ) -> None:
        status = self._load_run_status(run_id)
        worker_key = f"worker-{worker_id}"
        now = _iso_now()
        prior_health = status["worker_health"].get(worker_key, {})
        stale_reads = int(prior_health.get("stale_reads", 0))
        if outcome == "fresh":
            stale_reads = 0
            status["last_progress_at"] = now
        else:
            stale_reads += 1

        status["active_pairs"][worker_key] = {
            "symbol": symbol,
            "trial": trial,
            "last_event_at": now,
            "status": "running",
        }
        status["worker_health"][worker_key] = {
            "status": "healthy" if outcome == "fresh" else "warning",
            "stale_reads": stale_reads,
            "last_results_hash": results_hash_after,
        }
        self._write_status(status)

        event_path = self.results_dir / f"optimizer_worker_{worker_id}_{run_id}.jsonl"
        event_payload = {
            "ts": now,
            "run_id": run_id,
            "worker_id": worker_id,
            "symbol": symbol,
            "trial": trial,
            "outcome": outcome,
            "params_hash": params_hash,
            "results_hash_before": results_hash_before,
            "results_hash_after": results_hash_after,
            "metrics": metrics or {},
        }
        with event_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(event_payload) + "\n")

    def set_run_state(self, *, run_id: str, state: str) -> None:
        status = self._load_run_status(run_id)
        status["state"] = state
        if state in {"completed", "failed"}:
            status["last_progress_at"] = _iso_now()
        self._write_status(status)

    def record_run_event(self, *, run_id: str, event_type: str, payload: dict[str, Any]) -> None:
        event_path = self.results_dir / f"optimizer_events_{run_id}.jsonl"
        event = {"ts": _iso_now(), "run_id": run_id, "event_type": event_type, **payload}
        with event_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(event) + "\n")

    def append_restart_history(self, payload: dict[str, Any]) -> None:
        with self.restart_history_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload) + "\n")

    def _load_run_status(self, run_id: str) -> dict[str, Any]:
        status_path = self.results_dir / f"optimizer_status_{run_id}.json"
        if status_path.exists():
            return json.loads(status_path.read_text(encoding="utf-8"))
        return self.load_current_status()

    def _write_status(self, payload: dict[str, Any]) -> None:
        status_path = self.results_dir / f"optimizer_status_{payload['run_id']}.json"
        encoded = json.dumps(payload, indent=2)
        status_path.write_text(encoded, encoding="utf-8")
        self.current_status_path.write_text(encoded, encoding="utf-8")
