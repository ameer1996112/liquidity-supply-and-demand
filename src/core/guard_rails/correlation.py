"""
Correlation Guard - The Portfolio Optimizer.

This module prevents over-exposure to correlated positions, protecting
the portfolio from concentrated directional risk.

RULES ENFORCED:
1. EXPOSURE CHECK: Check all active trades in DB
2. CURRENCY CORRELATION: If Long USDJPY exists, REJECT Long USDCHF (double USD exposure)
3. MAX POSITIONS: Maximum 3 open positions total
4. SAME DIRECTION BLOCK: No duplicate direction on same symbol

CORRELATION MATRIX (High Correlation > 0.80):
- USDJPY ↔ USDCHF (USD strength play)
- EURUSD ↔ GBPUSD (Risk-on pairs)
- AUDUSD ↔ NZDUSD (Commodity currencies)
- XAUUSD ↔ XAGUSD (Precious metals)
- US30 ↔ SPX500 ↔ NAS100 (US equity indices)

Author: Trinity Engine v2.0
"""

import logging
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Tuple

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


# ══════════════════════════════════════════════════════════
# CONFIGURATION
# ══════════════════════════════════════════════════════════

DEFAULT_MAX_OPEN_POSITIONS = 3
DEFAULT_MAX_SAME_CURRENCY_EXPOSURE = 2
DEFAULT_MAX_CORRELATION_GROUP_POSITIONS = 1


class CorrelationRejectionReason(str, Enum):
    """Reasons for rejecting a trade based on correlation rules."""
    MAX_POSITIONS_REACHED = "max_positions_reached"
    CURRENCY_OVER_EXPOSURE = "currency_over_exposure"
    CORRELATION_GROUP_LIMIT = "correlation_group_limit"
    DUPLICATE_POSITION = "duplicate_position"
    OPPOSING_HEDGE = "opposing_hedge"


class CorrelationCheckResult(BaseModel):
    """Result of a correlation check."""
    passed: bool = Field(description="Whether the trade passed correlation checks")
    rejection_reason: Optional[CorrelationRejectionReason] = Field(
        default=None, description="Reason for rejection if passed=False"
    )
    rejection_message: Optional[str] = Field(
        default=None, description="Human-readable rejection message"
    )
    exposure_details: Dict[str, Any] = Field(
        default_factory=dict, description="Current exposure details"
    )

    class Config:
        use_enum_values = True


# ══════════════════════════════════════════════════════════
# CURRENCY & CORRELATION DEFINITIONS
# ══════════════════════════════════════════════════════════

# Currency extraction from symbol
def extract_currencies(symbol: str) -> Tuple[Optional[str], Optional[str]]:
    """
    Extract base and quote currencies from a forex symbol.

    Args:
        symbol: Trading symbol (e.g., "EURUSD", "XAUUSD")

    Returns:
        Tuple of (base_currency, quote_currency) or (None, None) if not forex
    """
    symbol_upper = symbol.upper().replace(".", "").replace("/", "")

    # Handle metals
    if "XAU" in symbol_upper or "GOLD" in symbol_upper:
        return "XAU", "USD"
    if "XAG" in symbol_upper or "SILVER" in symbol_upper:
        return "XAG", "USD"

    # Handle crypto
    if "BTC" in symbol_upper:
        return "BTC", "USD"
    if "ETH" in symbol_upper:
        return "ETH", "USD"

    # Handle indices (no currency pair)
    if any(x in symbol_upper for x in ["US30", "NAS", "SPX", "NDX", "DJI"]):
        return None, None

    # Standard forex pairs (6 characters)
    if len(symbol_upper) >= 6:
        base = symbol_upper[:3]
        quote = symbol_upper[3:6]
        if base.isalpha() and quote.isalpha():
            return base, quote

    return None, None


# Correlation groups - positions in the same group are correlated
CORRELATION_GROUPS: Dict[str, Set[str]] = {
    # USD strength plays (highly correlated when USD moves)
    "usd_jpy_chf": {"USDJPY", "USDCHF", "USDCAD"},

    # Risk-on European pairs
    "eur_gbp": {"EURUSD", "GBPUSD", "EURGBP"},

    # Commodity currencies (AUD, NZD, CAD)
    "commodity_fx": {"AUDUSD", "NZDUSD", "AUDNZD", "AUDCAD", "NZDCAD"},

    # Precious metals
    "precious_metals": {"XAUUSD", "XAGUSD", "GOLD", "SILVER"},

    # US equity indices
    "us_indices": {"US30", "NAS100", "SPX500", "NDX", "SPY", "DJI", "USTEC"},

    # JPY crosses (correlated via JPY)
    "jpy_crosses": {"USDJPY", "EURJPY", "GBPJPY", "AUDJPY", "NZDJPY", "CADJPY", "CHFJPY"},

    # CHF crosses
    "chf_crosses": {"USDCHF", "EURCHF", "GBPCHF", "AUDCHF", "NZDCHF", "CADCHF"},
}


def get_correlation_groups(symbol: str) -> List[str]:
    """
    Get all correlation groups a symbol belongs to.

    Args:
        symbol: Trading symbol

    Returns:
        List of correlation group names
    """
    symbol_upper = symbol.upper().replace(".", "").replace("/", "")
    groups = []

    for group_name, symbols in CORRELATION_GROUPS.items():
        if symbol_upper in symbols or any(s in symbol_upper for s in symbols):
            groups.append(group_name)

    return groups


@dataclass
class ActivePosition:
    """Represents an active position in the portfolio."""
    symbol: str
    side: str  # "buy" or "sell"
    size: float
    entry_price: float
    entry_time: datetime
    zone_id: Optional[str] = None
    trade_key: Optional[str] = None


class CorrelationManager:
    """
    The Portfolio Optimizer - Prevents correlated position over-exposure.

    Maintains awareness of active positions and enforces correlation rules
    to protect the portfolio from concentrated directional risk.

    Usage:
        manager = CorrelationManager(max_positions=3)

        # Check before entering a trade
        result = manager.check(
            symbol="USDCHF",
            side="buy",
            active_positions=active_positions_list,
        )

        if not result.passed:
            logger.warning(f"Trade rejected: {result.rejection_message}")
    """

    def __init__(
        self,
        max_positions: int = DEFAULT_MAX_OPEN_POSITIONS,
        max_same_currency_exposure: int = DEFAULT_MAX_SAME_CURRENCY_EXPOSURE,
        max_correlation_group_positions: int = DEFAULT_MAX_CORRELATION_GROUP_POSITIONS,
        allow_hedging: bool = False,
    ):
        """
        Initialize Correlation Manager.

        Args:
            max_positions: Maximum total open positions
            max_same_currency_exposure: Max positions with same base/quote currency
            max_correlation_group_positions: Max positions in same correlation group
            allow_hedging: Allow opposing positions on same symbol
        """
        self.max_positions = max_positions
        self.max_same_currency_exposure = max_same_currency_exposure
        self.max_correlation_group_positions = max_correlation_group_positions
        self.allow_hedging = allow_hedging

        logger.info(
            f"CorrelationManager initialized: max_positions={max_positions}, "
            f"max_currency_exposure={max_same_currency_exposure}, "
            f"max_correlation_group={max_correlation_group_positions}"
        )

    def _count_currency_exposure(
        self,
        currency: str,
        side: str,
        positions: List[ActivePosition],
    ) -> int:
        """
        Count positions with exposure to a currency in the same direction.

        Args:
            currency: Currency code (e.g., "USD", "EUR")
            side: Trade direction ("buy" or "sell")
            positions: List of active positions

        Returns:
            Number of positions with same-direction exposure to currency
        """
        count = 0
        for pos in positions:
            base, quote = extract_currencies(pos.symbol)
            if base is None:
                continue

            # For "buy" - we're long base, short quote
            # For "sell" - we're short base, long quote
            if pos.side == "buy":
                long_currency, short_currency = base, quote
            else:
                long_currency, short_currency = quote, base

            # New trade direction
            if side == "buy":
                new_long, new_short = currency, None
            else:
                new_long, new_short = None, currency

            # Check if adding to same-direction exposure
            if (long_currency == currency and side == "buy") or \
               (short_currency == currency and side == "sell"):
                count += 1

        return count

    def _count_correlation_group_positions(
        self,
        symbol: str,
        side: str,
        positions: List[ActivePosition],
    ) -> Dict[str, int]:
        """
        Count positions in each correlation group for the symbol.

        Args:
            symbol: New symbol to check
            side: Trade direction
            positions: List of active positions

        Returns:
            Dict of group_name -> position count
        """
        # Get groups for the new symbol
        new_symbol_groups = get_correlation_groups(symbol)
        group_counts: Dict[str, int] = {g: 0 for g in new_symbol_groups}

        for pos in positions:
            # Only count same-direction positions
            if pos.side != side:
                continue

            pos_groups = get_correlation_groups(pos.symbol)
            for group in pos_groups:
                if group in group_counts:
                    group_counts[group] += 1

        return group_counts

    def check(
        self,
        symbol: str,
        side: str,
        active_positions: Optional[List[ActivePosition]] = None,
        data: Optional[Dict[str, Any]] = None,
    ) -> CorrelationCheckResult:
        """
        Run correlation checks for a potential new trade.

        Checks performed:
        1. Max positions limit
        2. Duplicate position (same symbol, same direction)
        3. Opposing hedge (same symbol, opposite direction)
        4. Currency over-exposure
        5. Correlation group limits

        Args:
            symbol: Symbol to trade
            side: Trade direction ("buy" or "sell")
            active_positions: List of current open positions
            data: Optional raw trade data dict

        Returns:
            CorrelationCheckResult with pass/fail and details
        """
        positions = active_positions or []
        symbol_upper = symbol.upper()
        side_lower = side.lower()

        exposure_details = {
            "total_positions": len(positions),
            "max_positions": self.max_positions,
            "new_symbol": symbol_upper,
            "new_side": side_lower,
        }

        # ══════════════════════════════════════════════════════════
        # CHECK 1: Max Positions
        # ══════════════════════════════════════════════════════════

        if len(positions) >= self.max_positions:
            return CorrelationCheckResult(
                passed=False,
                rejection_reason=CorrelationRejectionReason.MAX_POSITIONS_REACHED,
                rejection_message=(
                    f"MAX POSITIONS: {len(positions)}/{self.max_positions} positions open. "
                    f"Close existing positions before opening new ones."
                ),
                exposure_details=exposure_details,
            )

        # ══════════════════════════════════════════════════════════
        # CHECK 2: Duplicate Position
        # ══════════════════════════════════════════════════════════

        for pos in positions:
            if pos.symbol.upper() == symbol_upper and pos.side.lower() == side_lower:
                return CorrelationCheckResult(
                    passed=False,
                    rejection_reason=CorrelationRejectionReason.DUPLICATE_POSITION,
                    rejection_message=(
                        f"DUPLICATE: Already have {pos.side.upper()} {pos.symbol} open. "
                        f"Cannot open another {side_lower.upper()} on same symbol."
                    ),
                    exposure_details=exposure_details,
                )

        # ══════════════════════════════════════════════════════════
        # CHECK 3: Opposing Hedge
        # ══════════════════════════════════════════════════════════

        if not self.allow_hedging:
            for pos in positions:
                if pos.symbol.upper() == symbol_upper and pos.side.lower() != side_lower:
                    return CorrelationCheckResult(
                        passed=False,
                        rejection_reason=CorrelationRejectionReason.OPPOSING_HEDGE,
                        rejection_message=(
                            f"HEDGE BLOCKED: Already have {pos.side.upper()} {pos.symbol}. "
                            f"Hedging with opposite direction not allowed."
                        ),
                        exposure_details=exposure_details,
                    )

        # ══════════════════════════════════════════════════════════
        # CHECK 4: Currency Over-Exposure
        # ══════════════════════════════════════════════════════════

        base, quote = extract_currencies(symbol_upper)

        if base and quote:
            # Check base currency exposure
            base_exposure = self._count_currency_exposure(base, side_lower, positions)
            quote_exposure = self._count_currency_exposure(quote, "sell" if side_lower == "buy" else "buy", positions)

            exposure_details["base_currency"] = base
            exposure_details["quote_currency"] = quote
            exposure_details["base_exposure"] = base_exposure
            exposure_details["quote_exposure"] = quote_exposure

            # Check if this trade would exceed currency exposure limit
            if side_lower == "buy":
                # Buying = long base, short quote
                if base_exposure >= self.max_same_currency_exposure:
                    return CorrelationCheckResult(
                        passed=False,
                        rejection_reason=CorrelationRejectionReason.CURRENCY_OVER_EXPOSURE,
                        rejection_message=(
                            f"CURRENCY EXPOSURE: Already have {base_exposure} long {base} positions. "
                            f"Max {self.max_same_currency_exposure} allowed. Would double {base} exposure."
                        ),
                        exposure_details=exposure_details,
                    )
            else:
                # Selling = short base, long quote
                if base_exposure >= self.max_same_currency_exposure:
                    return CorrelationCheckResult(
                        passed=False,
                        rejection_reason=CorrelationRejectionReason.CURRENCY_OVER_EXPOSURE,
                        rejection_message=(
                            f"CURRENCY EXPOSURE: Already have {base_exposure} short {base} positions. "
                            f"Max {self.max_same_currency_exposure} allowed. Would double {base} exposure."
                        ),
                        exposure_details=exposure_details,
                    )

        # ══════════════════════════════════════════════════════════
        # CHECK 5: Correlation Group Limits
        # ══════════════════════════════════════════════════════════

        group_counts = self._count_correlation_group_positions(symbol_upper, side_lower, positions)
        exposure_details["correlation_groups"] = group_counts

        for group_name, count in group_counts.items():
            if count >= self.max_correlation_group_positions:
                return CorrelationCheckResult(
                    passed=False,
                    rejection_reason=CorrelationRejectionReason.CORRELATION_GROUP_LIMIT,
                    rejection_message=(
                        f"CORRELATION LIMIT: {count} positions in '{group_name}' group "
                        f"(max {self.max_correlation_group_positions}). "
                        f"{symbol_upper} is correlated - diversify before adding."
                    ),
                    exposure_details=exposure_details,
                )

        # ══════════════════════════════════════════════════════════
        # ALL CHECKS PASSED
        # ══════════════════════════════════════════════════════════

        logger.info(
            f"CorrelationManager PASSED: {side_lower.upper()} {symbol_upper} "
            f"(positions: {len(positions)}/{self.max_positions})"
        )

        return CorrelationCheckResult(passed=True, exposure_details=exposure_details)

    def get_portfolio_exposure(
        self,
        positions: List[ActivePosition],
    ) -> Dict[str, Any]:
        """
        Get comprehensive portfolio exposure analysis.

        Args:
            positions: List of active positions

        Returns:
            Dictionary with exposure breakdown
        """
        exposure = {
            "total_positions": len(positions),
            "by_symbol": {},
            "by_currency": {"long": {}, "short": {}},
            "by_correlation_group": {},
            "positions": [],
        }

        for pos in positions:
            # By symbol
            if pos.symbol not in exposure["by_symbol"]:
                exposure["by_symbol"][pos.symbol] = []
            exposure["by_symbol"][pos.symbol].append({
                "side": pos.side,
                "size": pos.size,
            })

            # By currency
            base, quote = extract_currencies(pos.symbol)
            if base:
                if pos.side == "buy":
                    exposure["by_currency"]["long"][base] = exposure["by_currency"]["long"].get(base, 0) + 1
                    exposure["by_currency"]["short"][quote] = exposure["by_currency"]["short"].get(quote, 0) + 1
                else:
                    exposure["by_currency"]["short"][base] = exposure["by_currency"]["short"].get(base, 0) + 1
                    exposure["by_currency"]["long"][quote] = exposure["by_currency"]["long"].get(quote, 0) + 1

            # By correlation group
            groups = get_correlation_groups(pos.symbol)
            for group in groups:
                if group not in exposure["by_correlation_group"]:
                    exposure["by_correlation_group"][group] = []
                exposure["by_correlation_group"][group].append({
                    "symbol": pos.symbol,
                    "side": pos.side,
                })

            # Full position details
            exposure["positions"].append({
                "symbol": pos.symbol,
                "side": pos.side,
                "size": pos.size,
                "entry_price": pos.entry_price,
            })

        return exposure

    def check_with_correlation_matrix(
        self,
        symbol: str,
        side: str,
        active_positions: List[ActivePosition],
        correlation_matrix: Optional[Any] = None,
        max_avg_correlation: float = 0.7,
        historical_returns_service: Optional[Any] = None,
        lookback_days: int = 30,
    ) -> CorrelationCheckResult:
        """
        Enhanced correlation check using real correlation matrix.

        This method calculates actual historical correlations instead of
        relying on pre-defined correlation groups.

        Args:
            symbol: Symbol to trade
            side: Trade direction ("buy" or "sell")
            active_positions: List of current open positions
            correlation_matrix: Pre-calculated correlation matrix (optional)
            max_avg_correlation: Maximum allowed average correlation (0.0-1.0)
            historical_returns_service: Service for fetching historical data
            lookback_days: Historical lookback period for correlation

        Returns:
            CorrelationCheckResult with pass/fail and details
        """
        import numpy as np

        if not active_positions:
            return CorrelationCheckResult(passed=True)

        # Only check same-direction positions for correlation
        same_direction_positions = [
            pos for pos in active_positions
            if pos.side.lower() == side.lower()
        ]

        if not same_direction_positions:
            return CorrelationCheckResult(passed=True)

        # Get correlation matrix
        if correlation_matrix is None:
            if historical_returns_service is None:
                # Fallback to standard check if no correlation data available
                logger.warning(
                    "No correlation matrix or historical service provided, "
                    "falling back to standard correlation check"
                )
                return self.check(symbol, side, active_positions)

            # Calculate correlation matrix
            portfolio_symbols = [pos.symbol for pos in same_direction_positions]
            all_symbols = portfolio_symbols + [symbol]

            try:
                corr_matrix = historical_returns_service.get_correlation_matrix(
                    all_symbols,
                    lookback_days
                )

                if corr_matrix is None:
                    logger.warning("Failed to calculate correlation matrix, allowing trade")
                    return CorrelationCheckResult(passed=True)

            except Exception as e:
                logger.error(f"Error calculating correlation matrix: {e}")
                return CorrelationCheckResult(passed=True)
        else:
            corr_matrix = correlation_matrix

        # Calculate average correlation of new symbol with portfolio
        # New symbol is the last one in the matrix
        n_positions = len(same_direction_positions)
        new_symbol_correlations = corr_matrix[:-1, -1]  # Last column, excluding diagonal

        avg_correlation = float(np.mean(new_symbol_correlations))
        max_correlation = float(np.max(new_symbol_correlations))

        exposure_details = {
            "total_positions": len(active_positions),
            "same_direction_positions": n_positions,
            "new_symbol": symbol.upper(),
            "new_side": side.lower(),
            "avg_correlation": avg_correlation,
            "max_correlation": max_correlation,
            "correlation_threshold": max_avg_correlation,
        }

        logger.info(
            f"Correlation matrix check: {symbol} avg_corr={avg_correlation:.2f}, "
            f"max_corr={max_correlation:.2f}, threshold={max_avg_correlation:.2f}"
        )

        if avg_correlation > max_avg_correlation:
            highly_correlated_symbols = []
            for i, pos in enumerate(same_direction_positions):
                if new_symbol_correlations[i] > 0.7:
                    highly_correlated_symbols.append(
                        f"{pos.symbol} ({new_symbol_correlations[i]:.2f})"
                    )

            return CorrelationCheckResult(
                passed=False,
                rejection_reason=CorrelationRejectionReason.CORRELATION_GROUP_LIMIT,
                rejection_message=(
                    f"HIGH CORRELATION: {symbol} has avg correlation of {avg_correlation:.2f} "
                    f"with portfolio (max {max_avg_correlation:.2f}). "
                    f"Highly correlated with: {', '.join(highly_correlated_symbols[:3])}"
                ),
                exposure_details=exposure_details,
            )

        return CorrelationCheckResult(passed=True, exposure_details=exposure_details)


# ══════════════════════════════════════════════════════════
# DATABASE INTEGRATION HELPERS
# ══════════════════════════════════════════════════════════


def get_active_positions_from_db() -> List[ActivePosition]:
    """
    Fetch active positions from Supabase.

    Returns:
        List of ActivePosition objects
    """
    try:
        import src.adapters.supabase as supabase_db

        if not supabase_db.supabase:
            supabase_db.init_supabase()

        # Query active positions
        response = supabase_db.supabase.table("trading_signals").select(
            "symbol, side, size, entry, created_at, zone_id, trade_key"
        ).eq("status", "active").execute()

        positions = []
        for row in response.data:
            positions.append(ActivePosition(
                symbol=row.get("symbol", "UNKNOWN"),
                side=row.get("side", "buy"),
                size=float(row.get("size", 0)),
                entry_price=float(row.get("entry", 0)),
                entry_time=datetime.fromisoformat(row["created_at"]) if row.get("created_at") else datetime.utcnow(),
                zone_id=row.get("zone_id"),
                trade_key=row.get("trade_key"),
            ))

        logger.info(f"Fetched {len(positions)} active positions from DB")
        return positions

    except Exception as e:
        logger.error(f"Failed to fetch active positions: {e}")
        return []


# ══════════════════════════════════════════════════════════
# FACTORY FUNCTION
# ══════════════════════════════════════════════════════════


def create_correlation_manager_from_settings() -> CorrelationManager:
    """
    Factory function to create CorrelationManager from config settings.

    Returns:
        CorrelationManager instance configured from environment
    """
    from config import get_settings

    settings = get_settings()

    # Get Trinity Engine settings (with fallbacks)
    max_positions = getattr(settings, "trinity_max_positions", DEFAULT_MAX_OPEN_POSITIONS)
    max_currency_exposure = getattr(settings, "trinity_max_currency_exposure", DEFAULT_MAX_SAME_CURRENCY_EXPOSURE)
    max_correlation_group = getattr(settings, "trinity_max_correlation_group", DEFAULT_MAX_CORRELATION_GROUP_POSITIONS)
    allow_hedging = getattr(settings, "trinity_allow_hedging", False)

    return CorrelationManager(
        max_positions=max_positions,
        max_same_currency_exposure=max_currency_exposure,
        max_correlation_group_positions=max_correlation_group,
        allow_hedging=allow_hedging,
    )
