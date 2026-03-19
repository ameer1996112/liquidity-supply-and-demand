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
    """
    Rich performance summary for dashboards and E2E tests.

    Returns:
    - total_trades, win_rate, total_pnl_usd (backward-compat)
    - active_trades, executed_24h, filtered_24h
    - daily_pnl_usd, best_trade_usd, worst_trade_usd
    - avg_rr, profit_factor, max_consecutive_wins, max_consecutive_losses
    - cached for 30s in Redis to reduce DB load
    """
    sb = _get_supabase()
    if not sb:
        return _empty_summary()

    # Build cache key
    cache_key = f"cache:stats_summary:{run_mode}:{account_id or 'all'}"
    try:
        from src.services.redis_cache import cache_get, cache_set
        cached = cache_get(cache_key)
        if cached is not None:
            return cached
    except Exception:
        pass

    try:
        # ── All closed trades ──────────────────────────────────────────
        q = (
            sb.table("trading_signals")
            .select("pnl_usd, outcome, rr_ratio, created_at, status, run_mode")
            .in_("status", ["CLOSED", "closed"])
        )
        if run_mode and run_mode != "ALL":
            q = q.eq("run_mode", run_mode)
        if account_id:
            q = q.eq("account_id", account_id)
        resp = q.execute()
        closed = resp.data or []

        # ── Active / open trades ───────────────────────────────────────
        aq = (
            sb.table("trading_signals")
            .select("id, run_mode")
            .in_("status", ["active", "executed", "open"])
        )
        if run_mode and run_mode != "ALL":
            aq = aq.eq("run_mode", run_mode)
        if account_id:
            aq = aq.eq("account_id", account_id)
        active_resp = aq.execute()
        active_trades = len(active_resp.data or [])

        # ── 24h signals (all statuses) ─────────────────────────────────
        from datetime import date
        today_start = datetime.combine(date.today(), datetime.min.time()).isoformat()
        dq = (
            sb.table("trading_signals")
            .select("id, status, run_mode")
            .gte("created_at", today_start)
        )
        if run_mode and run_mode != "ALL":
            dq = dq.eq("run_mode", run_mode)
        if account_id:
            dq = dq.eq("account_id", account_id)
        day_resp = dq.execute()
        day_rows = day_resp.data or []
        executed_24h = sum(1 for r in day_rows if r.get("status") in ("executed", "closed", "active", "open"))
        filtered_24h = sum(1 for r in day_rows if r.get("status") in ("filtered", "rejected", "ai_rejected", "risk_rejected"))

        # ── Compute KPIs from closed trades ────────────────────────────
        total = len(closed)
        wins = [r for r in closed if (r.get("outcome") or "").lower() == "win"]
        losses = [r for r in closed if (r.get("outcome") or "").lower() in ("loss", "lose")]
        win_count = len(wins)
        loss_count = len(losses)
        win_rate = (win_count / total * 100) if total > 0 else 0.0

        pnl_values = [float(r.get("pnl_usd") or 0) for r in closed]
        total_pnl = sum(pnl_values)
        best_trade = max(pnl_values, default=0.0)
        worst_trade = min(pnl_values, default=0.0)

        # Daily PnL (today's closed trades)
        daily_pnl = sum(
            float(r.get("pnl_usd") or 0)
            for r in closed
            if (r.get("created_at") or "") >= today_start
        )

        # Average R:R
        rr_values = [float(r.get("rr_ratio") or 0) for r in closed if r.get("rr_ratio")]
        avg_rr = (sum(rr_values) / len(rr_values)) if rr_values else 0.0

        # Profit factor = gross_profit / abs(gross_loss)
        gross_profit = sum(v for v in pnl_values if v > 0)
        gross_loss = abs(sum(v for v in pnl_values if v < 0))
        profit_factor = (gross_profit / gross_loss) if gross_loss > 0 else (gross_profit if gross_profit > 0 else 0.0)

        # Consecutive wins/losses
        max_consec_wins = _max_consecutive(closed, "win")
        max_consec_losses = _max_consecutive(closed, "loss")

        result = {
            # Backward-compat fields
            "total_trades": total,
            "win_rate": round(win_rate, 1),
            "total_pnl_usd": round(total_pnl, 2),
            # Extended fields
            "active_trades": active_trades,
            "executed_24h": executed_24h,
            "filtered_24h": filtered_24h,
            "daily_pnl_usd": round(daily_pnl, 2),
            "win_count": win_count,
            "loss_count": loss_count,
            "best_trade_usd": round(best_trade, 2),
            "worst_trade_usd": round(worst_trade, 2),
            "avg_rr": round(avg_rr, 2),
            "profit_factor": round(profit_factor, 2),
            "max_consecutive_wins": max_consec_wins,
            "max_consecutive_losses": max_consec_losses,
            "run_mode": run_mode,
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }

        # Cache for 30s
        try:
            from src.services.redis_cache import cache_set
            cache_set(cache_key, result, ttl_seconds=30)
        except Exception:
            pass

        return result

    except Exception as e:
        logger.warning("Failed to fetch stats summary: %s", e)
        return _empty_summary()


def _empty_summary() -> Dict[str, Any]:
    return {
        "total_trades": 0, "win_rate": 0.0, "total_pnl_usd": 0.0,
        "active_trades": 0, "executed_24h": 0, "filtered_24h": 0,
        "daily_pnl_usd": 0.0, "win_count": 0, "loss_count": 0,
        "best_trade_usd": 0.0, "worst_trade_usd": 0.0,
        "avg_rr": 0.0, "profit_factor": 0.0,
        "max_consecutive_wins": 0, "max_consecutive_losses": 0,
    }


def _max_consecutive(rows: List[Dict[str, Any]], outcome: str) -> int:
    """Count the longest consecutive streak of a given outcome."""
    max_streak = 0
    current = 0
    for r in rows:
        o = (r.get("outcome") or "").lower()
        if o == outcome or (outcome == "loss" and o in ("loss", "lose")):
            current += 1
            max_streak = max(max_streak, current)
        else:
            current = 0
    return max_streak
