"""Prop firm risk guard - re-exports risk engine with settings integration."""

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

__all__ = [
    "RiskGuardian",
    "RiskCheckResult",
    "RiskRejectionReason",
    "TradeRiskParams",
    "calculate_max_position_size",
    "create_risk_guardian_from_settings",
]
