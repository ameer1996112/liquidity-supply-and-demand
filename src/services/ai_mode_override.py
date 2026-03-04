"""
Sprint 3.4: Runtime AI mode override (DB overrides env).
"""

from __future__ import annotations

import logging
from typing import Optional

logger = logging.getLogger(__name__)

_CACHE_TTL_SEC = 30
_CACHE_TS: float = 0.0
_CACHE_VAL: Optional[str] = None


def _get_supabase():
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


def get_ai_mode_override(supabase=None) -> Optional[str]:
    """Get ai_mode from DB override. Returns None if use env."""
    global _CACHE_TS, _CACHE_VAL
    import time

    now = time.time()
    if _CACHE_VAL is not None and (now - _CACHE_TS) < _CACHE_TTL_SEC:
        return _CACHE_VAL

    sb = supabase if supabase is not None else _get_supabase()
    if not sb:
        return None
    try:
        resp = sb.table("ai_mode_state").select("mode").eq("id", 1).limit(1).execute()
        if resp.data and len(resp.data) > 0:
            mode = (resp.data[0].get("mode") or "").strip().lower()
            if mode in ("shadow", "enforce"):
                _CACHE_VAL = mode
                _CACHE_TS = now
                return mode
    except Exception as e:
        logger.debug("ai_mode_state read failed: %s", e)
    _CACHE_VAL = None
    return None


def set_ai_mode(
    to_mode: str,
    *,
    supabase=None,
    from_mode: str = "shadow",
    reason: str = "",
    created_by: str = "",
) -> bool:
    """Set ai_mode in DB and log to audit. Returns True if updated."""
    if to_mode not in ("shadow", "enforce"):
        return False
    sb = supabase if supabase is not None else _get_supabase()
    if not sb:
        return False
    try:
        from datetime import datetime, timezone
        sb.table("ai_mode_state").upsert(
            {"id": 1, "mode": to_mode, "updated_at": datetime.now(timezone.utc).isoformat()},
            on_conflict="id",
        ).execute()
        sb.table("ai_mode_toggles").insert({
            "from_mode": from_mode,
            "to_mode": to_mode,
            "reason": reason or None,
            "created_by": created_by or None,
        }).execute()
        global _CACHE_VAL, _CACHE_TS
        import time
        _CACHE_VAL = to_mode
        _CACHE_TS = time.time()
        return True
    except Exception as e:
        logger.warning("set_ai_mode failed: %s", e)
        return False


def invalidate_cache() -> None:
    """Clear cache so next read fetches fresh."""
    global _CACHE_VAL
    _CACHE_VAL = None
