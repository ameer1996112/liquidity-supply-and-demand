from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Protocol

from src.adapters.supabase_api import get_api_supabase

logger = logging.getLogger(__name__)

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
_PARALLEL_RESULTS_FILE = _PROJECT_ROOT / "scripts" / "optimization_results" / "parallel_results.json"

_CONFIG_STATUSES = {"candidate", "approved", "archived"}
_BATCH_STATUSES = {"queued", "running", "completed", "failed", "cancelled", "interrupted"}
_BATCH_SOURCE_MODES = {"top3", "top5", "approved", "custom"}
_RESULT_STATUSES = {"pending", "running", "completed", "created", "skipped", "failed", "cancelled"}


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _coerce_payload(payload: dict[str, Any]) -> dict[str, Any]:
    return json.loads(json.dumps(payload, default=str))


def _normalize_pair(value: str) -> str:
    pair = (value or "").strip().upper()
    if not pair:
        raise ValueError("pair must not be empty")
    return pair


def _normalize_timeframe(value: str) -> str:
    timeframe = (value or "").strip()
    if not timeframe:
        raise ValueError("timeframe must not be empty")
    return timeframe


def _normalize_config(row: dict[str, Any] | None) -> dict[str, Any] | None:
    if row is None:
        return None
    return {
        "id": row["id"],
        "pair": row["pair"],
        "timeframe": row["timeframe"],
        "status": row["status"],
        "params": row.get("params") or {},
        "risk_weight": float(row.get("risk_weight", 1.0)),
        "source_run_id": row.get("source_run_id"),
        "source_score": float(row["source_score"]) if row.get("source_score") is not None else None,
        "source_metrics": row.get("source_metrics") or {},
        "notes": row.get("notes"),
        "created_by": row.get("created_by"),
        "created_at": row.get("created_at"),
        "updated_at": row.get("updated_at"),
    }


def _normalize_batch(row: dict[str, Any] | None) -> dict[str, Any] | None:
    if row is None:
        return None
    return {
        "id": row["id"],
        "status": row["status"],
        "source_mode": row["source_mode"],
        "timeframe": row["timeframe"],
        "pairs": row.get("pairs") or [],
        "alert_name_prefix": row.get("alert_name_prefix"),
        "webhook_url": row.get("webhook_url"),
        "use_approved_weights": bool(row.get("use_approved_weights", True)),
        "pair_risk_weights": row.get("pair_risk_weights") or {},
        "approved_config_ids": row.get("approved_config_ids") or [],
        "config_snapshot": row.get("config_snapshot") or [],
        "created_by": row.get("created_by"),
        "notes": row.get("notes"),
        "summary": row.get("summary") or {},
        "started_at": row.get("started_at"),
        "finished_at": row.get("finished_at"),
        "created_at": row.get("created_at"),
        "updated_at": row.get("updated_at"),
    }


def _normalize_result(row: dict[str, Any] | None) -> dict[str, Any] | None:
    if row is None:
        return None
    return {
        "id": row["id"],
        "batch_id": row["batch_id"],
        "pair": row["pair"],
        "timeframe": row["timeframe"],
        "status": row["status"],
        "params": row.get("params") or {},
        "config_snapshot": row.get("config_snapshot") or {},
        "risk_weight": float((row.get("config_snapshot") or {}).get("risk_weight", 1.0)),
        "alert_name": row.get("alert_name"),
        "alert_id": row.get("alert_id"),
        "error_message": row.get("error_message"),
        "started_at": row.get("started_at"),
        "finished_at": row.get("finished_at"),
        "created_at": row.get("created_at"),
        "updated_at": row.get("updated_at"),
    }


def _normalize_event(row: dict[str, Any] | None) -> dict[str, Any] | None:
    if row is None:
        return None
    return {
        "id": row["id"],
        "batch_id": row["batch_id"],
        "event_type": row["event_type"],
        "pair": row.get("pair"),
        "payload": row.get("payload") or {},
        "created_at": row.get("created_at"),
    }


class AlertSetupRepository(Protocol):
    def upsert_config(self, payload: dict[str, Any]) -> dict[str, Any]: ...
    def get_config(self, pair: str, timeframe: str) -> dict[str, Any] | None: ...
    def list_configs(
        self,
        *,
        limit: int = 100,
        status: str | None = None,
        pair: str | None = None,
        timeframe: str | None = None,
    ) -> list[dict[str, Any]]: ...
    def create_batch(self, payload: dict[str, Any]) -> dict[str, Any]: ...
    def get_batch(self, batch_id: str) -> dict[str, Any] | None: ...
    def update_batch(self, batch_id: str, updates: dict[str, Any]) -> dict[str, Any]: ...
    def list_batches(self, *, limit: int = 20, status: str | None = None) -> list[dict[str, Any]]: ...
    def create_results(self, batch_id: str, rows: list[dict[str, Any]]) -> None: ...
    def update_result(self, batch_id: str, pair: str, timeframe: str, updates: dict[str, Any]) -> dict[str, Any]: ...
    def list_results(self, batch_id: str) -> list[dict[str, Any]]: ...
    def append_event(self, payload: dict[str, Any]) -> dict[str, Any]: ...
    def list_events(self, batch_id: str, *, limit: int = 200) -> list[dict[str, Any]]: ...


class SupabaseAlertSetupRepository:
    def __init__(self) -> None:
        self._sb = get_api_supabase()

    def upsert_config(self, payload: dict[str, Any]) -> dict[str, Any]:
        key_query = (
            self._sb.table("approved_pair_configs")
            .select("*")
            .eq("pair", payload["pair"])
            .eq("timeframe", payload["timeframe"])
            .limit(1)
            .execute()
        )
        existing = key_query.data[0] if key_query.data else None
        if existing:
            updates = {**payload, "updated_at": _utc_now()}
            resp = (
                self._sb.table("approved_pair_configs")
                .update(updates)
                .eq("pair", payload["pair"])
                .eq("timeframe", payload["timeframe"])
                .execute()
            )
            return _normalize_config(resp.data[0]) if resp.data else _normalize_config(existing)  # type: ignore[return-value]
        row = {**payload, "id": str(uuid.uuid4())}
        resp = self._sb.table("approved_pair_configs").insert(row).execute()
        return _normalize_config(resp.data[0]) if resp.data else _normalize_config(row)  # type: ignore[return-value]

    def get_config(self, pair: str, timeframe: str) -> dict[str, Any] | None:
        resp = (
            self._sb.table("approved_pair_configs")
            .select("*")
            .eq("pair", pair)
            .eq("timeframe", timeframe)
            .limit(1)
            .execute()
        )
        if not resp.data:
            return None
        return _normalize_config(resp.data[0])

    def list_configs(
        self,
        *,
        limit: int = 100,
        status: str | None = None,
        pair: str | None = None,
        timeframe: str | None = None,
    ) -> list[dict[str, Any]]:
        query = (
            self._sb.table("approved_pair_configs")
            .select("*")
            .order("updated_at", desc=True)
            .limit(limit)
        )
        if status:
            query = query.eq("status", status)
        if pair:
            query = query.eq("pair", pair)
        if timeframe:
            query = query.eq("timeframe", timeframe)
        resp = query.execute()
        return [_normalize_config(row) for row in (resp.data or []) if row]

    def create_batch(self, payload: dict[str, Any]) -> dict[str, Any]:
        resp = self._sb.table("alert_batches").insert(payload).execute()
        return _normalize_batch(resp.data[0]) if resp.data else _normalize_batch(payload)  # type: ignore[return-value]

    def get_batch(self, batch_id: str) -> dict[str, Any] | None:
        resp = (
            self._sb.table("alert_batches")
            .select("*")
            .eq("id", batch_id)
            .limit(1)
            .execute()
        )
        if not resp.data:
            return None
        return _normalize_batch(resp.data[0])

    def update_batch(self, batch_id: str, updates: dict[str, Any]) -> dict[str, Any]:
        payload = {**updates, "updated_at": _utc_now()}
        resp = (
            self._sb.table("alert_batches")
            .update(payload)
            .eq("id", batch_id)
            .execute()
        )
        if resp.data:
            return _normalize_batch(resp.data[0])  # type: ignore[return-value]
        current = self.get_batch(batch_id)
        if current is None:
            raise KeyError(batch_id)
        current.update(payload)
        return current

    def list_batches(self, *, limit: int = 20, status: str | None = None) -> list[dict[str, Any]]:
        query = (
            self._sb.table("alert_batches")
            .select("*")
            .order("created_at", desc=True)
            .limit(limit)
        )
        if status:
            query = query.eq("status", status)
        resp = query.execute()
        return [_normalize_batch(row) for row in (resp.data or []) if row]

    def create_results(self, batch_id: str, rows: list[dict[str, Any]]) -> None:
        if rows:
            self._sb.table("alert_batch_results").insert(rows).execute()

    def update_result(self, batch_id: str, pair: str, timeframe: str, updates: dict[str, Any]) -> dict[str, Any]:
        payload = {**updates, "updated_at": _utc_now()}
        resp = (
            self._sb.table("alert_batch_results")
            .update(payload)
            .eq("batch_id", batch_id)
            .eq("pair", pair)
            .eq("timeframe", timeframe)
            .execute()
        )
        if resp.data:
            return _normalize_result(resp.data[0])  # type: ignore[return-value]
        current = self._sb.table("alert_batch_results").select("*").eq("batch_id", batch_id).eq("pair", pair).eq("timeframe", timeframe).limit(1).execute()
        if not current.data:
            raise KeyError(f"{batch_id}:{pair}:{timeframe}")
        merged = dict(current.data[0])
        merged.update(payload)
        return _normalize_result(merged)  # type: ignore[return-value]

    def list_results(self, batch_id: str) -> list[dict[str, Any]]:
        resp = (
            self._sb.table("alert_batch_results")
            .select("*")
            .eq("batch_id", batch_id)
            .order("pair")
            .execute()
        )
        return [_normalize_result(row) for row in (resp.data or []) if row]

    def append_event(self, payload: dict[str, Any]) -> dict[str, Any]:
        resp = self._sb.table("alert_batch_events").insert(payload).execute()
        return _normalize_event(resp.data[0]) if resp.data else _normalize_event(payload)  # type: ignore[return-value]

    def list_events(self, batch_id: str, *, limit: int = 200) -> list[dict[str, Any]]:
        resp = (
            self._sb.table("alert_batch_events")
            .select("*")
            .eq("batch_id", batch_id)
            .order("created_at", desc=False)
            .limit(limit)
            .execute()
        )
        return [_normalize_event(row) for row in (resp.data or []) if row]


class AlertSetupService:
    def __init__(self, repository: AlertSetupRepository) -> None:
        self._repository = repository

    def upsert_approved_config(
        self,
        *,
        pair: str,
        timeframe: str,
        params: dict[str, Any],
        risk_weight: float,
        status: str = "approved",
        source_run_id: str | None = None,
        source_score: float | None = None,
        source_metrics: dict[str, Any] | None = None,
        notes: str | None = None,
        created_by: str | None = None,
    ) -> dict[str, Any]:
        pair = _normalize_pair(pair)
        timeframe = _normalize_timeframe(timeframe)
        status = (status or "approved").strip().lower()
        if status not in _CONFIG_STATUSES:
            raise ValueError(f"invalid config status: {status}")
        if risk_weight < 0:
            raise ValueError("risk_weight must be >= 0")
        payload = {
            "pair": pair,
            "timeframe": timeframe,
            "status": status,
            "params": _coerce_payload(params or {}),
            "risk_weight": float(risk_weight),
            "source_run_id": source_run_id,
            "source_score": source_score,
            "source_metrics": _coerce_payload(source_metrics or {}),
            "notes": notes,
            "created_by": created_by,
            "updated_at": _utc_now(),
        }
        return self._repository.upsert_config(payload)

    def list_approved_configs(
        self,
        *,
        limit: int = 100,
        status: str | None = "approved",
        pair: str | None = None,
        timeframe: str | None = None,
    ) -> list[dict[str, Any]]:
        normalized_pair = _normalize_pair(pair) if pair else None
        normalized_timeframe = _normalize_timeframe(timeframe) if timeframe else None
        normalized_status = status.strip().lower() if status else None
        if normalized_status and normalized_status not in _CONFIG_STATUSES:
            raise ValueError(f"invalid config status: {normalized_status}")
        return self._repository.list_configs(
            limit=limit,
            status=normalized_status,
            pair=normalized_pair,
            timeframe=normalized_timeframe,
        )

    def start_batch(
        self,
        *,
        source_mode: str,
        pairs: list[str],
        timeframe: str,
        alert_name_prefix: str | None = None,
        webhook_url: str | None = None,
        use_approved_weights: bool = True,
        pair_risk_weights: dict[str, float] | None = None,
        created_by: str | None = None,
        notes: str | None = None,
    ) -> dict[str, Any]:
        if not pairs:
            raise ValueError("pairs must not be empty")
        source_mode = (source_mode or "").strip().lower()
        if source_mode not in _BATCH_SOURCE_MODES:
            raise ValueError(f"invalid source_mode: {source_mode}")
        timeframe = _normalize_timeframe(timeframe)
        normalized_pairs = [_normalize_pair(pair) for pair in pairs]
        normalized_risk_weights = {
            _normalize_pair(pair): float(weight)
            for pair, weight in (pair_risk_weights or {}).items()
        }

        if source_mode == "custom":
            configs = self._load_configs_from_parallel_results(
                pairs=normalized_pairs,
                timeframe=timeframe,
                use_approved_weights=use_approved_weights,
                pair_risk_weights=normalized_risk_weights,
                created_by=created_by,
            )
        else:
            configs = []
            missing: list[str] = []
            for pair in normalized_pairs:
                config = self._repository.get_config(pair, timeframe)
                if config is None or config["status"] != "approved":
                    missing.append(pair)
                else:
                    snapshot = dict(config)
                    if normalized_risk_weights.get(pair) is not None:
                        snapshot["risk_weight"] = normalized_risk_weights[pair]
                    elif not use_approved_weights:
                        snapshot["risk_weight"] = 1.0
                    configs.append(snapshot)
            if missing:
                raise ValueError(f"missing approved configs for: {', '.join(missing)}")

        batch_id = str(uuid.uuid4())
        created_at = _utc_now()
        summary = self._build_summary_from_configs(configs)
        batch = self._repository.create_batch(
            {
                "id": batch_id,
                "status": "queued",
                "source_mode": source_mode,
                "timeframe": timeframe,
                "pairs": normalized_pairs,
                "alert_name_prefix": alert_name_prefix,
                "webhook_url": webhook_url,
                "use_approved_weights": use_approved_weights,
                "pair_risk_weights": normalized_risk_weights,
                "approved_config_ids": [config["id"] for config in configs],
                "config_snapshot": configs,
                "created_by": created_by,
                "notes": notes,
                "summary": summary,
                "created_at": created_at,
                "updated_at": created_at,
            }
        )
        self._repository.create_results(
            batch_id,
            [
                {
                    "batch_id": batch_id,
                    "pair": config["pair"],
                    "timeframe": config["timeframe"],
                    "status": "pending",
                    "params": config.get("params") or {},
                    "config_snapshot": config,
                    "created_at": created_at,
                    "updated_at": created_at,
                }
                for config in configs
            ],
        )
        self.push_event(
            batch_id,
            {
                "event_type": "batch_started",
                "pair": None,
                "payload": {
                    "source_mode": source_mode,
                    "pairs": normalized_pairs,
                    "timeframe": timeframe,
                },
            },
        )
        return batch

    def _load_configs_from_parallel_results(
        self,
        *,
        pairs: list[str],
        timeframe: str,
        use_approved_weights: bool,
        pair_risk_weights: dict[str, float],
        created_by: str | None,
    ) -> list[dict[str, Any]]:
        rows = self._read_parallel_results_file()
        configs: list[dict[str, Any]] = []
        missing: list[str] = []

        for pair in pairs:
            row = rows.get(pair)
            if not isinstance(row, dict):
                missing.append(pair)
                continue

            existing = self._repository.get_config(pair, timeframe)
            risk_weight = pair_risk_weights.get(pair)
            if risk_weight is None:
                if use_approved_weights and existing is not None:
                    risk_weight = float(existing.get("risk_weight", 1.0))
                else:
                    risk_weight = 1.0

            source_metrics = {
                "net_profit": row.get("net_profit"),
                "win_rate": row.get("win_rate"),
                "profit_factor": row.get("profit_factor"),
                "max_drawdown_pct": row.get("max_drawdown_pct"),
                "total_trades": row.get("total_trades"),
                "worker_id": row.get("worker_id"),
                "timestamp": row.get("timestamp"),
            }
            config = self.upsert_approved_config(
                pair=pair,
                timeframe=timeframe,
                params=row.get("params") or {},
                risk_weight=float(risk_weight),
                status="approved",
                source_run_id=existing.get("source_run_id") if existing is not None else None,
                source_score=float(row["score"]) if row.get("score") is not None else None,
                source_metrics={k: v for k, v in source_metrics.items() if v is not None},
                notes="imported from parallel_results.json",
                created_by=created_by,
            )
            configs.append(config)

        if missing:
            raise ValueError(f"missing optimizer results for: {', '.join(missing)}")

        return configs

    def _read_parallel_results_file(self) -> dict[str, Any]:
        if not _PARALLEL_RESULTS_FILE.exists():
            raise ValueError(f"parallel_results.json not found at {_PARALLEL_RESULTS_FILE}")
        try:
            payload = json.loads(_PARALLEL_RESULTS_FILE.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise ValueError(f"parallel_results.json is invalid JSON: {exc}") from exc
        if not isinstance(payload, dict):
            raise ValueError("parallel_results.json must contain an object keyed by pair")
        return {str(key).strip().upper(): value for key, value in payload.items()}

    def list_batches(self, *, limit: int = 20, status: str | None = None) -> list[dict[str, Any]]:
        normalized_status = status.strip().lower() if status else None
        if normalized_status and normalized_status not in _BATCH_STATUSES:
            raise ValueError(f"invalid batch status: {normalized_status}")
        return self._repository.list_batches(limit=limit, status=normalized_status)

    def get_batch(self, batch_id: str) -> dict[str, Any]:
        batch = self._repository.get_batch(batch_id)
        if batch is None:
            raise KeyError(batch_id)
        return batch

    def list_results(self, batch_id: str) -> list[dict[str, Any]]:
        return self._repository.list_results(batch_id)

    def list_events(self, batch_id: str, *, limit: int = 200) -> list[dict[str, Any]]:
        return self._repository.list_events(batch_id, limit=limit)

    def cancel_batch(self, batch_id: str) -> dict[str, Any]:
        batch = self._repository.get_batch(batch_id)
        if batch is None:
            raise KeyError(batch_id)
        if batch["status"] in {"completed", "failed", "cancelled", "interrupted"}:
            return batch
        self.push_event(
            batch_id,
            {
                "event_type": "batch_cancelled",
                "pair": None,
                "payload": {"source": "api"},
            },
        )
        cancelled = self._repository.update_batch(
            batch_id,
            {
                "status": "cancelled",
                "finished_at": _utc_now(),
                "summary": self._rebuild_summary(batch_id),
            },
        )
        for result in self._repository.list_results(batch_id):
            if result["status"] in {"pending", "running"}:
                self._repository.update_result(
                    batch_id,
                    result["pair"],
                    result["timeframe"],
                    {"status": "cancelled", "finished_at": _utc_now()},
                )
        return cancelled

    def update_batch_from_agent(
        self,
        batch_id: str,
        *,
        status: str | None = None,
        summary: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        batch = self._repository.get_batch(batch_id)
        if batch is None:
            raise KeyError(batch_id)
        updates: dict[str, Any] = {}
        if status is not None:
            updates["status"] = status
            if status == "running" and not batch.get("started_at"):
                updates["started_at"] = _utc_now()
            if status in {"completed", "failed", "cancelled", "interrupted"}:
                updates["finished_at"] = _utc_now()
        if summary is not None:
            merged = dict(batch.get("summary") or {})
            merged.update(summary)
            updates["summary"] = merged
        if not updates:
            return batch
        return self._repository.update_batch(batch_id, updates)

    def update_result_from_agent(self, batch_id: str, pair: str, updates: dict[str, Any]) -> dict[str, Any]:
        batch = self._repository.get_batch(batch_id)
        if batch is None:
            raise KeyError(batch_id)
        pair = _normalize_pair(pair)
        result_updates = dict(updates)
        result = self._repository.update_result(batch_id, pair, batch["timeframe"], result_updates)
        self._repository.update_batch(batch_id, {"summary": self._rebuild_summary(batch_id)})
        return result

    def push_event(self, batch_id: str, event: dict[str, Any]) -> dict[str, Any]:
        batch = self._repository.get_batch(batch_id)
        if batch is None:
            raise KeyError(batch_id)
        event["batch_id"] = batch_id
        return self._repository.append_event(_coerce_payload(event))

    def _build_summary_from_configs(self, configs: list[dict[str, Any]]) -> dict[str, Any]:
        total = len(configs)
        best_pair = None
        best_score = None
        for config in configs:
            score = config.get("source_score")
            if isinstance(score, (int, float)) and (best_score is None or score > best_score):
                best_score = float(score)
                best_pair = config["pair"]
        return {
            "total_pairs": total,
            "pending_pairs": total,
            "running_pairs": 0,
            "completed_pairs": 0,
            "failed_pairs": 0,
            "cancelled_pairs": 0,
            "best_pair": best_pair,
            "best_score": best_score,
        }

    def _rebuild_summary(self, batch_id: str) -> dict[str, Any]:
        results = self._repository.list_results(batch_id)
        batch = self._repository.get_batch(batch_id) or {}
        summary = dict(batch.get("summary") or {})
        total_pairs = len(results)
        pending_pairs = sum(1 for result in results if result["status"] == "pending")
        running_pairs = sum(1 for result in results if result["status"] == "running")
        completed_pairs = sum(1 for result in results if result["status"] in {"completed", "created", "skipped"})
        failed_pairs = sum(1 for result in results if result["status"] == "failed")
        cancelled_pairs = sum(1 for result in results if result["status"] == "cancelled")
        created_alerts = sum(1 for result in results if result["status"] == "created")
        skipped_pairs = sum(1 for result in results if result["status"] == "skipped")
        best_pair = summary.get("best_pair")
        best_score = summary.get("best_score")
        for result in results:
            metrics = result.get("metrics") or {}
            score = metrics.get("score")
            if not isinstance(score, (int, float)):
                snapshot = result.get("config_snapshot") or {}
                score = snapshot.get("source_score")
            if isinstance(score, (int, float)) and (best_score is None or score > best_score):
                best_score = float(score)
                best_pair = result["pair"]
        summary.update(
            {
                "total_pairs": total_pairs,
                "pending_pairs": pending_pairs,
                "running_pairs": running_pairs,
                "completed_pairs": completed_pairs,
                "failed_pairs": failed_pairs,
                "cancelled_pairs": cancelled_pairs,
                "created_alerts": created_alerts,
                "skipped_pairs": skipped_pairs,
                "best_pair": best_pair,
                "best_score": best_score,
            }
        )
        return summary


_service: AlertSetupService | None = None


def get_alert_setup_service() -> AlertSetupService:
    global _service
    if _service is None:
        _service = AlertSetupService(repository=SupabaseAlertSetupRepository())
    return _service
