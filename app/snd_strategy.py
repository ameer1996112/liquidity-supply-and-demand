"""
SND Strategy - Stateful strategy class ported from SND_Strategy.pine.

on_bar(bar_idx, bar, history) -> list[Order]

Core flow:
1. Zone creation (demand/supply patterns)
2. Liquidity sweep detection
3. Zone priming (touch + valid setup)
4. Entry models: Flip, DirClose, BreakOfCandle
5. Time filters, position sizing
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional, Set, Tuple

import numpy as np
import pandas as pd

from app.config import BacktestConfig
from app.engine import Order, OrderSide, OrderType
from app.snd_core import Zone, calculate_zone_score, get_grade_from_score, get_grade_value
from app.snd_utils import (
    is_bearish,
    is_bullish,
    get_auto_pip_size,
    units_to_lots,
)

logger = logging.getLogger(__name__)


def _safe_get(arr: pd.Series, idx: int) -> float:
    """Safe series access (Pine [offset] semantics)."""
    if idx < 0 or idx >= len(arr):
        return np.nan
    v = arr.iloc[idx]
    return float(v) if not (isinstance(v, float) and np.isnan(v)) else np.nan


def _is_pivot_low(history: pd.DataFrame, pivot_bar: int) -> bool:
    """3-candle Makuchaku pivot low: low[middle] < low[older] and low[middle] < low[newer]."""
    n = len(history)
    if pivot_bar < 1 or pivot_bar >= n - 1:
        return False
    mid = float(history.iloc[pivot_bar]["low"])
    left = float(history.iloc[pivot_bar - 1]["low"])
    right = float(history.iloc[pivot_bar + 1]["low"])
    return mid < left and mid < right


def _is_pivot_high(history: pd.DataFrame, pivot_bar: int) -> bool:
    """3-candle Makuchaku pivot high."""
    n = len(history)
    if pivot_bar < 1 or pivot_bar >= n - 1:
        return False
    mid = float(history.iloc[pivot_bar]["high"])
    left = float(history.iloc[pivot_bar - 1]["high"])
    right = float(history.iloc[pivot_bar + 1]["high"])
    return mid > left and mid > right


def _is_htf_candle_open(bar_time: datetime) -> bool:
    """M5: valid at :00, :15, :30, :45."""
    return bar_time.minute in (0, 15, 30, 45)


def _is_time_dead_zone(bar_time: datetime) -> bool:
    """Block xx:50-xx:00."""
    return bar_time.minute >= 50


def _is_trading_hours(bar_time: datetime, start_hour: int, end_hour: int) -> bool:
    """UTC hours."""
    h = bar_time.hour
    if start_hour <= end_hour:
        return start_hour <= h <= end_hour
    return h >= start_hour or h <= end_hour


def _get_tp_ratio_gold(sl_pips: float, cfg: BacktestConfig) -> float:
    """Gold TP rules (Balanced profile)."""
    if sl_pips <= 50:
        return 4.5
    if sl_pips <= 100:
        return 3.0
    if sl_pips <= 150:
        return 2.5
    if sl_pips <= 200:
        return 2.0
    return 1.5


def _calc_pos_size_units(
    entry: float,
    stop: float,
    balance: float,
    risk_pct: float,
    is_short: bool,
    pip_size: float,
    ticker: str,
) -> float:
    """Position size in units (XAUUSD: 1 unit = 1 oz)."""
    risk_usd = balance * (risk_pct / 100)
    price_distance = abs(entry - stop)
    min_distance = max(2.0 * pip_size, 0.01)
    effective_distance = max(price_distance, min_distance)
    if effective_distance <= 0:
        return 0.0
    # XAUUSD: USD quote, 1 unit = $1 per point
    if "XAU" in ticker.upper() or "GOLD" in ticker.upper():
        return risk_usd / effective_distance
    # Forex USD quote
    if "USD" in ticker.upper() and "JPY" not in ticker.upper():
        return risk_usd / effective_distance
    # Default
    return risk_usd / effective_distance


@dataclass
class SNDStrategy:
    """Stateful SND strategy."""

    config: BacktestConfig

    # Optional: collector for zone creation (for visualization/export)
    zone_log: Optional[List[dict]] = None

    # Persistent state
    demand_zones: List[Zone] = field(default_factory=list)
    supply_zones: List[Zone] = field(default_factory=list)
    used_demand_base_times: Set[int] = field(default_factory=set)
    used_supply_base_times: Set[int] = field(default_factory=set)
    zone_id_counter: int = 0
    initial_scan_done: bool = False
    current_day_trades: int = 0
    last_trade_day: Optional[int] = None
    equity: float = 0.0

    def reset(self) -> None:
        """Reset state."""
        self.demand_zones = []
        self.supply_zones = []
        self.used_demand_base_times = set()
        self.used_supply_base_times = set()
        self.zone_id_counter = 0
        self.initial_scan_done = False
        self.current_day_trades = 0
        self.last_trade_day = None
        self.equity = self.config.initial_equity

    def _create_zone(
        self,
        bar_idx: int,
        base_idx: int,
        is_demand: bool,
        is_historical: bool,
        candles_in_base: int,
        leg_candles: int,
        history: pd.DataFrame,
    ) -> Optional[Zone]:
        """Create zone from base candle."""
        if base_idx < 0 or base_idx >= len(history):
            return None

        row = history.iloc[base_idx]
        base_high = float(row["high"])
        base_low = float(row["low"])
        base_open = float(row["open"])
        base_close = float(row["close"])
        base_time = row["time"]

        base_ts = int(pd.Timestamp(base_time).timestamp()) if base_time is not None else 0
        used = self.used_demand_base_times if is_demand else self.used_supply_base_times
        if base_ts in used:
            return None
        used.add(base_ts)

        # Accuracy zone check
        is_accuracy = False
        if self.config.enable_accuracy_zones and base_idx >= 1:
            reaction_high = float(history.iloc[base_idx - 1]["high"])
            reaction_low = float(history.iloc[base_idx - 1]["low"])
            if is_demand and base_high > reaction_high:
                is_accuracy = True
            elif not is_demand and base_low < reaction_low:
                is_accuracy = True

        if is_accuracy:
            if is_demand:
                z_top = base_open
                z_bottom = base_low
            else:
                z_top = base_high
                z_bottom = base_open
        else:
            z_top = base_high
            z_bottom = base_low

        pip_size = self.config.pip_size
        trend_ema = history["close"].ewm(span=200, adjust=False).mean()
        is_uptrend = float(history.iloc[bar_idx]["close"]) > float(trend_ema.iloc[bar_idx])
        is_downtrend = float(history.iloc[bar_idx]["close"]) < float(trend_ema.iloc[bar_idx])

        score = calculate_zone_score(
            is_demand=is_demand,
            top=z_top,
            bottom=z_bottom,
            base_idx=base_idx,
            leg_candles=leg_candles,
            has_liquidity=False,
            is_liquidity_sweep=False,
            candles_in_base=candles_in_base,
            is_accuracy=is_accuracy,
            is_uptrend=is_uptrend,
            is_downtrend=is_downtrend,
            zone_time=base_ts,
        )

        self.zone_id_counter += 1
        z = Zone(
            id=self.zone_id_counter,
            top=z_top,
            bottom=z_bottom,
            active=True,
            created_bar_index=base_idx,
            is_historical=is_historical,
            start_time=base_ts,
            leg_candle_count=leg_candles,
            is_accuracy=is_accuracy,
            score=score,
            grade=get_grade_from_score(score),
        )
        # Liquidity is set by _scan_*_liquidity (pivot-based, Pine-aligned)

        if self.zone_log is not None:
            base_time = row.get("time")
            self.zone_log.append({
                "zone_id": z.id,
                "type": "demand" if is_demand else "supply",
                "created_bar": base_idx,
                "created_time": pd.Timestamp(base_time).isoformat() if base_time is not None else "",
                "top": z_top,
                "bottom": z_bottom,
                "is_accuracy": is_accuracy,
                "is_historical": is_historical,
                "score": score,
                "grade": z.grade,
            })

        if is_demand:
            self.demand_zones.append(z)
        else:
            self.supply_zones.append(z)
        return z

    def _scan_demand_liquidity(
        self, zone_idx: int, bar_idx: int, history: pd.DataFrame) -> None:
        """Pine-aligned: find lowest pivot LOW above zone (inducement), then target high."""
        z = self.demand_zones[zone_idx]
        if z.created_bar_index < 0 or bar_idx <= z.created_bar_index or z.is_historical:
            return
        pip_size = self.config.pip_size
        effective_liq_max = self.config.get_effective_liq_max_dist(
            self.config.is_gold(), self.config.is_index()
        ) * pip_size

        # STEP A: Inducement = lowest valid pivot LOW above zone top
        best_liq_price = float("inf")
        best_liq_bar = -1
        max_scan = min(bar_idx - 1, z.created_bar_index + 500)  # Cap for performance
        for pivot_bar in range(z.created_bar_index + 1, max_scan):
            if not _is_pivot_low(history, pivot_bar):
                continue
            p_low = float(history.iloc[pivot_bar]["low"])
            if p_low <= z.top:
                continue
            dist = p_low - z.top
            if effective_liq_max > 0 and dist > effective_liq_max:
                continue
            if p_low < best_liq_price:
                best_liq_price = p_low
                best_liq_bar = pivot_bar

        if best_liq_bar < 0:
            z.liquidity_valid = False
            return

        # Inducement changed? Reset sweep flags
        induction_changed = (
            np.isnan(z.liq_low_price) or z.liq_low_price != best_liq_price
            or z.liq_low_bar != best_liq_bar
        )
        z.liquidity_price = best_liq_price
        z.liquidity_bar_index = best_liq_bar
        z.liq_low_price = best_liq_price
        z.liq_low_bar = best_liq_bar
        if induction_changed:
            z.liquidity_swept = False
            z.liquidity_swept_bar_index = -1

        # STEP B: Target = absolute highest high in [createdBar ... inducementBar - 1]
        range_start = z.created_bar_index
        range_end = best_liq_bar - 1
        best_target_price = np.nan
        best_target_bar = -1
        if range_end >= range_start and range_end < len(history):
            slice_high = history["high"].iloc[range_start : range_end + 1]
            if len(slice_high) > 0:
                best_target_bar = range_start + int(slice_high.values.argmax())
                best_target_price = float(history.iloc[best_target_bar]["high"])

        target_changed = (
            np.isnan(z.liq_high_price) or (not np.isnan(best_target_price) and z.liq_high_price != best_target_price)
            or z.liq_high_bar != best_target_bar
        )
        z.liq_high_bar = best_target_bar
        z.liq_high_price = best_target_price if not np.isnan(best_target_price) else np.nan
        if target_changed:
            z.target_swept = False
            z.target_swept_bar_index = -1

        z.liquidity_valid = True
        z.structure_sweep_level = z.liq_high_price
        z.structure_sweep_level_bar = z.liq_high_bar

    def _scan_supply_liquidity(
        self, zone_idx: int, bar_idx: int, history: pd.DataFrame) -> None:
        """Pine-aligned: find highest pivot HIGH below zone (inducement), then target low."""
        z = self.supply_zones[zone_idx]
        if z.created_bar_index < 0 or bar_idx <= z.created_bar_index or z.is_historical:
            return
        pip_size = self.config.pip_size
        effective_liq_max = self.config.get_effective_liq_max_dist(
            self.config.is_gold(), self.config.is_index()
        ) * pip_size

        best_liq_price = float("-inf")
        best_liq_bar = -1
        max_scan = min(bar_idx - 1, z.created_bar_index + 500)  # Cap for performance
        for pivot_bar in range(z.created_bar_index + 1, max_scan):
            if not _is_pivot_high(history, pivot_bar):
                continue
            p_high = float(history.iloc[pivot_bar]["high"])
            if p_high >= z.bottom:
                continue
            dist = z.bottom - p_high
            if effective_liq_max > 0 and dist > effective_liq_max:
                continue
            if p_high > best_liq_price:
                best_liq_price = p_high
                best_liq_bar = pivot_bar

        if best_liq_bar < 0:
            z.liquidity_valid = False
            return

        induction_changed = (
            np.isnan(z.liq_high_price) or z.liq_high_price != best_liq_price
            or z.liq_high_bar != best_liq_bar
        )
        z.liquidity_price = best_liq_price
        z.liquidity_bar_index = best_liq_bar
        z.liq_high_price = best_liq_price
        z.liq_high_bar = best_liq_bar
        if induction_changed:
            z.liquidity_swept = False
            z.liquidity_swept_bar_index = -1

        range_start = z.created_bar_index
        range_end = best_liq_bar - 1
        best_target_price = np.nan
        best_target_bar = -1
        if range_end >= range_start and range_end < len(history):
            slice_low = history["low"].iloc[range_start : range_end + 1]
            if len(slice_low) > 0:
                best_target_bar = range_start + int(slice_low.values.argmin())
                best_target_price = float(history.iloc[best_target_bar]["low"])

        target_changed = (
            np.isnan(z.liq_low_price) or z.liq_low_price != best_target_price
            or z.liq_low_bar != best_target_bar
        )
        z.liq_low_bar = best_target_bar
        z.liq_low_price = best_target_price if not np.isnan(best_target_price) else np.nan
        if target_changed:
            z.target_swept = False
            z.target_swept_bar_index = -1

        z.liquidity_valid = True
        z.structure_sweep_level = z.liq_low_price
        z.structure_sweep_level_bar = z.liq_low_bar

    def _check_demand_sweeps(
        self, zone_idx: int, bar_idx: int, high: float, low: float,
        history: pd.DataFrame) -> None:
        """Pine-aligned: inducement sweep (low <= liqLow+tol), target sweep (high >= liqHigh-tol)."""
        z = self.demand_zones[zone_idx]
        pip_size = self.config.pip_size
        sweep_tol = pip_size * 0.5
        if not np.isnan(z.liq_low_price) and not z.liquidity_swept:
            if low <= z.liq_low_price + sweep_tol:
                z.liquidity_swept = True
                z.liquidity_swept_bar_index = bar_idx
                z.caused_sweep = True
        if z.liquidity_valid and not np.isnan(z.liq_high_price) and not z.target_swept:
            if high >= z.liq_high_price - sweep_tol:
                z.target_swept = True
                z.target_swept_bar_index = bar_idx
                if not z.caused_sweep:
                    z.caused_sweep = True

    def _check_supply_sweeps(
        self, zone_idx: int, bar_idx: int, high: float, low: float,
        history: pd.DataFrame) -> None:
        """Pine-aligned: inducement sweep (high >= liqHigh-tol), target sweep (low <= liqLow+tol)."""
        z = self.supply_zones[zone_idx]
        pip_size = self.config.pip_size
        sweep_tol = pip_size * 0.5
        if not np.isnan(z.liq_high_price) and not z.liquidity_swept:
            if high >= z.liq_high_price - sweep_tol:
                z.liquidity_swept = True
                z.liquidity_swept_bar_index = bar_idx
                z.caused_sweep = True
        if z.liquidity_valid and not np.isnan(z.liq_low_price) and not z.target_swept:
            if low <= z.liq_low_price + sweep_tol:
                z.target_swept = True
                z.target_swept_bar_index = bar_idx
                if not z.caused_sweep:
                    z.caused_sweep = True

    def _update_zones(self, bar_idx: int, bar: pd.Series, history: pd.DataFrame) -> None:
        """Zone creation + liquidity sweep detection."""
        cfg = self.config
        close = float(bar["close"])
        open_ = float(bar["open"])
        high = float(bar["high"])
        low = float(bar["low"])

        # Demand zone creation (recent bars)
        if bar_idx > 10:
            if is_bullish(close, open_) and is_bullish(_safe_get(history["close"], bar_idx - 1), _safe_get(history["open"], bar_idx - 1)) and is_bearish(_safe_get(history["close"], bar_idx - 2), _safe_get(history["open"], bar_idx - 2)):
                self._create_zone(bar_idx, bar_idx - 1, True, False, 1, 1, history)
            elif is_bullish(close, open_) and is_bullish(_safe_get(history["close"], bar_idx - 1), _safe_get(history["open"], bar_idx - 1)) and is_bullish(_safe_get(history["close"], bar_idx - 2), _safe_get(history["open"], bar_idx - 2)) and is_bearish(_safe_get(history["close"], bar_idx - 3), _safe_get(history["open"], bar_idx - 3)):
                self._create_zone(bar_idx, bar_idx - 2, True, False, 1, 2, history)
            elif is_bullish(close, open_) and is_bullish(_safe_get(history["close"], bar_idx - 1), _safe_get(history["open"], bar_idx - 1)) and is_bullish(_safe_get(history["close"], bar_idx - 2), _safe_get(history["open"], bar_idx - 2)) and is_bullish(_safe_get(history["close"], bar_idx - 3), _safe_get(history["open"], bar_idx - 3)) and is_bearish(_safe_get(history["close"], bar_idx - 4), _safe_get(history["open"], bar_idx - 4)):
                self._create_zone(bar_idx, bar_idx - 3, True, False, 1, 3, history)

            # Supply zone creation
            if is_bearish(close, open_) and is_bearish(_safe_get(history["close"], bar_idx - 1), _safe_get(history["open"], bar_idx - 1)) and is_bullish(_safe_get(history["close"], bar_idx - 2), _safe_get(history["open"], bar_idx - 2)):
                self._create_zone(bar_idx, bar_idx - 1, False, False, 1, 1, history)
            elif is_bearish(close, open_) and is_bearish(_safe_get(history["close"], bar_idx - 1), _safe_get(history["open"], bar_idx - 1)) and is_bearish(_safe_get(history["close"], bar_idx - 2), _safe_get(history["open"], bar_idx - 2)) and is_bullish(_safe_get(history["close"], bar_idx - 3), _safe_get(history["open"], bar_idx - 3)):
                self._create_zone(bar_idx, bar_idx - 2, False, False, 1, 2, history)
            elif is_bearish(close, open_) and is_bearish(_safe_get(history["close"], bar_idx - 1), _safe_get(history["open"], bar_idx - 1)) and is_bearish(_safe_get(history["close"], bar_idx - 2), _safe_get(history["open"], bar_idx - 2)) and is_bearish(_safe_get(history["close"], bar_idx - 3), _safe_get(history["open"], bar_idx - 3)) and is_bullish(_safe_get(history["close"], bar_idx - 4), _safe_get(history["open"], bar_idx - 4)):
                self._create_zone(bar_idx, bar_idx - 3, False, False, 1, 3, history)

        # Historical scan (once)
        if not self.initial_scan_done and bar_idx > 50:
            self.initial_scan_done = True
            for i in range(2, min(100, bar_idx)):
                base_idx = bar_idx - i
                c_i = _safe_get(history["close"], bar_idx - i)
                o_i = _safe_get(history["open"], bar_idx - i)
                c_1 = _safe_get(history["close"], bar_idx - i + 1)
                o_1 = _safe_get(history["open"], bar_idx - i + 1)
                c_2 = _safe_get(history["close"], bar_idx - i + 2)
                o_2 = _safe_get(history["open"], bar_idx - i + 2)
                if is_bearish(c_i, o_i) and is_bullish(c_1, o_1) and is_bullish(c_2, o_2):
                    self._create_zone(bar_idx, base_idx, True, True, 1, 2 if i >= 3 else 1, history)
                if is_bullish(c_i, o_i) and is_bearish(c_1, o_1) and is_bearish(c_2, o_2):
                    self._create_zone(bar_idx, base_idx, False, True, 1, 2 if i >= 3 else 1, history)

        # Demand: scan liquidity, check sweeps, mitigation (Pine-aligned)
        for i in range(len(self.demand_zones)):
            z = self.demand_zones[i]
            if not z.active or z.is_historical:
                continue
            if not (z.liquidity_valid and not z.liquidity_swept):
                self._scan_demand_liquidity(i, bar_idx, history)
            self._check_demand_sweeps(i, bar_idx, high, low, history)
            # Mitigation: kill zone if touched before sweep
            if not z.mitigated and bar_idx > z.created_bar_index:
                closes_inside = close <= z.top and close >= z.bottom
                breaches_zone = low < z.bottom
                wicks_into_zone = low <= z.top and low >= z.bottom
                current_bar_sweeping = (
                    not np.isnan(z.structure_sweep_level) and high > z.structure_sweep_level
                )
                if not z.liquidity_swept and (closes_inside or breaches_zone or wicks_into_zone) and not current_bar_sweeping:
                    z.mitigated = True
                    z.touched_pre_sweep = True

        # Supply: scan liquidity, check sweeps, mitigation (Pine-aligned)
        for i in range(len(self.supply_zones)):
            z = self.supply_zones[i]
            if not z.active or z.is_historical:
                continue
            if not (z.liquidity_valid and not z.liquidity_swept):
                self._scan_supply_liquidity(i, bar_idx, history)
            self._check_supply_sweeps(i, bar_idx, high, low, history)
            if not z.mitigated and bar_idx > z.created_bar_index:
                closes_inside = close >= z.bottom and close <= z.top
                breaches_zone = high > z.top
                wicks_into_zone = high >= z.bottom and high <= z.top
                current_bar_sweeping = (
                    not np.isnan(z.structure_sweep_level) and low < z.structure_sweep_level
                )
                if not z.liquidity_swept and (closes_inside or breaches_zone or wicks_into_zone) and not current_bar_sweeping:
                    z.mitigated = True
                    z.touched_pre_sweep = True

        # Zone invalidation (24h, close inside, wick)
        bar_time = bar.get("time")
        if bar_time is not None:
            if hasattr(bar_time, "to_pydatetime"):
                bar_time = bar_time.to_pydatetime()
            current_ts = int(pd.Timestamp(bar_time).timestamp())
        else:
            current_ts = 0
        HOURS_24_SEC = 24 * 60 * 60

        for i in range(len(self.demand_zones) - 1, -1, -1):
            z = self.demand_zones[i]
            if not z.active:
                continue
            is_too_old = z.start_time > 0 and (current_ts - z.start_time) > HOURS_24_SEC
            close_inside = close <= z.top and close >= z.bottom
            close_below = close < z.bottom
            wick_below = low < z.bottom
            if is_too_old or close_inside or close_below or (cfg.invalidate_on_wick and wick_below):
                self.demand_zones.pop(i)

        for i in range(len(self.supply_zones) - 1, -1, -1):
            z = self.supply_zones[i]
            if not z.active:
                continue
            is_too_old = z.start_time > 0 and (current_ts - z.start_time) > HOURS_24_SEC
            close_inside = close >= z.bottom and close <= z.top
            close_above = close > z.top
            wick_above = high > z.top
            if is_too_old or close_inside or close_above or (cfg.invalidate_on_wick and wick_above):
                self.supply_zones.pop(i)

    def on_bar(
        self,
        bar_idx: int,
        bar: pd.Series,
        history: pd.DataFrame,
        has_position: bool,
    ) -> List[Order]:
        """Generate orders for this bar. Called once per bar (calc_on_every_tick=False)."""
        cfg = self.config
        pip_size = cfg.pip_size
        tick_size = cfg.tick_size

        bar_time = bar["time"]
        if hasattr(bar_time, "to_pydatetime"):
            bar_time = bar_time.to_pydatetime()
        close = float(bar["close"])
        open_ = float(bar["open"])
        high = float(bar["high"])
        low = float(bar["low"])

        # Update daily trade count
        day_start = int(pd.Timestamp(bar_time).replace(hour=0, minute=0, second=0).timestamp())
        if self.last_trade_day is None or day_start != self.last_trade_day:
            self.current_day_trades = 0
            self.last_trade_day = day_start

        # Skip first N bars
        if bar_idx < cfg.min_bar_index_for_entries:
            return []

        # Time filters
        if cfg.filter_dead_zone and _is_time_dead_zone(bar_time):
            return []
        if cfg.filter_trading_hours and not _is_trading_hours(bar_time, cfg.trading_start_hour, cfg.trading_end_hour):
            return []
        if cfg.enable_trade_limit and self.current_day_trades >= cfg.max_trades_per_day:
            return []

        # Update zones
        self._update_zones(bar_idx, bar, history)

        if has_position:
            return []

        orders: List[Order] = []

        # Demand entry
        if cfg.trade_direction in ("Both", "Long Only"):
            for i, z in enumerate(self.demand_zones):
                # Pine: block historical zones
                if z.is_historical:
                    continue
                if z.mitigated or z.touched_pre_sweep:
                    continue
                if not z.active or not z.primed:
                    # Prime check: require liquidity_swept + target_swept + caused_sweep
                    if (
                        z.active
                        and not z.primed
                        and z.liquidity_swept
                        and z.target_swept
                        and z.caused_sweep
                    ):
                        # Demand: LOW must be INSIDE zone (z.bottom <= low <= z.top)
                        touch = (low >= z.bottom - tick_size) and (low <= z.top + tick_size)
                        if touch:
                            z.touch_count += 1
                            z.was_touched = True
                            z.last_touch_bar = bar_idx
                            if z.touch_count <= 1:
                                z.primed = True
                                z.primed_bar = bar_idx
                                z.primed_ref_close = close
                                z.primed_ref_high = high
                                z.primed_ref_low = low
                    continue

                # CRITICAL FIX: Verify current candle is still touching the zone before entry
                # Demand zone: candle LOW must be within zone bounds (allow 1 tick tolerance)
                zone_touch = (low >= z.bottom - tick_size) and (low <= z.top + tick_size)
                if not zone_touch:
                    continue  # Skip if current candle doesn't touch zone

                # CRITICAL FIX: Retrace Entry Block (from Pine lines 3769-3773)
                # Block entries if zone touched more than once (prevent overtrading weak zones)
                if z.touch_count > 1:
                    continue  # Skip - zone already retouched

                # 24h freshness (Pine: zoneIsFresh)
                current_ts = int(pd.Timestamp(bar_time).timestamp())
                if z.start_time > 0 and (current_ts - z.start_time) > 86400:
                    continue

                # Liquidity distance (Pine: checkLiquidityDistance) - skip for indices
                if not cfg.is_index() and cfg.liq_entry_max_dist > 0 and not np.isnan(z.liq_low_price):
                    dist_pips = abs(z.liq_low_price - z.top) / pip_size
                    pip_scale = 10.0 if cfg.is_gold() and pip_size <= 0.011 else 1.0
                    effective_max = cfg.liq_entry_max_dist * pip_scale
                    if dist_pips > effective_max:
                        continue

                # Entry models
                prev_close = _safe_get(history["close"], bar_idx - 1)
                prev_open = _safe_get(history["open"], bar_idx - 1)
                basic_flip = close > open_ and prev_close < prev_open
                is_flip = (basic_flip and _is_htf_candle_open(bar_time)) if cfg.require_htf_flip else basic_flip
                is_dir_close = close > open_
                is_break = (open_ > z.primed_ref_close or high > z.primed_ref_high) and close > open_ and not is_flip

                chosen = "FLIP" if is_flip else ("BREAK_CANDLE" if is_break else ("DIR_CLOSE" if is_dir_close else "NONE"))
                if chosen == "NONE":
                    continue

                # Quality filter
                if cfg.enable_ai_quality_filter and z.score < cfg.ai_quality_threshold:
                    continue
                if cfg.enable_grade_filter and get_grade_value(get_grade_from_score(z.score)) < get_grade_value(cfg.min_entry_grade):
                    continue

                # CRITICAL FIX: Entry price = current close (Pine line 3857)
                # Do NOT clamp to zone - Pine uses close directly
                entry_price = close

                # CRITICAL FIX: SL = deepest wick from 6 bars that touched zone (Pine lines 3859-3878)
                # Scan lookback bars for lowest wick that interacted with zone
                sl_buffer = cfg.stop_loss_buffer_pips * pip_size * (10.0 if cfg.is_gold() else 1.0)
                deepest_wick = None
                lookback = min(6, bar_idx)  # 6-bar lookback or less if near start
                for j in range(lookback):
                    idx = bar_idx - j
                    if idx < 0 or idx >= len(history):
                        continue
                    bar_high = float(history.iloc[idx]["high"])
                    bar_low = float(history.iloc[idx]["low"])
                    # Check if this bar touched the zone
                    if bar_high >= z.bottom and bar_low <= z.top:
                        if deepest_wick is None or bar_low < deepest_wick:
                            deepest_wick = bar_low

                # If no wick found (shouldn't happen), use current low
                if deepest_wick is None:
                    deepest_wick = low

                stop_loss_price = deepest_wick - sl_buffer

                # Safety clamp: ensure SL is below entry with minimum gap
                min_gap = 2.0 * pip_size  # Minimum 2 pips gap
                if stop_loss_price >= entry_price - min_gap:
                    stop_loss_price = entry_price - min_gap
                sl_pips = abs(entry_price - stop_loss_price) / pip_size
                tp_ratio = _get_tp_ratio_gold(sl_pips, cfg) if cfg.is_gold() else 2.0
                if cfg.use_custom_rr:
                    tp_ratio = cfg.risk_reward_ratio
                take_profit_price = entry_price + (entry_price - stop_loss_price) * tp_ratio

                balance = cfg.account_size_usd
                qty_raw = _calc_pos_size_units(entry_price, stop_loss_price, balance, cfg.risk_per_trade_pct, False, pip_size, cfg.symbol)
                qty_units = max(1, int(round(qty_raw)))
                qty_lots = units_to_lots(qty_units, cfg.symbol)
                if qty_lots > cfg.max_position_size_lots:
                    continue

                orders.append(Order(
                    side=OrderSide.LONG,
                    order_type=OrderType.ENTRY,
                    qty=qty_units,
                    stop_price=stop_loss_price,
                    limit_price=take_profit_price,
                    comment=chosen,
                    zone_bottom=z.bottom,
                    zone_top=z.top,
                ))
                z.active = False
                z.last_entry_bar = bar_idx
                self.current_day_trades += 1
                break

        # Supply entry
        if cfg.trade_direction in ("Both", "Short Only") and not orders:
            for i, z in enumerate(self.supply_zones):
                if z.is_historical:
                    continue
                if z.mitigated or z.touched_pre_sweep:
                    continue
                if not z.active or not z.primed:
                    if (
                        z.active
                        and not z.primed
                        and z.liquidity_swept
                        and z.target_swept
                        and z.caused_sweep
                    ):
                        # Supply: HIGH must be INSIDE zone (z.bottom <= high <= z.top)
                        touch = (high >= z.bottom - tick_size) and (high <= z.top + tick_size)
                        if touch:
                            z.touch_count += 1
                            z.was_touched = True
                            z.last_touch_bar = bar_idx
                            if z.touch_count <= 1:
                                z.primed = True
                                z.primed_bar = bar_idx
                                z.primed_ref_close = close
                                z.primed_ref_high = high
                                z.primed_ref_low = low
                    continue

                # CRITICAL FIX: Verify current candle is still touching the zone before entry
                # Supply zone: candle HIGH must be within zone bounds (allow 1 tick tolerance)
                zone_touch = (high >= z.bottom - tick_size) and (high <= z.top + tick_size)
                if not zone_touch:
                    continue  # Skip if current candle doesn't touch zone

                # CRITICAL FIX: Retrace Entry Block (from Pine lines 4214-4218)
                # Block entries if zone touched more than once (prevent overtrading weak zones)
                if z.touch_count > 1:
                    continue  # Skip - zone already retouched

                # 24h freshness (Pine: zoneIsFresh)
                current_ts = int(pd.Timestamp(bar_time).timestamp())
                if z.start_time > 0 and (current_ts - z.start_time) > 86400:
                    continue

                # Liquidity distance (Pine: checkLiquidityDistance) - skip for indices
                if not cfg.is_index() and cfg.liq_entry_max_dist > 0 and not np.isnan(z.liq_high_price):
                    dist_pips = abs(z.bottom - z.liq_high_price) / pip_size
                    pip_scale = 10.0 if cfg.is_gold() and pip_size <= 0.011 else 1.0
                    effective_max = cfg.liq_entry_max_dist * pip_scale
                    if dist_pips > effective_max:
                        continue

                prev_close = _safe_get(history["close"], bar_idx - 1)
                prev_open = _safe_get(history["open"], bar_idx - 1)
                basic_flip = close < open_ and prev_close > prev_open
                is_flip = (basic_flip and _is_htf_candle_open(bar_time)) if cfg.require_htf_flip else basic_flip
                is_dir_close = close < open_
                is_break = (open_ < z.primed_ref_close or low < z.primed_ref_low) and close < open_ and not is_flip

                chosen = "FLIP" if is_flip else ("BREAK_CANDLE" if is_break else ("DIR_CLOSE" if is_dir_close else "NONE"))
                if chosen == "NONE":
                    continue

                if cfg.enable_ai_quality_filter and z.score < cfg.ai_quality_threshold:
                    continue

                # CRITICAL FIX: Entry price = current close (Pine line 4302)
                # Do NOT clamp to zone - Pine uses close directly
                entry_price = close

                # CRITICAL FIX: SL = highest wick from 6 bars that touched zone (Pine lines 4304-4323)
                # Scan lookback bars for highest wick that interacted with zone
                sl_buffer = cfg.stop_loss_buffer_pips * pip_size * (10.0 if cfg.is_gold() else 1.0)
                highest_wick = None
                lookback = min(6, bar_idx)  # 6-bar lookback or less if near start
                for j in range(lookback):
                    idx = bar_idx - j
                    if idx < 0 or idx >= len(history):
                        continue
                    bar_high = float(history.iloc[idx]["high"])
                    bar_low = float(history.iloc[idx]["low"])
                    # Check if this bar touched the zone
                    if bar_high >= z.bottom and bar_low <= z.top:
                        if highest_wick is None or bar_high > highest_wick:
                            highest_wick = bar_high

                # If no wick found (shouldn't happen), use current high
                if highest_wick is None:
                    highest_wick = high

                stop_loss_price = highest_wick + sl_buffer

                # Safety clamp: ensure SL is above entry with minimum gap
                min_gap = 2.0 * pip_size  # Minimum 2 pips gap
                if stop_loss_price <= entry_price + min_gap:
                    stop_loss_price = entry_price + min_gap
                sl_pips = abs(stop_loss_price - entry_price) / pip_size
                tp_ratio = _get_tp_ratio_gold(sl_pips, cfg) if cfg.is_gold() else 2.0
                if cfg.use_custom_rr:
                    tp_ratio = cfg.risk_reward_ratio
                take_profit_price = entry_price - (stop_loss_price - entry_price) * tp_ratio

                balance = cfg.account_size_usd
                qty_raw = _calc_pos_size_units(entry_price, stop_loss_price, balance, cfg.risk_per_trade_pct, True, pip_size, cfg.symbol)
                qty_units = max(1, int(round(qty_raw)))
                qty_lots = units_to_lots(qty_units, cfg.symbol)
                if qty_lots > cfg.max_position_size_lots:
                    continue

                orders.append(Order(
                    side=OrderSide.SHORT,
                    order_type=OrderType.ENTRY,
                    qty=qty_units,
                    stop_price=stop_loss_price,
                    limit_price=take_profit_price,
                    comment=chosen,
                    zone_bottom=z.bottom,
                    zone_top=z.top,
                ))
                z.active = False
                z.last_entry_bar = bar_idx
                self.current_day_trades += 1
                break

        return orders
