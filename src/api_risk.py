"""Risk Cockpit API -- live risk state + kill switch toggle."""

import logging
from datetime import date, datetime, timezone
from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from config import get_settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/risk", tags=["risk"])

# ── Lazy Supabase client (same pattern as api_rules.py) ──────

from src.adapters.supabase_api import get_api_supabase as _get_supabase


# ── Singleton guard rail instances ───────────────────────────

_correlation_manager = None


def _get_correlation_manager():
    global _correlation_manager
    if _correlation_manager is None:
        from src.core.guard_rails.correlation import create_correlation_manager_from_settings

        _correlation_manager = create_correlation_manager_from_settings()
    return _correlation_manager


# ── Request / Response Models ────────────────────────────────


class KillSwitchRequest(BaseModel):
    enabled: bool
    reason: str = Field(default="Manual toggle from UI")


class RiskStatusResponse(BaseModel):
    kill_switch_active: bool
    kill_switch_reason: Optional[str] = None
    daily_pnl: float
    daily_pnl_pct: float
    live_daily_pnl: Optional[float] = None
    paper_daily_pnl: Optional[float] = None
    max_daily_loss_pct: float
    drawdown_pct: float
    max_drawdown_pct: float
    active_positions: int
    max_positions: int
    current_equity: float
    starting_equity: float
    correlation_exposure: Dict[str, Any]
    risk_mode: str
    risk_multiplier: float
    risk_label: str


# ── Endpoints ────────────────────────────────────────────────


@router.get("/status", response_model=RiskStatusResponse)
def get_risk_status():
    """Return live risk state: daily PnL, drawdown, kill switch, positions, correlation."""
    s = get_settings()
    sb = _get_supabase()

    # 1. Daily PnL from closed trades today (combined + by run_mode for UI)
    # Use UTC date to match database timestamps which are stored in UTC
    today_start_utc = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0).isoformat()
    daily_pnl = 0.0
    live_daily_pnl: Optional[float] = None
    paper_daily_pnl: Optional[float] = None
    try:
        # Combined (backward compat)
        resp = (
            sb.table("trading_signals")
            .select("pnl_usd, run_mode")
            .in_("status", ["CLOSED", "closed"])
            .gte("created_at", today_start_utc)
            .execute()
        )
        rows = resp.data or []
        for t in rows:
            daily_pnl += float(t.get("pnl_usd") or 0)
        # Mode-specific for RiskBar / TopBar (LIVE vs PAPER)
        live_daily_pnl = sum(
            float(t.get("pnl_usd") or 0)
            for t in rows
            if (t.get("run_mode") or "LIVE").upper() == "LIVE"
        )
        paper_daily_pnl = sum(
            float(t.get("pnl_usd") or 0)
            for t in rows
            if (t.get("run_mode") or "").upper() == "PAPER"
        )
    except Exception:
        pass

    # 2. Active positions + correlation exposure
    try:
        active_resp = (
            sb.table("trading_signals")
            .select("symbol, side, size, entry, created_at, zone_id, trade_key")
            .in_("status", ["active", "executed"])
            .execute()
        )
        active_data = active_resp.data or []
    except Exception:
        active_data = []

    active_count = len(active_data)

    # Build correlation exposure map
    from src.core.guard_rails.correlation import ActivePosition

    cm = _get_correlation_manager()
    positions = []
    for r in active_data:
        try:
            positions.append(
                ActivePosition(
                    symbol=r.get("symbol", "UNKNOWN"),
                    side=r.get("side", "buy"),
                    size=float(r.get("size") or 0),
                    entry_price=float(r.get("entry") or 0),
                    entry_time=(
                        datetime.fromisoformat(r["created_at"])
                        if r.get("created_at")
                        else datetime.now(timezone.utc)
                    ),
                    zone_id=r.get("zone_id"),
                    trade_key=r.get("trade_key"),
                )
            )
        except Exception:
            continue

    correlation_exposure = cm.get_portfolio_exposure(positions)

    # 3. Equity & drawdown
    # Try to get real balance from account_status_snapshots (MetaAPI synced by AccountSyncService)
    starting_equity = s.account_balance  # fallback
    try:
        from datetime import timedelta
        cutoff = (datetime.now(timezone.utc) - timedelta(hours=24)).isoformat()

        # Get all active accounts
        accounts_resp = sb.table("account_strategies")\
            .select("account_name")\
            .eq("is_active", True)\
            .execute()

        if accounts_resp.data:
            total_balance = 0.0
            found_any = False
            for acct in accounts_resp.data:
                acct_name = acct["account_name"]
                snap = sb.table("account_status_snapshots")\
                    .select("balance")\
                    .eq("account_name", acct_name)\
                    .gte("snapshot_time", cutoff)\
                    .order("snapshot_time", desc=True)\
                    .limit(1)\
                    .execute()
                if snap.data:
                    total_balance += float(snap.data[0]["balance"])
                    found_any = True
            if found_any:
                starting_equity = total_balance
                logger.debug("Risk status: using live MetaAPI balance $%.2f", starting_equity)
    except Exception as _eq_err:
        logger.warning("Risk status: failed to fetch live balance: %s", _eq_err)

    current_equity = starting_equity + daily_pnl
    drawdown_pct = max(0.0, (starting_equity - current_equity) / starting_equity * 100) if starting_equity > 0 else 0.0
    daily_pnl_pct = abs(daily_pnl / starting_equity * 100) if daily_pnl < 0 and starting_equity > 0 else 0.0

    # 4. Risk mode & multiplier from PropGuard
    from src.core.guard_rails.prop_guard import check_safety

    _, risk_mult, risk_label = check_safety(current_equity, starting_equity, daily_pnl)

    # 5. Kill switch: check both Redis key and env var
    redis_kill = False
    try:
        from src.adapters.redis_queue import get_redis

        redis_kill = get_redis().get("trading:kill_switch") == "1"
    except Exception:
        pass

    kill_active = bool(getattr(s, "trading_kill_switch", False)) or redis_kill

    kill_reason = None
    if redis_kill:
        kill_reason = "Engaged from UI"
    elif getattr(s, "trading_kill_switch", False):
        kill_reason = "Environment variable"

    return RiskStatusResponse(
        kill_switch_active=kill_active,
        kill_switch_reason=kill_reason,
        daily_pnl=round(daily_pnl, 2),
        daily_pnl_pct=round(daily_pnl_pct, 2),
        live_daily_pnl=round(live_daily_pnl, 2) if live_daily_pnl is not None else None,
        paper_daily_pnl=round(paper_daily_pnl, 2) if paper_daily_pnl is not None else None,
        max_daily_loss_pct=s.trinity_max_daily_loss_pct,
        drawdown_pct=round(drawdown_pct, 2),
        max_drawdown_pct=s.trinity_max_drawdown_pct,
        active_positions=active_count,
        max_positions=s.trinity_max_positions,
        current_equity=round(current_equity, 2),
        starting_equity=starting_equity,
        correlation_exposure=correlation_exposure,
        risk_mode=getattr(s, "risk_mode", "step_up"),
        risk_multiplier=round(risk_mult, 2),
        risk_label=risk_label,
    )


@router.get("/dashboard")
def get_risk_dashboard():
    """
    Full risk state dashboard: daily/weekly/monthly PnL, active guard states,
    guard rejection stats, multipliers, consecutive losses.
    """
    from datetime import timedelta

    s = get_settings()
    sb = _get_supabase()
    now_utc = datetime.now(timezone.utc)

    today_start = now_utc.replace(hour=0, minute=0, second=0, microsecond=0).isoformat()
    week_start = (now_utc - timedelta(days=7)).isoformat()
    month_start = now_utc.replace(day=1, hour=0, minute=0, second=0, microsecond=0).isoformat()

    # ── PnL windows ──────────────────────────────────────────────────
    daily_pnl = weekly_pnl = monthly_pnl = 0.0
    consecutive_losses = 0
    try:
        month_resp = (
            sb.table("trading_signals")
            .select("pnl_usd, created_at, exit_time")
            .in_("status", ["CLOSED", "closed"])
            .gte("created_at", month_start)
            .order("exit_time", desc=True)
            .execute()
        )
        rows = month_resp.data or []
        for t in rows:
            pnl = float(t.get("pnl_usd") or 0)
            monthly_pnl += pnl
            created = t.get("created_at", "")
            if created >= today_start:
                daily_pnl += pnl
            if created >= week_start:
                weekly_pnl += pnl
        # Consecutive losses from latest closed trades
        last_resp = (
            sb.table("trading_signals")
            .select("pnl_usd")
            .in_("status", ["CLOSED", "closed"])
            .order("exit_time", desc=True)
            .limit(10)
            .execute()
        )
        for t in (last_resp.data or []):
            if (float(t.get("pnl_usd") or 0)) < 0:
                consecutive_losses += 1
            else:
                break
    except Exception:
        pass

    # ── Account balance ───────────────────────────────────────────────
    account_balance = float(s.account_balance)
    try:
        cutoff = (now_utc - timedelta(hours=24)).isoformat()
        accounts_resp = sb.table("account_strategies").select("account_name").eq("is_active", True).execute()
        if accounts_resp.data:
            total = 0.0
            found = False
            for acct in accounts_resp.data:
                snap = (
                    sb.table("account_status_snapshots")
                    .select("balance")
                    .eq("account_name", acct["account_name"])
                    .gte("snapshot_time", cutoff)
                    .order("snapshot_time", desc=True)
                    .limit(1)
                    .execute()
                )
                if snap.data:
                    total += float(snap.data[0]["balance"])
                    found = True
            if found:
                account_balance = total
    except Exception:
        pass

    # ── Active guard states ───────────────────────────────────────────
    daily_loss_pct = abs(daily_pnl / account_balance * 100) if daily_pnl < 0 and account_balance > 0 else 0.0
    daily_profit_pct = (daily_pnl / account_balance * 100) if daily_pnl > 0 and account_balance > 0 else 0.0
    weekly_loss_pct = abs(weekly_pnl / account_balance * 100) if weekly_pnl < 0 and account_balance > 0 else 0.0
    monthly_loss_pct = abs(monthly_pnl / account_balance * 100) if monthly_pnl < 0 and account_balance > 0 else 0.0

    guards: Dict[str, Any] = {
        "kill_switch": {"active": False, "label": ""},
        "drawdown_scaling": {"active": False, "label": "Normal (1.0x)", "multiplier": 1.0},
        "profit_lockdown": {"active": False, "label": "No lock-in", "multiplier": 1.0},
        "weekly_loss_limit": {"active": False, "label": "", "pct_used": round(weekly_loss_pct, 2)},
        "monthly_loss_limit": {"active": False, "label": "", "pct_used": round(monthly_loss_pct, 2)},
        "consecutive_losses": {"count": consecutive_losses, "active": False, "label": ""},
    }

    # Kill switch
    try:
        from src.adapters.redis_queue import get_redis
        redis_kill = get_redis().get("trading:kill_switch") == "1"
        env_kill = bool(getattr(s, "trading_kill_switch", False))
        guards["kill_switch"]["active"] = redis_kill or env_kill
        if redis_kill or env_kill:
            guards["kill_switch"]["label"] = "Kill switch ENGAGED"
    except Exception:
        pass

    # Drawdown scaling
    dd_th1 = getattr(s, "drawdown_threshold_1", 0.02) * 100
    dd_th2 = getattr(s, "drawdown_threshold_2", 0.03) * 100
    if daily_loss_pct >= dd_th2:
        guards["drawdown_scaling"].update({"active": True, "label": f"-{daily_loss_pct:.1f}% → 0.25x size", "multiplier": 0.25})
    elif daily_loss_pct >= dd_th1:
        guards["drawdown_scaling"].update({"active": True, "label": f"-{daily_loss_pct:.1f}% → 0.5x size", "multiplier": 0.50})

    # Profit lock-in
    pl_th1 = getattr(s, "profit_lockdown_threshold_1", 0.02) * 100
    pl_th2 = getattr(s, "profit_lockdown_threshold_2", 0.03) * 100
    if daily_profit_pct >= pl_th2:
        guards["profit_lockdown"].update({"active": True, "label": f"+{daily_profit_pct:.1f}% → 0.5x size", "multiplier": 0.50})
    elif daily_profit_pct >= pl_th1:
        guards["profit_lockdown"].update({"active": True, "label": f"+{daily_profit_pct:.1f}% → 0.75x size", "multiplier": 0.75})

    # Weekly / monthly limits
    w_limit = getattr(s, "weekly_max_loss_pct", 10.0)
    if weekly_loss_pct >= w_limit:
        guards["weekly_loss_limit"].update({"active": True, "label": f"HALTED — {weekly_loss_pct:.1f}% / {w_limit:.0f}% limit"})

    m_limit = getattr(s, "monthly_max_loss_pct", 8.0)
    if monthly_loss_pct >= m_limit:
        guards["monthly_loss_limit"].update({"active": True, "label": f"HALTED — {monthly_loss_pct:.1f}% / {m_limit:.0f}% limit"})

    # Consecutive losses
    max_consec = getattr(s, "max_consecutive_losses", 3)
    if consecutive_losses >= max_consec:
        guards["consecutive_losses"].update({"active": True, "label": f"{consecutive_losses} losses in a row — cooling off"})

    # ── Guard rejection stats (last 7 days from trade_events) ────────
    rejection_stats: Dict[str, int] = {}
    try:
        events_resp = (
            sb.table("trade_events")
            .select("event_type, metadata")
            .gte("created_at", week_start)
            .in_("event_type", ["guard_decision"])
            .execute()
        )
        for ev in (events_resp.data or []):
            meta = ev.get("metadata") or {}
            guard_name = meta.get("guard_name", "unknown")
            result = meta.get("result", "")
            if result in ("rejected", "blocked"):
                rejection_stats[guard_name] = rejection_stats.get(guard_name, 0) + 1
    except Exception:
        pass

    return {
        "account_balance": round(account_balance, 2),
        "pnl": {
            "daily": round(daily_pnl, 2),
            "daily_pct": round(daily_loss_pct if daily_pnl < 0 else -daily_profit_pct, 2),
            "weekly": round(weekly_pnl, 2),
            "weekly_pct": round(-weekly_loss_pct if weekly_pnl < 0 else weekly_pnl / account_balance * 100, 2),
            "monthly": round(monthly_pnl, 2),
            "monthly_pct": round(-monthly_loss_pct if monthly_pnl < 0 else monthly_pnl / account_balance * 100, 2),
        },
        "consecutive_losses": consecutive_losses,
        "guards": guards,
        "rejection_stats_7d": rejection_stats,
        "limits": {
            "daily_loss_kill_pct": s.trinity_max_daily_loss_pct,
            "weekly_loss_pct": getattr(s, "weekly_max_loss_pct", 10.0),
            "monthly_loss_pct": getattr(s, "monthly_max_loss_pct", 8.0),
            "max_consecutive_losses": getattr(s, "max_consecutive_losses", 3),
            "profit_lockdown_threshold_1_pct": getattr(s, "profit_lockdown_threshold_1", 0.02) * 100,
            "profit_lockdown_threshold_2_pct": getattr(s, "profit_lockdown_threshold_2", 0.03) * 100,
        },
    }


@router.post("/kill-switch")
def toggle_kill_switch(body: KillSwitchRequest):
    """Toggle kill switch on/off.  Sets Redis key for cross-process sync + audit log."""
    sb = _get_supabase()

    # Toggle Redis key (worker reads this on every trade)
    from src.adapters.redis_queue import get_redis

    r = get_redis()
    if body.enabled:
        r.set("trading:kill_switch", "1")
        action = "engage"
    else:
        r.delete("trading:kill_switch")
        action = "reset"

    # Audit log
    try:
        sb.table("kill_switch_log").insert(
            {"action": action, "reason": body.reason, "toggled_by": "ui"}
        ).execute()
    except Exception as exc:
        logger.error("Failed to log kill switch toggle: %s", exc)

    # Event trail
    try:
        from src.services.trade_events import log_event

        log_event(
            None,
            f"kill_switch_{action}",
            "api",
            {
                "reason": body.reason,
                "who": "ui",
                "what": f"kill_switch_{action}",
            },
        )
    except Exception:
        pass

    return {
        "status": "ok",
        "kill_switch_active": body.enabled,
        "action": action,
        "reason": body.reason,
    }


@router.get("/kill-switch/log")
def get_kill_switch_log(limit: int = 50):
    """
    Return recent kill switch toggles for audit UI.

    Each row includes:
    - action: engage | reset
    - reason: free-form text from operator
    - toggled_by: who initiated the toggle (ui/api/etc)
    - created_at: timestamp
    """
    sb = _get_supabase()
    try:
        resp = (
            sb.table("kill_switch_log")
            .select("*")
            .order("created_at", desc=True)
            .limit(limit)
            .execute()
        )
        rows = resp.data or []
        return {"events": rows, "count": len(rows)}
    except Exception as exc:
        logger.error("Failed to fetch kill_switch_log: %s", exc)
        raise HTTPException(status_code=500, detail="Failed to fetch kill switch log")


@router.post("/circuit-breaker/reset")
def reset_circuit_breaker():
    """Reset the MetaApi circuit breaker so LIVE execution and watchdog can call MetaApi again."""
    try:
        from src.core.circuit_breaker import reset_metaapi_circuit
        reset_metaapi_circuit(reset_all=True)
        return {"status": "ok", "message": "Circuit breaker reset (all keys cleared)"}
    except Exception as exc:
        logger.warning("Circuit breaker reset failed: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))
