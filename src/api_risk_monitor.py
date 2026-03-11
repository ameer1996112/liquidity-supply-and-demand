"""
Risk Monitor API - Read-only endpoint for displaying Pine Script risk state.
Aggregates data from DB, Redis, and settings to show current risk utilization.
"""

import logging
from datetime import date, datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from config import get_settings
from src.adapters.redis_queue import get_redis
from src.adapters.supabase import get_supabase
from src.core.guard_rails.prop_guard import check_safety
from src.core.circuit_breaker import is_metaapi_circuit_open

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/risk", tags=["risk-monitor"])


class DailyRiskStatus(BaseModel):
    loss_used_usd: float
    loss_limit_usd: float
    loss_pct: float
    remaining_usd: float
    profit_target_usd: float
    profit_current_usd: float
    is_profit_target_hit: bool
    is_loss_limit_hit: bool


class PositionLimitsStatus(BaseModel):
    open_positions: int
    max_positions: int
    trades_today: int
    max_trades_today: int
    warning: Optional[str] = None


class DrawdownStatus(BaseModel):
    current_dd_pct: float
    max_dd_allowed_pct: float
    dd_utilization_pct: float
    remaining_dd_pct: float
    peak_equity_usd: float
    current_equity_usd: float


class ActiveSettings(BaseModel):
    risk_per_trade_pct: float
    min_rr_ratio: float
    stop_loss_buffer_pips: float
    trading_hours_utc: str
    max_trades_per_day: int
    dead_zone_block_enabled: bool
    account_balance_usd: float
    pine_min_return_strength: float


class GuardRailStatus(BaseModel):
    name: str
    status: str  # 'passed', 'warning', 'critical'
    severity: str  # 'success', 'warning', 'critical', 'info'
    message: str


class SymbolOverride(BaseModel):
    symbol: str
    risk_pct: float
    max_lots: float
    sl_buffer_pips: float
    pip_size: float


class RiskMonitorResponse(BaseModel):
    daily_risk: DailyRiskStatus
    position_limits: PositionLimitsStatus
    drawdown: DrawdownStatus
    active_settings: ActiveSettings
    guard_rails: List[GuardRailStatus]
    symbol_overrides: List[SymbolOverride]
    last_updated: str
    data_source: str = "Backend calculation (Pine Script does not publish risk state)"


def _get_daily_pnl(supabase) -> float:
    """Calculate today's PnL from closed trades."""
    try:
        today_start = datetime.combine(date.today(), datetime.min.time()).isoformat()
        resp = (
            supabase.table("trading_signals")
            .select("pnl_usd")
            .eq("status", "closed")
            .gte("created_at", today_start)
            .execute()
        )
        return sum(float(t.get("pnl_usd") or 0) for t in (resp.data or []))
    except Exception as e:
        logger.error(f"Failed to calculate daily PnL: {e}")
        return 0.0


def _get_open_positions_count(supabase) -> int:
    """Count active open positions."""
    try:
        resp = (
            supabase.table("trading_signals")
            .select("id")
            .in_("status", ["active", "executed"])
            .execute()
        )
        return len(resp.data or [])
    except Exception as e:
        logger.error(f"Failed to count open positions: {e}")
        return 0


def _get_trades_today_count(supabase) -> int:
    """Count trades executed today."""
    try:
        today_start = datetime.combine(date.today(), datetime.min.time()).isoformat()
        resp = (
            supabase.table("trading_signals")
            .select("id")
            .in_("status", ["active", "executed", "closed"])
            .gte("created_at", today_start)
            .execute()
        )
        return len(resp.data or [])
    except Exception as e:
        logger.error(f"Failed to count trades today: {e}")
        return 0


def _calculate_drawdown(current_equity: float, account_balance: float) -> tuple[float, float]:
    """
    Calculate current drawdown percentage and peak equity.
    For simplicity, use account_balance as peak (can be enhanced with portfolio_snapshots later).
    """
    peak = max(account_balance, current_equity)
    dd_pct = ((current_equity - peak) / peak * 100) if peak > 0 else 0.0
    return dd_pct, peak


def _get_symbol_overrides(supabase) -> List[SymbolOverride]:
    """Fetch symbol-specific risk overrides."""
    try:
        resp = supabase.table("symbol_risk_rules").select("*").execute()
        overrides = []
        for row in resp.data or []:
            overrides.append(SymbolOverride(
                symbol=row.get("symbol", ""),
                risk_pct=float(row.get("risk_pct", 0)),
                max_lots=float(row.get("max_lot_size", 0)),
                sl_buffer_pips=float(row.get("sl_buffer_pips", 0)),
                pip_size=float(row.get("pip_size", 0.0001))
            ))
        return overrides
    except Exception as e:
        logger.error(f"Failed to fetch symbol overrides: {e}")
        return []


@router.get("/monitor", response_model=RiskMonitorResponse)
async def get_risk_monitor():
    """
    Risk Monitor endpoint - aggregates real-time risk state.
    Shows Pine Script risk limits, current utilization, and guard rail status.
    """
    settings = get_settings()
    supabase = get_supabase()

    if not supabase:
        raise HTTPException(status_code=503, detail="Supabase not configured")

    # 1. Calculate daily PnL and loss limits
    daily_pnl = _get_daily_pnl(supabase)
    daily_loss_limit_pct = 2.0  # Pine default (can be read from settings if exposed)
    daily_profit_target_pct = 5.0  # Pine default

    loss_limit_usd = settings.account_balance * (daily_loss_limit_pct / 100.0)
    profit_target_usd = settings.account_balance * (daily_profit_target_pct / 100.0)

    loss_used_usd = abs(min(0, daily_pnl))  # Only negative PnL counts as loss
    loss_pct = (loss_used_usd / loss_limit_usd * 100) if loss_limit_usd > 0 else 0
    remaining_loss_usd = loss_limit_usd - loss_used_usd

    is_loss_limit_hit = loss_used_usd >= loss_limit_usd
    is_profit_target_hit = daily_pnl >= profit_target_usd

    # 2. Position limits
    open_positions = _get_open_positions_count(supabase)
    trades_today = _get_trades_today_count(supabase)
    max_positions = settings.trinity_max_positions
    max_trades_today = 2  # Pine default (Balanced profile)

    warning = None
    if trades_today >= max_trades_today:
        warning = "Daily trade limit reached"
    elif trades_today == max_trades_today - 1:
        warning = f"{max_trades_today - trades_today} more trade allowed today"

    # 3. Drawdown
    current_equity = settings.account_balance + daily_pnl
    dd_pct, peak_equity = _calculate_drawdown(current_equity, settings.account_balance)
    max_dd_allowed_pct = settings.trinity_max_drawdown_pct
    dd_utilization = abs(dd_pct / max_dd_allowed_pct * 100) if max_dd_allowed_pct > 0 else 0
    remaining_dd_pct = max_dd_allowed_pct + dd_pct  # dd_pct is negative

    # 4. Active settings (from .env or DB overrides)
    active_settings = ActiveSettings(
        risk_per_trade_pct=settings.risk_percent,
        min_rr_ratio=settings.min_rr_ratio,
        stop_loss_buffer_pips=1.0,  # Pine default
        trading_hours_utc=f"{settings.pine_trading_start_hour}-{settings.pine_trading_end_hour}",
        max_trades_per_day=max_trades_today,
        dead_zone_block_enabled=settings.pine_block_dead_zone,
        account_balance_usd=settings.account_balance,
        pine_min_return_strength=settings.pine_min_return_strength
    )

    # 5. Guard rails status
    guard_rails: List[GuardRailStatus] = []

    # Kill Switch
    try:
        redis = get_redis()
        kill_switch_on = redis.get("trading:kill_switch") == "1" or settings.trading_kill_switch
        guard_rails.append(GuardRailStatus(
            name="Kill Switch",
            status="critical" if kill_switch_on else "passed",
            severity="critical" if kill_switch_on else "success",
            message="ON - Trading blocked" if kill_switch_on else "OFF"
        ))
    except Exception as e:
        logger.warning(f"Kill switch check failed: {e}")
        guard_rails.append(GuardRailStatus(
            name="Kill Switch",
            status="unknown",
            severity="info",
            message="Status unavailable"
        ))

    # PropGuard
    allowed, risk_multiplier, risk_label = check_safety(current_equity, settings.account_balance, daily_pnl)
    guard_rails.append(GuardRailStatus(
        name="PropGuard",
        status="critical" if not allowed else ("warning" if risk_multiplier < 1.0 else "passed"),
        severity="critical" if not allowed else ("warning" if risk_multiplier < 1.0 else "success"),
        message=f"{risk_label} ({risk_multiplier:.1f}x multiplier)"
    ))

    # Portfolio VaR (if enabled)
    if settings.portfolio_var_enabled:
        try:
            latest_snapshot = (
                supabase.table("portfolio_snapshots")
                .select("var_95_1d, var_limit_usd")
                .order("snapshot_time", desc=True)
                .limit(1)
                .execute()
            )
            if latest_snapshot.data:
                var_current = latest_snapshot.data[0].get("var_95_1d", 0)
                var_limit = latest_snapshot.data[0].get("var_limit_usd", settings.portfolio_max_var_usd)
                var_pct = (var_current / var_limit * 100) if var_limit > 0 else 0

                guard_rails.append(GuardRailStatus(
                    name="Portfolio VaR",
                    status="critical" if var_pct > 100 else ("warning" if var_pct > 80 else "passed"),
                    severity="critical" if var_pct > 100 else ("warning" if var_pct > 80 else "success"),
                    message=f"${var_current:.0f} / ${var_limit:.0f} limit ({var_pct:.0f}%)"
                ))
        except Exception as e:
            logger.warning(f"VaR check failed: {e}")

    # Correlation Limits
    guard_rails.append(GuardRailStatus(
        name="Correlation Limits",
        status="critical" if open_positions >= max_positions else ("warning" if open_positions == max_positions - 1 else "passed"),
        severity="critical" if open_positions >= max_positions else ("warning" if open_positions == max_positions - 1 else "success"),
        message=f"{open_positions} / {max_positions} positions"
    ))

    # Circuit Breaker (LIVE only)
    if settings.run_mode == "LIVE":
        try:
            circuit_open = is_metaapi_circuit_open()
            guard_rails.append(GuardRailStatus(
                name="Circuit Breaker",
                status="critical" if circuit_open else "passed",
                severity="critical" if circuit_open else "success",
                message="MetaApi circuit OPEN - calls blocked" if circuit_open else "MetaApi operational"
            ))
        except Exception as e:
            logger.warning(f"Circuit breaker check failed: {e}")

    # 6. Symbol overrides
    symbol_overrides = _get_symbol_overrides(supabase)

    return RiskMonitorResponse(
        daily_risk=DailyRiskStatus(
            loss_used_usd=loss_used_usd,
            loss_limit_usd=loss_limit_usd,
            loss_pct=loss_pct,
            remaining_usd=remaining_loss_usd,
            profit_target_usd=profit_target_usd,
            profit_current_usd=max(0, daily_pnl),  # Only positive PnL shown as profit
            is_profit_target_hit=is_profit_target_hit,
            is_loss_limit_hit=is_loss_limit_hit
        ),
        position_limits=PositionLimitsStatus(
            open_positions=open_positions,
            max_positions=max_positions,
            trades_today=trades_today,
            max_trades_today=max_trades_today,
            warning=warning
        ),
        drawdown=DrawdownStatus(
            current_dd_pct=dd_pct,
            max_dd_allowed_pct=max_dd_allowed_pct,
            dd_utilization_pct=dd_utilization,
            remaining_dd_pct=remaining_dd_pct,
            peak_equity_usd=peak_equity,
            current_equity_usd=current_equity
        ),
        active_settings=active_settings,
        guard_rails=guard_rails,
        symbol_overrides=symbol_overrides,
        last_updated=datetime.now(timezone.utc).isoformat()
    )
