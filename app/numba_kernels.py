"""
Numba-compiled kernel functions for high-performance backtesting.

These @njit-decorated functions run in the hot path of the backtest loop.
Week 1: Stub implementations for parity testing
Week 2: Full optimization for 20-50x speedup

All functions use only NumPy dtypes and operations (no Pandas, no Python objects).
"""

from numba import njit
import numpy as np
from app.zone_manager import ZONE_DTYPE
from app.utils_numba import (
    is_bullish_numba,
    is_bearish_numba,
    apply_slippage_entry_numba,
    apply_slippage_exit_numba,
    detect_liquidity_sweep_numba,
    calculate_zone_score_numba,
    calc_position_size_numba,
    get_tp_ratio_numba,
    extract_minute_hour_from_timestamp,
    is_htf_candle_open_numba,
    calculate_pnl_numba,
)


# ========== Main Backtest Loop (Stub for Week 1) ==========

@njit
def run_backtest_numba(
    candles: np.ndarray,
    timestamps: np.ndarray,
    zones: np.ndarray,
    config_tuple: tuple,
    equity_curve: np.ndarray
) -> tuple:
    """
    Main backtest loop (Numba-compiled).

    WEEK 1 STUB: Simple implementation for parity testing
    WEEK 2: Full optimization with vectorization

    Args:
        candles: (N, 4) array [open, high, low, close]
        timestamps: (N,) array of Unix timestamps (int64)
        zones: (max_zones,) structured array (ZONE_DTYPE)
        config_tuple: (tick_size, pip_size, slippage_ticks, sl_buffer, risk_pct,
                       account_size, quality_threshold, min_bar, is_gold,
                       require_htf_flip)
        equity_curve: (N, 2) output array [timestamp, equity]

    Returns:
        (trades_array, zone_count, equity_curve)
        trades_array: (M, 8) array [entry_bar, exit_bar, entry_price, exit_price,
                                     pnl, is_long, reason, zone_idx]
    """
    # Unpack config
    (tick_size, pip_size, slippage_ticks, sl_buffer, risk_pct,
     account_size, quality_threshold, min_bar, is_gold, require_htf_flip) = config_tuple

    n_bars = len(candles)
    zone_count = 0

    # Position state (use has_position flag to avoid None type)
    has_position = False
    # Always have position tuple (even when empty) to avoid Numba None type issues
    # Use float for is_long (1.0=True, 0.0=False) to keep tuple homogeneous
    position = (0, 0.0, 0.0, 0.0, 0.0, 1.0, 0)  # (entry_bar, entry_price, sl, tp, qty, is_long, zone_idx)

    trades = []
    equity = account_size

    # Historical scan flag (do once at bar 50)
    historical_scan_done = False

    for bar_idx in range(n_bars):
        bar_open = candles[bar_idx, 0]
        bar_high = candles[bar_idx, 1]
        bar_low = candles[bar_idx, 2]
        bar_close = candles[bar_idx, 3]
        bar_time = timestamps[bar_idx]

        # 1. Check exits if in position
        if has_position:
            exit_result = check_exit_numba_stub(
                position, bar_high, bar_low, bar_close, bar_idx,
                slippage_ticks, tick_size, 0.0  # commission_pct
            )
            if exit_result[0] >= 0:  # exit_bar >= 0 means we exited
                exit_bar = int(exit_result[0])
                exit_price = exit_result[1]
                pnl = exit_result[2]
                reason = exit_result[3]

                trades.append((
                    float(position[0]),  # entry_bar
                    float(exit_bar),
                    position[1],  # entry_price
                    exit_price,
                    pnl,
                    float(position[5]),  # is_long
                    reason,
                    float(position[6]),  # zone_idx
                ))
                equity += pnl
                has_position = False

        # 2. Update zones (creation + liquidity sweep)
        if bar_idx >= 10:  # Need history for patterns
            zone_count, historical_scan_done = update_zones_numba_stub(
                zones, zone_count, candles, bar_idx, quality_threshold,
                tick_size, pip_size, historical_scan_done
            )

        # 3. Check entry signals
        if not has_position and bar_idx >= min_bar:
            signal = check_entry_signals_numba_stub(
                zones, zone_count, bar_idx, candles, timestamps,
                tick_size, pip_size, sl_buffer, risk_pct,
                account_size, quality_threshold, is_gold, require_htf_flip
            )
            if signal[0] >= 0:  # entry_bar >= 0 means we have a signal
                position = signal
                has_position = True
                # Mitigate zone
                zone_idx = int(signal[6])
                if zone_idx < len(zones):
                    zones[zone_idx]['active'] = False

        # Update equity curve
        equity_curve[bar_idx, 0] = float(bar_time)
        equity_curve[bar_idx, 1] = equity

    # Convert trades list to NumPy array
    if len(trades) > 0:
        trades_array = np.array(trades, dtype=np.float64)
    else:
        trades_array = np.zeros((0, 8), dtype=np.float64)

    return trades_array, zone_count, equity_curve


# ========== Zone Creation & Updates (Stub) ==========

@njit
def update_zones_numba_stub(
    zones: np.ndarray,
    zone_count: int,
    candles: np.ndarray,
    bar_idx: int,
    quality_threshold: float,
    tick_size: float,
    pip_size: float,
    historical_scan_done: bool
) -> tuple:
    """
    Zone creation + liquidity sweep detection.

    Matches legacy snd_strategy.py patterns:
    - 1-3 leg demand/supply zones
    - Historical scan at bar 50 (once)

    Returns:
        (zone_count, historical_scan_done)
    """
    if bar_idx < 10:
        return (zone_count, historical_scan_done)

    # Get recent candles (need up to 5 bars back for 3-leg patterns)
    close_0 = candles[bar_idx, 3]
    open_0 = candles[bar_idx, 0]
    close_1 = candles[bar_idx - 1, 3]
    open_1 = candles[bar_idx - 1, 0]
    close_2 = candles[bar_idx - 2, 3]
    open_2 = candles[bar_idx - 2, 0]

    # Need more bars for 2-3 leg patterns
    if bar_idx >= 3:
        close_3 = candles[bar_idx - 3, 3]
        open_3 = candles[bar_idx - 3, 0]
    else:
        close_3 = close_2
        open_3 = open_2

    if bar_idx >= 4:
        close_4 = candles[bar_idx - 4, 3]
        open_4 = candles[bar_idx - 4, 0]
    else:
        close_4 = close_3
        open_4 = open_3

    # === DEMAND ZONES (1-3 leg patterns) ===
    # Pattern: Bearish base, then 1-3 bullish legs

    # 1-leg demand: [bearish, bullish, bullish]
    if (is_bullish_numba(close_0, open_0) and
        is_bullish_numba(close_1, open_1) and
        is_bearish_numba(close_2, open_2)):
        zone_count = create_zone_numba_stub(
            zones, zone_count, candles, bar_idx - 1,
            True, 50.0, False, bar_idx
        )

    # 2-leg demand: [bearish, bullish, bullish, bullish]
    elif bar_idx >= 3 and (
        is_bullish_numba(close_0, open_0) and
        is_bullish_numba(close_1, open_1) and
        is_bullish_numba(close_2, open_2) and
        is_bearish_numba(close_3, open_3)
    ):
        zone_count = create_zone_numba_stub(
            zones, zone_count, candles, bar_idx - 2,
            True, 50.0, False, bar_idx
        )

    # 3-leg demand: [bearish, bullish, bullish, bullish, bullish]
    elif bar_idx >= 4 and (
        is_bullish_numba(close_0, open_0) and
        is_bullish_numba(close_1, open_1) and
        is_bullish_numba(close_2, open_2) and
        is_bullish_numba(close_3, open_3) and
        is_bearish_numba(close_4, open_4)
    ):
        zone_count = create_zone_numba_stub(
            zones, zone_count, candles, bar_idx - 3,
            True, 50.0, False, bar_idx
        )

    # === SUPPLY ZONES (1-3 leg patterns) ===
    # Pattern: Bullish base, then 1-3 bearish legs

    # 1-leg supply: [bullish, bearish, bearish]
    if (is_bearish_numba(close_0, open_0) and
        is_bearish_numba(close_1, open_1) and
        is_bullish_numba(close_2, open_2)):
        zone_count = create_zone_numba_stub(
            zones, zone_count, candles, bar_idx - 1,
            False, 50.0, False, bar_idx
        )

    # 2-leg supply: [bullish, bearish, bearish, bearish]
    elif bar_idx >= 3 and (
        is_bearish_numba(close_0, open_0) and
        is_bearish_numba(close_1, open_1) and
        is_bearish_numba(close_2, open_2) and
        is_bullish_numba(close_3, open_3)
    ):
        zone_count = create_zone_numba_stub(
            zones, zone_count, candles, bar_idx - 2,
            False, 50.0, False, bar_idx
        )

    # 3-leg supply: [bullish, bearish, bearish, bearish, bearish]
    elif bar_idx >= 4 and (
        is_bearish_numba(close_0, open_0) and
        is_bearish_numba(close_1, open_1) and
        is_bearish_numba(close_2, open_2) and
        is_bearish_numba(close_3, open_3) and
        is_bullish_numba(close_4, open_4)
    ):
        zone_count = create_zone_numba_stub(
            zones, zone_count, candles, bar_idx - 3,
            False, 50.0, False, bar_idx
        )

    # Liquidity sweep check
    high = candles[bar_idx, 1]
    low = candles[bar_idx, 2]
    lookback_start = max(0, bar_idx - 10)
    lookback = candles[lookback_start:bar_idx]

    if len(lookback) > 0:
        liq_high = np.max(lookback[:, 1])
        liq_low = np.min(lookback[:, 2])

        # Update all active zones
        for i in range(zone_count):
            if not zones[i]['active']:
                continue

            is_demand = zones[i]['is_demand']
            swept = detect_liquidity_sweep_numba(high, low, liq_high, liq_low, is_demand)

            if swept and not zones[i]['liquidity_swept']:
                zones[i]['liquidity_swept'] = True
                zones[i]['caused_sweep'] = True
                zones[i]['liq_high'] = liq_high
                zones[i]['liq_low'] = liq_low

            # Target swept
            if is_demand and not zones[i]['target_swept']:
                if high >= zones[i]['liq_high']:
                    zones[i]['target_swept'] = True
            elif not is_demand and not zones[i]['target_swept']:
                if low <= zones[i]['liq_low']:
                    zones[i]['target_swept'] = True

    # === HISTORICAL SCAN (once at bar 50+) ===
    if not historical_scan_done and bar_idx > 50:
        # Scan last 100 bars for historical zones (marked as is_historical=True)
        scan_range = min(100, bar_idx)
        for i in range(2, scan_range):
            base_idx = bar_idx - i
            if base_idx < 2:
                break

            c_i = candles[base_idx, 3]
            o_i = candles[base_idx, 0]

            if base_idx + 2 < len(candles):
                c_1 = candles[base_idx + 1, 3]
                o_1 = candles[base_idx + 1, 0]
                c_2 = candles[base_idx + 2, 3]
                o_2 = candles[base_idx + 2, 0]

                # Historical demand: bearish, bullish, bullish
                if is_bearish_numba(c_i, o_i) and is_bullish_numba(c_1, o_1) and is_bullish_numba(c_2, o_2):
                    zone_count = create_zone_numba_stub(
                        zones, zone_count, candles, base_idx,
                        True, 50.0, True, bar_idx  # is_historical=True
                    )

                # Historical supply: bullish, bearish, bearish
                if is_bullish_numba(c_i, o_i) and is_bearish_numba(c_1, o_1) and is_bearish_numba(c_2, o_2):
                    zone_count = create_zone_numba_stub(
                        zones, zone_count, candles, base_idx,
                        False, 50.0, True, bar_idx  # is_historical=True
                    )

        historical_scan_done = True

    return (zone_count, historical_scan_done)


@njit
def create_zone_numba_stub(
    zones: np.ndarray,
    zone_count: int,
    candles: np.ndarray,
    base_idx: int,
    is_demand: bool,
    score: float,
    is_historical: bool,
    current_bar: int
) -> int:
    """Create new zone (STUB)."""
    if zone_count >= len(zones):
        return zone_count  # At capacity

    base_high = candles[base_idx, 1]
    base_low = candles[base_idx, 2]

    zones[zone_count]['id'] = zone_count + 1
    zones[zone_count]['top'] = base_high
    zones[zone_count]['bottom'] = base_low
    zones[zone_count]['is_demand'] = is_demand
    zones[zone_count]['active'] = True
    zones[zone_count]['created_bar'] = base_idx
    zones[zone_count]['is_historical'] = is_historical
    zones[zone_count]['score'] = score
    zones[zone_count]['primed'] = False
    zones[zone_count]['liquidity_swept'] = False
    zones[zone_count]['target_swept'] = False
    zones[zone_count]['caused_sweep'] = False
    zones[zone_count]['touch_count'] = 0
    zones[zone_count]['last_touch_bar'] = -1
    zones[zone_count]['leg_candles'] = 1
    zones[zone_count]['candles_in_base'] = 1

    return zone_count + 1


# ========== Entry Signal Checks (Stub) ==========

@njit
def check_entry_signals_numba_stub(
    zones: np.ndarray,
    zone_count: int,
    bar_idx: int,
    candles: np.ndarray,
    timestamps: np.ndarray,
    tick_size: float,
    pip_size: float,
    sl_buffer: float,
    risk_pct: float,
    account_size: float,
    quality_threshold: float,
    is_gold: bool,
    require_htf_flip: bool
) -> tuple:
    """
    Entry signal detection (STUB).

    WEEK 1: Simple FLIP entry only
    WEEK 2: Add BREAK_CANDLE and DIR_CLOSE models

    Returns:
        Signal tuple: (entry_bar, entry_price, sl, tp, qty, is_long, zone_idx)
        Sentinel: entry_bar = -1 if no entry
    """
    # No signal sentinel
    NO_SIGNAL = (-1, 0.0, 0.0, 0.0, 0.0, True, 0)

    if bar_idx < 1:
        return NO_SIGNAL

    bar_close = candles[bar_idx, 3]
    bar_open = candles[bar_idx, 0]
    bar_high = candles[bar_idx, 1]
    bar_low = candles[bar_idx, 2]
    bar_time = timestamps[bar_idx]

    prev_close = candles[bar_idx - 1, 3]
    prev_open = candles[bar_idx - 1, 0]

    # Extract minute from timestamp
    minute, hour = extract_minute_hour_from_timestamp(bar_time)

    # Scan demand zones for long entry
    for i in range(zone_count):
        z = zones[i]

        if not z['active'] or not z['is_demand'] or z['is_historical']:
            continue

        # Priming check
        if not z['primed']:
            if z['liquidity_swept'] and z['target_swept'] and z['caused_sweep']:
                # Check touch
                touch = (bar_low >= z['bottom'] - tick_size and
                        bar_low <= z['top'] + tick_size)

                if touch:
                    zones[i]['touch_count'] += 1
                    if zones[i]['touch_count'] <= 1:
                        zones[i]['primed'] = True
                        zones[i]['primed_bar'] = bar_idx
                        zones[i]['primed_ref_close'] = bar_close
                        zones[i]['primed_ref_high'] = bar_high
                        zones[i]['primed_ref_low'] = bar_low
            continue

        # Quality filter
        if z['score'] < quality_threshold:
            continue

        # === ENTRY MODELS ===
        # FLIP: Bullish candle after bearish candle
        is_flip = is_bullish_numba(bar_close, bar_open) and is_bearish_numba(prev_close, prev_open)

        # HTF filter for FLIP (if enabled)
        if require_htf_flip and is_flip:
            if not is_htf_candle_open_numba(minute):
                is_flip = False

        # DIR_CLOSE: Simple bullish close
        is_dir_close = is_bullish_numba(bar_close, bar_open)

        # BREAK_CANDLE: Open or high breaks above primed reference + bullish close
        is_break = False
        if not np.isnan(z['primed_ref_close']) and not np.isnan(z['primed_ref_high']):
            break_condition = (bar_open > z['primed_ref_close'] or bar_high > z['primed_ref_high'])
            is_break = break_condition and is_bullish_numba(bar_close, bar_open) and not is_flip

        # Choose entry model (priority: FLIP > BREAK > DIR_CLOSE)
        if is_flip:
            chosen_model = 1  # FLIP
        elif is_break:
            chosen_model = 2  # BREAK_CANDLE
        elif is_dir_close:
            chosen_model = 3  # DIR_CLOSE
        else:
            continue

        # Calculate entry, SL, TP
        entry_price = bar_close
        sl_buffer_val = sl_buffer * pip_size * (10.0 if is_gold else 1.0)
        sl = z['bottom'] - sl_buffer_val

        sl_pips = abs(entry_price - sl) / pip_size
        tp_ratio = get_tp_ratio_numba(sl_pips, is_gold)
        tp = entry_price + (entry_price - sl) * tp_ratio

        # Position size
        qty = calc_position_size_numba(entry_price, sl, account_size, risk_pct, is_gold)

        if qty <= 0:
            continue

        # Return signal (entry_bar, entry_price, sl, tp, qty, is_long, zone_idx)
        return (bar_idx, entry_price, sl, tp, qty, 1.0, i)  # 1.0 = True for is_long

    # Scan supply zones for short entry (simplified for STUB)
    for i in range(zone_count):
        z = zones[i]

        if not z['active'] or z['is_demand'] or z['is_historical']:
            continue

        if not z['primed']:
            if z['liquidity_swept'] and z['target_swept'] and z['caused_sweep']:
                touch = (bar_high >= z['bottom'] - tick_size and
                        bar_high <= z['top'] + tick_size)

                if touch:
                    zones[i]['touch_count'] += 1
                    if zones[i]['touch_count'] <= 1:
                        zones[i]['primed'] = True
                        zones[i]['primed_bar'] = bar_idx
                        zones[i]['primed_ref_close'] = bar_close
                        zones[i]['primed_ref_high'] = bar_high
                        zones[i]['primed_ref_low'] = bar_low
            continue

        if z['score'] < quality_threshold:
            continue

        # === ENTRY MODELS (SHORT) ===
        # FLIP: Bearish candle after bullish candle
        is_flip = is_bearish_numba(bar_close, bar_open) and is_bullish_numba(prev_close, prev_open)

        # HTF filter for FLIP (if enabled)
        if require_htf_flip and is_flip:
            if not is_htf_candle_open_numba(minute):
                is_flip = False

        # DIR_CLOSE: Simple bearish close
        is_dir_close = is_bearish_numba(bar_close, bar_open)

        # BREAK_CANDLE: Open or low breaks below primed reference + bearish close
        is_break = False
        if not np.isnan(z['primed_ref_close']) and not np.isnan(z['primed_ref_low']):
            break_condition = (bar_open < z['primed_ref_close'] or bar_low < z['primed_ref_low'])
            is_break = break_condition and is_bearish_numba(bar_close, bar_open) and not is_flip

        # Choose entry model (priority: FLIP > BREAK > DIR_CLOSE)
        if is_flip:
            chosen_model = 1  # FLIP
        elif is_break:
            chosen_model = 2  # BREAK_CANDLE
        elif is_dir_close:
            chosen_model = 3  # DIR_CLOSE
        else:
            continue

        entry_price = bar_close
        sl_buffer_val = sl_buffer * pip_size * (10.0 if is_gold else 1.0)
        sl = z['top'] + sl_buffer_val

        sl_pips = abs(sl - entry_price) / pip_size
        tp_ratio = get_tp_ratio_numba(sl_pips, is_gold)
        tp = entry_price - (sl - entry_price) * tp_ratio

        qty = calc_position_size_numba(entry_price, sl, account_size, risk_pct, is_gold)

        if qty <= 0:
            continue

        return (bar_idx, entry_price, sl, tp, qty, 0.0, i)  # 0.0 = False for is_long

    return NO_SIGNAL


# ========== Exit Checks (Stub) ==========

@njit
def check_exit_numba_stub(
    position: tuple,
    bar_high: float,
    bar_low: float,
    bar_close: float,
    bar_idx: int,
    slippage_ticks: int,
    tick_size: float,
    commission_pct: float
) -> tuple:
    """
    Check SL/TP exit (STUB).

    WEEK 1: Basic SL/TP checks
    WEEK 2: Add time-based exit

    Returns:
        (exit_bar, exit_price, pnl, reason)
        Sentinel: exit_bar = -1 if no exit
        reason: 0=stop, 1=limit, 2=time
    """
    # No exit sentinel
    NO_EXIT = (-1, 0.0, 0.0, -1)

    entry_bar, entry_price, sl, tp, qty, is_long, zone_idx = position
    is_long_bool = is_long > 0.5  # Convert float to bool

    if is_long_bool:
        # Check SL
        if bar_low <= sl:
            exit_price = apply_slippage_exit_numba(sl, True, slippage_ticks, tick_size)
            pnl = calculate_pnl_numba(entry_price, exit_price, qty, True, commission_pct)
            return (bar_idx, exit_price, pnl, 0.0)

        # Check TP
        if bar_high >= tp:
            exit_price = apply_slippage_exit_numba(tp, True, slippage_ticks, tick_size)
            pnl = calculate_pnl_numba(entry_price, exit_price, qty, True, commission_pct)
            return (bar_idx, exit_price, pnl, 1.0)
    else:
        # Short
        if bar_high >= sl:
            exit_price = apply_slippage_exit_numba(sl, False, slippage_ticks, tick_size)
            pnl = calculate_pnl_numba(entry_price, exit_price, qty, False, commission_pct)
            return (bar_idx, exit_price, pnl, 0.0)

        if bar_low <= tp:
            exit_price = apply_slippage_exit_numba(tp, False, slippage_ticks, tick_size)
            pnl = calculate_pnl_numba(entry_price, exit_price, qty, False, commission_pct)
            return (bar_idx, exit_price, pnl, 1.0)

    return NO_EXIT
