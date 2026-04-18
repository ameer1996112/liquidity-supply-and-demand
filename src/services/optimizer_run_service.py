from __future__ import annotations

import copy
import json
import os
import subprocess
import sys
import threading
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Protocol

from src.adapters.supabase_api import get_api_supabase
from src.services.optimizer_defaults import DEFAULT_PAIRS


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _coerce_event_payload(payload: dict[str, Any]) -> dict[str, Any]:
    return json.loads(json.dumps(payload, default=str))


def _normalize_run(row: dict[str, Any] | None) -> dict[str, Any] | None:
    if row is None:
        return None
    return {
        "id": row["id"],
        "strategy_id": row.get("strategy_id"),
        "strategy_version": row.get("strategy_version"),
        "status": row["status"],
        "mode": row["mode"],
        "workers": row["workers"],
        "pairs": row.get("pairs") or [],
        "n_trials": row["n_trials"],
        "dd_limit": float(row["dd_limit"]),
        "dry_run": bool(row.get("dry_run", False)),
        "broker": row.get("broker"),
        "market": row.get("market"),
        "created_by": row.get("created_by"),
        "summary": row.get("summary") or {},
        "started_at": row.get("started_at"),
        "finished_at": row.get("finished_at"),
        "created_at": row.get("created_at"),
        "updated_at": row.get("updated_at"),
    }


def _normalize_portfolio_result(row: dict[str, Any] | None) -> dict[str, Any] | None:
    if row is None:
        return None
    metrics = row.get("metrics")
    return metrics if isinstance(metrics, dict) else {}


def _build_artifact_summary(
    trials: list[dict[str, Any]],
    stress_results: list[dict[str, Any]],
    events: list[dict[str, Any]],
) -> dict[str, Any]:
    symbols: dict[str, dict[str, Any]] = {}

    for trial in trials:
        symbol = trial.get("symbol")
        if not symbol:
            continue
        entry = symbols.setdefault(
            symbol,
            {"trial_count": 0, "stress_result_count": 0, "latest_event_type": None},
        )
        entry["trial_count"] += 1

    for stress_result in stress_results:
        symbol = stress_result.get("symbol")
        if not symbol:
            continue
        entry = symbols.setdefault(
            symbol,
            {"trial_count": 0, "stress_result_count": 0, "latest_event_type": None},
        )
        entry["stress_result_count"] += 1

    for event in events:
        symbol = event.get("symbol")
        if not symbol:
            continue
        entry = symbols.setdefault(
            symbol,
            {"trial_count": 0, "stress_result_count": 0, "latest_event_type": None},
        )
        entry["latest_event_type"] = event.get("event_type")

    return {
        "trial_count": len(trials),
        "stress_result_count": len(stress_results),
        "event_count": len(events),
        "symbols": symbols,
    }


_TERMINAL_RUN_STATUSES = {"completed", "failed", "cancelled", "interrupted"}


class OptimizerRunRepository(Protocol):
    def create_run(self, payload: dict[str, Any]) -> dict[str, Any]: ...
    def update_run(self, run_id: str, updates: dict[str, Any]) -> dict[str, Any]: ...
    def get_run(self, run_id: str) -> dict[str, Any] | None: ...
    def list_runs(
        self,
        *,
        limit: int = 20,
        status: str | None = None,
        strategy_id: str | None = None,
        strategy_version: str | None = None,
    ) -> list[dict[str, Any]]: ...
    def list_incomplete_runs(self) -> list[dict[str, Any]]: ...
    def create_results(self, run_id: str, symbols: list[str]) -> None: ...
    def update_result(self, run_id: str, symbol: str, updates: dict[str, Any]) -> dict[str, Any]: ...
    def list_results(self, run_id: str) -> list[dict[str, Any]]: ...
    def create_trial(self, run_id: str, symbol: str, payload: dict[str, Any]) -> dict[str, Any]: ...
    def list_trials(self, run_id: str, symbol: str | None = None) -> list[dict[str, Any]]: ...
    def create_stress_result(self, run_id: str, symbol: str, payload: dict[str, Any]) -> dict[str, Any]: ...
    def list_stress_results(self, run_id: str, symbol: str | None = None) -> list[dict[str, Any]]: ...
    def upsert_portfolio_result(self, run_id: str, payload: dict[str, Any]) -> dict[str, Any]: ...
    def get_portfolio_result(self, run_id: str) -> dict[str, Any] | None: ...
    def append_event(self, payload: dict[str, Any]) -> dict[str, Any]: ...
    def list_events(self, run_id: str, *, limit: int = 200) -> list[dict[str, Any]]: ...


class SupabaseOptimizerRunRepository:
    def __init__(self) -> None:
        self._sb = get_api_supabase()

    def create_run(self, payload: dict[str, Any]) -> dict[str, Any]:
        resp = self._sb.table("optimizer_runs").insert(payload).execute()
        return _normalize_run(resp.data[0]) if resp.data else payload

    def update_run(self, run_id: str, updates: dict[str, Any]) -> dict[str, Any]:
        payload = {**updates, "updated_at": _utc_now()}
        resp = (
            self._sb.table("optimizer_runs")
            .update(payload)
            .eq("id", run_id)
            .execute()
        )
        if resp.data:
            return _normalize_run(resp.data[0])
        current = self.get_run(run_id)
        if current is None:
            raise KeyError(run_id)
        current.update(payload)
        return current

    def get_run(self, run_id: str) -> dict[str, Any] | None:
        resp = (
            self._sb.table("optimizer_runs")
            .select("*")
            .eq("id", run_id)
            .limit(1)
            .execute()
        )
        if not resp.data:
            return None
        return _normalize_run(resp.data[0])

    def list_runs(
        self,
        *,
        limit: int = 20,
        status: str | None = None,
        strategy_id: str | None = None,
        strategy_version: str | None = None,
    ) -> list[dict[str, Any]]:
        query = (
            self._sb.table("optimizer_runs")
            .select("*")
            .order("created_at", desc=True)
            .limit(limit)
        )
        if status:
            query = query.eq("status", status)
        if strategy_id:
            query = query.eq("strategy_id", strategy_id)
        if strategy_version:
            query = query.eq("strategy_version", strategy_version)
        resp = query.execute()
        return [_normalize_run(row) for row in (resp.data or []) if row]

    def list_incomplete_runs(self) -> list[dict[str, Any]]:
        resp = (
            self._sb.table("optimizer_runs")
            .select("*")
            .in_("status", ["queued", "running"])
            .execute()
        )
        return [_normalize_run(row) for row in (resp.data or []) if row]

    def create_results(self, run_id: str, symbols: list[str]) -> None:
        rows = [
            {
                "run_id": run_id,
                "symbol": symbol,
                "status": "pending",
                "params": {},
                "metrics": {},
            }
            for symbol in symbols
        ]
        if rows:
            self._sb.table("optimizer_run_results").insert(rows).execute()

    def update_result(self, run_id: str, symbol: str, updates: dict[str, Any]) -> dict[str, Any]:
        payload = {**updates, "updated_at": _utc_now()}
        resp = (
            self._sb.table("optimizer_run_results")
            .update(payload)
            .eq("run_id", run_id)
            .eq("symbol", symbol)
            .execute()
        )
        return resp.data[0] if resp.data else {"run_id": run_id, "symbol": symbol, **payload}

    def list_results(self, run_id: str) -> list[dict[str, Any]]:
        resp = (
            self._sb.table("optimizer_run_results")
            .select("*")
            .eq("run_id", run_id)
            .order("symbol")
            .execute()
        )
        return resp.data or []

    def create_trial(self, run_id: str, symbol: str, payload: dict[str, Any]) -> dict[str, Any]:
        row = {"run_id": run_id, "symbol": symbol, **payload}
        resp = self._sb.table("optimizer_run_trials").insert(row).execute()
        return resp.data[0] if resp.data else row

    def list_trials(self, run_id: str, symbol: str | None = None) -> list[dict[str, Any]]:
        query = (
            self._sb.table("optimizer_run_trials")
            .select("*")
            .eq("run_id", run_id)
            .order("trial_number")
        )
        if symbol is not None:
            query = query.eq("symbol", symbol)
        resp = query.execute()
        return resp.data or []

    def create_stress_result(self, run_id: str, symbol: str, payload: dict[str, Any]) -> dict[str, Any]:
        row = {"run_id": run_id, "symbol": symbol, **payload}
        resp = self._sb.table("optimizer_run_stress_tests").insert(row).execute()
        return resp.data[0] if resp.data else row

    def list_stress_results(self, run_id: str, symbol: str | None = None) -> list[dict[str, Any]]:
        query = (
            self._sb.table("optimizer_run_stress_tests")
            .select("*")
            .eq("run_id", run_id)
            .order("created_at")
        )
        if symbol is not None:
            query = query.eq("symbol", symbol)
        resp = query.execute()
        return resp.data or []

    def upsert_portfolio_result(self, run_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        row = {"run_id": run_id, "metrics": payload}
        resp = (
            self._sb.table("optimizer_portfolio_results")
            .upsert(row, on_conflict="run_id")
            .execute()
        )
        return _normalize_portfolio_result(resp.data[0]) if resp.data else payload

    def get_portfolio_result(self, run_id: str) -> dict[str, Any] | None:
        resp = (
            self._sb.table("optimizer_portfolio_results")
            .select("*")
            .eq("run_id", run_id)
            .limit(1)
            .execute()
        )
        if not resp.data:
            return None
        return _normalize_portfolio_result(resp.data[0])

    def append_event(self, payload: dict[str, Any]) -> dict[str, Any]:
        resp = self._sb.table("optimizer_run_events").insert(payload).execute()
        return resp.data[0] if resp.data else payload

    def list_events(self, run_id: str, *, limit: int = 200) -> list[dict[str, Any]]:
        resp = (
            self._sb.table("optimizer_run_events")
            .select("*")
            .eq("run_id", run_id)
            .order("created_at", desc=True)
            .limit(limit)
            .execute()
        )
        return list(reversed(resp.data or []))


@dataclass
class _ManagedProcess:
    process: subprocess.Popen[str]
    reader: threading.Thread


class OptimizerRunService:
    def __init__(self, repository: OptimizerRunRepository, project_root: Path | None = None, results_dir: Path | None = None) -> None:
        self._repository = repository
        self._project_root = project_root
        self._results_dir = results_dir
        self._processes: dict[str, _ManagedProcess] = {}
        self._lock = threading.Lock()

    def _require_run_exists(self, run_id: str) -> dict[str, Any]:
        run = self._repository.get_run(run_id)
        if run is None:
            raise KeyError(run_id)
        return run

    def start_run(
        self,
        *,
        strategy_id: str,
        strategy_version: str,
        mode: str,
        workers: int,
        pairs: list[str],
        n_trials: int,
        dd_limit: float,
        dry_run: bool,
        broker: str,
        created_by: str | None = None,
    ) -> dict[str, Any]:
        """Create a queued optimizer run for the local agent to pick up."""
        if not strategy_id:
            raise ValueError("strategy_id is required")
        if not strategy_version:
            raise ValueError("strategy_version is required")
        if not pairs:
            raise ValueError("pairs must not be empty")
        if broker not in {"vantage", "oanda", "fxcm"}:
            raise ValueError(f"invalid broker: {broker}")
        if self._active_run_exists():
            raise ValueError("another optimizer run is already active")

        if pairs == ["ALL"]:
            pairs = list(DEFAULT_PAIRS)

        run_id = str(uuid.uuid4())
        created_at = _utc_now()
        run = self._repository.create_run(
            {
                "id": run_id,
                "strategy_id": strategy_id,
                "strategy_version": strategy_version,
                "status": "queued",
                "mode": mode,
                "workers": workers,
                "pairs": pairs,
                "n_trials": n_trials,
                "dd_limit": dd_limit,
                "dry_run": dry_run,
                "broker": broker,
                "market": "forex",
                "created_by": created_by,
                "summary": {
                    "total_pairs": len(pairs),
                    "running_pairs": 0,
                    "completed_pairs": 0,
                    "failed_pairs": 0,
                },
                "created_at": created_at,
                "updated_at": created_at,
            }
        )
        self._repository.create_results(run_id, pairs)
        return run

    # ── Agent-facing write methods ─────────────────────────────────────────────

    def update_run_from_agent(
        self, run_id: str, *, status: str | None = None, summary: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """Update run status/summary from the local agent."""
        run = self._repository.get_run(run_id)
        if run is None:
            raise KeyError(run_id)
        updates: dict[str, Any] = {}
        if status is not None:
            updates["status"] = status
            if status == "running" and not run.get("started_at"):
                updates["started_at"] = _utc_now()
            if status in {"completed", "failed"}:
                updates["finished_at"] = _utc_now()
        if summary is not None:
            merged = dict(run.get("summary") or {})
            merged.update(summary)
            updates["summary"] = merged
        if not updates:
            return run
        return self._repository.update_run(run_id, updates)

    def update_result_from_agent(
        self, run_id: str, symbol: str, updates: dict[str, Any]
    ) -> dict[str, Any]:
        """Update a per-symbol result from the local agent."""
        run = self._repository.get_run(run_id)
        if run is None:
            raise KeyError(run_id)
        result = self._repository.update_result(run_id, symbol, updates)
        # Rebuild summary after result change
        self._repository.update_run(
            run_id, {"summary": self._rebuild_summary(run_id)}
        )
        return result

    def push_event(self, run_id: str, event: dict[str, Any]) -> dict[str, Any]:
        """Push a timeline event from the local agent."""
        self._require_run_exists(run_id)
        event["run_id"] = run_id
        return self._repository.append_event(event)

    def record_trial(self, run_id: str, symbol: str, payload: dict[str, Any]) -> dict[str, Any]:
        self._require_run_exists(run_id)
        return self._repository.create_trial(run_id, symbol, payload)

    def list_trials(self, run_id: str, symbol: str | None = None) -> list[dict[str, Any]]:
        self.get_run(run_id)
        return self._repository.list_trials(run_id, symbol)

    def record_stress_result(self, run_id: str, symbol: str, payload: dict[str, Any]) -> dict[str, Any]:
        self._require_run_exists(run_id)
        return self._repository.create_stress_result(run_id, symbol, payload)

    def list_stress_results(self, run_id: str, symbol: str | None = None) -> list[dict[str, Any]]:
        self.get_run(run_id)
        return self._repository.list_stress_results(run_id, symbol)

    def update_portfolio_result(self, run_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        self._require_run_exists(run_id)
        return self._repository.upsert_portfolio_result(run_id, payload)

    def get_portfolio_result(self, run_id: str) -> dict[str, Any] | None:
        self._require_run_exists(run_id)
        return self._repository.get_portfolio_result(run_id)

    # ── Read methods ─────────────────────────────────────────────────────────

    def list_runs(
        self,
        *,
        limit: int = 20,
        status: str | None = None,
        strategy_id: str | None = None,
        strategy_version: str | None = None,
    ) -> list[dict[str, Any]]:
        return self._repository.list_runs(
            limit=limit,
            status=status,
            strategy_id=strategy_id,
            strategy_version=strategy_version,
        )

    def get_run(self, run_id: str) -> dict[str, Any]:
        run = self._repository.get_run(run_id)
        if run is None:
            raise KeyError(run_id)
        run = copy.deepcopy(run)
        run["portfolio_result"] = copy.deepcopy(self._repository.get_portfolio_result(run_id))
        if run.get("status") in _TERMINAL_RUN_STATUSES:
            results = copy.deepcopy(self._repository.list_results(run_id))
            trials = copy.deepcopy(self._repository.list_trials(run_id))
            stress_results = copy.deepcopy(self._repository.list_stress_results(run_id))
            events = copy.deepcopy(self._repository.list_events(run_id, limit=200))
            run["results"] = results
            run["artifacts"] = {
                "trials": trials,
                "stress_results": stress_results,
                "events": events,
                "summary": _build_artifact_summary(trials, stress_results, events),
            }
        return run

    def list_results(self, run_id: str) -> list[dict[str, Any]]:
        return self._repository.list_results(run_id)

    def list_events(self, run_id: str, *, limit: int = 200) -> list[dict[str, Any]]:
        return self._repository.list_events(run_id, limit=limit)

    def cancel_run(self, run_id: str) -> dict[str, Any]:
        """Mark a run as cancelled. The local agent polls for this and stops."""
        run = self._repository.get_run(run_id)
        if run is None:
            raise KeyError(run_id)
        if run["status"] in {"completed", "failed", "cancelled", "interrupted"}:
            return run
        # Kill local subprocess if one exists (legacy path)
        managed = self._processes.get(run_id)
        if managed is not None:
            managed.process.terminate()
        self._repository.append_event(
            {
                "run_id": run_id,
                "event_type": "run_cancelled",
                "worker_id": None,
                "symbol": None,
                "payload": {"source": "api"},
            }
        )
        cancelled_run = self._repository.update_run(
            run_id,
            {
                "status": "cancelled",
                "finished_at": _utc_now(),
                "summary": self._rebuild_summary(run_id),
            },
        )
        for result in self._repository.list_results(run_id):
            if result["status"] in {"pending", "running"}:
                self._repository.update_result(
                    run_id,
                    result["symbol"],
                    {"status": "cancelled", "finished_at": _utc_now()},
                )
        return cancelled_run

    def reconcile_incomplete_runs(self) -> None:
        for run in self._repository.list_incomplete_runs():
            if run["id"] not in self._processes:
                self._repository.update_run(
                    run["id"],
                    {
                        "status": "interrupted",
                        "finished_at": _utc_now(),
                        "summary": self._rebuild_summary(run["id"], existing=run.get("summary") or {}),
                    },
                )

    def ingest_event(self, event: dict[str, Any]) -> None:
        run_id = event["run_id"]
        event_type = event["event_type"]
        symbol = event.get("symbol")
        worker_id = event.get("worker_id")
        payload = _coerce_event_payload(event)
        self._repository.append_event(
            {
                "run_id": run_id,
                "event_type": event_type,
                "worker_id": worker_id,
                "symbol": symbol,
                "payload": payload,
            }
        )
        now = _utc_now()
        if event_type == "pair_started" and symbol:
            self._repository.update_result(run_id, symbol, {"status": "running", "started_at": now})
        elif event_type == "pair_completed" and symbol:
            self._repository.update_result(
                run_id,
                symbol,
                {
                    "status": "completed",
                    "params": event.get("params", {}),
                    "metrics": event.get("metrics", {}),
                    "finished_at": now,
                },
            )
        elif event_type == "pair_failed" and symbol:
            self._repository.update_result(
                run_id,
                symbol,
                {
                    "status": "failed",
                    "error_message": event.get("error_message") or "optimizer pair failed",
                    "finished_at": now,
                },
            )
        elif event_type == "run_finished":
            updates: dict[str, Any] = {
                "status": event.get("status", "completed"),
                "finished_at": now,
            }
            updates["summary"] = self._rebuild_summary(run_id, outputs=event.get("output_paths"))
            self._repository.update_run(run_id, updates)
            self._cleanup_process(run_id)
            return
        self._repository.update_run(
            run_id,
            {
                "summary": self._rebuild_summary(run_id),
            },
        )

    def _active_run_exists(self) -> bool:
        return any(run["status"] in {"queued", "running"} for run in self._repository.list_runs(limit=10))

    def _spawn_process(
        self,
        *,
        mode: str,
        workers: int,
        pairs: list[str],
        n_trials: int,
        dd_limit: float,
        dry_run: bool,
        broker: str,
    ) -> subprocess.Popen[str]:
        command = [
            sys.executable,
            "-m",
            "scripts.optimizer.parallel_runner",
            "--workers",
            str(workers),
            "--mode",
            mode,
            "--trials",
            str(n_trials),
            "--dd-limit",
            str(dd_limit),
            "--pairs",
            ",".join(pairs),
            "--broker",
            broker,
        ]
        if dry_run:
            command.append("--dry-run")
        env = dict(**os.environ)
        env["PYTHONPATH"] = env.get("PYTHONPATH") or "."
        return subprocess.Popen(
            command,
            cwd=self._project_root,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            env=env,
        )

    def _stream_process_output(self, run_id: str, process: subprocess.Popen[str]) -> None:
        if process.stdout is None:
            return
        for raw_line in process.stdout:
            line = raw_line.strip()
            if not line:
                continue
            event = self._parse_event_line(line)
            if event is not None:
                if "run_id" not in event:
                    event["run_id"] = run_id
                self.ingest_event(event)
                continue
            self._repository.append_event(
                {
                    "run_id": run_id,
                    "event_type": "log",
                    "worker_id": None,
                    "symbol": None,
                    "payload": {"message": line},
                }
            )
        exit_code = process.wait()
        run = self._repository.get_run(run_id)
        if run is None:
            return
        if run["status"] == "cancelled":
            self._cleanup_process(run_id)
            return
        if run["status"] in {"completed", "failed"}:
            self._cleanup_process(run_id)
            return
        final_status = "completed" if exit_code == 0 else "failed"
        self._repository.update_run(
            run_id,
            {
                "status": final_status,
                "finished_at": _utc_now(),
                "summary": self._rebuild_summary(run_id, existing=run.get("summary") or {}),
            },
        )
        self._cleanup_process(run_id)

    def _parse_event_line(self, line: str) -> dict[str, Any] | None:
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            return None
        if isinstance(payload, dict) and "event_type" in payload:
            return payload
        return None

    def _cleanup_process(self, run_id: str) -> None:
        with self._lock:
            self._processes.pop(run_id, None)

    def _rebuild_summary(
        self,
        run_id: str,
        *,
        existing: dict[str, Any] | None = None,
        outputs: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        results = self._repository.list_results(run_id)
        summary = dict(existing or {})
        total_pairs = len(results)
        running_pairs = sum(1 for result in results if result["status"] == "running")
        completed_pairs = sum(1 for result in results if result["status"] == "completed")
        failed_pairs = sum(1 for result in results if result["status"] == "failed")
        best_symbol = summary.get("best_symbol")
        best_score = summary.get("best_score")
        for result in results:
            metrics = result.get("metrics") or {}
            score = metrics.get("score")
            if isinstance(score, (int, float)) and (best_score is None or score > best_score):
                best_score = float(score)
                best_symbol = result["symbol"]
        summary.update(
            {
                "total_pairs": total_pairs,
                "running_pairs": running_pairs,
                "completed_pairs": completed_pairs,
                "failed_pairs": failed_pairs,
                "best_symbol": best_symbol,
                "best_score": best_score,
            }
        )
        if outputs:
            summary["output_paths"] = outputs
        return summary


_service_lock = threading.Lock()
_service: OptimizerRunService | None = None


def get_optimizer_run_service() -> OptimizerRunService:
    global _service
    if _service is None:
        with _service_lock:
            if _service is None:
                _service = OptimizerRunService(
                    repository=SupabaseOptimizerRunRepository(),
                )
                _service.reconcile_incomplete_runs()
    return _service
