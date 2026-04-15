"""
Risk Monitor API - multi-account read-only monitor for guard and risk state.
Aggregates per-account metrics plus a combined summary for the operator UI.
"""

import logging
from datetime import date, datetime, timezone
from typing import Any, List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from config import get_settings
from src.adapters.redis_queue import get_redis
from src.adapters.supabase import get_supabase
from src.core.circuit_breaker import is_metaapi_circuit_open
from src.core.guard_rails.prop_guard import check_safety

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/risk", tags=["risk-monitor"])

DEFAULT_DAILY_LOSS_LIMIT_PCT = 2.0
DEFAULT_DAILY_PROFIT_TARGET_PCT = 5.0
DEFAULT_MAX_TRADES_PER_DAY = 2


class GuardRailStatus(BaseModel):
    name: str
    status: str
    severity: str
    message: str


class SymbolOverride(BaseModel):
    symbol: str
    risk_pct: float
    max_lots: float
    sl_buffer_pips: float
    pip_size: float


class AccountGuardCard(BaseModel):
    account_name: str
    broker_profile_id: Optional[int] = None
    account_type: str
    evaluation_phase: Optional[str] = None
    prop_firm_name: Optional[str] = None
    run_mode: str
    connection_status: Optional[str] = None
    starting_balance_usd: float
    current_equity_usd: float
    daily_pnl_usd: float
    daily_pnl_pct: float
    peak_equity_usd: float
    current_drawdown_pct: float
    max_drawdown_allowed_pct: float
    drawdown_utilization_pct: float
    daily_loss_used_usd: float
    daily_loss_limit_usd: float
    open_positions: int
    max_positions: int
    trades_today: int
    max_trades_today: int
    risk_multiplier: float
    risk_label: str
    effective_risk_pct: float
    base_risk_pct: float
    kill_switch_active: bool
    blocked: bool
    warning_message: Optional[str] = None
    blocked_reason: Optional[str] = None
    guard_rails: list[GuardRailStatus]


class RiskMonitorSummary(BaseModel):
    total_accounts: int
    active_accounts: int
    total_equity_usd: float
    total_starting_balance_usd: float
    total_daily_pnl_usd: float
    total_open_positions: int
    accounts_in_warning: int
    accounts_blocked: int
    global_kill_switch_active: bool


class RiskMonitorResponse(BaseModel):
    summary: RiskMonitorSummary
    accounts: list[AccountGuardCard]
    symbol_overrides: List[SymbolOverride]
    last_updated: str
    data_source: str = "Backend calculation (multi-account guard monitor)"


def _today_start_iso() -> str:
    return datetime.combine(date.today(), datetime.min.time()).isoformat()


def _get_trading_hours_for_display(settings: Any) -> str:
    try:
        sb = get_supabase()
        rows = (
            sb.table("system_config")
            .select("key,value")
            .in_("key", ["pine_trading_start_hour_local", "pine_trading_end_hour_local"])
            .execute()
        )
        kv = {r["key"]: r["value"] for r in (rows.data or [])}
        start = int(kv.get("pine_trading_start_hour_local", str(getattr(settings, "pine_trading_start_hour_local", 6))))
        end = int(kv.get("pine_trading_end_hour_local", str(getattr(settings, "pine_trading_end_hour_local", 22))))
    except Exception:
        start = getattr(settings, "pine_trading_start_hour_local", 6)
        end = getattr(settings, "pine_trading_end_hour_local", 22)
    return f"{start}-{end}"


def _calculate_drawdown(current_equity: float, starting_balance: float) -> tuple[float, float]:
    peak = max(starting_balance, current_equity)
    dd_pct = ((peak - current_equity) / peak * 100) if peak > 0 else 0.0
    return dd_pct, peak


def _get_symbol_overrides(supabase: Any) -> List[SymbolOverride]:
    try:
        resp = supabase.table("symbol_risk_rules").select("*").execute()
        overrides = []
        for row in resp.data or []:
            overrides.append(
                SymbolOverride(
                    symbol=row.get("symbol", ""),
                    risk_pct=float(row.get("risk_pct", row.get("risk_percent", 0)) or 0),
                    max_lots=float(row.get("max_lot_size", 0) or 0),
                    sl_buffer_pips=float(row.get("sl_buffer_pips", row.get("stop_loss_buffer_pips", 0)) or 0),
                    pip_size=float(row.get("pip_size", 0.0001) or 0.0001),
                )
            )
        return overrides
    except Exception as e:
        logger.error("Failed to fetch symbol overrides: %s", e)
        return []


def _load_active_account_rows(supabase: Any) -> list[dict[str, Any]]:
    try:
        strategy_rows = (
            supabase.table("account_strategies")
            .select("account_name,broker_profile_id")
            .eq("is_active", True)
            .execute()
        ).data or []
    except Exception:
        strategy_rows = []

    try:
        profile_rows = (
            supabase.table("broker_profiles")
            .select(
                "id,name,selected_for_trading,is_active,starting_balance,"
                "evaluation_mode,evaluation_phase,prop_firm_name,run_mode,connection_status"
            )
            .eq("is_active", True)
            .eq("selected_for_trading", True)
            .execute()
        ).data or []
    except Exception:
        profile_rows = []

    by_name: dict[str, dict[str, Any]] = {}
    for row in profile_rows:
        name = row.get("name")
        if name:
            by_name[name] = dict(row)

    for row in strategy_rows:
        acct_name = row.get("account_name")
        if not acct_name:
            continue
        merged = by_name.setdefault(acct_name, {"name": acct_name})
        if merged.get("id") is None and row.get("broker_profile_id") is not None:
            merged["id"] = row.get("broker_profile_id")

    return list(by_name.values())


def _scope_query(query: Any, account_name: str, profile_id: Optional[int]) -> Any:
    if profile_id is not None:
        return query.eq("broker_profile_id", profile_id)
    return query.eq("account_name", account_name)


def _get_daily_pnl_for_account(supabase: Any, account_name: str, profile_id: Optional[int]) -> float:
    try:
        query = (
            supabase.table("trading_signals")
            .select("pnl_usd")
            .in_("status", ["CLOSED", "closed"])
            .gte("created_at", _today_start_iso())
        )
        rows = _scope_query(query, account_name, profile_id).execute().data or []
        return sum(float(row.get("pnl_usd") or 0.0) for row in rows)
    except Exception as e:
        logger.warning("Daily PnL lookup failed for %s: %s", account_name, e)
        return 0.0


def _get_open_positions_for_account(supabase: Any, account_name: str, profile_id: Optional[int]) -> int:
    try:
        query = (
            supabase.table("trading_signals")
            .select("id")
            .in_("status", ["active", "executed"])
        )
        rows = _scope_query(query, account_name, profile_id).execute().data or []
        return len(rows)
    except Exception as e:
        logger.warning("Open positions lookup failed for %s: %s", account_name, e)
        return 0


def _get_trades_today_for_account(supabase: Any, account_name: str, profile_id: Optional[int]) -> int:
    try:
        query = (
            supabase.table("trading_signals")
            .select("id")
            .in_("status", ["active", "executed", "closed", "CLOSED", "EXECUTED"])
            .gte("created_at", _today_start_iso())
        )
        rows = _scope_query(query, account_name, profile_id).execute().data or []
        return len(rows)
    except Exception as e:
        logger.warning("Trades today lookup failed for %s: %s", account_name, e)
        return 0


def _get_equity_for_account(supabase: Any, account_name: str, starting_balance: float) -> float:
    try:
        cutoff = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0).isoformat()
        snap = (
            supabase.table("account_status_snapshots")
            .select("balance")
            .eq("account_name", account_name)
            .gte("snapshot_time", cutoff)
            .order("snapshot_time", desc=True)
            .limit(1)
            .execute()
        )
        if snap.data:
            return float(snap.data[0].get("balance") or starting_balance)
    except Exception as e:
        logger.warning("Equity lookup failed for %s: %s", account_name, e)
    return starting_balance


def _is_account_kill_switch_on(account_name: str, settings: Any) -> bool:
    try:
        redis = get_redis()
        account_key = f"trading:kill_switch:{account_name}" if account_name != "default" else "trading:kill_switch"
        return redis.get(account_key) == "1" or bool(getattr(settings, "trading_kill_switch", False))
    except Exception:
        return bool(getattr(settings, "trading_kill_switch", False))


def _build_account_guard_rails(
    *,
    account_name: str,
    run_mode: str,
    kill_switch_active: bool,
    allowed: bool,
    risk_multiplier: float,
    risk_label: str,
    open_positions: int,
    max_positions: int,
    trades_today: int,
    max_trades_today: int,
) -> list[GuardRailStatus]:
    rails: list[GuardRailStatus] = [
        GuardRailStatus(
            name="Kill Switch",
            status="critical" if kill_switch_active else "passed",
            severity="critical" if kill_switch_active else "success",
            message="ON - Trading blocked" if kill_switch_active else "OFF",
        ),
        GuardRailStatus(
            name="PropGuard",
            status="critical" if not allowed else ("warning" if risk_multiplier < 1.0 else "passed"),
            severity="critical" if not allowed else ("warning" if risk_multiplier < 1.0 else "success"),
            message=f"{risk_label} ({risk_multiplier:.1f}x multiplier)",
        ),
        GuardRailStatus(
            name="Correlation Limits",
            status="critical" if open_positions >= max_positions else ("warning" if open_positions == max_positions - 1 else "passed"),
            severity="critical" if open_positions >= max_positions else ("warning" if open_positions == max_positions - 1 else "success"),
            message=f"{open_positions} / {max_positions} positions",
        ),
        GuardRailStatus(
            name="Daily Trade Limit",
            status="critical" if trades_today >= max_trades_today else ("warning" if trades_today == max_trades_today - 1 else "passed"),
            severity="critical" if trades_today >= max_trades_today else ("warning" if trades_today == max_trades_today - 1 else "success"),
            message=f"{trades_today} / {max_trades_today} trades today",
        ),
    ]

    if run_mode.upper() == "LIVE":
        try:
            circuit_open = is_metaapi_circuit_open(account_name=account_name)
            rails.append(
                GuardRailStatus(
                    name="Circuit Breaker",
                    status="critical" if circuit_open else "passed",
                    severity="critical" if circuit_open else "success",
                    message="MetaApi circuit OPEN - calls blocked" if circuit_open else "MetaApi operational",
                )
            )
        except Exception as e:
            logger.warning("Circuit breaker check failed for %s: %s", account_name, e)
            rails.append(
                GuardRailStatus(
                    name="Circuit Breaker",
                    status="unknown",
                    severity="info",
                    message="Status unavailable",
                )
            )
    return rails


def _build_account_guard_card(supabase: Any, settings: Any, profile: dict[str, Any]) -> AccountGuardCard:
    account_name = profile.get("name") or profile.get("account_name") or "Unknown"
    profile_id = profile.get("id")
    starting_balance = float(profile.get("starting_balance") or settings.account_balance)
    daily_pnl = _get_daily_pnl_for_account(supabase, account_name, profile_id)
    current_balance = _get_equity_for_account(supabase, account_name, starting_balance)
    current_equity = current_balance + daily_pnl
    open_positions = _get_open_positions_for_account(supabase, account_name, profile_id)
    trades_today = _get_trades_today_for_account(supabase, account_name, profile_id)
    drawdown_pct, peak_equity = _calculate_drawdown(current_equity, starting_balance)

    allowed, risk_multiplier, risk_label = check_safety(
        current_equity,
        starting_balance,
        daily_pnl,
        account_name=account_name,
    )
    kill_switch_active = _is_account_kill_switch_on(account_name, settings)
    blocked = kill_switch_active or not allowed
    max_dd = float(getattr(settings, "trinity_max_drawdown_pct", 8.0))
    dd_utilization = round((drawdown_pct / max_dd * 100.0), 2) if max_dd > 0 else 0.0
    daily_loss_used = abs(min(0.0, daily_pnl))
    daily_loss_limit = starting_balance * (DEFAULT_DAILY_LOSS_LIMIT_PCT / 100.0)
    max_positions = int(getattr(settings, "trinity_max_positions", 3))
    max_trades_today = DEFAULT_MAX_TRADES_PER_DAY
    run_mode = str(profile.get("run_mode") or settings.run_mode)
    warning_message = None
    if not blocked and trades_today >= max_trades_today - 1:
        warning_message = f"{max_trades_today - trades_today} more trade allowed today" if trades_today < max_trades_today else "Daily trade limit reached"
    elif not blocked and risk_multiplier < 1.0:
        warning_message = risk_label

    return AccountGuardCard(
        account_name=account_name,
        broker_profile_id=profile_id,
        account_type="Evaluation" if profile.get("evaluation_mode") else "Funded",
        evaluation_phase=profile.get("evaluation_phase"),
        prop_firm_name=profile.get("prop_firm_name"),
        run_mode=run_mode,
        connection_status=profile.get("connection_status"),
        starting_balance_usd=round(starting_balance, 2),
        current_equity_usd=round(current_equity, 2),
        daily_pnl_usd=round(daily_pnl, 2),
        daily_pnl_pct=round((daily_pnl / starting_balance * 100.0), 2) if starting_balance > 0 else 0.0,
        peak_equity_usd=round(peak_equity, 2),
        current_drawdown_pct=round(drawdown_pct, 2),
        max_drawdown_allowed_pct=max_dd,
        drawdown_utilization_pct=dd_utilization,
        daily_loss_used_usd=round(daily_loss_used, 2),
        daily_loss_limit_usd=round(daily_loss_limit, 2),
        open_positions=open_positions,
        max_positions=max_positions,
        trades_today=trades_today,
        max_trades_today=max_trades_today,
        risk_multiplier=round(risk_multiplier, 2),
        risk_label=risk_label,
        effective_risk_pct=round(settings.risk_percent * risk_multiplier, 2),
        base_risk_pct=float(settings.risk_percent),
        kill_switch_active=kill_switch_active,
        blocked=blocked,
        warning_message=warning_message,
        blocked_reason=risk_label if blocked else None,
        guard_rails=_build_account_guard_rails(
            account_name=account_name,
            run_mode=run_mode,
            kill_switch_active=kill_switch_active,
            allowed=allowed,
            risk_multiplier=risk_multiplier,
            risk_label=risk_label,
            open_positions=open_positions,
            max_positions=max_positions,
            trades_today=trades_today,
            max_trades_today=max_trades_today,
        ),
    )


def _build_summary(accounts: list[AccountGuardCard], settings: Any) -> RiskMonitorSummary:
    return RiskMonitorSummary(
        total_accounts=len(accounts),
        active_accounts=len(accounts),
        total_equity_usd=round(sum(account.current_equity_usd for account in accounts), 2),
        total_starting_balance_usd=round(sum(account.starting_balance_usd for account in accounts), 2),
        total_daily_pnl_usd=round(sum(account.daily_pnl_usd for account in accounts), 2),
        total_open_positions=sum(account.open_positions for account in accounts),
        accounts_in_warning=sum(1 for account in accounts if account.warning_message and not account.blocked),
        accounts_blocked=sum(1 for account in accounts if account.blocked),
        global_kill_switch_active=bool(getattr(settings, "trading_kill_switch", False)),
    )


@router.get("/monitor", response_model=RiskMonitorResponse)
async def get_risk_monitor() -> RiskMonitorResponse:
    settings = get_settings()
    supabase = get_supabase()

    if not supabase:
        raise HTTPException(status_code=503, detail="Supabase not configured")

    profiles = _load_active_account_rows(supabase)
    accounts = [_build_account_guard_card(supabase, settings, profile) for profile in profiles]

    return RiskMonitorResponse(
        summary=_build_summary(accounts, settings),
        accounts=accounts,
        symbol_overrides=_get_symbol_overrides(supabase),
        last_updated=datetime.now(timezone.utc).isoformat(),
    )
