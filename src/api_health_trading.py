"""Trading Health API (HEALTH-01, HEALTH-02, HEALTH-03) — Phase v1.1.

Provides a single GET /api/health/trading endpoint that returns:
- Account equity + balance (HEALTH-01)
- Open positions count + unrealised P&L (HEALTH-01)
- Today's closed trades + realised P&L (HEALTH-02)
- Worker + Redis pipeline status (HEALTH-03)
"""

import logging
import os
import json
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from fastapi import APIRouter

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/health", tags=["health-v11"])
WORKER_HEARTBEAT_KEY = "trading:worker:heartbeat"
WORKER_HEARTBEAT_STALE_SECONDS = 120


def _get_meta_api_cache() -> Optional[Dict]:
    """Try to get cached MetaAPI account info from existing meta_api cache module."""
    try:
        from src.adapters import meta_api_cache  # noqa: F401 — varies by project
        if hasattr(meta_api_cache, "get_cached_account_info"):
            return meta_api_cache.get_cached_account_info()
    except ImportError:
        pass
    try:
        from src.core.meta_api_cache import get_cached_account_info
        return get_cached_account_info()
    except (ImportError, Exception):
        pass
    return None


def _get_redis_status() -> str:
    """Check Redis liveness — returns 'running', 'stopped', or 'unknown'."""
    try:
        import redis as _redis
        from config import get_settings
        s = get_settings()
        r = _redis.from_url(s.redis_url, socket_connect_timeout=2)
        r.ping()
        return "running"
    except Exception:
        return "stopped"


def _get_worker_snapshot() -> Dict[str, Any]:
    """Check worker liveness via Redis heartbeat shared across services."""
    try:
        from src.adapters.redis_queue import QUEUE_NAME, get_redis

        redis_client = get_redis()
        raw = redis_client.get(WORKER_HEARTBEAT_KEY)
        queue_depth = int(redis_client.llen(QUEUE_NAME))
        if not raw:
            return {"status": "stopped", "queue_depth": queue_depth}

        payload = json.loads(raw)
        heartbeat_ts = float(payload.get("ts") or 0.0)
        age_seconds = max(0, int(datetime.now(timezone.utc).timestamp() - heartbeat_ts))
        status = "running" if age_seconds <= WORKER_HEARTBEAT_STALE_SECONDS else "stale"
        return {
            "status": status,
            "last_seen_at": datetime.fromtimestamp(heartbeat_ts, tz=timezone.utc).isoformat() if heartbeat_ts else None,
            "age_seconds": age_seconds,
            "queue_depth": queue_depth,
            "host": payload.get("host"),
            "pid": payload.get("pid"),
        }
    except Exception:
        return {"status": "unknown", "queue_depth": None}


def _get_todays_trades() -> Dict[str, Any]:
    """Fetch today's closed signals from Supabase for realised P&L."""
    try:
        from src.adapters.supabase_api import get_api_supabase
        sb = get_api_supabase()
        today = datetime.now(timezone.utc).date().isoformat()
        resp = (
            sb.table("trading_signals")
            .select("id, pnl_usd, status, closed_at")
            .in_("status", ["closed", "executed", "CLOSED", "EXECUTED"])
            .gte("closed_at", f"{today}T00:00:00")
            .limit(500)
            .execute()
        )
        trades = [t for t in (resp.data or []) if float(t.get("pnl_usd") or 0) != 0]
        realised_pnl = round(sum(float(t.get("pnl_usd") or 0) for t in trades), 2)
        return {"count": len(trades), "realised_pnl": realised_pnl}
    except Exception as exc:
        logger.warning("Could not fetch today's trades: %s", exc)
        return {"count": 0, "realised_pnl": 0.0}


def _get_open_positions() -> Dict[str, Any]:
    """Get open positions from MetaAPI cache / positions endpoint."""
    try:
        from src.adapters.supabase_api import get_api_supabase
        sb = get_api_supabase()
        resp = (
            sb.table("trading_signals")
            .select("id, pnl_usd, status")
            .in_("status", ["pending", "active", "open", "PENDING", "ACTIVE", "OPEN"])
            .limit(200)
            .execute()
        )
        positions = resp.data or []
        unrealised_pnl = round(sum(float(p.get("pnl_usd") or 0) for p in positions), 2)
        return {"count": len(positions), "unrealised_pnl": unrealised_pnl}
    except Exception:
        return {"count": 0, "unrealised_pnl": 0.0}


@router.get("/trading")
def get_trading_health():
    """
    Trading system health snapshot for the sidebar widget.

    Returns:
    - account: equity, balance (HEALTH-01)
    - open_positions: count, unrealised_pnl (HEALTH-01)
    - today_trades: count, realised_pnl (HEALTH-02)
    - pipeline: redis_status, worker_status (HEALTH-03)
    """
    # Account info from MetaAPI cache
    account_info = _get_meta_api_cache() or {}
    equity = account_info.get("equity") or account_info.get("balance") or 0.0
    balance = account_info.get("balance") or 0.0

    # Open positions
    positions = _get_open_positions()

    # Today's closed trades
    today = _get_todays_trades()

    # Pipeline status
    redis_status = _get_redis_status()
    worker = _get_worker_snapshot()
    worker_status = worker["status"]

    overall = "healthy" if redis_status == "running" and worker_status == "running" else "degraded"

    return {
        "account": {
            "equity": round(float(equity), 2),
            "balance": round(float(balance), 2),
        },
        "open_positions": {
            "count": positions["count"],
            "unrealised_pnl": positions["unrealised_pnl"],
        },
        "today_trades": {
            "count": today["count"],
            "realised_pnl": today["realised_pnl"],
        },
        "pipeline": {
            "redis": redis_status,
            "worker": worker_status,
            "worker_last_seen_at": worker.get("last_seen_at"),
            "worker_age_seconds": worker.get("age_seconds"),
            "worker_host": worker.get("host"),
            "queue_depth": worker.get("queue_depth"),
            "overall": overall,
        },
        "refreshed_at": datetime.now(timezone.utc).isoformat(),
    }
