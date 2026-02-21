"""Trade event audit trail logger.

Fire-and-forget: never raises, never blocks the pipeline.
Writes to the ``trade_events`` Supabase table.
"""

import json
import logging
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

_supabase = None


def _get_client():
    global _supabase
    if _supabase is not None:
        return _supabase
    try:
        from config import get_settings
        from supabase import create_client

        s = get_settings()
        key = (s.supabase_service_role_key or s.supabase_key or "").strip().strip('"\'')
        if s.supabase_url and key:
            _supabase = create_client(s.supabase_url, key)
    except Exception as exc:
        logger.debug("trade_events: Supabase init skipped (%s)", exc)
    return _supabase


def log_event(
    signal_id: Optional[int],
    event_type: str,
    stage: str = "",
    metadata: Optional[Dict[str, Any]] = None,
) -> None:
    """Insert one row into ``trade_events``.  Best-effort — silently drops on error."""
    try:
        client = _get_client()
        if not client:
            return
        row: Dict[str, Any] = {
            "event_type": event_type,
            "stage": stage,
            "metadata": json.dumps(metadata or {}),
        }
        if signal_id is not None:
            row["signal_id"] = signal_id
        client.table("trade_events").insert(row).execute()
    except Exception as exc:
        logger.debug("trade_events log failed: %s", exc)


def log_guard_decision(
    guard_name: str,
    result: str,
    reason: str,
    symbol: str = "",
    metadata: Optional[Dict[str, Any]] = None,
) -> None:
    """
    Log a guard or AI decision for audit and future tuning (Package C).
    Writes to trade_events with event_type='guard_decision', stage=guard_name.
    When guard_decisions table exists, also inserts a row there for easier analytics.
    """
    meta: Dict[str, Any] = {"result": result, "reason": reason[:500]}
    if symbol:
        meta["symbol"] = symbol
    if metadata:
        for k, v in list(metadata.items())[:10]:
            if v is not None and k not in meta:
                meta[k] = str(v)[:200] if not isinstance(v, (int, float, bool)) else v
    log_event(None, "guard_decision", guard_name, meta)

    # Optional: write to guard_decisions table for analytics (migration 005)
    try:
        client = _get_client()
        if client:
            row = {
                "guard_name": guard_name[:200],
                "result": result[:100],
                "reason": (reason or "")[:1000],
                "symbol": (symbol or "")[:50],
                "metadata": json.dumps(metadata or {}),
            }
            client.table("guard_decisions").insert(row).execute()
    except Exception as exc:
        logger.debug("guard_decisions insert skipped (table may not exist): %s", exc)
