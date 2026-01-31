"""
Market Adapter - The Universal Translator for Multi-Asset Position Sizing.

This module converts generic "Risk $X" requests into exact lot sizes for
specific asset classes, handling the nuances of each market.

ASSET CLASSES SUPPORTED:
1. FOREX: Standard pairs (EURUSD, GBPUSD) - 100,000 units/lot
2. FOREX JPY: JPY pairs (USDJPY, EURJPY) - Different pip value calculation
3. GOLD (XAUUSD): 100 oz/lot, $0.01 = 1 pip
4. SILVER (XAGUSD): 5,000 oz/lot
5. INDICES: US30, NAS100, SPX500 - Point value varies by broker
6. CRYPTO: BTC, ETH - Fractional lots (0.001 precision)

FORMULAS:
- Forex: Lot = Risk / (SL_Pips * Pip_Value)
- Indices: Lot = Risk / (SL_Points * Point_Value)
- Crypto: Lot = Risk / (SL_Distance * Contract_Size)

Author: Trinity Engine v2.0
"""

import logging
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, Optional, Tuple

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


# ══════════════════════════════════════════════════════════
# ASSET CLASS DEFINITIONS
# ══════════════════════════════════════════════════════════

class AssetClass(str, Enum):
    """Supported asset classes."""
    FOREX_STANDARD = "forex_standard"   # EURUSD, GBPUSD, AUDUSD, etc.
    FOREX_JPY = "forex_jpy"             # USDJPY, EURJPY, GBPJPY, etc.
    GOLD = "gold"                        # XAUUSD
    SILVER = "silver"                    # XAGUSD
    INDEX_US30 = "index_us30"           # Dow Jones
    INDEX_NAS100 = "index_nas100"       # NASDAQ 100
    INDEX_SPX500 = "index_spx500"       # S&P 500
    CRYPTO_BTC = "crypto_btc"           # Bitcoin
    CRYPTO_ETH = "crypto_eth"           # Ethereum
    UNKNOWN = "unknown"


@dataclass
class AssetSpecs:
    """Specifications for an asset class."""
    contract_size: float           # Units per 1.0 lot
    pip_size: float               # Minimum price movement that counts as 1 pip
    pip_value_per_lot: float      # Value in USD of 1 pip for 1.0 lot
    min_lot_size: float           # Minimum tradeable lot size
    lot_precision: int            # Decimal places for lot size (2 = 0.01)
    point_value: Optional[float] = None  # For indices: value per point


# ══════════════════════════════════════════════════════════
# ASSET SPECIFICATIONS DATABASE
# ══════════════════════════════════════════════════════════

ASSET_SPECS: Dict[AssetClass, AssetSpecs] = {
    # FOREX - Standard pairs (USD quote)
    # 1 pip = 0.0001, 1 lot = 100,000 units, pip value = $10/pip
    AssetClass.FOREX_STANDARD: AssetSpecs(
        contract_size=100_000,
        pip_size=0.0001,
        pip_value_per_lot=10.0,
        min_lot_size=0.01,
        lot_precision=2,
    ),

    # FOREX - JPY pairs
    # 1 pip = 0.01, pip value depends on USDJPY rate
    AssetClass.FOREX_JPY: AssetSpecs(
        contract_size=100_000,
        pip_size=0.01,
        pip_value_per_lot=6.67,  # Approximate at USDJPY=150
        min_lot_size=0.01,
        lot_precision=2,
    ),

    # GOLD (XAUUSD)
    # 1 lot = 100 oz, 1 pip = $0.01, pip value = $1.00/pip per lot
    # Example: SL = 456 pips ($4.56), Risk $50 -> Lot = 50 / (456 * 1) = 0.11
    AssetClass.GOLD: AssetSpecs(
        contract_size=100,
        pip_size=0.01,
        pip_value_per_lot=1.0,
        min_lot_size=0.01,
        lot_precision=2,
    ),

    # SILVER (XAGUSD)
    # 1 lot = 5,000 oz, 1 pip = $0.001
    AssetClass.SILVER: AssetSpecs(
        contract_size=5_000,
        pip_size=0.001,
        pip_value_per_lot=5.0,
        min_lot_size=0.01,
        lot_precision=2,
    ),

    # US30 (Dow Jones)
    # Point value varies: $1, $5, or $50 depending on broker
    # Most common: $1 per point per contract
    AssetClass.INDEX_US30: AssetSpecs(
        contract_size=1,
        pip_size=1.0,       # 1 point
        pip_value_per_lot=1.0,  # $1 per point (adjust per broker)
        min_lot_size=0.1,
        lot_precision=1,
        point_value=1.0,
    ),

    # NAS100 (NASDAQ 100)
    # Point value: typically $1 per point per contract
    AssetClass.INDEX_NAS100: AssetSpecs(
        contract_size=1,
        pip_size=1.0,       # 1 point
        pip_value_per_lot=1.0,
        min_lot_size=0.1,
        lot_precision=1,
        point_value=1.0,
    ),

    # SPX500 (S&P 500)
    # Point value: typically $1 per point per contract
    AssetClass.INDEX_SPX500: AssetSpecs(
        contract_size=1,
        pip_size=0.1,       # 0.1 point precision
        pip_value_per_lot=1.0,
        min_lot_size=0.1,
        lot_precision=1,
        point_value=1.0,
    ),

    # Bitcoin (BTCUSD)
    # 1 lot = 1 BTC, high precision (0.001 lots)
    AssetClass.CRYPTO_BTC: AssetSpecs(
        contract_size=1,
        pip_size=1.0,       # $1 movement
        pip_value_per_lot=1.0,
        min_lot_size=0.001,
        lot_precision=3,
    ),

    # Ethereum (ETHUSD)
    # 1 lot = 1 ETH, high precision
    AssetClass.CRYPTO_ETH: AssetSpecs(
        contract_size=1,
        pip_size=0.01,
        pip_value_per_lot=0.01,
        min_lot_size=0.01,
        lot_precision=2,
    ),

    # Unknown/Default
    AssetClass.UNKNOWN: AssetSpecs(
        contract_size=100_000,
        pip_size=0.0001,
        pip_value_per_lot=10.0,
        min_lot_size=0.01,
        lot_precision=2,
    ),
}


# ══════════════════════════════════════════════════════════
# SYMBOL MAPPING
# ══════════════════════════════════════════════════════════

def detect_asset_class(symbol: str) -> AssetClass:
    """
    Detect asset class from symbol name.

    Args:
        symbol: Trading symbol (e.g., "EURUSD", "XAUUSD", "US30")

    Returns:
        AssetClass enum value
    """
    symbol_upper = symbol.upper().replace(".", "").replace("/", "")

    # Gold
    if any(x in symbol_upper for x in ["XAU", "GOLD"]):
        return AssetClass.GOLD

    # Silver
    if any(x in symbol_upper for x in ["XAG", "SILVER"]):
        return AssetClass.SILVER

    # Bitcoin
    if "BTC" in symbol_upper:
        return AssetClass.CRYPTO_BTC

    # Ethereum
    if "ETH" in symbol_upper:
        return AssetClass.CRYPTO_ETH

    # US30 / Dow Jones
    if any(x in symbol_upper for x in ["US30", "DJ30", "DOW", "DJI"]):
        return AssetClass.INDEX_US30

    # NASDAQ 100
    if any(x in symbol_upper for x in ["NAS100", "NDX", "USTEC", "US100"]):
        return AssetClass.INDEX_NAS100

    # S&P 500
    if any(x in symbol_upper for x in ["SPX", "SP500", "US500", "SPY"]):
        return AssetClass.INDEX_SPX500

    # JPY pairs
    if "JPY" in symbol_upper:
        return AssetClass.FOREX_JPY

    # Standard Forex (assume if not matched above)
    if len(symbol_upper) == 6 and symbol_upper.isalpha():
        return AssetClass.FOREX_STANDARD

    # Forex with suffix (EURUSD.pro, etc.)
    forex_pairs = ["EUR", "USD", "GBP", "AUD", "NZD", "CAD", "CHF"]
    if any(p in symbol_upper for p in forex_pairs):
        return AssetClass.FOREX_STANDARD

    return AssetClass.UNKNOWN


class LotSizeResult(BaseModel):
    """Result of lot size calculation."""
    lots: float = Field(description="Calculated lot size")
    lots_rounded: float = Field(description="Lot size rounded to broker precision")
    risk_usd: float = Field(description="Actual risk in USD at this lot size")
    asset_class: str = Field(description="Detected asset class")
    pip_value: float = Field(description="Pip value per lot")
    sl_pips: float = Field(description="Stop loss in pips")
    calculation_details: Dict[str, Any] = Field(
        default_factory=dict, description="Full calculation breakdown"
    )


class MarketAdapter:
    """
    The Universal Translator - Converts risk to exact lot sizes.

    Handles the complexity of multi-asset position sizing, ensuring
    precise execution across all supported markets.

    Usage:
        adapter = MarketAdapter()

        result = adapter.calculate_lot_size(
            symbol="XAUUSD",
            entry_price=2650.50,
            stop_loss=2646.00,
            risk_usd=50.0,
        )

        print(f"Trade {result.lots_rounded} lots (risk ${result.risk_usd})")
    """

    def __init__(
        self,
        usdjpy_rate: float = 150.0,
        index_point_values: Optional[Dict[str, float]] = None,
    ):
        """
        Initialize Market Adapter.

        Args:
            usdjpy_rate: Current USDJPY rate for JPY pair calculations
            index_point_values: Override point values for indices (broker-specific)
        """
        self.usdjpy_rate = usdjpy_rate
        self.index_point_values = index_point_values or {}

        logger.info(f"MarketAdapter initialized: USDJPY={usdjpy_rate}")

    def get_asset_specs(self, symbol: str) -> Tuple[AssetClass, AssetSpecs]:
        """
        Get asset specifications for a symbol.

        Args:
            symbol: Trading symbol

        Returns:
            Tuple of (AssetClass, AssetSpecs)
        """
        asset_class = detect_asset_class(symbol)
        specs = ASSET_SPECS.get(asset_class, ASSET_SPECS[AssetClass.UNKNOWN])

        # Apply broker-specific point value overrides for indices
        if asset_class in (AssetClass.INDEX_US30, AssetClass.INDEX_NAS100, AssetClass.INDEX_SPX500):
            symbol_upper = symbol.upper()
            if symbol_upper in self.index_point_values:
                specs = AssetSpecs(
                    contract_size=specs.contract_size,
                    pip_size=specs.pip_size,
                    pip_value_per_lot=self.index_point_values[symbol_upper],
                    min_lot_size=specs.min_lot_size,
                    lot_precision=specs.lot_precision,
                    point_value=self.index_point_values[symbol_upper],
                )

        return asset_class, specs

    def price_to_pips(self, symbol: str, price_distance: float) -> float:
        """
        Convert price distance to pips for a symbol.

        Args:
            symbol: Trading symbol
            price_distance: Absolute price difference

        Returns:
            Distance in pips
        """
        _, specs = self.get_asset_specs(symbol)
        return price_distance / specs.pip_size

    def pips_to_price(self, symbol: str, pips: float) -> float:
        """
        Convert pips to price distance for a symbol.

        Args:
            symbol: Trading symbol
            pips: Distance in pips

        Returns:
            Price distance
        """
        _, specs = self.get_asset_specs(symbol)
        return pips * specs.pip_size

    def get_pip_value(self, symbol: str, lot_size: float = 1.0) -> float:
        """
        Get pip value in USD for a position.

        Args:
            symbol: Trading symbol
            lot_size: Position size in lots

        Returns:
            Pip value in USD
        """
        asset_class, specs = self.get_asset_specs(symbol)

        pip_value = specs.pip_value_per_lot * lot_size

        # Adjust for JPY pairs using current USDJPY rate
        if asset_class == AssetClass.FOREX_JPY:
            # Pip value = (0.01 * lot_size * 100,000) / USDJPY
            pip_value = (specs.pip_size * lot_size * specs.contract_size) / self.usdjpy_rate

        return pip_value

    def calculate_lot_size(
        self,
        symbol: str,
        entry_price: float,
        stop_loss: float,
        risk_usd: float,
        max_lots: Optional[float] = None,
    ) -> LotSizeResult:
        """
        Calculate exact lot size for a trade based on risk.

        This is the core function that converts "Risk $X" into exact lots.

        Formula: Lot = Risk / (SL_Pips * Pip_Value_Per_Lot)

        Args:
            symbol: Trading symbol
            entry_price: Entry price
            stop_loss: Stop loss price
            risk_usd: Maximum risk in USD
            max_lots: Maximum lot size cap (optional)

        Returns:
            LotSizeResult with calculated lot size and details
        """
        asset_class, specs = self.get_asset_specs(symbol)

        # Calculate stop loss distance in pips
        sl_distance = abs(entry_price - stop_loss)
        sl_pips = sl_distance / specs.pip_size

        # Minimum 1 pip to prevent division issues
        sl_pips = max(sl_pips, 1.0)

        # Get pip value per lot (adjust for JPY pairs)
        pip_value_per_lot = specs.pip_value_per_lot
        if asset_class == AssetClass.FOREX_JPY:
            pip_value_per_lot = (specs.pip_size * specs.contract_size) / self.usdjpy_rate

        # Calculate lot size: Lot = Risk / (SL_Pips * Pip_Value)
        lots = risk_usd / (sl_pips * pip_value_per_lot)

        # Apply max lots cap if specified
        if max_lots is not None:
            lots = min(lots, max_lots)

        # Apply minimum lot size
        lots = max(lots, specs.min_lot_size)

        # Round to broker precision
        precision_multiplier = 10 ** specs.lot_precision
        lots_rounded = round(lots * precision_multiplier) / precision_multiplier

        # Ensure at least minimum after rounding
        lots_rounded = max(lots_rounded, specs.min_lot_size)

        # Calculate actual risk at rounded lot size
        actual_risk = sl_pips * pip_value_per_lot * lots_rounded

        # Build calculation details
        details = {
            "symbol": symbol,
            "entry_price": entry_price,
            "stop_loss": stop_loss,
            "sl_distance": sl_distance,
            "sl_pips": sl_pips,
            "pip_size": specs.pip_size,
            "pip_value_per_lot": pip_value_per_lot,
            "contract_size": specs.contract_size,
            "lot_precision": specs.lot_precision,
            "min_lot_size": specs.min_lot_size,
            "requested_risk_usd": risk_usd,
            "actual_risk_usd": actual_risk,
            "risk_variance_pct": abs(actual_risk - risk_usd) / risk_usd * 100 if risk_usd > 0 else 0,
        }

        logger.info(
            f"MarketAdapter: {symbol} ({asset_class.value}) -> "
            f"{lots_rounded} lots (SL: {sl_pips:.1f} pips, Risk: ${actual_risk:.2f})"
        )

        return LotSizeResult(
            lots=lots,
            lots_rounded=lots_rounded,
            risk_usd=actual_risk,
            asset_class=asset_class.value,
            pip_value=pip_value_per_lot,
            sl_pips=sl_pips,
            calculation_details=details,
        )

    def validate_lot_size(
        self,
        symbol: str,
        requested_lots: float,
        entry_price: float,
        stop_loss: float,
        risk_usd: float,
        variance_threshold: float = 0.10,  # 10% variance allowed
    ) -> Tuple[bool, Optional[str], Optional[float]]:
        """
        Validate if requested lot size matches expected lot size for given risk.

        Used to catch fat-finger errors and calculation bugs.

        Args:
            symbol: Trading symbol
            requested_lots: Lot size from signal
            entry_price: Entry price
            stop_loss: Stop loss price
            risk_usd: Expected risk in USD
            variance_threshold: Maximum allowed variance (0.10 = 10%)

        Returns:
            Tuple of (is_valid, error_message, calculated_lots)
        """
        result = self.calculate_lot_size(symbol, entry_price, stop_loss, risk_usd)

        variance = abs(requested_lots - result.lots_rounded) / result.lots_rounded
        if variance > variance_threshold:
            return (
                False,
                f"Lot size mismatch: requested {requested_lots:.3f} vs calculated {result.lots_rounded:.3f} "
                f"({variance*100:.1f}% variance > {variance_threshold*100}% threshold)",
                result.lots_rounded,
            )

        return True, None, result.lots_rounded

    def get_supported_symbols_info(self) -> Dict[str, Dict[str, Any]]:
        """
        Get information about supported symbol types.

        Returns:
            Dictionary of asset classes with their specifications
        """
        return {
            asset_class.value: {
                "contract_size": specs.contract_size,
                "pip_size": specs.pip_size,
                "pip_value_per_lot": specs.pip_value_per_lot,
                "min_lot_size": specs.min_lot_size,
                "lot_precision": specs.lot_precision,
            }
            for asset_class, specs in ASSET_SPECS.items()
        }


# ══════════════════════════════════════════════════════════
# FACTORY FUNCTION
# ══════════════════════════════════════════════════════════


def create_market_adapter_from_settings() -> MarketAdapter:
    """
    Factory function to create MarketAdapter from config settings.

    Returns:
        MarketAdapter instance configured from environment
    """
    from backend.config import get_settings

    settings = get_settings()

    # Get broker-specific settings (with fallbacks)
    usdjpy_rate = getattr(settings, "usdjpy_rate", 150.0)

    # Index point values can be overridden per broker
    index_point_values = {}
    if hasattr(settings, "us30_point_value"):
        index_point_values["US30"] = settings.us30_point_value
    if hasattr(settings, "nas100_point_value"):
        index_point_values["NAS100"] = settings.nas100_point_value

    return MarketAdapter(
        usdjpy_rate=usdjpy_rate,
        index_point_values=index_point_values,
    )
