"""
Numba-compatible utility functions for high-performance backtesting.

All functions are decorated with @njit for JIT compilation.
Only use NumPy dtypes and operations (no Pandas, no Python objects in hot paths).
"""

from numba import njit
import numpy as np


@njit
def is_bullish_numba(close: float, open_: float) -> bool:
    """Check if candle is bullish (close > open)."""
    return close > open_


@njit
def is_bearish_numba(close: float, open_: float) -> bool:
    """Check if candle is bearish (close < open)."""
    return close < open_


@njit
def round_to_tick_numba(price: float, tick_size: float) -> float:
    """Round price to tick size."""
    if tick_size <= 0:
        return price
    return round(price / tick_size) * tick_size


@njit
def apply_slippage_entry_numba(
    close: float,
    is_long: bool,
    slippage_ticks: int,
    tick_size: float
) -> float:
    """
    Apply slippage for entry orders.

    Long entry: close + slippage (buying at ask)
    Short entry: close - slippage (selling at bid)
    """
    slip = slippage_ticks * tick_size
    if is_long:
        return round_to_tick_numba(close + slip, tick_size)
    return round_to_tick_numba(close - slip, tick_size)


@njit
def apply_slippage_exit_numba(
    price: float,
    is_long: bool,
    slippage_ticks: int,
    tick_size: float
) -> float:
    """
    Apply slippage for exit orders.

    Long exit: price - slippage (selling at bid)
    Short exit: price + slippage (buying at ask)
    """
    slip = slippage_ticks * tick_size
    if is_long:
        return round_to_tick_numba(price - slip, tick_size)
    return round_to_tick_numba(price + slip, tick_size)


@njit
def get_tp_ratio_numba(sl_pips: float, is_gold: bool) -> float:
    """
    Calculate TP ratio based on SL distance.

    Gold (XAUUSD): Dynamic TP ratios based on SL size
    Forex: Fixed 2.0 TP ratio
    """
    if is_gold:
        if sl_pips <= 50:
            return 4.5
        elif sl_pips <= 100:
            return 3.0
        elif sl_pips <= 150:
            return 2.5
        elif sl_pips <= 200:
            return 2.0
        return 1.5
    return 2.0


@njit
def calc_position_size_numba(
    entry: float,
    sl: float,
    account_size: float,
    risk_pct: float,
    is_gold: bool
) -> float:
    """
    Calculate position size in units.

    For XAUUSD: 1 unit = 1 oz, $1 per point
    For Forex USD quote: 1 unit = $1 per point

    Returns: Position size in units (not lots)
    """
    risk_usd = account_size * (risk_pct / 100.0)
    distance = abs(entry - sl)

    if distance <= 0:
        return 0.0

    # XAUUSD and Forex USD quote: $1 per point per unit
    return risk_usd / distance


@njit
def units_to_lots_numba(units: float, is_gold: bool) -> float:
    """
    Convert units to lots.

    XAUUSD: 100 units = 1 lot
    Forex: 100,000 units = 1 lot (standard lot)
    """
    if is_gold:
        return units / 100.0
    return units / 100_000.0


@njit
def lots_to_units_numba(lots: float, is_gold: bool) -> float:
    """
    Convert lots to units.

    XAUUSD: 1 lot = 100 units
    Forex: 1 lot = 100,000 units (standard lot)
    """
    if is_gold:
        return lots * 100.0
    return lots * 100_000.0


@njit
def is_htf_candle_open_numba(minute: int) -> bool:
    """
    Check if current minute is HTF candle open (M15 boundaries).

    Valid minutes: 0, 15, 30, 45
    """
    return minute in (0, 15, 30, 45)


@njit
def is_time_dead_zone_numba(minute: int) -> bool:
    """
    Check if current minute is in dead zone (xx:50-xx:00).

    Block entries 10 minutes before hour rollover.
    """
    return minute >= 50


@njit
def is_trading_hours_numba(hour: int, start_hour: int, end_hour: int) -> bool:
    """
    Check if current hour is within trading hours (UTC).

    Handles both normal ranges (7-22) and overnight ranges (22-7).
    """
    if start_hour <= end_hour:
        return start_hour <= hour <= end_hour
    # Overnight range (e.g., 22-7)
    return hour >= start_hour or hour <= end_hour


@njit
def detect_liquidity_sweep_numba(
    current_high: float,
    current_low: float,
    lookback_high: float,
    lookback_low: float,
    is_demand: bool
) -> bool:
    """
    Detect liquidity sweep.

    Demand: Current low sweeps below lookback low (takes liquidity below)
    Supply: Current high sweeps above lookback high (takes liquidity above)
    """
    if is_demand:
        return current_low <= lookback_low
    return current_high >= lookback_high


@njit
def calculate_zone_score_numba(
    is_demand: bool,
    top: float,
    bottom: float,
    leg_candles: int,
    is_liquidity_sweep: bool,
    candles_in_base: int,
    is_accuracy: bool,
    is_uptrend: bool,
    is_downtrend: bool,
    zone_hour: int
) -> float:
    """
    Calculate zone quality score (0-100).

    Scoring components:
    1. Trend alignment: 20 pts
    2. Strength of move: 20 pts
    3. Base quality: 20 pts
    4. Liquidity: 20 pts
    5. Time & freshness: 20 pts
    """
    score = 0.0

    # 1. TREND ALIGNMENT (20 pts)
    if is_demand and is_uptrend:
        score += 20.0
    elif not is_demand and is_downtrend:
        score += 20.0

    # 2. STRENGTH OF MOVE (20 pts)
    if is_accuracy:
        score += 20.0
    elif leg_candles >= 3:
        score += 15.0
    else:
        score += 10.0

    # 3. BASE QUALITY (20 pts)
    zone_size = top - bottom
    if candles_in_base <= 2 and zone_size > 0:
        score += 20.0
    elif candles_in_base <= 4:
        score += 10.0
    else:
        score += 5.0

    # 4. LIQUIDITY (20 pts)
    if is_liquidity_sweep:
        score += 20.0
    else:
        score += 10.0  # Basic liquidity presence

    # 5. TIME & FRESHNESS (20 pts)
    is_london = 7 <= zone_hour <= 10
    is_ny = 13 <= zone_hour <= 16
    if is_london or is_ny:
        score += 10.0
    else:
        score += 5.0
    score += 10.0  # Freshness component

    return min(score, 100.0)


@njit
def get_grade_value_numba(score: float) -> int:
    """
    Convert score (0-100) to grade value (1-6).

    A+: 90-100 → 6
    A:  80-89  → 5
    B+: 70-79  → 4
    B:  60-69  → 3
    C+: 50-59  → 2
    C:  <50    → 1
    """
    if score >= 90:
        return 6
    elif score >= 80:
        return 5
    elif score >= 70:
        return 4
    elif score >= 60:
        return 3
    elif score >= 50:
        return 2
    return 1


@njit
def extract_minute_hour_from_timestamp(timestamp: np.int64) -> tuple:
    """
    Extract minute and hour from Unix timestamp.

    Returns: (minute, hour) as integers
    """
    # Convert timestamp to seconds
    total_seconds = timestamp

    # Calculate hours and minutes
    total_minutes = total_seconds // 60
    hour = (total_minutes // 60) % 24
    minute = total_minutes % 60

    return (int(minute), int(hour))


@njit
def calculate_pnl_numba(
    entry_price: float,
    exit_price: float,
    qty: float,
    is_long: bool,
    commission_pct: float
) -> float:
    """
    Calculate PnL for a trade.

    Long: (exit - entry) * qty
    Short: (entry - exit) * qty
    Apply commission as percentage of notional
    """
    if is_long:
        pnl = (exit_price - entry_price) * qty
    else:
        pnl = (entry_price - exit_price) * qty

    # Apply commission
    pnl *= (1.0 - commission_pct / 100.0)

    return pnl
