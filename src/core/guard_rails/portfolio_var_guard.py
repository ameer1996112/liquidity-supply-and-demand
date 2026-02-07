"""
Portfolio VaR Guard

Prevents trades that would push portfolio VaR above configured limits.
"""

import logging
from typing import Dict, List, Optional, Tuple

from src.services.portfolio_analyzer import PortfolioAnalyzer, Position

logger = logging.getLogger(__name__)


class PortfolioVarGuard:
    """
    Guard that checks portfolio VaR before allowing new positions.

    Prevents trades that would exceed maximum portfolio Value-at-Risk limits.
    """

    def __init__(self, portfolio_analyzer: PortfolioAnalyzer):
        """
        Initialize the VaR guard.

        Args:
            portfolio_analyzer: Portfolio analyzer service
        """
        self.analyzer = portfolio_analyzer

    def _signal_to_position(
        self,
        signal: Dict,
        current_price: Optional[float] = None
    ) -> Position:
        """
        Convert a signal dict to a Position object.

        Args:
            signal: Signal dict with symbol, side, entry, size
            current_price: Current market price (defaults to entry if not provided)

        Returns:
            Position object
        """
        symbol = signal.get("symbol", "")
        side = signal.get("side", "long")
        entry = signal.get("entry", 0.0)
        size = signal.get("size", 0.0)

        # Use current_price if provided, otherwise entry
        price = current_price if current_price is not None else entry

        # Calculate notional value (simplified - assumes 1 lot = 100k for forex)
        notional = abs(size) * 100_000 * price

        return Position(
            symbol=symbol,
            side=side,
            entry_price=entry,
            current_price=price,
            size=size,
            pnl_usd=0.0,  # New position, no P&L yet
            notional_value=notional
        )

    def _db_position_to_position(self, db_pos: Dict) -> Position:
        """
        Convert a database position dict to a Position object.

        Args:
            db_pos: Position from database

        Returns:
            Position object
        """
        return Position(
            symbol=db_pos.get("symbol", ""),
            side=db_pos.get("side", "long"),
            entry_price=db_pos.get("entry", 0.0),
            current_price=db_pos.get("current_price", db_pos.get("entry", 0.0)),
            size=db_pos.get("size", 0.0),
            pnl_usd=db_pos.get("pnl", 0.0),
            notional_value=db_pos.get("notional_value", 0.0)
        )

    def check(
        self,
        new_signal: Dict,
        current_positions: List[Dict],
        max_var_usd: float,
        confidence: float = 0.95,
        lookback_days: int = 30
    ) -> Tuple[bool, str]:
        """
        Check if adding a new position would exceed VaR limits.

        Args:
            new_signal: New signal to evaluate
            current_positions: List of current active positions
            max_var_usd: Maximum allowed VaR in USD
            confidence: VaR confidence level (default 0.95)
            lookback_days: Historical lookback period

        Returns:
            (passes_check, reason)
        """
        # Convert current positions to Position objects
        positions = [self._db_position_to_position(pos) for pos in current_positions]

        # Calculate current portfolio VaR
        current_var = self.analyzer.calculate_var(
            positions,
            confidence=confidence,
            lookback_days=lookback_days
        )

        if current_var is None:
            logger.warning("Failed to calculate current VaR, allowing trade")
            return True, ""

        # Add new position
        new_position = self._signal_to_position(new_signal)
        projected_positions = positions + [new_position]

        # Calculate projected VaR with new position
        projected_var = self.analyzer.calculate_var(
            projected_positions,
            confidence=confidence,
            lookback_days=lookback_days
        )

        if projected_var is None:
            logger.warning("Failed to calculate projected VaR, allowing trade")
            return True, ""

        # VaR is negative (potential loss), so check absolute value
        current_var_abs = abs(current_var)
        projected_var_abs = abs(projected_var)

        logger.info(
            f"Portfolio VaR check: current=${current_var_abs:,.0f}, "
            f"projected=${projected_var_abs:,.0f}, limit=${max_var_usd:,.0f}"
        )

        if projected_var_abs > max_var_usd:
            return False, (
                f"Portfolio VaR limit exceeded: "
                f"${projected_var_abs:,.0f} > ${max_var_usd:,.0f} "
                f"(current: ${current_var_abs:,.0f}, delta: ${projected_var_abs - current_var_abs:,.0f})"
            )

        return True, ""

    def get_var_utilization(
        self,
        current_positions: List[Dict],
        max_var_usd: float,
        confidence: float = 0.95,
        lookback_days: int = 30
    ) -> float:
        """
        Calculate current VaR utilization as a percentage.

        Args:
            current_positions: List of current active positions
            max_var_usd: Maximum allowed VaR in USD
            confidence: VaR confidence level
            lookback_days: Historical lookback period

        Returns:
            VaR utilization (0.0 to 1.0+)
        """
        positions = [self._db_position_to_position(pos) for pos in current_positions]

        current_var = self.analyzer.calculate_var(
            positions,
            confidence=confidence,
            lookback_days=lookback_days
        )

        if current_var is None or max_var_usd == 0:
            return 0.0

        utilization = abs(current_var) / max_var_usd

        return utilization

    def suggest_var_capacity(
        self,
        current_positions: List[Dict],
        max_var_usd: float,
        confidence: float = 0.95,
        lookback_days: int = 30
    ) -> float:
        """
        Calculate remaining VaR capacity in USD.

        Args:
            current_positions: List of current active positions
            max_var_usd: Maximum allowed VaR in USD
            confidence: VaR confidence level
            lookback_days: Historical lookback period

        Returns:
            Remaining VaR capacity in USD
        """
        positions = [self._db_position_to_position(pos) for pos in current_positions]

        current_var = self.analyzer.calculate_var(
            positions,
            confidence=confidence,
            lookback_days=lookback_days
        )

        if current_var is None:
            return max_var_usd

        remaining_capacity = max_var_usd - abs(current_var)

        return max(0.0, remaining_capacity)
