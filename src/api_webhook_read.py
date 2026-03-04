"""Webhook read API — signals/recent, trades/open, stats/summary for E2E tests and dashboards."""

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Query

from src.adapters.supabase_api import get_api_supabase as _get_supabase

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/webhook", tags=["webhook-read"])


@router.get("/signals/recent")
def get_signals_recent(
    limit: int = Query(10, ge=1, le=100),
    run_mode: Optional[str] = Query(None),
):
    """Get recent trading signals (any status) for E2E verification and dashboards."""
    sb = _get_supabase()
    if not sb:
        return {"signals": [], "count": 0}

    try:
        q = sb.table("trading_signals").select("*").order("created_at", desc=True).limit(limit)
        if run_mode:
            q = q.eq("run_mode", run_mode)
        resp = q.execute()
        signals = resp.data or []
        return {"signals": signals, "count": len(signals)}
    except Exception as e:
        logger.warning("Failed to fetch recent signals: %s", e)
        return {"signals": [], "count": 0}


@router.get("/trades/open")
def get_trades_open(
    account_id: Optional[str] = Query(None),
):
    """Get open trades (DB + broker positions) for E2E verification and dashboards."""
    sb = _get_supabase()
    if not sb:
        return {"trades": [], "db_trades": [], "broker_positions": [], "count": 0}

    try:
        q = (
            sb.table("trading_signals")
            .select("*")
            .in_("status", ["active", "executed", "OPEN", "open", "PENDING", "pending"])
            .order("created_at", desc=True)
        )
        if account_id:
            q = q.eq("account_id", account_id)
        resp = q.execute()
        db_trades = resp.data or []

        # Broker positions: use MetaApiAdapter when credentials exist (read-only, works even if execution_mode=SHADOW)
        broker_positions: List[Dict[str, Any]] = []
        try:
            from config import get_settings

            s = get_settings()
            token = (s.meta_api_token or "").strip()
            account_id = (s.meta_api_account_id or "").strip()
            if token and account_id:
                from src.adapters.execution.meta_api_adapter import MetaApiAdapter

                adapter = MetaApiAdapter(token=token, account_id=account_id)
                raw = adapter.get_open_positions()
                if isinstance(raw, list):
                    broker_positions = raw
                elif isinstance(raw, dict):
                    broker_positions = list(raw.values())
                else:
                    broker_positions = []
            else:
                logger.debug("Broker positions skipped: META_API_TOKEN or META_API_ACCOUNT_ID not set")
        except Exception as e:
            logger.warning("Broker positions fetch failed: %s", e)

        trades = db_trades
        return {
            "trades": trades,
            "db_trades": db_trades,
            "broker_positions": broker_positions,
            "count": len(trades),
        }
    except Exception as e:
        logger.warning("Failed to fetch open trades: %s", e)
        return {"trades": [], "db_trades": [], "broker_positions": [], "count": 0}


@router.get("/stats/summary")
def get_stats_summary(
    run_mode: str = Query("LIVE"),
    account_id: Optional[str] = Query(None),
):
    """Get performance summary (total_trades, win_rate, total_pnl_usd) for E2E and dashboards."""
    sb = _get_supabase()
    if not sb:
        return {"total_trades": 0, "win_rate": 0, "total_pnl_usd": 0}

    try:
        q = (
            sb.table("trading_signals")
            .select("pnl_usd, outcome")
            .eq("status", "closed")
        )
        if run_mode and run_mode != "ALL":
            q = q.eq("run_mode", run_mode)
        if account_id:
            q = q.eq("account_id", account_id)
        resp = q.execute()
        rows = resp.data or []

        total = len(rows)
        wins = sum(1 for r in rows if (r.get("outcome") or "").lower() == "win")
        total_pnl = sum(float(r.get("pnl_usd") or 0) for r in rows)
        win_rate = (wins / total * 100) if total > 0 else 0

        return {
            "total_trades": total,
            "win_rate": round(win_rate, 1),
            "total_pnl_usd": round(total_pnl, 2),
        }
    except Exception as e:
        logger.warning("Failed to fetch stats summary: %s", e)
        return {"total_trades": 0, "win_rate": 0, "total_pnl_usd": 0}
