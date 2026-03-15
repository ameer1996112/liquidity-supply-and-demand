"""Prop firm risk guard utilities.

This module wires the pure risk engine to configuration and exposes
a lightweight \"PropGuard\"-style check for dynamic risk scaling.
"""

from src.core.risk_engine import (
    RiskCheckResult,
    RiskGuardian,
    RiskRejectionReason,
    TradeRiskParams,
    calculate_max_position_size,
)


# Lazy factory to avoid circular config import at module load
def create_risk_guardian_from_settings() -> RiskGuardian:
    from config import get_settings

    s = get_settings()
    return RiskGuardian(
        starting_equity=s.account_balance,
        max_daily_loss_pct=getattr(s, "trinity_max_daily_loss_pct", 4.0),
        max_drawdown_pct=getattr(s, "trinity_max_drawdown_pct", 8.0),
        max_risk_per_trade_pct=getattr(s, "trinity_max_risk_per_trade_pct", 1.0),
    )


def check_safety(
    current_equity: float,
    starting_balance: float,
    daily_pnl: float,
    *,
    account_name: str | None = None,
    kill_threshold_override: float | None = None,
    risk_pct_override: float | None = None,
) -> tuple[bool, float, str]:
    """Step-Up Protocol guard (asymmetric compounding + survival mode).

    Args:
        current_equity: Current account equity in USD.
        starting_balance: Reference starting balance in USD.
        daily_pnl: PnL for the current day in USD (negative = loss).
        account_name: Optional account identifier for logging.
        kill_threshold_override: Override daily loss kill threshold (%).
        risk_pct_override: Override base risk percent for multiplier calc.

    Returns:
        (allowed, risk_multiplier, reason)
    """

    from config import get_settings

    s = get_settings()

    if starting_balance <= 0:
        return True, 1.0, "Invalid starting balance"

    # Daily hard stop (kill switch) based on existing Trinity limit
    daily_loss_pct = abs(daily_pnl / starting_balance) if daily_pnl < 0 else 0.0
    kill_threshold = kill_threshold_override or getattr(s, "trinity_max_daily_loss_pct", 4.0)
    if daily_loss_pct >= kill_threshold:
        return False, 0.0, "Kill Switch"

    # If risk mode is not step-up, use linear behaviour
    if getattr(s, "risk_mode", "step_up") != "step_up":
        return True, 1.0, "Linear risk mode"

    # Step-Up zones based on equity curve vs starting balance
    profit_pct = (current_equity - starting_balance) / starting_balance

    base_risk = risk_pct_override or getattr(s, "risk_percent", 1.0)
    survival_risk = getattr(s, "survival_risk", 0.5)
    th1 = getattr(s, "step_up_threshold_1", 0.02)
    r1 = getattr(s, "step_up_risk_1", 1.0)
    th2 = getattr(s, "step_up_threshold_2", 0.05)
    r2 = getattr(s, "step_up_risk_2", 2.0)

    # During prop firm evaluation: cap multiplier at 1.0x.
    # Rationale: in a challenge, being ahead doesn't mean take more risk —
    # it means protect the profit target. One bad 2x trade can breach the daily
    # loss limit and fail the challenge. Aggressive scaling is for funded accounts only.
    evaluation_mode = getattr(s, "evaluation_mode", False)
    evaluation_phase = getattr(s, "evaluation_phase", "phase1")
    in_evaluation = evaluation_mode and evaluation_phase in ("phase1", "phase2")

    if profit_pct < 0:
        # Below starting balance: preserve capital
        return True, survival_risk / max(base_risk, 1e-6), "Survival Mode"
    if profit_pct > th2:
        if in_evaluation:
            # Evaluation: hold at 1x even when ahead — protect profit target
            return True, r1 / max(base_risk, 1e-6), "Normal Buffer (Evaluation: no scale-up)"
        # Funded/live: house money mode — scale up
        return True, r2 / max(base_risk, 1e-6), "Aggressive Kill Zone"
    if profit_pct > th1:
        # Healthy buffer built: normal base risk
        return True, r1 / max(base_risk, 1e-6), "Normal Buffer"
    # 0–2% profit: build buffer with slightly reduced risk
    return True, 0.75, "Building Buffer"


__all__ = [
    "RiskGuardian",
    "RiskCheckResult",
    "RiskRejectionReason",
    "TradeRiskParams",
    "calculate_max_position_size",
    "create_risk_guardian_from_settings",
    "check_safety",
]
