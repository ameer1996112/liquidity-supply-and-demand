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

router = APIRouter(prefix="/api/portfolio-control", tags=["portfolio-control"])

# ── Shared Supabase client with auto-reconnect ──────────────────

from src.adapters.supabase_api import get_api_supabase as _get_supabase, reset_api_supabase, supabase_query


def _is_connection_error(exc: Exception) -> bool:
    """Check if an exception is a transient Supabase/HTTP2 connection error."""
    err = str(exc).lower()
    return any(k in err for k in ("connectionterminated", "remoteprotocolerror", "connection reset", "broken pipe"))


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
    equity: float
    daily_pnl: float
    daily_pnl_pct: float
    win_rate: float
    sharpe_ratio: float
    max_drawdown_pct: float
    profit_factor: float
    active_positions: int
    total_trades: int
    # Live broker data
    free_margin: Optional[float] = None
    margin_used: Optional[float] = None
    margin_level_pct: Optional[float] = None
    # Account config
    provider: Optional[str] = None
    account_type: Optional[str] = None
    strategy_type: Optional[str] = None
    connection_status: Optional[str] = None
    last_sync_time: Optional[str] = None
    server_name: Optional[str] = None
    platform_type: Optional[str] = None
    leverage: Optional[int] = None
    # Risk config
    risk_percent: Optional[float] = None
    min_rr_ratio: Optional[float] = None
    max_lot_size: Optional[float] = None
    max_positions: Optional[int] = None
    pause_trading: Optional[bool] = None


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


# ── Account Creation ─────────────────────────────────────────────

class CreateAccountRequest(BaseModel):
    account_name: str = Field(..., min_length=1, max_length=100)
    account_type: str = Field(default="Personal", description="Personal, Eval, Funded")
    provider: str = Field(default="Personal", description="FTMO, MyFundedFX, Personal, etc.")
    strategy_type: str = Field(default="BALANCED")
    risk_percent: float = Field(default=1.0, ge=0.1, le=10.0)
    max_positions: int = Field(default=3, ge=1, le=20)
    allocated_capital_usd: float = Field(default=10000, ge=0)
    max_lot_size: float = Field(default=1.0, ge=0.01, le=100)
    min_rr_ratio: float = Field(default=0.0, ge=0)
    meta_api_account_id: Optional[str] = None
    meta_api_token: Optional[str] = Field(default=None, description="MetaAPI JWT token (stored in DB, takes priority over env var)")
    meta_api_token_env_key: str = Field(default="META_API_TOKEN")


class TestConnectionRequest(BaseModel):
    meta_api_account_id: str = Field(..., min_length=1)
    meta_api_token: str = Field(..., min_length=10)


# ── Evaluation Progress ───────────────────────────────────────────

class EvaluationRulesRequest(BaseModel):
    profit_target_usd: float = Field(..., ge=100, description="Total profit required to pass (e.g., 10000)")
    daily_loss_limit_pct: float = Field(..., ge=0, le=100, description="Max daily loss % of starting balance (e.g., 5)")
    max_drawdown_pct: float = Field(..., ge=0, le=100, description="Max drawdown % from peak equity (e.g., 10)")
    min_trading_days: int = Field(default=0, ge=0, description="Minimum number of trading days required")
    consistency_max_day_pct: Optional[float] = Field(None, ge=0, le=1, description="Max % of total profit from single day (e.g., 0.40)")


class EvaluationProgressResponse(BaseModel):
    id: int
    account_name: str
    profit_target_usd: float
    daily_loss_limit_pct: float
    max_drawdown_pct: float
    min_trading_days: int
    consistency_max_day_pct: Optional[float]
    current_profit_usd: float
    current_dd_pct: float
    daily_loss_today_pct: float
    days_traded: int
    largest_day_profit_pct: float
    largest_day_profit_usd: float
    status: str
    failure_reason: Optional[str]
    started_at: str
    completed_at: Optional[str]
    created_at: str
    updated_at: str


class JournalEntryRequest(BaseModel):
    signal_id: Optional[int] = None
    note_text: str = Field(..., min_length=1, max_length=5000)
    tags: Optional[List[str]] = None
    trade_rating: Optional[int] = Field(None, ge=1, le=5)
    emotional_state: Optional[str] = None


class ReconcileStatusRow(BaseModel):
    account_name: str
    last_reconcile_time: Optional[str] = None
    last_reconcile_drift_count: int = 0
    connection_status: Optional[str] = None
    last_sync_time: Optional[str] = None


class ReconcileStatusResponse(BaseModel):
    accounts: List[ReconcileStatusRow]


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
        # Calculate notional value using instrument-aware calculation
        from src.services.position_optimizer import PositionOptimizer
        optimizer = PositionOptimizer()
        notional = optimizer.calculate_notional_value(
            symbol=pos.symbol,
            side=pos.side,
            size=abs(pos.size),
            entry_price=pos.entry_price
        )

        position_dicts.append({
            "symbol": pos.symbol,
            "side": pos.side,
            "notional_value": notional,
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

    for attempt in range(2):
        try:
            sb = _get_supabase()
            orchestrator = AccountOrchestrator(sb)
            comparison = orchestrator.get_account_comparison()
            return {"accounts": comparison}
        except Exception as e:
            if attempt == 0 and _is_connection_error(e):
                logger.warning("Supabase connection error in comparison, retrying: %s", e)
                reset_api_supabase()
                continue
            raise



@router.get("/accounts/allocation-suggest", response_model=AllocationPlanResponse)
@router.post("/accounts/allocation/suggest", response_model=AllocationPlanResponse)
@supabase_query
def suggest_capital_allocation(
    total_capital: float,
    goal: str = "maximize_sharpe",
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

    plan = orchestrator.suggest_capital_allocation(total_capital, goal)

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
    for attempt in range(2):
        try:
            sb = _get_supabase()
            result = sb.table("trade_copy_rules").select("*").order("id").execute()
            return {"rules": result.data or []}
        except Exception as e:
            if attempt == 0 and _is_connection_error(e):
                logger.warning("Supabase connection error in trade-copy-rules, retrying: %s", e)
                reset_api_supabase()
                continue
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



@router.get("/accounts/{account_name}")
def get_account_detail(account_name: str):
    """Get detail for a single account by name."""
    from src.services.account_orchestrator import AccountOrchestrator

    for attempt in range(2):
        try:
            sb = _get_supabase()
            orchestrator = AccountOrchestrator(sb)
            accounts = orchestrator.get_account_comparison()
            match = next(
                (a for a in accounts if a.get("account_name") == account_name),
                None,
            )
            if match is None:
                raise HTTPException(404, detail=f"Account '{account_name}' not found")
            return match
        except HTTPException:
            raise
        except Exception as e:
            if attempt == 0 and _is_connection_error(e):
                logger.warning("Supabase connection error in account detail, retrying: %s", e)
                reset_api_supabase()
                continue
            raise


@router.post("/accounts/{account_name}/sync")
def sync_account(account_name: str):
    """
    Manually trigger sync for a specific account.

    Fetches account status and positions from MetaAPI and saves to database.

    Args:
        account_name: Name of the account to sync

    Returns:
        Sync status and results
    """
    from src.services.account_sync_service import AccountSyncService

    sb = _get_supabase()
    sync_service = AccountSyncService(sb)

    # Sync account status
    status_ok = sync_service.sync_account_status(account_name)

    # Sync positions
    positions_ok = sync_service.sync_account_positions(account_name)

    if not status_ok and not positions_ok:
        raise HTTPException(
            500,
            detail=f"Failed to sync account {account_name}. Check logs for details."
        )

    return {
        "status": "ok",
        "account_name": account_name,
        "status_synced": status_ok,
        "positions_synced": positions_ok,
    }


@router.post("/accounts/sync-all")
def sync_all_accounts():
    """
    Manually trigger sync for all active accounts.

    Returns:
        Sync results for all accounts
    """
    from src.services.account_sync_service import AccountSyncService

    sb = _get_supabase()
    sync_service = AccountSyncService(sb)

    results = sync_service.sync_all_active_accounts()

    success_count = sum(1 for v in results.values() if v)

    return {
        "status": "ok",
        "total_accounts": len(results),
        "success_count": success_count,
        "failed_count": len(results) - success_count,
        "results": results,
    }


@router.get("/reconcile/status", response_model=ReconcileStatusResponse)
def get_reconcile_status():
    """
    Reconciliation status per account.

    Returns:
      - last_reconcile_time per account
      - last_reconcile_drift_count per account
      - connection_status (broker health)
      - last_sync_time (MetaAPI sync recency)
    """
    sb = _get_supabase()
    try:
        resp = (
            sb.table("account_strategies")
            .select(
                "account_name, connection_status, last_sync_time, last_reconcile_time, last_reconcile_drift_count"
            )
            .eq("is_active", True)
            .order("account_name", desc=False)
            .execute()
        )
        rows = resp.data or []
        accounts: List[ReconcileStatusRow] = []
        for r in rows:
            accounts.append(
                ReconcileStatusRow(
                    account_name=r.get("account_name"),
                    last_reconcile_time=r.get("last_reconcile_time"),
                    last_reconcile_drift_count=int(
                        r.get("last_reconcile_drift_count") or 0
                    ),
                    connection_status=r.get("connection_status"),
                    last_sync_time=r.get("last_sync_time") or r.get("last_sync_time")
                    or r.get("last_sync_time"),
                )
            )
        return ReconcileStatusResponse(accounts=accounts)
    except Exception as e:
        logger.error("Failed to fetch reconcile status: %s", e)
        raise HTTPException(500, detail=f"Failed to fetch reconcile status: {e}")


@router.get("/accounts/{account_name}/positions")
def get_account_positions(account_name: str):
    """
    Get open positions for a specific account.
    Returns broker positions (from MetaAPI if available) and DB positions
    from trading_signals, with a basic reconciliation summary.
    """
    sb = _get_supabase()

    try:
        # Fetch active positions from DB
        resp = (
            sb.table("trading_signals")
            .select("*")
            .eq("account_name", account_name)
            .in_("status", ["active", "executed"])
            .order("created_at", desc=True)
            .execute()
        )
        db_positions = resp.data or []

        # Tag each with reconciliation status (all DB-only for now)
        for pos in db_positions:
            pos["reconciliation_status"] = "pending"

        return {
            "broker": [],  # MetaAPI live positions — populated when broker sync is active
            "db": db_positions,
            "reconciliation_summary": {
                "matched": 0,
                "orphaned": 0,
                "pending": len(db_positions),
            },
        }

    except Exception as e:
        logger.error(f"Failed to fetch positions for {account_name}: {e}")
        raise HTTPException(500, detail=f"Failed to fetch positions: {str(e)}")


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
        equity=perf.equity,
        daily_pnl=perf.daily_pnl,
        daily_pnl_pct=perf.daily_pnl_pct,
        win_rate=perf.win_rate,
        sharpe_ratio=perf.sharpe_ratio,
        max_drawdown_pct=perf.max_drawdown_pct,
        profit_factor=perf.profit_factor,
        active_positions=perf.active_positions,
        total_trades=perf.total_trades,
        # Live broker data
        free_margin=perf.free_margin,
        margin_used=perf.margin_used,
        margin_level_pct=perf.margin_level_pct,
        # Account config
        provider=perf.provider,
        account_type=perf.account_type,
        strategy_type=perf.strategy_type,
        connection_status=perf.connection_status,
        last_sync_time=perf.last_sync_time,
        server_name=perf.server_name,
        platform_type=perf.platform_type,
        leverage=perf.leverage,
        # Risk config
        risk_percent=perf.risk_percent,
        min_rr_ratio=perf.min_rr_ratio,
        max_lot_size=perf.max_lot_size,
        max_positions=perf.max_positions,
        pause_trading=perf.pause_trading,
    )


@router.post("/accounts/test-connection")
def test_metaapi_connection(body: TestConnectionRequest):
    """
    Validate MetaAPI credentials before saving an account.
    Returns account info from MetaAPI if the token and account ID are valid.
    """
    import requests as _requests

    account_id = body.meta_api_account_id.strip()
    token = body.meta_api_token.strip()

    try:
        resp = _requests.get(
            f"https://mt-provisioning-api-v1.agiliumtrade.agiliumtrade.ai/users/current/accounts/{account_id}",
            headers={"auth-token": token},
            timeout=15,
        )
    except Exception as exc:
        raise HTTPException(503, detail=f"Could not reach MetaAPI: {exc}")

    if resp.status_code == 401:
        raise HTTPException(401, detail="Invalid MetaAPI token")
    if resp.status_code == 404:
        raise HTTPException(404, detail="MetaAPI account ID not found")
    if resp.status_code != 200:
        raise HTTPException(502, detail=f"MetaAPI returned {resp.status_code}: {resp.text[:200]}")

    data = resp.json()
    return {
        "valid": True,
        "account_id": account_id,
        "name": data.get("name"),
        "server": data.get("server"),
        "platform": data.get("platform"),
        "state": data.get("state"),
        "connection_status": data.get("connectionStatus"),
    }


@router.post("/accounts")
def create_account(body: CreateAccountRequest):
    """
    Create a new account strategy (and optionally a linked broker profile).

    Uses the service-role key so RLS is bypassed.
    """
    sb = _get_supabase()
    account_name = body.account_name.strip()
    meta_api_id = (body.meta_api_account_id or "").strip() or None

    # Check duplicate name
    existing = sb.table("account_strategies").select("id").eq("account_name", account_name).execute()
    if existing.data:
        raise HTTPException(409, detail=f"Account '{account_name}' already exists")

    try:
        # 1. Insert into account_strategies
        payload = {
            "account_name": account_name,
            "strategy_type": body.strategy_type,
            "risk_percent": body.risk_percent,
            "max_positions": body.max_positions,
            "allocated_capital_usd": body.allocated_capital_usd,
            "max_lot_size": body.max_lot_size,
            "min_rr_ratio": body.min_rr_ratio,
            "is_active": True,
            "account_type": body.account_type,
            "provider": body.provider,
            "meta_api_account_id": meta_api_id,
            "meta_api_token_env_key": body.meta_api_token_env_key,
            "connection_status": "disconnected" if meta_api_id else "not_configured",
            "broker_profile_id": None,
        }
        account_result = sb.table("account_strategies").insert(payload).execute()
        account_data = account_result.data[0] if account_result.data else None
        if not account_data:
            raise HTTPException(500, detail="Insert returned no data")

        # 2. Auto-create broker profile if MetaAPI ID provided
        broker_profile = None
        if meta_api_id:
            # Check if profile already exists
            existing_bp = (
                sb.table("broker_profiles")
                .select("id")
                .eq("meta_api_account_id", meta_api_id)
                .limit(1)
                .execute()
            )

            if existing_bp.data:
                profile_id = existing_bp.data[0]["id"]
                # Update token if provided
                new_token = (body.meta_api_token or "").strip() or None
                if new_token:
                    sb.table("broker_profiles").update(
                        {"token": new_token}
                    ).eq("id", profile_id).execute()
            else:
                stored_token = (body.meta_api_token or "").strip() or None
                bp_payload = {
                    "name": account_name,
                    "meta_api_account_id": meta_api_id,
                    "token_env_key": body.meta_api_token_env_key,
                    "token": stored_token,
                    "risk_pct": body.risk_percent,
                    "max_positions": body.max_positions,
                    "run_mode": "LIVE",
                    "is_active": True,
                    "evaluation_mode": body.account_type == "Eval",
                    "starting_balance": body.allocated_capital_usd,
                }
                bp_result = sb.table("broker_profiles").insert(bp_payload).execute()
                broker_profile = bp_result.data[0] if bp_result.data else None
                profile_id = broker_profile["id"] if broker_profile else None

            if profile_id:
                sb.table("account_strategies").update(
                    {"broker_profile_id": profile_id}
                ).eq("id", account_data["id"]).execute()
                account_data["broker_profile_id"] = profile_id

        return {
            "status": "ok",
            "account": account_data,
            "broker_profile": broker_profile,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to create account '%s': %s", account_name, e, exc_info=True)
        raise HTTPException(500, detail=f"Failed to create account: {str(e)}")


@router.delete("/accounts/{account_name}")
def delete_account(account_name: str):
    """
    Delete an account strategy from account_strategies table.

    Cleans up dependent rows so the delete succeeds: portfolio_snapshots
    (unlink via update where supported), capital_allocation_history,
    and trade_copy_rules that reference this account. Trades in
    trading_signals are left as-is (account_name may become orphaned).
    """
    sb = _get_supabase()

    try:
        # Check if account exists
        result = sb.table("account_strategies").select("id").eq(
            "account_name", account_name
        ).execute()

        if not result.data or len(result.data) == 0:
            raise HTTPException(404, detail=f"Account '{account_name}' not found")

        # Unlink dependent data so delete is not blocked by references
        # 1. portfolio_snapshots: set account_name to NULL (if FK is ON DELETE SET NULL this happens automatically; otherwise do it explicitly)
        try:
            sb.table("portfolio_snapshots").update({"account_name": None}).eq(
                "account_name", account_name
            ).execute()
        except Exception:
            pass  # Column or table may not exist; continue

        # 2. capital_allocation_history: delete history for this account (audit trail is optional)
        try:
            sb.table("capital_allocation_history").delete().eq(
                "account_name", account_name
            ).execute()
        except Exception:
            pass

        # 3. trade_copy_rules: delete rules where this account is master; for slave, remove from array (or delete rule if only slave)
        try:
            rules = sb.table("trade_copy_rules").select("id, master_account_name, slave_account_names").execute()
            if rules.data:
                for rule in rules.data:
                    if rule.get("master_account_name") == account_name:
                        sb.table("trade_copy_rules").delete().eq("id", rule["id"]).execute()
                    elif account_name in (rule.get("slave_account_names") or []):
                        new_slaves = [s for s in (rule.get("slave_account_names") or []) if s != account_name]
                        if new_slaves:
                            sb.table("trade_copy_rules").update({"slave_account_names": new_slaves}).eq("id", rule["id"]).execute()
                        else:
                            sb.table("trade_copy_rules").delete().eq("id", rule["id"]).execute()
        except Exception:
            pass

        # Delete the account
        sb.table("account_strategies").delete().eq(
            "account_name", account_name
        ).execute()

        return {"success": True, "message": f"Account '{account_name}' deleted successfully"}

    except HTTPException:
        raise
    except Exception as e:
        err_msg = str(e)
        if "foreign key" in err_msg.lower() or "violates" in err_msg.lower():
            raise HTTPException(
                409,
                detail=f"Cannot delete account: it is still referenced by other data (e.g. portfolio_snapshots). {err_msg}",
            )
        raise HTTPException(500, detail=f"Failed to delete account: {err_msg}")


# ══════════════════════════════════════════════════════════════════
# CHALLENGE SETTINGS ENDPOINTS (Per-account prop firm config)
# ══════════════════════════════════════════════════════════════════


class ChallengeSettingsRequest(BaseModel):
    """Per-account prop firm challenge configuration stored in broker_profiles."""
    evaluation_mode: bool = Field(default=True, description="Enable prop firm guardrails for this account")
    evaluation_phase: str = Field(default="phase1", description="phase1 | phase2 | funded")
    starting_balance: float = Field(default=50000.0, ge=100, description="Account starting balance ($)")
    profit_target: float = Field(default=5000.0, ge=0, description="Profit target to pass phase ($)")
    max_daily_loss_pct: float = Field(default=4.0, ge=0.1, le=20.0, description="Bot kill daily loss % (set below firm limit for buffer)")
    max_drawdown_pct: float = Field(default=8.0, ge=0.1, le=50.0, description="Bot kill drawdown % (set below firm limit for buffer)")
    min_trading_days: int = Field(default=4, ge=0, description="Minimum trading days required")
    consistency_limit_pct: float = Field(default=40.0, ge=10, le=100, description="FTMO 40% rule: best day max % of total profit")


class ChallengeSettingsResponse(BaseModel):
    account_name: str
    broker_profile_id: Optional[int]
    evaluation_mode: bool
    evaluation_phase: str
    starting_balance: float
    profit_target: float
    max_daily_loss_pct: float
    max_drawdown_pct: float
    min_trading_days: int
    consistency_limit_pct: float
    evaluation_start_date: Optional[str]


@router.get("/accounts/{account_name}/challenge", response_model=ChallengeSettingsResponse)
def get_challenge_settings(account_name: str):
    """Get challenge/evaluation settings for an account from its broker_profile."""
    sb = _get_supabase()

    # Get account + its broker_profile_id
    acct = sb.table("account_strategies").select("broker_profile_id").eq(
        "account_name", account_name
    ).limit(1).execute()

    if not acct.data:
        raise HTTPException(404, detail=f"Account '{account_name}' not found")

    profile_id = acct.data[0].get("broker_profile_id")
    if not profile_id:
        # Return defaults — no broker profile yet
        return ChallengeSettingsResponse(
            account_name=account_name,
            broker_profile_id=None,
            evaluation_mode=False,
            evaluation_phase="phase1",
            starting_balance=50000.0,
            profit_target=5000.0,
            max_daily_loss_pct=4.0,
            max_drawdown_pct=8.0,
            min_trading_days=4,
            consistency_limit_pct=40.0,
            evaluation_start_date=None,
        )

    bp = sb.table("broker_profiles").select(
        "id, evaluation_mode, evaluation_phase, evaluation_start_date, "
        "starting_balance, max_daily_loss_pct, max_drawdown_pct, "
        "profit_target, consistency_limit_pct"
    ).eq("id", profile_id).limit(1).execute()

    if not bp.data:
        raise HTTPException(404, detail=f"Broker profile not found for '{account_name}'")

    d = bp.data[0]
    return ChallengeSettingsResponse(
        account_name=account_name,
        broker_profile_id=d["id"],
        evaluation_mode=d.get("evaluation_mode", False),
        evaluation_phase=d.get("evaluation_phase", "phase1"),
        starting_balance=d.get("starting_balance", 50000.0),
        profit_target=d.get("profit_target", 0.0),
        max_daily_loss_pct=d.get("max_daily_loss_pct", 4.0),
        max_drawdown_pct=d.get("max_drawdown_pct", 8.0),
        min_trading_days=d.get("min_trading_days", 4) if d.get("min_trading_days") is not None else 4,
        consistency_limit_pct=d.get("consistency_limit_pct", 40.0),
        evaluation_start_date=str(d["evaluation_start_date"]) if d.get("evaluation_start_date") else None,
    )


@router.put("/accounts/{account_name}/challenge", response_model=ChallengeSettingsResponse)
def update_challenge_settings(account_name: str, body: ChallengeSettingsRequest):
    """Update challenge/evaluation settings for an account.

    Creates a broker_profile if one doesn't exist yet.
    Activates evaluation mode and sets phase-specific limits.
    """
    sb = _get_supabase()

    if body.evaluation_phase not in ("phase1", "phase2", "funded"):
        raise HTTPException(422, detail="evaluation_phase must be phase1, phase2, or funded")

    # Get account
    acct = sb.table("account_strategies").select(
        "id, broker_profile_id, account_name, meta_api_account_id, meta_api_token_env_key, allocated_capital_usd"
    ).eq("account_name", account_name).limit(1).execute()

    if not acct.data:
        raise HTTPException(404, detail=f"Account '{account_name}' not found")

    acct_data = acct.data[0]
    profile_id = acct_data.get("broker_profile_id")

    challenge_fields = {
        "evaluation_mode": body.evaluation_mode,
        "evaluation_phase": body.evaluation_phase,
        "starting_balance": body.starting_balance,
        "profit_target": body.profit_target,
        "max_daily_loss_pct": body.max_daily_loss_pct,
        "max_drawdown_pct": body.max_drawdown_pct,
        "consistency_limit_pct": body.consistency_limit_pct,
    }
    # Set evaluation start date when activating phase1
    if body.evaluation_mode and body.evaluation_phase == "phase1":
        from datetime import date as _date
        challenge_fields["evaluation_start_date"] = str(_date.today())

    if profile_id:
        # Update existing broker_profile
        sb.table("broker_profiles").update(challenge_fields).eq("id", profile_id).execute()
        logger.info("Challenge settings updated for %s (profile_id=%s): phase=%s, eval=%s",
                    account_name, profile_id, body.evaluation_phase, body.evaluation_mode)
    else:
        # Create broker_profile with challenge settings
        bp_payload = {
            "name": account_name,
            "meta_api_account_id": acct_data.get("meta_api_account_id") or "",
            "token_env_key": acct_data.get("meta_api_token_env_key") or "META_API_TOKEN",
            "run_mode": "LIVE",
            "is_active": True,
            **challenge_fields,
        }
        bp_result = sb.table("broker_profiles").insert(bp_payload).execute()
        if not bp_result.data:
            raise HTTPException(500, detail="Failed to create broker profile")
        profile_id = bp_result.data[0]["id"]
        sb.table("account_strategies").update({"broker_profile_id": profile_id}).eq(
            "id", acct_data["id"]
        ).execute()
        logger.info("Broker profile created for %s (id=%s) with challenge settings", account_name, profile_id)

    # Also update account_type if activating evaluation
    if body.evaluation_mode and body.evaluation_phase != "funded":
        sb.table("account_strategies").update({"account_type": "Eval"}).eq(
            "account_name", account_name
        ).execute()
    elif body.evaluation_phase == "funded":
        sb.table("account_strategies").update({"account_type": "Funded"}).eq(
            "account_name", account_name
        ).execute()

    # Return updated settings
    return get_challenge_settings(account_name)


# ══════════════════════════════════════════════════════════════════
# EVALUATION PROGRESS ENDPOINTS (FTMO/PropFirm Challenges)
# ══════════════════════════════════════════════════════════════════


@router.get("/accounts/{account_name}/evaluation", response_model=EvaluationProgressResponse)
def get_evaluation_progress(account_name: str):
    """
    Get evaluation progress for an account.

    Returns current challenge status, rules, and progress metrics.
    Returns 404 if no evaluation is configured.
    """
    from src.services.evaluation_tracker import EvaluationTracker

    sb = _get_supabase()
    tracker = EvaluationTracker(sb)

    eval_data = tracker.get_evaluation(account_name)

    if not eval_data:
        raise HTTPException(404, detail=f"No evaluation configured for account '{account_name}'")

    return EvaluationProgressResponse(**eval_data)


@router.put("/accounts/{account_name}/evaluation")
def update_evaluation_rules(account_name: str, rules: EvaluationRulesRequest):
    """
    Create or update evaluation rules for an account.

    This configures the challenge parameters (profit target, DD limits, etc.).
    Use POST /accounts/{account_name}/evaluation/recalculate to update progress.
    """
    from src.services.evaluation_tracker import EvaluationTracker

    sb = _get_supabase()
    tracker = EvaluationTracker(sb)

    eval_data = tracker.create_or_update_evaluation(
        account_name=account_name,
        profit_target_usd=rules.profit_target_usd,
        daily_loss_limit_pct=rules.daily_loss_limit_pct,
        max_drawdown_pct=rules.max_drawdown_pct,
        min_trading_days=rules.min_trading_days,
        consistency_max_day_pct=rules.consistency_max_day_pct,
    )

    return {
        "status": "ok",
        "message": "Evaluation rules updated successfully",
        "evaluation": eval_data,
    }


@router.post("/accounts/{account_name}/evaluation/recalculate")
def recalculate_evaluation_progress(account_name: str):
    """
    Recalculate evaluation progress from closed trades.

    This updates current_profit, days_traded, drawdown, etc.
    Also checks for rule violations and updates status (active -> passed/failed).
    """
    from src.services.evaluation_tracker import EvaluationTracker

    sb = _get_supabase()
    tracker = EvaluationTracker(sb)

    try:
        eval_data = tracker.calculate_progress(account_name)

        return {
            "status": "ok",
            "message": "Evaluation progress recalculated successfully",
            "evaluation": eval_data,
        }
    except ValueError as e:
        raise HTTPException(404, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to recalculate evaluation for {account_name}: {e}")
        raise HTTPException(500, detail=f"Failed to recalculate evaluation: {str(e)}")


@router.delete("/accounts/{account_name}/evaluation")
def delete_evaluation(account_name: str):
    """
    Delete evaluation configuration for an account.

    Use this to remove challenge tracking when account transitions
    from Eval to Funded or is no longer needed.
    """
    from src.services.evaluation_tracker import EvaluationTracker

    sb = _get_supabase()
    tracker = EvaluationTracker(sb)

    deleted = tracker.delete_evaluation(account_name)

    if not deleted:
        raise HTTPException(404, detail=f"No evaluation found for account '{account_name}'")

    return {
        "status": "ok",
        "message": f"Evaluation deleted for '{account_name}'",
    }


@router.post("/evaluation/recalculate-all")
def recalculate_all_evaluations():
    """
    Recalculate progress for all active evaluations.

    Useful for daily cron jobs or batch processing.
    Returns summary of success/failure counts.
    """
    from src.services.evaluation_tracker import EvaluationTracker

    sb = _get_supabase()
    tracker = EvaluationTracker(sb)

    results = tracker.recalculate_all_active()

    return {
        "status": "ok",
        "message": f"Recalculated {results['total']} evaluations",
        "results": results,
    }


# ══════════════════════════════════════════════════════════════════
# METAAPI DIAGNOSTICS
# ══════════════════════════════════════════════════════════════════

@router.post("/accounts/{account_name}/metaapi/test-connection")
def test_metaapi_connection(account_name: str):
    """
    Manually test the MetaAPI connection for a specific account.
    Returns explicit token presence and authentication status.
    """
    from src.services.account_sync_service import AccountSyncService
    
    # 1. We instantiate the service to grab the adapter safely.
    sb = _get_supabase()
    service = AccountSyncService(sb)
    
    try:
        account_req = sb.table("account_strategies").select("*").eq("account_name", account_name).single().execute()
        if not account_req.data:
            raise HTTPException(404, detail=f"Account {account_name} not found")
            
        adapter = service._get_adapter_for_account(account_req.data)
        if not adapter:
            return {"status": "error", "message": "MetaAPI is not configured or token is completely missing."}
            
        # 2. Force an Account Info fetch. This triggers the 401 interceptor.
        info = adapter.get_account_information()
        return {
            "status": "success", 
            "message": "Connected successfully.",
            "diagnostics": {
                "balance": info.get("balance"),
                "equity": info.get("equity")
            }
        }
        
    except ValueError as ve:
        if str(ve) == "METAAPI_TOKEN_MISSING":
            return {"status": "error", "code": "METAAPI_TOKEN_MISSING", "message": "The environment variable holds an empty string."}
        raise HTTPException(500, detail=str(ve))
    except PermissionError as pe:
        if str(pe) == "METAAPI_AUTH_FAILED":
            return {"status": "error", "code": "METAAPI_AUTH_FAILED", "message": "MetaAPI rejected the token (401 Unauthorized)."}
        raise HTTPException(401, detail=str(pe))
    except Exception as e:
        logger.exception("Failed to test MetaAPI connection")
        return {"status": "error", "message": str(e)}

# ══════════════════════════════════════════════════════════════════
# ANALYTICS & JOURNAL ENDPOINTS
# ══════════════════════════════════════════════════════════════════


@router.get("/accounts/{account_name}/analytics/pairs")
def get_per_pair_analytics(account_name: str):
    """
    Get per-pair performance analytics for an account.

    Returns win rate, profit factor, avg hold time, etc. for each symbol.
    """
    sb = _get_supabase()

    try:
        # Fetch all closed trades for this account (with fallback for legacy trades)
        result = (
            sb.table("trading_signals")
            .select("symbol, pnl_usd, exit_time, created_at, exit_price")
            .eq("account_name", account_name)
            .not_.is_("exit_price", "null")
            .not_.is_("pnl_usd", "null")
            .execute()
        )

        trades = list(result.data or [])

        # If no trades found, try broker_profile_id fallback for legacy trades without account_name
        if len(trades) == 0:
            account_query = sb.table("account_strategies").select("broker_profile_id").eq("account_name", account_name).limit(1).execute()
            if account_query.data and account_query.data[0].get("broker_profile_id"):
                broker_profile_id = account_query.data[0]["broker_profile_id"]
                fallback_result = (
                    sb.table("trading_signals")
                    .select("symbol, pnl_usd, exit_time, created_at, exit_price")
                    .eq("broker_profile_id", broker_profile_id)
                    .is_("account_name", "null")
                    .not_.is_("exit_price", "null")
                    .not_.is_("pnl_usd", "null")
                    .execute()
                )
                trades.extend(fallback_result.data or [])

        if not trades:
            return {"pairs": []}

        # Group by symbol
        from collections import defaultdict
        from datetime import datetime

        pair_data = defaultdict(lambda: {
            "wins": [], "losses": [], "hold_times": []
        })

        for trade in trades:
            symbol = trade.get("symbol")
            pnl = trade.get("pnl_usd", 0)
            exit_time = trade.get("exit_time")
            created_at = trade.get("created_at")

            if not symbol:
                continue

            if pnl >= 0:
                pair_data[symbol]["wins"].append(pnl)
            else:
                pair_data[symbol]["losses"].append(pnl)

            # Calculate hold time
            if exit_time and created_at:
                try:
                    exit_dt = datetime.fromisoformat(exit_time.replace('Z', '+00:00'))
                    entry_dt = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
                    hold_hours = (exit_dt - entry_dt).total_seconds() / 3600
                    pair_data[symbol]["hold_times"].append(hold_hours)
                except Exception as e:
                    logger.error(f"Failed to calculate hold time for {symbol}: {e}", exc_info=True)

        # Calculate stats per pair
        pairs = []
        for symbol, data in pair_data.items():
            wins = data["wins"]
            losses = data["losses"]
            total_trades = len(wins) + len(losses)

            if total_trades == 0:
                continue

            total_wins_usd = sum(wins)
            total_losses_usd = abs(sum(losses))
            total_pnl = sum(wins) + sum(losses)

            win_rate = len(wins) / total_trades if total_trades > 0 else 0
            avg_win = total_wins_usd / len(wins) if wins else 0
            avg_loss = total_losses_usd / len(losses) if losses else 0
            profit_factor = total_wins_usd / total_losses_usd if total_losses_usd > 0 else (10.0 if total_wins_usd > 0 else 1.0)

            avg_hold_time = sum(data["hold_times"]) / len(data["hold_times"]) if data["hold_times"] else 0

            pairs.append({
                "symbol": symbol,
                "total_trades": total_trades,
                "wins": len(wins),
                "losses": len(losses),
                "win_rate": win_rate,
                "total_pnl": total_pnl,
                "avg_win": avg_win,
                "avg_loss": avg_loss,
                "profit_factor": profit_factor,
                "largest_win": max(wins) if wins else 0,
                "largest_loss": min(losses) if losses else 0,
                "avg_hold_time_hours": avg_hold_time,
            })

        # Sort by total trades descending
        pairs.sort(key=lambda x: x["total_trades"], reverse=True)

        return {"pairs": pairs}

    except Exception as e:
        logger.error(f"Failed to calculate pair analytics for {account_name}: {e}")
        raise HTTPException(500, detail=f"Failed to calculate analytics: {str(e)}")


@router.get("/accounts/{account_name}/analytics/streaks")
def get_losing_streaks(account_name: str, min_streak_length: int = 3):
    """
    Detect losing streaks (consecutive losses) for an account.

    Args:
        min_streak_length: Minimum number of consecutive losses to report (default 3)
    """
    sb = _get_supabase()

    try:
        # Fetch all closed trades ordered by exit time
        result = (
            sb.table("trading_signals")
            .select("symbol, pnl_usd, exit_time")
            .eq("account_name", account_name)
            .not_.is_("exit_price", "null")
            .not_.is_("pnl_usd", "null")
            .order("exit_time", desc=False)
            .execute()
        )

        if not result.data or len(result.data) < min_streak_length:
            return {"streaks": []}

        # Detect streaks
        streaks = []
        current_streak = None

        for trade in trades:
            pnl = trade.get("pnl_usd", 0)
            symbol = trade.get("symbol", "UNKNOWN")
            exit_time = trade.get("exit_time")

            if pnl < 0:  # Loss
                if current_streak is None:
                    # Start new streak
                    current_streak = {
                        "start_date": exit_time,
                        "end_date": exit_time,
                        "streak_length": 1,
                        "total_loss": pnl,
                        "symbols": [symbol],
                    }
                else:
                    # Continue streak
                    current_streak["end_date"] = exit_time
                    current_streak["streak_length"] += 1
                    current_streak["total_loss"] += pnl
                    if symbol not in current_streak["symbols"]:
                        current_streak["symbols"].append(symbol)
            else:  # Win - streak broken
                if current_streak and current_streak["streak_length"] >= min_streak_length:
                    current_streak["status"] = "ended"
                    streaks.append(current_streak)
                current_streak = None

        # Check if last streak is still active
        if current_streak and current_streak["streak_length"] >= min_streak_length:
            current_streak["status"] = "active"
            streaks.append(current_streak)

        return {"streaks": streaks}

    except Exception as e:
        logger.error(f"Failed to detect losing streaks for {account_name}: {e}")
        raise HTTPException(500, detail=f"Failed to detect streaks: {str(e)}")


@router.get("/accounts/{account_name}/journal")
def get_journal_entries(account_name: str, tag: Optional[str] = None):
    """
    Get journal entries for an account, optionally filtered by tag.
    """
    sb = _get_supabase()

    try:
        # Step 1: get signal IDs belonging to this account
        sig_resp = (
            sb.table("trading_signals")
            .select("id, symbol, pnl_usd")
            .eq("account_name", account_name)
            .execute()
        )
        signals = sig_resp.data or []
        if not signals:
            return {"entries": []}

        signal_map = {s["id"]: s for s in signals}
        signal_ids = list(signal_map.keys())

        # Step 2: fetch journal entries for those signal IDs
        query = (
            sb.table("trade_journal")
            .select("*")
            .in_("signal_id", signal_ids)
        )

        if tag:
            query = query.contains("tags", [tag])

        query = query.order("created_at", desc=True)
        result = query.execute()

        entries = []
        for entry in result.data or []:
            sig = signal_map.get(entry.get("signal_id"), {})
            pnl = sig.get("pnl_usd")
            entries.append({
                "id": entry.get("id"),
                "signal_id": entry.get("signal_id"),
                "symbol": sig.get("symbol"),
                "note_text": entry.get("note_text"),
                "tags": entry.get("tags", []),
                "screenshot_urls": entry.get("screenshot_urls", []),
                "trade_rating": entry.get("trade_rating"),
                "emotional_state": entry.get("emotional_state"),
                "created_at": entry.get("created_at"),
                "trade_outcome": "win" if pnl and pnl >= 0 else "loss" if pnl else "open",
                "trade_pnl": pnl,
            })

        return {"entries": entries}

    except Exception as e:
        logger.error(f"Failed to fetch journal entries for {account_name}: {e}")
        # Return empty rather than 500 if table doesn't exist yet
        if "trade_journal" in str(e) or "does not exist" in str(e):
            return {"entries": []}
        raise HTTPException(500, detail=f"Failed to fetch journal: {str(e)}")


@router.get("/accounts/{account_name}/history")
def get_trade_history(
    account_name: str,
    days: Optional[int] = None,
    outcome: Optional[str] = None
):
    """
    Get closed trade history for an account (hybrid approach).

    Fetches from:
    1. Local database (trading_signals table)
    2. MetaAPI historical deals

    Then merges and deduplicates the results.

    Args:
        account_name: Account to fetch history for
        days: Number of days to look back (7, 30, 90, or None for all time, max 90 for MetaAPI)
        outcome: Filter by outcome ('win', 'loss', or None for all)

    Returns:
        List of closed trades with entry/exit details, P&L, and metrics
    """
    sb = _get_supabase()
    from datetime import timedelta

    try:
        # ======================================================================
        # 1. FETCH FROM DATABASE (with fallback for legacy trades)
        # ======================================================================
        query = (
            sb.table("trading_signals")
            .select("*")
            .eq("account_name", account_name)
            .not_.is_("exit_price", "null")
            .not_.is_("pnl_usd", "null")
        )

        # Date range filter
        cutoff_time = None
        if days:
            cutoff_time = datetime.now(timezone.utc) - timedelta(days=days)
            query = query.gte("exit_time", cutoff_time.isoformat())

        query = query.order("exit_time", desc=True)
        db_result = query.execute()

        db_trades_data = list(db_result.data or [])

        # If no trades found by account_name, try broker_profile_id fallback for legacy trades
        if len(db_trades_data) == 0:
            account_query = sb.table("account_strategies").select("broker_profile_id").eq("account_name", account_name).limit(1).execute()
            if account_query.data and account_query.data[0].get("broker_profile_id"):
                broker_profile_id = account_query.data[0]["broker_profile_id"]
                fallback_query = (
                    sb.table("trading_signals")
                    .select("*")
                    .eq("broker_profile_id", broker_profile_id)
                    .is_("account_name", "null")
                    .not_.is_("exit_price", "null")
                    .not_.is_("pnl_usd", "null")
                )
                if cutoff_time:
                    fallback_query = fallback_query.gte("exit_time", cutoff_time.isoformat())
                fallback_query = fallback_query.order("exit_time", desc=True)
                fallback_result = fallback_query.execute()
                db_trades_data.extend(fallback_result.data or [])

        # Transform database trades
        db_trades = []
        db_position_ids = set()  # Track position IDs we have in DB
        db_fingerprints = set()  # Fallback dedup: symbol+exit_minute+rounded_pnl

        for trade in db_trades_data:
            # Calculate R multiple if possible
            r_multiple = None
            if trade.get("realized_r_multiple") is not None:
                r_multiple = float(trade.get("realized_r_multiple"))
            elif trade.get("pnl_usd") and trade.get("entry") and trade.get("sl"):
                risk_pips = abs(float(trade.get("entry")) - float(trade.get("sl")))
                risk_usd = risk_pips * float(trade.get("size", 0.01)) * 100000 * 0.0001
                if risk_usd > 0:
                    r_multiple = float(trade.get("pnl_usd")) / risk_usd

            # Gross profit = net pnl_usd minus commission/swap (matches MetaTrader "Profit" column)
            net_pnl_usd = float(trade.get("pnl_usd", 0))
            commission_val = float(trade.get("commission") or 0)
            swap_val = float(trade.get("swap") or 0)
            gross_pnl_usd = net_pnl_usd - commission_val - swap_val

            trade_dict = {
                "id": trade.get("id"),
                "symbol": trade.get("symbol"),
                "side": trade.get("side"),
                "size": float(trade.get("size", 0)),
                "entry": float(trade.get("entry", 0)),
                "exit": float(trade.get("exit_price", 0)),
                "sl": float(trade.get("sl", 0)) if trade.get("sl") else None,
                "tp": float(trade.get("tp", 0)) if trade.get("tp") else None,
                "pnl_usd": gross_pnl_usd,
                "pnl_percent": float(trade.get("pnl_percent", 0)) if trade.get("pnl_percent") else None,
                "r_multiple": r_multiple,
                "mae": float(trade.get("mae", 0)) if trade.get("mae") else None,
                "mfe": float(trade.get("mfe", 0)) if trade.get("mfe") else None,
                "entry_time": trade.get("entry_time"),
                "exit_time": trade.get("exit_time"),
                "exit_reason": trade.get("exit_reason"),
                "outcome": "win" if gross_pnl_usd >= 0 else "loss",
                "trade_key": trade.get("trade_key"),
                "source": "database",
            }
            db_trades.append(trade_dict)

            # Track broker order ID for deduplication
            if trade.get("broker_order_id"):
                db_position_ids.add(str(trade.get("broker_order_id")))

            # Fallback fingerprint: symbol + exit_time (minute) + rounded pnl
            # Used when broker_order_id is null so MetaAPI dedup still works.
            # Fall back to closed_at if exit_time is null (migration 026 backfills closed_at
            # from exit_time/close_time, so some rows only have closed_at populated).
            exit_t = trade.get("exit_time") or trade.get("closed_at") or ""
            symbol = trade.get("symbol") or ""
            pnl_rounded = round(float(trade.get("pnl_usd") or 0) * 100)
            if exit_t and symbol:
                db_fingerprints.add(f"{symbol}|{exit_t[:16]}|{pnl_rounded}")

        logger.info(f"Fetched {len(db_trades)} trades from database for {account_name}")

        # ======================================================================
        # 2. FETCH FROM METAAPI
        # ======================================================================
        metaapi_trades = []

        # Get account's broker profile
        account_query = (
            sb.table("account_strategies")
            .select("*, broker_profiles(*)")
            .eq("account_name", account_name)
            .eq("is_active", True)
            .limit(1)
        )
        account_result = account_query.execute()

        if account_result.data and len(account_result.data) > 0:
            account = account_result.data[0]
            broker_profile = account.get("broker_profiles")

            if broker_profile and broker_profile.get("meta_api_account_id"):
                try:
                    # Get MetaAPI credentials
                    import os
                    token_env_key = broker_profile.get("meta_api_token_env_key", "META_API_TOKEN")
                    token = os.getenv(token_env_key)
                    meta_account_id = broker_profile.get("meta_api_account_id")

                    if token and meta_account_id:
                        from src.adapters.execution.meta_api_adapter import MetaApiAdapter

                        adapter = MetaApiAdapter(token=token, account_id=meta_account_id, account_name=account_name)

                        # Calculate time range (max 90 days for MetaAPI)
                        lookback_days = min(days or 90, 90)
                        start_time = datetime.now(timezone.utc) - timedelta(days=lookback_days)
                        end_time = datetime.now(timezone.utc)

                        start_str = start_time.isoformat().replace("+00:00", "Z")
                        end_str = end_time.isoformat().replace("+00:00", "Z")

                        # Fetch historical deals
                        deals = adapter.get_historical_deals(start_str, end_str)

                        # Group deals by position ID and convert to closed trades
                        positions_map: Dict[str, List[Dict]] = {}
                        for deal in deals:
                            position_id = str(deal.get("positionId", ""))
                            if not position_id:
                                continue
                            if position_id not in positions_map:
                                positions_map[position_id] = []
                            positions_map[position_id].append(deal)

                        # Process each position
                        for position_id, position_deals in positions_map.items():
                            # Skip if we already have this position in database
                            if position_id in db_position_ids:
                                continue

                            # Sort deals by time
                            position_deals.sort(key=lambda d: d.get("time", ""))

                            # Find entry and exit deals
                            entry_deal = None
                            exit_deal = None

                            for deal in position_deals:
                                entry_type = deal.get("entryType", "")
                                if entry_type in ("DEAL_ENTRY_IN", "DEAL_ENTRY_INOUT"):
                                    entry_deal = deal
                                elif entry_type in ("DEAL_ENTRY_OUT", "DEAL_ENTRY_OUT_BY"):
                                    exit_deal = deal

                            # Only include closed positions
                            if not entry_deal or not exit_deal:
                                continue

                            # Calculate P&L
                            profit = float(exit_deal.get("profit", 0) or 0)
                            swap = float(exit_deal.get("swap", 0) or 0)
                            commission = float(exit_deal.get("commission", 0) or 0)
                            total_pnl = profit + swap + commission
                            # Gross profit = price movement only (matches MetaTrader "Profit" column)
                            gross_pnl = profit

                            # Fallback dedup: skip if fingerprint matches a DB trade
                            # (catches cases where broker_order_id is null in DB)
                            ma_symbol = entry_deal.get("symbol", "")
                            ma_exit_t = (exit_deal.get("time") or "")[:16]
                            ma_pnl_rounded = round(total_pnl * 100)
                            if f"{ma_symbol}|{ma_exit_t}|{ma_pnl_rounded}" in db_fingerprints:
                                logger.debug(f"Skipping MetaAPI position {position_id} — fingerprint matches DB trade")
                                continue

                            # Determine side
                            deal_type = entry_deal.get("type", "")
                            side = "buy" if "BUY" in deal_type else "sell"

                            metaapi_trade = {
                                "id": f"meta_{position_id}",
                                "symbol": entry_deal.get("symbol", ""),
                                "side": side,
                                "size": float(entry_deal.get("volume", 0)),
                                "entry": float(entry_deal.get("price", 0)),
                                "exit": float(exit_deal.get("price", 0)),
                                "sl": None,  # MetaAPI deals don't include SL/TP
                                "tp": None,
                                "pnl_usd": gross_pnl,
                                "pnl_percent": None,
                                "r_multiple": None,
                                "mae": None,
                                "mfe": None,
                                "entry_time": entry_deal.get("time"),
                                "exit_time": exit_deal.get("time"),
                                "exit_reason": "MetaAPI",
                                "outcome": "win" if gross_pnl >= 0 else "loss",
                                "trade_key": position_id,
                                "source": "metaapi",
                            }
                            metaapi_trades.append(metaapi_trade)

                        logger.info(f"Fetched {len(metaapi_trades)} trades from MetaAPI for {account_name}")

                    else:
                        logger.warning(f"MetaAPI credentials not found for {account_name}")

                except Exception as metaapi_err:
                    logger.error(f"Failed to fetch MetaAPI history for {account_name}: {metaapi_err}")
                    # Continue with database trades only

        # ======================================================================
        # 3. MERGE AND FILTER
        # ======================================================================
        all_trades = db_trades + metaapi_trades

        # Apply outcome filter
        if outcome == "win":
            all_trades = [t for t in all_trades if t["pnl_usd"] >= 0]
        elif outcome == "loss":
            all_trades = [t for t in all_trades if t["pnl_usd"] < 0]

        # Sort by exit time (most recent first)
        all_trades.sort(key=lambda t: t.get("exit_time") or "", reverse=True)

        return {
            "trades": all_trades,
            "total": len(all_trades),
            "sources": {
                "database": len(db_trades),
                "metaapi": len(metaapi_trades),
            }
        }

    except Exception as e:
        logger.exception("Failed to fetch trade history for %s", account_name)
        raise HTTPException(500, detail=f"Failed to fetch trade history: {str(e)}")


@router.post("/accounts/{account_name}/journal")
def create_journal_entry(account_name: str, entry: JournalEntryRequest):
    """
    Create a new journal entry for an account.

    Can be linked to a specific trade (signal_id) or a general note.
    """
    sb = _get_supabase()

    try:
        # If signal_id provided, verify it belongs to this account
        if entry.signal_id:
            signal_check = (
                sb.table("trading_signals")
                .select("id")
                .eq("id", entry.signal_id)
                .eq("account_name", account_name)
                .single()
                .execute()
            )
            if not signal_check.data:
                raise HTTPException(404, detail=f"Signal {entry.signal_id} not found for account {account_name}")

        payload = {
            "signal_id": entry.signal_id,
            "note_text": entry.note_text,
            "tags": entry.tags or [],
            "trade_rating": entry.trade_rating,
            "emotional_state": entry.emotional_state,
        }

        result = sb.table("trade_journal").insert(payload).execute()

        return {
            "status": "ok",
            "message": "Journal entry created successfully",
            "entry": result.data[0] if result.data else payload,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to create journal entry for {account_name}: {e}")
        raise HTTPException(500, detail=f"Failed to create journal entry: {str(e)}")


@router.delete("/journal/{journal_id}")
def delete_journal_entry_endpoint(journal_id: int):
    """
    Delete a journal entry by ID.
    """
    sb = _get_supabase()

    try:
        result = sb.table("trade_journal").delete().eq("id", journal_id).execute()

        if not result.data or len(result.data) == 0:
            raise HTTPException(404, detail=f"Journal entry {journal_id} not found")

        return {
            "status": "ok",
            "message": f"Journal entry {journal_id} deleted successfully",
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete journal entry {journal_id}: {e}")
        raise HTTPException(500, detail=f"Failed to delete journal entry: {str(e)}")


# ══════════════════════════════════════════════════════════════════
# HEALTH CHECK & MONITORING
# ══════════════════════════════════════════════════════════════════


@router.get("/health")
def get_health_status():
    """
    Get system health status including background worker status.

    Returns:
        - API status
        - Background sync worker status
        - Last sync info
        - Cache status
    """
    from src.services.background_sync_worker import get_background_worker

    worker = get_background_worker()

    health_data = {
        "api_status": "healthy",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "background_worker": None,
        "metaapi_streaming": None,
    }

    if worker:
        health_data["background_worker"] = worker.get_health_status()
    else:
        health_data["background_worker"] = {
            "worker_status": "disabled",
            "message": "Background sync is disabled (ACCOUNT_SYNC_ENABLED=false)"
        }

    try:
        from src.services.metaapi_streaming_service import get_streaming_status
        health_data["metaapi_streaming"] = get_streaming_status()
    except Exception:
        health_data["metaapi_streaming"] = {"status": "unavailable"}

    return health_data
