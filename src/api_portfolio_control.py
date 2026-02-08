"""
Portfolio Command Center API

Comprehensive API for:
- Live Risk Controls
- Portfolio Optimization
- Multi-Account Orchestration
"""

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/portfolio-control", tags=["portfolio-control"])

# ── Lazy initialization ──────────────────────────────────────────

_client = None


def _get_supabase():
    global _client
    if _client is not None:
        return _client

    from config import get_settings
    from supabase import create_client

    s = get_settings()
    key = (s.supabase_service_role_key or s.supabase_key or "").strip()
    if not s.supabase_url or not key:
        raise HTTPException(status_code=503, detail="Supabase not configured")

    _client = create_client(s.supabase_url, key)
    return _client


# ══════════════════════════════════════════════════════════════════
# REQUEST / RESPONSE MODELS
# ══════════════════════════════════════════════════════════════════

# ── Live Risk Controls ────────────────────────────────────────────

class UpdateRiskSettingRequest(BaseModel):
    value: float | bool | int | dict
    change_reason: Optional[str] = None


class RiskSettingResponse(BaseModel):
    setting_key: str
    value: float | bool | int | dict
    value_type: str
    updated_at: Optional[str] = None
    updated_by: Optional[str] = None


class AllRiskSettingsResponse(BaseModel):
    settings: Dict[str, Any]
    overrides_count: int


class TimeRiskRuleRequest(BaseModel):
    rule_name: str
    trigger_type: str = Field(..., description="TIME_OF_DAY, DAY_OF_WEEK, NFP_RELEASE")
    trigger_time_start: Optional[str] = None
    trigger_time_end: Optional[str] = None
    trigger_days: Optional[List[str]] = None
    risk_multiplier: float = Field(default=1.0, description="0.5 = reduce 50%, 1.5 = increase 50%")
    enabled: bool = True


# ── Portfolio Optimizer ──────────────────────────────────────────

class AddTrailingStopRequest(BaseModel):
    signal_id: int
    trail_distance_pips: float = Field(..., ge=5, le=200)
    activation_price: Optional[float] = None
    wait_for_breakeven: bool = False


class ProfitLockRuleRequest(BaseModel):
    rule_name: str
    trigger_r_multiple: float = Field(..., ge=0.5, le=10.0)
    close_percent: Optional[float] = Field(None, ge=0.1, le=1.0)
    move_sl_to: Optional[str] = Field(None, description="BREAKEVEN, ENTRY, +1R, TRAILING_50PIPS")
    apply_to_symbol: Optional[str] = None
    enabled: bool = True


class BatchPositionActionRequest(BaseModel):
    signal_ids: List[int]
    action: str = Field(..., description="close, scale_out, move_sl_breakeven, add_trailing")
    action_params: Optional[Dict[str, Any]] = None


class HedgeSuggestionResponse(BaseModel):
    id: int
    suggested_symbol: str
    suggested_side: str
    suggested_size: float
    expected_var_reduction_pct: float
    hedge_reason: str
    currency_exposure: Dict[str, float]
    total_exposure_usd: float
    current_var: float


# ── Multi-Account Orchestration ──────────────────────────────────

class AccountPerformanceResponse(BaseModel):
    account_name: str
    balance: float
    daily_pnl: float
    daily_pnl_pct: float
    win_rate: float
    sharpe_ratio: float
    active_positions: int
    total_trades: int


class AllocationRecommendationResponse(BaseModel):
    account_name: str
    current_balance: float
    suggested_allocation_usd: float
    change_usd: float
    change_pct: float
    reason: str


class AllocationPlanResponse(BaseModel):
    total_capital: float
    total_allocated: float
    unallocated: float
    recommendations: List[AllocationRecommendationResponse]
    expected_portfolio_sharpe: float


class TradeCopyRuleRequest(BaseModel):
    rule_name: str
    master_account_name: str
    slave_account_names: List[str]
    scale_by_balance: bool = True
    risk_multiplier: float = 1.0
    copy_sl_tp: bool = True
    enabled: bool = True


# ══════════════════════════════════════════════════════════════════
# LIVE RISK CONTROLS ENDPOINTS
# ══════════════════════════════════════════════════════════════════

@router.get("/risk/settings", response_model=AllRiskSettingsResponse)
def get_all_risk_settings():
    """Get all current risk settings (DB overrides + .env defaults)."""
    from src.core.dynamic_config import get_dynamic_setting, get_all_active_overrides
    from config import get_settings

    s = get_settings()

    # Build complete settings dict
    settings = {
        "risk_percent": get_dynamic_setting("risk_percent", s.risk_percent),
        "max_lot_size": get_dynamic_setting("max_lot_size", s.max_lot_size),
        "min_rr_ratio": get_dynamic_setting("min_rr_ratio", s.min_rr_ratio),
        "portfolio_max_var_usd": get_dynamic_setting("portfolio_max_var_usd", s.portfolio_max_var_usd),
        "portfolio_var_enabled": get_dynamic_setting("portfolio_var_enabled", s.portfolio_var_enabled),
        "kelly_enabled": get_dynamic_setting("kelly_enabled", s.kelly_enabled),
        "kelly_fraction": get_dynamic_setting("kelly_fraction", s.kelly_fraction),
        "sector_limit_forex_majors": get_dynamic_setting("sector_limit_forex_majors", s.sector_limit_forex_majors),
        "sector_limit_forex_jpy": get_dynamic_setting("sector_limit_forex_jpy", s.sector_limit_forex_jpy),
        "sector_limit_forex_eur": get_dynamic_setting("sector_limit_forex_eur", s.sector_limit_forex_eur),
        "sector_limit_indices_us": get_dynamic_setting("sector_limit_indices_us", s.sector_limit_indices_us),
        "pine_min_score": get_dynamic_setting("pine_min_score", s.pine_min_score),
        "pine_min_grade": get_dynamic_setting("pine_min_grade", s.pine_min_grade),
        "pine_require_liq_swept": get_dynamic_setting("pine_require_liq_swept", s.pine_require_liq_swept),
    }

    overrides = get_all_active_overrides()

    return AllRiskSettingsResponse(
        settings=settings,
        overrides_count=len(overrides)
    )


@router.patch("/risk/settings/{setting_key}")
def update_risk_setting(setting_key: str, body: UpdateRiskSettingRequest):
    """
    Update a risk setting live (no restart required).

    Example:
        PATCH /api/portfolio-control/risk/settings/risk_percent
        {"value": 0.75, "change_reason": "Market conditions favorable"}
    """
    from src.core.dynamic_config import update_setting

    # Validate setting key
    ALLOWED_SETTINGS = {
        "risk_percent", "max_lot_size", "min_rr_ratio",
        "portfolio_max_var_usd", "portfolio_var_enabled",
        "kelly_enabled", "kelly_fraction",
        "sector_limit_forex_majors", "sector_limit_forex_jpy",
        "sector_limit_forex_eur", "sector_limit_forex_gbp",
        "sector_limit_indices_us", "sector_limit_indices_eu",
        "sector_limit_precious_metals", "sector_limit_crypto",
        "pine_min_score", "pine_min_grade", "pine_require_liq_swept",
        "pine_min_departure_strength", "pine_min_return_strength",
    }

    if setting_key not in ALLOWED_SETTINGS:
        raise HTTPException(400, detail=f"Setting '{setting_key}' not configurable")

    success = update_setting(
        setting_key,
        body.value,
        updated_by="UI",
        change_reason=body.change_reason
    )

    if not success:
        raise HTTPException(500, detail="Failed to update setting")

    return {"status": "ok", "setting": setting_key, "value": body.value}


@router.post("/risk/settings/{setting_key}/reset")
def reset_risk_setting(setting_key: str):
    """Reset a setting to .env default (remove override)."""
    from src.core.dynamic_config import reset_setting

    success = reset_setting(setting_key)

    if not success:
        raise HTTPException(500, detail="Failed to reset setting")

    return {"status": "ok", "setting": setting_key, "reset": True}


@router.get("/risk/time-rules")
def get_time_based_rules():
    """Get all time-based risk rules."""
    sb = _get_supabase()

    try:
        result = sb.table("time_based_risk_rules").select("*").order("id").execute()
        return {"rules": result.data or []}
    except Exception as e:
        raise HTTPException(500, detail=f"Failed to fetch time rules: {e}")


@router.post("/risk/time-rules")
def create_time_risk_rule(body: TimeRiskRuleRequest):
    """Create a new time-based risk rule."""
    sb = _get_supabase()

    try:
        data = body.model_dump()
        result = sb.table("time_based_risk_rules").insert(data).execute()

        if result.data:
            return {"status": "ok", "rule": result.data[0]}

        raise HTTPException(500, detail="Failed to create rule")

    except Exception as e:
        raise HTTPException(500, detail=f"Failed to create time rule: {e}")


@router.patch("/risk/time-rules/{rule_id}/toggle")
def toggle_time_risk_rule(rule_id: int, enabled: bool):
    """Enable/disable a time-based risk rule."""
    sb = _get_supabase()

    try:
        sb.table("time_based_risk_rules").update({"enabled": enabled}).eq("id", rule_id).execute()
        return {"status": "ok", "rule_id": rule_id, "enabled": enabled}
    except Exception as e:
        raise HTTPException(500, detail=f"Failed to toggle rule: {e}")


# ══════════════════════════════════════════════════════════════════
# PORTFOLIO OPTIMIZER ENDPOINTS
# ══════════════════════════════════════════════════════════════════

@router.post("/optimizer/trailing-stop")
def add_trailing_stop(body: AddTrailingStopRequest):
    """Add a trailing stop to an active position."""
    from src.services.trailing_stop_manager import TrailingStopManager

    sb = _get_supabase()
    manager = TrailingStopManager(sb)

    ts_id = manager.add_trailing_stop(
        signal_id=body.signal_id,
        trail_distance_pips=body.trail_distance_pips,
        activation_price=body.activation_price,
        wait_for_breakeven=body.wait_for_breakeven
    )

    if not ts_id:
        raise HTTPException(500, detail="Failed to add trailing stop")

    return {"status": "ok", "trailing_stop_id": ts_id}


@router.get("/optimizer/trailing-stops")
def get_active_trailing_stops():
    """Get all active trailing stops."""
    from src.services.trailing_stop_manager import TrailingStopManager

    sb = _get_supabase()
    manager = TrailingStopManager(sb)

    trailing_stops = manager.get_active_trailing_stops()

    return {
        "trailing_stops": [
            {
                "id": ts.id,
                "signal_id": ts.signal_id,
                "symbol": ts.symbol,
                "side": ts.side,
                "trail_distance_pips": ts.trail_distance_pips,
                "current_sl": ts.current_sl,
                "is_activated": ts.is_activated,
                "times_moved": ts.times_moved,
            }
            for ts in trailing_stops
        ]
    }


@router.delete("/optimizer/trailing-stops/{trailing_stop_id}")
def remove_trailing_stop(trailing_stop_id: int):
    """Remove (deactivate) a trailing stop."""
    from src.services.trailing_stop_manager import TrailingStopManager

    sb = _get_supabase()
    manager = TrailingStopManager(sb)

    success = manager.remove_trailing_stop(trailing_stop_id)

    if not success:
        raise HTTPException(500, detail="Failed to remove trailing stop")

    return {"status": "ok", "trailing_stop_id": trailing_stop_id}


@router.post("/optimizer/profit-lock-rule")
def create_profit_lock_rule(body: ProfitLockRuleRequest):
    """Create a new profit lock rule."""
    sb = _get_supabase()

    try:
        data = body.model_dump()
        result = sb.table("profit_lock_rules").insert(data).execute()

        if result.data:
            return {"status": "ok", "rule": result.data[0]}

        raise HTTPException(500, detail="Failed to create rule")

    except Exception as e:
        raise HTTPException(500, detail=f"Failed to create profit lock rule: {e}")


@router.get("/optimizer/profit-lock-rules")
def get_profit_lock_rules():
    """Get all profit lock rules."""
    sb = _get_supabase()

    try:
        result = sb.table("profit_lock_rules").select("*").order("priority").execute()
        return {"rules": result.data or []}
    except Exception as e:
        raise HTTPException(500, detail=f"Failed to fetch rules: {e}")


@router.post("/optimizer/batch-action")
def batch_position_action(body: BatchPositionActionRequest):
    """
    Execute batch actions on multiple positions.

    Actions:
    - close: Close all selected positions
    - scale_out: Close X% of all selected positions
    - move_sl_breakeven: Move SL to breakeven for all
    - add_trailing: Add trailing stop to all
    """
    sb = _get_supabase()

    if not body.signal_ids:
        raise HTTPException(400, detail="No signal IDs provided")

    results = []

    for signal_id in body.signal_ids:
        try:
            if body.action == "close":
                # Close position
                sb.table("trading_signals").update({
                    "status": "closed",
                    "closed_at": datetime.now(timezone.utc).isoformat(),
                    "exit_type": "MANUAL_BATCH",
                }).eq("id", signal_id).execute()

                results.append({"signal_id": signal_id, "success": True})

            elif body.action == "move_sl_breakeven":
                # Get entry price
                signal = sb.table("trading_signals").select("entry").eq("id", signal_id).single().execute()
                entry = signal.data.get("entry")

                if entry:
                    sb.table("trading_signals").update({"sl": entry}).eq("id", signal_id).execute()
                    results.append({"signal_id": signal_id, "success": True})

            elif body.action == "add_trailing":
                # Add trailing stop
                from src.services.trailing_stop_manager import TrailingStopManager

                manager = TrailingStopManager(sb)
                trail_distance = body.action_params.get("trail_distance_pips", 50) if body.action_params else 50

                ts_id = manager.add_trailing_stop(
                    signal_id=signal_id,
                    trail_distance_pips=trail_distance,
                    wait_for_breakeven=True
                )

                results.append({"signal_id": signal_id, "success": bool(ts_id), "trailing_stop_id": ts_id})

        except Exception as e:
            logger.error(f"Batch action failed for signal {signal_id}: {e}")
            results.append({"signal_id": signal_id, "success": False, "error": str(e)})

    success_count = sum(1 for r in results if r.get("success"))

    return {
        "status": "ok",
        "action": body.action,
        "total": len(body.signal_ids),
        "success": success_count,
        "failed": len(body.signal_ids) - success_count,
        "results": results,
    }


@router.get("/optimizer/hedge-suggestions")
def get_hedge_suggestions():
    """Get pending hedge suggestions."""
    from src.services.hedging_engine import HedgingEngine

    sb = _get_supabase()
    hedge_engine = HedgingEngine(sb)

    suggestions = hedge_engine.get_pending_suggestions()

    return {"suggestions": suggestions}


@router.post("/optimizer/generate-hedge")
def generate_hedge_suggestion():
    """
    Analyze current portfolio and generate hedge suggestion.
    """
    from src.services.hedging_engine import HedgingEngine
    from src.core.guard_rails.correlation import get_active_positions_from_db

    sb = _get_supabase()
    hedge_engine = HedgingEngine(sb)

    # Get active positions
    active_positions = get_active_positions_from_db()

    position_dicts = []
    for pos in active_positions:
        position_dicts.append({
            "symbol": pos.symbol,
            "side": pos.side,
            "notional_value": abs(pos.size) * 100_000,  # Simplified
            "size": pos.size,
            "entry_price": pos.entry_price,
        })

    # Generate suggestion
    suggestion = hedge_engine.suggest_hedge(position_dicts)

    if not suggestion:
        return {"status": "ok", "suggestion": None, "message": "No hedge needed"}

    # Save suggestion
    suggestion_id = hedge_engine.save_hedge_suggestion(suggestion)

    return {
        "status": "ok",
        "suggestion_id": suggestion_id,
        "suggestion": {
            "symbol": suggestion.symbol,
            "side": suggestion.side,
            "size": suggestion.size,
            "expected_var_reduction_pct": suggestion.expected_var_reduction_pct,
            "reason": suggestion.reason,
            "currency_exposure": suggestion.currency_exposure,
        }
    }


@router.post("/optimizer/hedge-suggestions/{suggestion_id}/accept")
def accept_hedge_suggestion(suggestion_id: int):
    """Accept a hedge suggestion (marks as accepted)."""
    from src.services.hedging_engine import HedgingEngine

    sb = _get_supabase()
    hedge_engine = HedgingEngine(sb)

    # For now, just mark as accepted
    # Actual execution would happen via normal signal flow
    success = hedge_engine.accept_hedge_suggestion(suggestion_id, executed_signal_id=0)

    if not success:
        raise HTTPException(500, detail="Failed to accept hedge suggestion")

    return {"status": "ok", "suggestion_id": suggestion_id}


@router.post("/optimizer/hedge-suggestions/{suggestion_id}/reject")
def reject_hedge_suggestion(suggestion_id: int):
    """Reject/dismiss a hedge suggestion."""
    from src.services.hedging_engine import HedgingEngine

    sb = _get_supabase()
    hedge_engine = HedgingEngine(sb)

    success = hedge_engine.reject_hedge_suggestion(suggestion_id)

    if not success:
        raise HTTPException(500, detail="Failed to reject hedge suggestion")

    return {"status": "ok", "suggestion_id": suggestion_id}


# ══════════════════════════════════════════════════════════════════
# MULTI-ACCOUNT ORCHESTRATION ENDPOINTS
# ══════════════════════════════════════════════════════════════════

@router.get("/accounts/comparison")
def get_account_comparison():
    """Get side-by-side comparison of all accounts."""
    from src.services.account_orchestrator import AccountOrchestrator

    sb = _get_supabase()
    orchestrator = AccountOrchestrator(sb)

    comparison = orchestrator.get_account_comparison()

    return {"accounts": comparison}


@router.get("/accounts/{account_name}/performance", response_model=AccountPerformanceResponse)
def get_account_performance(account_name: str, lookback_days: int = 30):
    """Get performance metrics for a specific account."""
    from src.services.account_orchestrator import AccountOrchestrator

    sb = _get_supabase()
    orchestrator = AccountOrchestrator(sb)

    perf = orchestrator.get_account_performance(account_name, lookback_days)

    if not perf:
        raise HTTPException(404, detail=f"Account '{account_name}' not found")

    return AccountPerformanceResponse(
        account_name=perf.account_name,
        balance=perf.balance,
        daily_pnl=perf.daily_pnl,
        daily_pnl_pct=perf.daily_pnl_pct,
        win_rate=perf.win_rate,
        sharpe_ratio=perf.sharpe_ratio,
        active_positions=perf.active_positions,
        total_trades=perf.total_trades,
    )


@router.delete("/accounts/{account_name}")
def delete_account(account_name: str):
    """
    Delete an account strategy from account_strategies table.

    This does NOT delete associated trades - trades remain in trading_signals.
    """
    sb = _get_supabase()

    try:
        # Check if account exists
        result = sb.table("account_strategies").select("id").eq(
            "account_name", account_name
        ).execute()

        if not result.data or len(result.data) == 0:
            raise HTTPException(404, detail=f"Account '{account_name}' not found")

        # Delete the account
        sb.table("account_strategies").delete().eq(
            "account_name", account_name
        ).execute()

        return {"success": True, "message": f"Account '{account_name}' deleted successfully"}

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, detail=f"Failed to delete account: {str(e)}")


@router.post("/accounts/allocation/suggest", response_model=AllocationPlanResponse)
def suggest_capital_allocation(
    total_capital: float,
    optimization_goal: str = "maximize_sharpe"
):
    """
    Suggest optimal capital allocation across all accounts.

    Args:
        total_capital: Total available capital to allocate
        optimization_goal: maximize_sharpe, maximize_return, minimize_risk
    """
    from src.services.account_orchestrator import AccountOrchestrator

    sb = _get_supabase()
    orchestrator = AccountOrchestrator(sb)

    plan = orchestrator.suggest_capital_allocation(total_capital, optimization_goal)

    return AllocationPlanResponse(
        total_capital=plan.total_capital,
        total_allocated=plan.total_allocated,
        unallocated=plan.unallocated,
        recommendations=[
            AllocationRecommendationResponse(
                account_name=r.account_name,
                current_balance=r.current_balance,
                suggested_allocation_usd=r.suggested_allocation_usd,
                change_usd=r.change_usd,
                change_pct=r.change_pct,
                reason=r.reason,
            )
            for r in plan.recommendations
        ],
        expected_portfolio_sharpe=plan.expected_portfolio_sharpe,
    )


@router.post("/accounts/allocation/execute/{account_name}")
def execute_allocation(account_name: str, allocation_usd: float):
    """Execute capital allocation for a specific account."""
    from src.services.account_orchestrator import AccountOrchestrator, AllocationRecommendation

    sb = _get_supabase()
    orchestrator = AccountOrchestrator(sb)

    # Get current balance
    current_balance = 0.0
    try:
        account = sb.table("account_strategies").select("allocated_capital_usd").eq(
            "account_name", account_name
        ).single().execute()

        current_balance = account.data.get("allocated_capital_usd", 0)
    except Exception:
        pass

    # Create recommendation
    recommendation = AllocationRecommendation(
        account_name=account_name,
        current_balance=current_balance,
        suggested_allocation_usd=allocation_usd,
        change_usd=allocation_usd - current_balance,
        change_pct=(allocation_usd - current_balance) / current_balance * 100 if current_balance > 0 else 0,
        reason="Manual allocation via UI",
        performance_score=0.0,
    )

    success = orchestrator.execute_allocation(recommendation)

    if not success:
        raise HTTPException(500, detail="Failed to execute allocation")

    return {"status": "ok", "account_name": account_name, "new_allocation": allocation_usd}


@router.get("/accounts/trade-copy-rules")
def get_trade_copy_rules():
    """Get all trade copy rules."""
    sb = _get_supabase()

    try:
        result = sb.table("trade_copy_rules").select("*").order("id").execute()
        return {"rules": result.data or []}
    except Exception as e:
        raise HTTPException(500, detail=f"Failed to fetch trade copy rules: {e}")


@router.post("/accounts/trade-copy-rules")
def create_trade_copy_rule(body: TradeCopyRuleRequest):
    """Create a new trade copy rule."""
    sb = _get_supabase()

    try:
        data = body.model_dump()
        result = sb.table("trade_copy_rules").insert(data).execute()

        if result.data:
            return {"status": "ok", "rule": result.data[0]}

        raise HTTPException(500, detail="Failed to create rule")

    except Exception as e:
        raise HTTPException(500, detail=f"Failed to create trade copy rule: {e}")


@router.patch("/accounts/trade-copy-rules/{rule_id}/toggle")
def toggle_trade_copy_rule(rule_id: int, enabled: bool):
    """Enable/disable a trade copy rule."""
    sb = _get_supabase()

    try:
        sb.table("trade_copy_rules").update({"enabled": enabled}).eq("id", rule_id).execute()
        return {"status": "ok", "rule_id": rule_id, "enabled": enabled}
    except Exception as e:
        raise HTTPException(500, detail=f"Failed to toggle rule: {e}")


@router.get("/accounts/trade-copy-log")
def get_trade_copy_log(limit: int = 50):
    """Get recent trade copy operations."""
    sb = _get_supabase()

    try:
        result = sb.table("trade_copy_log").select("*").order(
            "copied_at", desc=True
        ).limit(limit).execute()

        return {"log": result.data or []}
    except Exception as e:
        raise HTTPException(500, detail=f"Failed to fetch trade copy log: {e}")
