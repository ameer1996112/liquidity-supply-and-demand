"""Evaluation API - Track prop firm evaluation progress."""

from datetime import date, datetime, timedelta
from fastapi import APIRouter

from config import get_settings
from src.adapters.supabase import init_supabase

router = APIRouter(prefix="/evaluation", tags=["evaluation"])


@router.get("/stats")
def get_evaluation_stats():
    """Get evaluation progress metrics."""
    from src.adapters import supabase as supabase_module

    s = get_settings()

    if not s.evaluation_mode:
        return {"error": "Evaluation mode not enabled", "evaluation_mode": False}

    # Calculate metrics
    stats = calculate_evaluation_metrics()

    return {
        "evaluation_mode": True,
        "phase": s.evaluation_phase,
        "current_day": stats["current_day"],
        "total_days": stats["total_days"],
        "profit_target": stats["profit_target"],
        "current_profit": stats["current_profit"],
        "profit_progress_pct": stats["profit_progress_pct"],
        "max_daily_loss": stats["max_daily_loss"],
        "today_pnl": stats["today_pnl"],
        "daily_loss_buffer": stats["daily_loss_buffer"],
        "max_drawdown_pct": stats["max_drawdown_pct"],
        "current_drawdown_pct": stats["current_drawdown_pct"],
        "min_trading_days": stats["min_trading_days"],
        "actual_trading_days": stats["actual_trading_days"],
        "consistency_pct": stats["consistency_pct"],
        "consistency_target_pct": s.consistency_target_pct,
        "rules_passed": stats["rules_passed"],
        "violations": stats["violations"],
        "can_upgrade": stats["can_upgrade"],
    }


def calculate_evaluation_metrics():
    from src.adapters import supabase as supabase_module

    supabase_module.init_supabase()
    supabase = supabase_module.supabase
    s = get_settings()

    # Determine phase rules
    if s.evaluation_phase == "phase1":
        profit_target = s.phase1_profit_target
        max_daily_loss = s.phase1_max_daily_loss
        max_dd_pct = s.phase1_max_drawdown_pct
        min_days = s.phase1_min_trading_days
        total_days = 30
    elif s.evaluation_phase == "phase2":
        profit_target = s.phase2_profit_target
        max_daily_loss = s.phase2_max_daily_loss
        max_dd_pct = s.phase2_max_drawdown_pct
        min_days = s.phase2_min_trading_days
        total_days = 60
    else:  # funded
        profit_target = 0  # No target for funded
        max_daily_loss = s.funded_max_daily_loss
        max_dd_pct = s.funded_max_drawdown_pct
        min_days = 0
        total_days = 365

    # Calculate current day
    start = datetime.fromisoformat(s.evaluation_start_date).date()
    current_day = (date.today() - start).days + 1

    # Get all closed trades since evaluation start
    resp = (
        supabase.table("trading_signals")
        .select("*")
        .eq("status", "closed")
        .eq("run_mode", "LIVE")  # Only count LIVE trades for evaluation
        .gte("created_at", s.evaluation_start_date)
        .order("created_at", desc=False)
        .execute()
    )
    trades = resp.data or []

    # Helper to get PnL from trade
    def get_pnl(t):
        pnl = t.get("pnl_usd") or t.get("pnl")
        if pnl is not None:
            return float(pnl)
        # Fallback: calculate from entry/exit
        entry = t.get("entry") or t.get("price")
        exit_price = t.get("exit_price")
        if entry and exit_price and t.get("position_size"):
            side = str(t.get("side", "buy")).lower()
            diff = exit_price - entry if side == "buy" else entry - exit_price
            return diff * t["position_size"]
        return 0.0

    # Calculate total profit
    current_profit = sum(get_pnl(t) for t in trades)

    # Calculate today's PnL
    today_start = datetime.combine(date.today(), datetime.min.time()).isoformat()
    today_trades = [t for t in trades if t["created_at"] >= today_start]
    today_pnl = sum(get_pnl(t) for t in today_trades)

    # Calculate drawdown from peak
    cumulative_pnl = []
    running_sum = s.account_balance
    for t in trades:
        running_sum += get_pnl(t)
        cumulative_pnl.append(running_sum)

    if cumulative_pnl:
        peak = max(cumulative_pnl)
        current = cumulative_pnl[-1]
        current_drawdown_pct = ((peak - current) / peak * 100) if peak > 0 else 0
    else:
        current_drawdown_pct = 0

    # Calculate trading days (days with at least 1 closed trade)
    trading_days_set = set(t["created_at"][:10] for t in trades)
    actual_trading_days = len(trading_days_set)

    # Calculate consistency (% of profitable days)
    daily_pnls = {}
    for t in trades:
        day = t["created_at"][:10]
        daily_pnls[day] = daily_pnls.get(day, 0) + get_pnl(t)

    profitable_days = sum(1 for pnl in daily_pnls.values() if pnl > 0)
    consistency_pct = (profitable_days / len(daily_pnls) * 100) if daily_pnls else 0

    # Check rules
    rules_passed = {
        "profit_target": current_profit >= profit_target
        if s.evaluation_phase != "funded"
        else True,
        "min_trading_days": actual_trading_days >= min_days,
        "max_daily_loss": today_pnl >= -max_daily_loss,
        "max_drawdown": current_drawdown_pct <= max_dd_pct,
        "consistency": consistency_pct >= s.consistency_target_pct,
    }

    violations = []
    if not rules_passed["max_daily_loss"]:
        violations.append(
            {
                "type": "daily_loss",
                "message": f"Daily loss ${abs(today_pnl):.2f} exceeds max ${max_daily_loss}",
            }
        )
    if not rules_passed["max_drawdown"]:
        violations.append(
            {
                "type": "max_drawdown",
                "message": f"Drawdown {current_drawdown_pct:.1f}% exceeds max {max_dd_pct}%",
            }
        )

    can_upgrade = all(rules_passed.values()) and current_day >= min_days

    return {
        "current_day": current_day,
        "total_days": total_days,
        "profit_target": profit_target,
        "current_profit": current_profit,
        "profit_progress_pct": (current_profit / profit_target * 100)
        if profit_target > 0
        else 0,
        "max_daily_loss": max_daily_loss,
        "today_pnl": today_pnl,
        "daily_loss_buffer": max_daily_loss + today_pnl,
        "max_drawdown_pct": max_dd_pct,
        "current_drawdown_pct": current_drawdown_pct,
        "min_trading_days": min_days,
        "actual_trading_days": actual_trading_days,
        "consistency_pct": consistency_pct,
        "rules_passed": rules_passed,
        "violations": violations,
        "can_upgrade": can_upgrade,
    }
