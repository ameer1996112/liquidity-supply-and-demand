"""
TraceObserver — end-to-end pipeline latency instrumentation (Sprint 2.1).

Writes/upserts one row per correlation_id into the ``pipeline_traces`` table.
All DB calls are fire-and-forget: any exception is logged and swallowed so
this observer can NEVER affect trading logic or pipeline throughput.

Hop stamps written by this observer
-------------------------------------
  SIGNAL_RECEIVED  → received_at       (INSERT)
  ORDER_SUBMITTED  → exec_submitted_at  (UPSERT)
  ERROR            → error_at + error_type + error_message  (UPSERT)

Future hops (enqueued_at, risk_started_at, …) will be written by other
observers once those milestones are emitted from WorkerSubject.

Backward-compat alias
---------------------
``MetricsObserver = TraceObserver`` — the worker and any existing tests that
attach ``MetricsObserver`` continue to work without change.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict

from src.core.observers.base import ERROR, ORDER_SUBMITTED, SIGNAL_RECEIVED, Observer, TradeEvent

logger = logging.getLogger(__name__)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _ts_to_iso(ts: float) -> str:
    return datetime.fromtimestamp(ts, tz=timezone.utc).isoformat()


class TraceObserver(Observer):
    """Writes pipeline hop timestamps into ``pipeline_traces``.

    One row per correlation_id, upserted incrementally as events arrive.
    The Supabase client is resolved lazily so tests can inject a mock via
    the ``supabase_client`` constructor argument.
    """

    def __init__(self, supabase_client=None) -> None:
        self._client = supabase_client

    def _get_client(self):
        if self._client is not None:
            return self._client
        try:
            from src.adapters.supabase import supabase as sb
            if sb is None:
                from src.adapters.supabase import init_supabase
                init_supabase()
                from src.adapters.supabase import supabase as sb2
                return sb2
            return sb
        except Exception:
            return None

    # ── Event handler ─────────────────────────────────────────────────────

    def on_event(self, event: TradeEvent) -> None:
        try:
            if event.event_type == SIGNAL_RECEIVED:
                self._handle_received(event)
            elif event.event_type == ORDER_SUBMITTED:
                self._handle_submitted(event)
            elif event.event_type == ERROR:
                self._handle_error(event)
        except Exception as exc:  # noqa: BLE001
            logger.warning("TraceObserver.on_event failed [%s]: %s", event.event_type, exc)

    # ── Hop handlers ──────────────────────────────────────────────────────

    def _handle_received(self, event: TradeEvent) -> None:
        client = self._get_client()
        if client is None:
            return
        row: Dict[str, Any] = {
            "correlation_id": event.correlation_id,
            "symbol":         event.payload.get("symbol"),
            "run_mode":       event.payload.get("run_mode"),
            "received_at":    _ts_to_iso(event.timestamp),
        }
        client.table("pipeline_traces").upsert(
            row, on_conflict="correlation_id"
        ).execute()

    def _handle_submitted(self, event: TradeEvent) -> None:
        client = self._get_client()
        if client is None:
            return
        row: Dict[str, Any] = {
            "correlation_id":   event.correlation_id,
            "exec_submitted_at": _ts_to_iso(event.timestamp),
        }
        # Also capture signal_id if process_trade stamped it onto the payload
        sig_id = event.payload.get("_signal_id")
        if sig_id is not None:
            row["signal_id"] = int(sig_id)
        account = event.payload.get("_account_name") or event.payload.get("account_name")
        if account:
            row["account_id"] = str(account)

        client.table("pipeline_traces").upsert(
            row, on_conflict="correlation_id"
        ).execute()

    def _handle_error(self, event: TradeEvent) -> None:
        client = self._get_client()
        if client is None:
            return
        row: Dict[str, Any] = {
            "correlation_id": event.correlation_id,
            "error_at":       _ts_to_iso(event.timestamp),
            "error_type":     event.metadata.get("error_type", "")[:128],
            "error_message":  event.metadata.get("error", "")[:500],
        }
        client.table("pipeline_traces").upsert(
            row, on_conflict="correlation_id"
        ).execute()


# Backward-compat alias — the worker attaches MetricsObserver by name
MetricsObserver = TraceObserver
