"""
SND_Utils - Helper functions ported from SND_Utils.pine.

No inputs, no strategy calls. All series data passed as parameters.
"""

from __future__ import annotations

import math
from typing import Optional

import numpy as np

# Constants from Pine
FOREX_LOT_SIZE = 100_000.0
GOLD_LOT_SIZE = 100.0
SILVER_LOT_SIZE = 5000.0
CRYPTO_LOT_SIZE = 1.0
USDJPY_FALLBACK = 150.0


def is_na(x: float) -> bool:
    """Pine na() equivalent."""
    return x is None or (isinstance(x, float) and math.isnan(x))


def nz(x: Optional[float], repl: float = 0.0) -> float:
    """Pine nz() - replace na with repl."""
    if is_na(x):
        return repl
    return float(x)


def get_auto_pip_size(ticker: str, mintick: float = 0.01) -> float:
    """Auto-detect pip size based on symbol (from SND_Utils)."""
    t = ticker.upper()
    if "NAS" in t or "US100" in t or "NDX" in t:
        return 1.0
    if "SPX" in t or "US500" in t or "SPY" in t:
        return 1.0
    if "US30" in t or "DJI" in t:
        return 1.0
    if "JPY" in t:
        return 0.01
    if "XAU" in t or "GOLD" in t:
        return 0.01
    if "XAG" in t or "SILVER" in t:
        return 0.01
    if "BTC" in t or "ETH" in t:
        return 1.0
    if mintick >= 0.01:
        return 0.01
    return 0.0001


def get_pip(x: float, pip_size: float) -> float:
    """Convert price to pips."""
    return x / pip_size if pip_size > 0 else 0.0


def is_bullish(c_close: float, c_open: float) -> bool:
    return c_close > c_open


def is_bearish(c_close: float, c_open: float) -> bool:
    return c_close < c_open


def is_strong_bull(c_close: float, c_open: float, c_high: float, c_low: float) -> bool:
    range_size = c_high - c_low
    return c_close > c_open and range_size > 0 and (abs(c_close - c_open) / range_size > 0.5)


def is_strong_bear(c_close: float, c_open: float, c_high: float, c_low: float) -> bool:
    range_size = c_high - c_low
    return c_close < c_open and range_size > 0 and (abs(c_close - c_open) / range_size > 0.5)


def detect_liquidity_sweep(
    current_high: float,
    current_low: float,
    lookback_high: float,
    lookback_low: float,
    is_demand: bool,
) -> bool:
    """True if liquidity sweep occurred."""
    if is_demand:
        return current_low <= lookback_low
    return current_high >= lookback_high


def detect_structure_break(
    current_close: float,
    structure_level: float,
    is_demand: bool,
) -> bool:
    """True if structure was broken."""
    if is_na(current_close) or is_na(structure_level):
        return False
    if is_demand:
        return current_close > structure_level
    return current_close < structure_level


def units_to_lots(units: float, ticker: str) -> float:
    """Convert position size in units to lots."""
    if "XAU" in ticker.upper() or "GOLD" in ticker.upper():
        return units / GOLD_LOT_SIZE
    if "XAG" in ticker.upper() or "SILVER" in ticker.upper():
        return units / SILVER_LOT_SIZE
    if "BTC" in ticker.upper() or "ETH" in ticker.upper():
        return units / CRYPTO_LOT_SIZE
    return units / FOREX_LOT_SIZE


def safe_percent(wins: int, total: int) -> float:
    """Safe percentage (0 if total is 0)."""
    return (wins * 100.0) / total if total > 0 else 0.0
