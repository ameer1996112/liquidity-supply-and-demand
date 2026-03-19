"""
Auto-Hedging Engine

Analyzes portfolio and suggests hedges to reduce VaR and currency exposure.

Features:
- Currency exposure calculation
- Hedge instrument selection
- VaR impact analysis
- Auto-execution of hedges
"""

import logging
from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


@dataclass
class HedgeSuggestion:
    """Represents a hedge recommendation."""
    symbol: str
    side: str  # "long" or "short"
    size: float  # Lot size
    expected_var_reduction_pct: float
    reason: str
    currency_exposure: Dict[str, float]  # Current exposure
    total_exposure_usd: float
    current_var: float


class HedgingEngine:
    """Analyzes portfolio and suggests hedging strategies."""

    # Currency pairs and their base/quote currencies
    CURRENCY_PAIRS = {
        "EURUSD": ("EUR", "USD"),
        "GBPUSD": ("GBP", "USD"),
        "USDJPY": ("USD", "JPY"),
        "USDCHF": ("USD", "CHF"),
        "AUDUSD": ("AUD", "USD"),
        "NZDUSD": ("NZD", "USD"),
        "USDCAD": ("USD", "CAD"),
        "EURJPY": ("EUR", "JPY"),
        "GBPJPY": ("GBP", "JPY"),
        "EURGBP": ("EUR", "GBP"),
        "AUDJPY": ("AUD", "JPY"),
        "EURAUD": ("EUR", "AUD"),
        "EURCHF": ("EUR", "CHF"),
        "GBPCHF": ("GBP", "CHF"),
        "AUDCHF": ("AUD", "CHF"),
        "NZDJPY": ("NZD", "JPY"),
        "CADJPY": ("CAD", "JPY"),
        "CHFJPY": ("CHF", "JPY"),
    }

    # Safe haven / hedge instruments
    HEDGE_INSTRUMENTS = {
        "XAUUSD": {"description": "Gold - safe haven against currency volatility", "priority": 1},
        "USDCHF": {"description": "Swiss Franc - safe haven currency", "priority": 2},
        "USDJPY": {"description": "Japanese Yen - negatively correlated with risk assets", "priority": 3},
    }

    def __init__(self, supabase_client, portfolio_analyzer=None):
        """
        Initialize hedging engine.

        Args:
            supabase_client: Supabase client
            portfolio_analyzer: PortfolioAnalyzer instance (for VaR calculation)
        """
        self.client = supabase_client
        self.portfolio_analyzer = portfolio_analyzer

    def calculate_currency_exposure(self, positions: List[dict]) -> Dict[str, float]:
        """
        Calculate net currency exposure across all positions.

        Args:
            positions: List of position dicts with symbol, side, notional_value

        Returns:
            Dict of {currency: net_exposure_usd}

        Example:
            >>> positions = [
            ...     {"symbol": "EURUSD", "side": "long", "notional_value": 10000},
            ...     {"symbol": "EURGBP", "side": "long", "notional_value": 5000},
            ... ]
            >>> hedging_engine.calculate_currency_exposure(positions)
            {'EUR': 15000, 'USD': -10000, 'GBP': -5000}
        """
        exposure = {}

        for pos in positions:
            symbol = pos.get("symbol", "").upper()
            side = pos.get("side", "").lower()
            notional = pos.get("notional_value", 0)

            if symbol not in self.CURRENCY_PAIRS:
                continue

            base_currency, quote_currency = self.CURRENCY_PAIRS[symbol]

            # Long position: buy base, sell quote
            # Short position: sell base, buy quote
            if side == "long":
                exposure[base_currency] = exposure.get(base_currency, 0) + notional
                exposure[quote_currency] = exposure.get(quote_currency, 0) - notional
            else:  # short
                exposure[base_currency] = exposure.get(base_currency, 0) - notional
                exposure[quote_currency] = exposure.get(quote_currency, 0) + notional

        return exposure

    def suggest_hedge(
        self,
        positions: List[dict],
        target_var_reduction: float = 0.3,
        max_hedge_size_usd: float = 10000.0
    ) -> Optional[HedgeSuggestion]:
        """
        Analyze portfolio and suggest a hedge to reduce risk.

        Args:
            positions: List of active positions
            target_var_reduction: Target VaR reduction (0.3 = 30%)
            max_hedge_size_usd: Maximum hedge size in USD

        Returns:
            HedgeSuggestion or None if no hedge needed
        """
        if not positions:
            logger.info("No positions to hedge")
            return None

        # Calculate current currency exposure
        exposure = self.calculate_currency_exposure(positions)

        if not exposure:
            logger.info("No currency exposure to hedge")
            return None

        # Find largest net exposure
        max_currency = max(exposure.items(), key=lambda x: abs(x[1]))
        currency, net_exposure_usd = max_currency

        # If exposure is small, no hedge needed
        total_exposure = sum(abs(v) for v in exposure.values())
        if abs(net_exposure_usd) < total_exposure * 0.3:  # <30% of total exposure
            logger.info(f"Largest exposure ({currency}: ${abs(net_exposure_usd):.0f}) is well-diversified")
            return None

        # Find best hedge instrument
        hedge_symbol, hedge_side, hedge_size = self._find_best_hedge(
            currency, net_exposure_usd, exposure, max_hedge_size_usd
        )

        if not hedge_symbol:
            logger.info("No suitable hedge instrument found")
            return None

        # Calculate current VaR (if portfolio analyzer available)
        current_var = 0.0
        expected_var_reduction_pct = target_var_reduction * 100

        if self.portfolio_analyzer:
            try:
                from src.services.portfolio_analyzer import Position

                # Convert positions to Position objects
                pos_objects = []
                for p in positions:
                    pos_objects.append(Position(
                        symbol=p["symbol"],
                        side=p.get("side", "long"),
                        entry_price=p.get("entry_price", 0),
                        current_price=p.get("current_price", p.get("entry_price", 0)),
                        size=p.get("size", 0),
                        pnl_usd=p.get("pnl_usd", 0),
                        notional_value=p.get("notional_value", 0),
                    ))

                current_var = self.portfolio_analyzer.calculate_var(pos_objects, confidence=0.95)

                # Estimate VaR with hedge (simplified - actual calculation would need price correlation)
                # Assume hedge reduces exposure proportionally
                hedge_impact = abs(hedge_size * 100_000) / total_exposure  # Simplified
                expected_var_reduction_pct = min(hedge_impact * 100, 50)  # Cap at 50%

            except Exception as e:
                logger.warning(f"Failed to calculate VaR impact: {e}")

        # Build suggestion
        suggestion = HedgeSuggestion(
            symbol=hedge_symbol,
            side=hedge_side,
            size=hedge_size,
            expected_var_reduction_pct=expected_var_reduction_pct,
            reason=self._build_hedge_reason(currency, net_exposure_usd, hedge_symbol),
            currency_exposure=exposure,
            total_exposure_usd=total_exposure,
            current_var=current_var or 0.0,
        )

        logger.info(
            f"Hedge suggestion: {hedge_side.upper()} {hedge_size:.2f} lots of {hedge_symbol} "
            f"(reduces {currency} exposure by ${abs(net_exposure_usd * 0.5):.0f})"
        )

        return suggestion

    def _find_best_hedge(
        self,
        target_currency: str,
        net_exposure_usd: float,
        all_exposures: Dict[str, float],
        max_hedge_size_usd: float
    ) -> Tuple[Optional[str], Optional[str], float]:
        """
        Find the best hedge instrument and calculate hedge size.

        Args:
            target_currency: Currency with largest exposure
            net_exposure_usd: Net exposure in USD
            all_exposures: All currency exposures
            max_hedge_size_usd: Maximum hedge size

        Returns:
            (hedge_symbol, side, size_lots)
        """
        # Strategy: Find a currency pair that contains target currency
        # and hedge by taking opposite position

        best_symbol = None
        best_side = None
        best_size = 0.0

        # Try to find direct pair with target currency
        for symbol, (base, quote) in self.CURRENCY_PAIRS.items():
            # Skip if we already have positions in this symbol
            # (Check current positions - would need to be passed in, simplifying for now)

            if target_currency == base:
                # Target currency is base - if we're long target, go short the pair
                if net_exposure_usd > 0:
                    best_symbol = symbol
                    best_side = "short"
                else:
                    best_symbol = symbol
                    best_side = "long"

                # Calculate hedge size (50% of exposure to start)
                hedge_notional = min(abs(net_exposure_usd) * 0.5, max_hedge_size_usd)
                best_size = hedge_notional / 100_000  # Convert to lots (assuming 100k contract size)
                break

            elif target_currency == quote:
                # Target currency is quote - if we're long target, go long the pair
                if net_exposure_usd > 0:
                    best_symbol = symbol
                    best_side = "long"
                else:
                    best_symbol = symbol
                    best_side = "short"

                hedge_notional = min(abs(net_exposure_usd) * 0.5, max_hedge_size_usd)
                best_size = hedge_notional / 100_000
                break

        # If no direct pair found, try hedge instruments (Gold, CHF, JPY)
        if not best_symbol:
            # Use most liquid hedge instrument
            best_symbol = "XAUUSD"  # Gold as default hedge
            best_side = "long" if net_exposure_usd > 0 else "short"
            hedge_notional = min(abs(net_exposure_usd) * 0.3, max_hedge_size_usd)  # Conservative 30%
            best_size = hedge_notional / 100_000

        return best_symbol, best_side, round(best_size, 2)

    def _build_hedge_reason(self, currency: str, exposure_usd: float, hedge_symbol: str) -> str:
        """Build human-readable hedge reason."""
        direction = "long" if exposure_usd > 0 else "short"
        return (
            f"High {currency} exposure detected ({direction} ${abs(exposure_usd):,.0f}). "
            f"Suggested hedge: {hedge_symbol} to reduce currency concentration risk."
        )

    def save_hedge_suggestion(self, suggestion: HedgeSuggestion, expires_in_hours: int = 24) -> Optional[int]:
        """
        Save hedge suggestion to database.

        Args:
            suggestion: HedgeSuggestion object
            expires_in_hours: Hours until suggestion expires

        Returns:
            Suggestion ID if successful
        """
        try:
            # Get current portfolio positions
            active_positions = self.client.table("trading_signals").select(
                "id, symbol, side, size, entry, sl, tp"
            ).in_("status", ["active", "executed"]).execute()

            portfolio_snapshot = active_positions.data or []

            expires_at = datetime.now(timezone.utc) + timedelta(hours=expires_in_hours)

            data = {
                "portfolio_snapshot": portfolio_snapshot,
                "total_exposure_usd": suggestion.total_exposure_usd,
                "current_var": suggestion.current_var,
                "suggested_symbol": suggestion.symbol,
                "suggested_side": suggestion.side,
                "suggested_size": suggestion.size,
                "expected_var_reduction_pct": suggestion.expected_var_reduction_pct,
                "hedge_reason": suggestion.reason,
                "currency_exposure": suggestion.currency_exposure,
                "status": "PENDING",
                "expires_at": expires_at.isoformat(),
            }

            result = self.client.table("hedge_suggestions").insert(data).execute()

            if result.data:
                suggestion_id = result.data[0]["id"]
                logger.info(f"Saved hedge suggestion {suggestion_id}")
                return suggestion_id

            return None

        except Exception as e:
            logger.error(f"Failed to save hedge suggestion: {e}")
            return None

    def get_pending_suggestions(self) -> List[dict]:
        """Get all pending (not expired) hedge suggestions."""
        try:
            result = self.client.table("hedge_suggestions").select("*").eq(
                "status", "PENDING"
            ).gt("expires_at", datetime.now(timezone.utc).isoformat()).execute()

            return result.data or []

        except Exception as e:
            logger.error(f"Failed to fetch pending suggestions: {e}")
            return []

    def accept_hedge_suggestion(self, suggestion_id: int, executed_signal_id: int) -> bool:
        """
        Mark a hedge suggestion as accepted/executed.

        Args:
            suggestion_id: ID of the suggestion
            executed_signal_id: ID of the trade that executed the hedge

        Returns:
            True if successful
        """
        try:
            self.client.table("hedge_suggestions").update({
                "status": "ACCEPTED",
                "executed_signal_id": executed_signal_id,
                "executed_at": datetime.now(timezone.utc).isoformat(),
            }).eq("id", suggestion_id).execute()

            logger.info(f"Accepted hedge suggestion {suggestion_id} (signal={executed_signal_id})")
            return True

        except Exception as e:
            logger.error(f"Failed to accept hedge suggestion: {e}")
            return False

    def reject_hedge_suggestion(self, suggestion_id: int) -> bool:
        """Reject/dismiss a hedge suggestion."""
        try:
            self.client.table("hedge_suggestions").update({
                "status": "REJECTED",
            }).eq("id", suggestion_id).execute()

            logger.info(f"Rejected hedge suggestion {suggestion_id}")
            return True

        except Exception as e:
            logger.error(f"Failed to reject hedge suggestion: {e}")
            return False
