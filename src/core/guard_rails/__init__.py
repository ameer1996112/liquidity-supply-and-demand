"""Guard rails: prop (risk), market filter, correlation."""

from src.core.guard_rails.prop_guard import create_risk_guardian_from_settings
from src.core.guard_rails.market_filter import MarketAdapter, create_market_adapter_from_settings
from src.core.guard_rails.correlation import CorrelationManager, create_correlation_manager_from_settings
from src.core.guard_rails.approved_pairs_guard import ApprovedPairsGuard
from src.core.guard_rails.trading_permission_guard import TradingPermissionGuard

__all__ = [
    "ApprovedPairsGuard",
    "TradingPermissionGuard",
    "create_risk_guardian_from_settings",
    "MarketAdapter",
    "create_market_adapter_from_settings",
    "CorrelationManager",
    "create_correlation_manager_from_settings",
]
