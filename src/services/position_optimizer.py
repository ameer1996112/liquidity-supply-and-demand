"""
Position Optimizer Service

Implements Kelly Criterion position sizing, sector exposure analysis,
and portfolio optimization algorithms.
"""

import logging
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple
import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class RebalanceAction:
    """Recommended rebalancing action for a position."""
    symbol: str
    action: str  # "reduce", "increase", "close"
    current_size: float
    target_size: float
    reason: str


class PositionOptimizer:
    """Optimizes position sizing and portfolio allocation."""

    # Sector definitions
    SECTORS = {
        "forex_majors": {"EURUSD", "GBPUSD", "USDJPY", "USDCHF", "AUDUSD", "NZDUSD", "USDCAD"},
        "forex_jpy": {"USDJPY", "EURJPY", "GBPJPY", "AUDJPY", "NZDJPY", "CHFJPY", "CADJPY"},
        "forex_eur": {"EURUSD", "EURJPY", "EURGBP", "EURAUD", "EURNZD", "EURCHF", "EURCAD"},
        "forex_gbp": {"GBPUSD", "GBPJPY", "EURGBP", "GBPAUD", "GBPNZD", "GBPCHF", "GBPCAD"},
        "indices_us": {"US30", "NAS100", "SPX500", "US2000"},
        "indices_eu": {"UK100", "GER40", "FRA40", "ESP35", "ITA40"},
        "indices_asia": {"JPN225", "HK50", "AUS200", "CHINA50"},
        "precious_metals": {"XAUUSD", "XAGUSD"},
        "commodities": {"USOIL", "UKOIL", "NATGAS"},
        "crypto": {"BTCUSD", "ETHUSD", "BCHUSD", "LTCUSD"},
    }

    def __init__(self):
        """Initialize the optimizer."""
        pass

    def kelly_fraction(
        self,
        win_rate: float,
        avg_win_r: float,
        avg_loss_r: float = 1.0
    ) -> float:
        """
        Calculate Kelly Criterion optimal position size.

        Formula: f* = (p*b - q) / b
        Where:
        - f* = fraction of capital to risk
        - p = win rate (probability of win)
        - q = 1 - p (probability of loss)
        - b = avg_win / avg_loss (in R multiples)

        Args:
            win_rate: Win rate (0.0 to 1.0)
            avg_win_r: Average win in R multiples
            avg_loss_r: Average loss in R multiples (default 1.0)

        Returns:
            Kelly fraction (0.0 to 1.0)
        """
        if not (0 <= win_rate <= 1):
            logger.warning(f"Invalid win_rate: {win_rate}, must be 0-1")
            return 0.0

        if avg_win_r <= 0 or avg_loss_r <= 0:
            logger.warning("Invalid R values: must be positive")
            return 0.0

        p = win_rate
        q = 1 - p
        b = avg_win_r / avg_loss_r

        # Kelly formula
        kelly_f = (p * b - q) / b

        # Clamp to valid range
        kelly_f = max(0.0, min(kelly_f, 1.0))

        return kelly_f

    def fractional_kelly(
        self,
        win_rate: float,
        avg_win_r: float,
        avg_loss_r: float = 1.0,
        kelly_fraction: float = 0.25
    ) -> float:
        """
        Calculate fractional Kelly (more conservative than full Kelly).

        Args:
            win_rate: Win rate
            avg_win_r: Average win in R
            avg_loss_r: Average loss in R
            kelly_fraction: Fraction of Kelly to use (0.25 = quarter Kelly)

        Returns:
            Fractional Kelly sizing
        """
        full_kelly = self.kelly_fraction(win_rate, avg_win_r, avg_loss_r)
        return full_kelly * kelly_fraction

    def get_symbol_sector(self, symbol: str) -> Optional[str]:
        """
        Get the sector for a symbol.

        Args:
            symbol: Trading symbol

        Returns:
            Sector name, or None if not found
        """
        for sector, symbols in self.SECTORS.items():
            if symbol.upper() in symbols:
                return sector

        return None

    def calculate_sector_exposure(
        self,
        positions: List[Dict],
        total_equity: float
    ) -> Dict[str, Dict[str, float]]:
        """
        Calculate exposure by sector.

        Args:
            positions: List of position dicts with 'symbol' and 'notional_value'
            total_equity: Total account equity

        Returns:
            Dict of {sector: {"exposure_usd": X, "exposure_pct": Y}}
        """
        sector_exposure = {}

        for position in positions:
            symbol = position.get("symbol", "")
            notional = position.get("notional_value", 0.0)

            sector = self.get_symbol_sector(symbol)

            if sector:
                if sector not in sector_exposure:
                    sector_exposure[sector] = {"exposure_usd": 0.0, "exposure_pct": 0.0}

                sector_exposure[sector]["exposure_usd"] += notional

        # Calculate percentages
        if total_equity > 0:
            for sector in sector_exposure:
                exposure_usd = sector_exposure[sector]["exposure_usd"]
                sector_exposure[sector]["exposure_pct"] = (exposure_usd / total_equity) * 100

        return sector_exposure

    def check_sector_limits(
        self,
        positions: List[Dict],
        new_signal: Dict,
        sector_limits: Dict[str, float],
        total_equity: float
    ) -> Tuple[bool, str]:
        """
        Check if adding a new position violates sector limits.

        Args:
            positions: Current active positions
            new_signal: New signal with 'symbol' and 'notional_value'
            sector_limits: Dict of {sector: max_exposure_pct}
            total_equity: Total account equity

        Returns:
            (passes_check, reason)
        """
        symbol = new_signal.get("symbol", "")
        new_notional = new_signal.get("notional_value", 0.0)

        sector = self.get_symbol_sector(symbol)

        if not sector:
            # Symbol not in any sector, allow
            return True, ""

        if sector not in sector_limits:
            # Sector has no limit defined, allow
            return True, ""

        # Calculate current sector exposure
        sector_exposure = self.calculate_sector_exposure(positions, total_equity)

        current_exposure_usd = sector_exposure.get(sector, {}).get("exposure_usd", 0.0)
        projected_exposure_usd = current_exposure_usd + new_notional

        if total_equity == 0:
            return False, f"Cannot calculate sector exposure: equity is zero"

        projected_exposure_pct = (projected_exposure_usd / total_equity) * 100
        limit_pct = sector_limits[sector] * 100

        if projected_exposure_pct > limit_pct:
            return False, (
                f"Sector '{sector}' limit exceeded: "
                f"{projected_exposure_pct:.1f}% > {limit_pct:.1f}% "
                f"(${projected_exposure_usd:,.0f} / ${total_equity:,.0f})"
            )

        return True, ""

    def optimize_position_sizes(
        self,
        signals: List[Dict],
        portfolio: Dict,
        max_var: float
    ) -> Dict[str, float]:
        """
        Optimize position sizes to maximize return subject to VaR constraint.

        This is a placeholder for quadratic programming optimization.
        Full implementation would use scipy.optimize or cvxpy.

        Args:
            signals: List of signals to size
            portfolio: Current portfolio state
            max_var: Maximum portfolio VaR

        Returns:
            Dict of {symbol: optimal_size}
        """
        # TODO: Implement quadratic programming optimization
        # For now, return equal-weighted positions

        logger.warning("optimize_position_sizes not fully implemented, using equal weights")

        equal_weight = 1.0 / len(signals) if signals else 0.0

        return {signal["symbol"]: equal_weight for signal in signals}

    def rebalance_recommendations(
        self,
        portfolio: Dict,
        target_var: float
    ) -> List[RebalanceAction]:
        """
        Generate rebalancing recommendations to hit target VaR.

        Args:
            portfolio: Current portfolio with positions and risk metrics
            target_var: Target portfolio VaR

        Returns:
            List of rebalancing actions
        """
        # TODO: Implement rebalancing logic
        # For now, return empty list

        logger.warning("rebalance_recommendations not fully implemented")

        return []

    def suggest_position_size(
        self,
        base_risk_pct: float,
        win_rate: float,
        avg_win_r: float,
        kelly_fraction: float = 0.25,
        use_kelly: bool = True
    ) -> float:
        """
        Suggest optimal position size combining base risk and Kelly.

        Args:
            base_risk_pct: Base risk per trade (%)
            win_rate: Strategy win rate
            avg_win_r: Average win in R
            kelly_fraction: Fractional Kelly multiplier
            use_kelly: Whether to use Kelly optimization

        Returns:
            Suggested risk percentage
        """
        if not use_kelly:
            return base_risk_pct

        kelly_risk = self.fractional_kelly(win_rate, avg_win_r, 1.0, kelly_fraction) * 100

        # Take minimum of base risk and Kelly (conservative)
        suggested_risk = min(base_risk_pct, kelly_risk)

        logger.info(
            f"Position sizing: base={base_risk_pct:.2f}%, "
            f"Kelly={kelly_risk:.2f}%, suggested={suggested_risk:.2f}%"
        )

        return suggested_risk

    def calculate_notional_value(
        self,
        symbol: str,
        side: str,
        size: float,
        entry_price: float
    ) -> float:
        """
        Calculate notional value of a position.

        Args:
            symbol: Trading symbol
            side: "long" or "short"
            size: Position size in lots
            entry_price: Entry price

        Returns:
            Notional value in USD
        """
        # Standard lot sizes
        LOT_SIZES = {
            "forex": 100_000,  # 1 lot = 100k units
            "metals": 100,  # 1 lot = 100 oz
            "indices": 1,  # 1 lot = 1 contract
            "crypto": 1,  # 1 lot = 1 coin
        }

        # Determine instrument type
        if any(curr in symbol.upper() for curr in ["USD", "EUR", "GBP", "JPY", "CHF", "AUD", "NZD", "CAD"]):
            lot_size = LOT_SIZES["forex"]
        elif "XAU" in symbol.upper() or "XAG" in symbol.upper():
            lot_size = LOT_SIZES["metals"]
        elif any(idx in symbol.upper() for idx in ["US30", "NAS100", "SPX", "UK100", "GER", "FRA", "JPN"]):
            lot_size = LOT_SIZES["indices"]
        elif any(crypto in symbol.upper() for crypto in ["BTC", "ETH", "BCH", "LTC"]):
            lot_size = LOT_SIZES["crypto"]
        else:
            lot_size = 1  # Default

        notional = abs(size) * lot_size * entry_price

        return notional

    def check_portfolio_concentration(
        self,
        positions: List[Dict],
        new_position: Dict,
        max_single_position_pct: float = 0.3
    ) -> Tuple[bool, str]:
        """
        Check if adding a new position creates concentration risk.

        Args:
            positions: Current positions
            new_position: New position to add
            max_single_position_pct: Max single position as % of total exposure

        Returns:
            (passes_check, reason)
        """
        total_exposure = sum(p.get("notional_value", 0.0) for p in positions)
        new_notional = new_position.get("notional_value", 0.0)

        projected_total = total_exposure + new_notional

        if projected_total == 0:
            return True, ""

        new_position_pct = new_notional / projected_total

        if new_position_pct > max_single_position_pct:
            symbol = new_position.get("symbol", "unknown")
            return False, (
                f"Position concentration risk: {symbol} would be "
                f"{new_position_pct * 100:.1f}% of portfolio "
                f"(max {max_single_position_pct * 100:.1f}%)"
            )

        return True, ""
