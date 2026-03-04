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
    today_start = datetime.combine(date.today(), datetime.min.time()).isoformat()
    daily_pnl = 0.0
    live_daily_pnl: Optional[float] = None
    paper_daily_pnl: Optional[float] = None
    try:
        # Combined (backward compat)
        resp = (
            sb.table("trading_signals")
            .select("pnl_usd, run_mode")
            .eq("status", "closed")
            .gte("created_at", today_start)
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
    starting_equity = s.account_balance
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
        reset_metaapi_circuit()
        return {"status": "ok", "message": "Circuit breaker reset"}
    except Exception as exc:
        logger.warning("Circuit breaker reset failed: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))
