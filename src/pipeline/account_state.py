"""
src/pipeline/account_state.py

Lightweight DB-read helpers for per-account state queries.

These are called inside the account guard loop, before any execution
happens. They must be fast (indexed queries) and failure-safe (return
safe defaults on any exception).
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from config.logging_config import get_logger

logger = get_logger("trinity.pipeline.account_state")


def _get_closed_pnl_since(
    since_iso: str,
    profile: Optional[Dict[str, Any]] = None,
    *,
    timestamp_field: str = "closed_at",
) -> float:
    """Return closed PnL since ``since_iso`` for a profile-scoped window."""
    try:
        import src.adapters.supabase as _sb_mod

        sb = _sb_mod.supabase
        if not sb:
            return 0.0

        q = (
            sb.table("trading_signals")
            .select("pnl_usd")
            .in_("status", ["CLOSED", "closed"])
            .gte(timestamp_field, since_iso)
        )
        if profile and profile.get("id") is not None:
            q = q.eq("broker_profile_id", profile["id"])
        elif profile and profile.get("name"):
            q = q.eq("account_name", profile["name"])

        pnl_resp = q.execute()
        return sum(float(t.get("pnl_usd") or 0) for t in (pnl_resp.data or []))
    except Exception:
        return 0.0


def get_account_daily_pnl(profile: Optional[Dict[str, Any]] = None) -> float:
    """Return today's closed PnL (USD) for *profile* (or global if None).

    Queries ``trading_signals`` for all CLOSED rows since 00:00 UTC today,
    scoped to the profile's broker_profile_id or account_name when provided.
    Returns 0.0 on any error.
    """
    from datetime import datetime as _dt, timezone

    today_start = (
        _dt.now(timezone.utc)
        .replace(hour=0, minute=0, second=0, microsecond=0)
        .isoformat()
    )
    return _get_closed_pnl_since(today_start, profile, timestamp_field="created_at")


def get_account_weekly_pnl(profile: Optional[Dict[str, Any]] = None) -> float:
    """Return trailing 7-day closed PnL (USD) for *profile*."""
    from datetime import datetime as _dt, timedelta, timezone

    week_start = (_dt.now(timezone.utc) - timedelta(days=7)).isoformat()
    return _get_closed_pnl_since(week_start, profile, timestamp_field="closed_at")


def get_account_monthly_pnl(profile: Optional[Dict[str, Any]] = None) -> float:
    """Return month-to-date closed PnL (USD) for *profile*."""
    from datetime import datetime as _dt, timezone

    month_start = (
        _dt.now(timezone.utc)
        .replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        .isoformat()
    )
    return _get_closed_pnl_since(month_start, profile, timestamp_field="closed_at")


def get_account_daily_trade_count(profile: Optional[Dict[str, Any]] = None) -> int:
    """Count today's executed/active/closed trades for *profile*.

    Returns 0 on any error.
    """
    try:
        import src.adapters.supabase as _sb_mod
        sb = _sb_mod.supabase
        if not sb:
            return 0
        from datetime import datetime as _dt, timezone
        today_start = (
            _dt.now(timezone.utc)
            .replace(hour=0, minute=0, second=0, microsecond=0)
            .isoformat()
        )
        q = (
            sb.table("trading_signals")
            .select("id")
            .in_("status", ["active", "executed", "closed"])
            .gte("created_at", today_start)
        )
        if profile and profile.get("id") is not None:
            q = q.eq("broker_profile_id", profile["id"])
        elif profile and profile.get("name"):
            q = q.eq("account_name", profile["name"])
        result = q.execute()
        return len(result.data or [])
    except Exception:
        return 0


def get_account_positions_from_db(
    profile: Optional[Dict[str, Any]] = None,
) -> List[Any]:
    """Fetch active ``ActivePosition`` objects for *profile*.

    Returns an empty list on any error so correlation guard fails safely.
    """
    try:
        import src.adapters.supabase as supabase_db
        if not supabase_db.supabase:
            supabase_db.init_supabase()
        q = (
            supabase_db.supabase.table("trading_signals")
            .select("symbol, side, size, entry, created_at, zone_id, trade_key")
            .in_("status", ["active", "executed"])
        )
        if profile and profile.get("id") is not None:
            q = q.eq("broker_profile_id", profile["id"])
        elif profile and profile.get("name"):
            q = q.eq("account_name", profile["name"])
        response = q.execute()
        from src.core.guard_rails.correlation import ActivePosition
        from datetime import datetime
        positions = []
        for row in response.data:
            positions.append(
                ActivePosition(
                    symbol=row.get("symbol", "UNKNOWN"),
                    side=row.get("side", "buy"),
                    size=float(row.get("size", 0)),
                    entry_price=float(row.get("entry", 0)),
                    entry_time=(
                        datetime.fromisoformat(row["created_at"])
                        if row.get("created_at")
                        else datetime.utcnow()
                    ),
                    zone_id=row.get("zone_id"),
                    trade_key=row.get("trade_key"),
                )
            )
        return positions
    except Exception as e:
        logger.error("Failed to fetch account positions: %s", e)
        return []
