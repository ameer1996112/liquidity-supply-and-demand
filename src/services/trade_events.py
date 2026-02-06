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
        key = (s.supabase_service_role_key or s.supabase_key or "").strip()
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
