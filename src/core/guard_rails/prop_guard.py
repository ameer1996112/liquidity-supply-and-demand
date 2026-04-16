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

    # Intraday drawdown scaling — reduce size (not kill) when loss hits thresholds
    # Uses existing drawdown_threshold_1/2 + risk_reduction_1/2 settings
    if daily_pnl < 0 and getattr(s, "enable_risk_scaling", True):
        th2 = getattr(s, "drawdown_threshold_2", 0.03)
        th1 = getattr(s, "drawdown_threshold_1", 0.02)
        red2 = getattr(s, "risk_reduction_2", 0.25)
        red1 = getattr(s, "risk_reduction_1", 0.5)
        if daily_loss_pct >= th2:
            return True, red2, f"Drawdown Scale (severe): -{daily_loss_pct:.1%} loss → {red2:.0%} size"
        elif daily_loss_pct >= th1:
            return True, red1, f"Drawdown Scale (moderate): -{daily_loss_pct:.1%} loss → {red1:.0%} size"

    # Profit lock-in scaling — reduce size when daily gains reach thresholds
    # Protects accumulated daily profit from being given back in late-session trades
    if daily_pnl > 0 and getattr(s, "enable_profit_lockdown", True):
        daily_profit_pct = daily_pnl / starting_balance
        th2_p = getattr(s, "profit_lockdown_threshold_2", 0.03)
        th1_p = getattr(s, "profit_lockdown_threshold_1", 0.02)
        red2_p = getattr(s, "profit_lockdown_reduction_2", 0.5)
        red1_p = getattr(s, "profit_lockdown_reduction_1", 0.75)
        if daily_profit_pct >= th2_p:
            return True, red2_p, f"Profit Lock-in (protect gains): +{daily_profit_pct:.1%} today → {red2_p:.0%} size"
        elif daily_profit_pct >= th1_p:
            return True, red1_p, f"Profit Lock-in (build buffer): +{daily_profit_pct:.1%} today → {red1_p:.0%} size"

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


def check_signal_guards(
    payload: dict,
    supabase=None,
    *,
    profile: dict | None = None,
    fail_closed: bool = False,
) -> tuple[bool, str | None]:
    """Phase 13: Prop-firm aware signal guards — RR ratio + consecutive loss check.

    Runs before trade execution. Returns (allowed, rejection_reason).
    - Enforces phase-aware min_rr_ratio (1.5 for evaluation, 0 disabled otherwise)
    - Checks consecutive loss streak via Supabase (if available)

    Args:
        payload: Parsed signal dict (must contain rr_ratio field if checking RR).
        supabase: Optional Supabase client for consecutive loss lookup.
        profile: Optional broker profile to scope account-level checks.
        fail_closed: Block the trade if required dependencies are unavailable.

    Returns:
        (True, None) if all guards pass.
        (False, reason_string) if a guard rejects the signal.
    """
    from config import get_settings

    s = get_settings()
    evaluation_mode = getattr(s, "evaluation_mode", False)
    evaluation_phase = getattr(s, "evaluation_phase", "phase1")

    # ── RR Ratio Guard ────────────────────────────────────────────────────────
    # Phase-aware default: 1.5 during evaluation phases, 0 (disabled) otherwise.
    # Explicit MIN_RR_RATIO env var always wins.
    min_rr = getattr(s, "min_rr_ratio", 0.0)
    if min_rr == 0.0 and evaluation_mode and evaluation_phase in ("phase1", "phase2"):
        min_rr = 1.5  # Default evaluation-phase guard

    rr = payload.get("rr_ratio")
    if min_rr > 0 and rr is not None:
        try:
            if float(rr) < min_rr:
                return False, f"RR ratio {rr:.2f} below phase minimum {min_rr} ({evaluation_phase})"
        except (ValueError, TypeError):
            pass  # Non-numeric rr_ratio — skip silently

    # ── Consecutive Loss Circuit Breaker ─────────────────────────────────────
    max_consec = getattr(s, "max_consecutive_losses", 3)
    if max_consec > 0:
        if not supabase:
            if fail_closed:
                return False, "Consecutive loss guard unavailable"
            return True, None
        try:
            import datetime as _dt

            query = (
                supabase.table("trading_signals")
                .select("outcome, pnl_usd, exit_time, broker_profile_id, account_name")
                .not_.is_("exit_time", "null")
            )
            if profile and profile.get("id") is not None:
                query = query.eq("broker_profile_id", profile["id"])
            elif profile and profile.get("name"):
                query = query.eq("account_name", profile["name"])

            trades = query.order("exit_time", desc=True).limit(max_consec).execute().data or []
            consecutive = 0
            for trade in trades:
                outcome = str(trade.get("outcome") or "").lower()
                pnl_usd = float(trade.get("pnl_usd") or 0.0)
                is_loss = outcome == "loss" or (not outcome and pnl_usd < 0)
                if is_loss:
                    consecutive += 1
                else:
                    break

            if consecutive >= max_consec and trades:
                pause_hours = float(getattr(s, "consec_loss_pause_hours", 4.0))
                last_exit_str = trades[0].get("exit_time")
                if last_exit_str:
                    try:
                        last_exit = _dt.datetime.fromisoformat(
                            str(last_exit_str).replace("Z", "+00:00")
                        )
                        elapsed = (_dt.datetime.now(_dt.timezone.utc) - last_exit).total_seconds() / 3600
                        if elapsed < pause_hours:
                            remaining = pause_hours - elapsed
                            return False, (
                                f"Circuit breaker: {max_consec} consecutive losses — "
                                f"paused {remaining:.1f}h remaining (resets after {pause_hours}h)"
                            )
                    except Exception:
                        if fail_closed:
                            return False, "Consecutive loss guard could not parse exit_time"
        except Exception:
            if fail_closed:
                return False, "Consecutive loss guard query failed"

    return True, None


__all__ = [
    "RiskGuardian",
    "RiskCheckResult",
    "RiskRejectionReason",
    "TradeRiskParams",
    "calculate_max_position_size",
    "create_risk_guardian_from_settings",
    "check_safety",
    "check_signal_guards",
]
