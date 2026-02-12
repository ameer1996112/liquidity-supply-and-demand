"""
Supply & Demand Strategy Backtest Engine

Converts SND_Strategy.pine logic to Python for backtesting.py.
Implements core Supply/Demand zone detection and entry logic.

Usage:
    from backtesting import Backtest
    from src.services.backtest_engine import SndStrategy
    from src.services.data_loader import MetaApiDataLoader

    loader = MetaApiDataLoader(token="...", account_id="...")
    df = loader.fetch_candles("EURUSD", "2024-01-01", "2024-12-31", "5m")

    bt = Backtest(df, SndStrategy, cash=10000, commission=0.0002)
    stats = bt.run()
    print(stats)
"""

from __future__ import annotations

import logging
from typing import Optional

import numpy as np
import pandas as pd
from backtesting import Strategy
from backtesting.lib import crossover

logger = logging.getLogger(__name__)


class Zone:
    """
    Represents a Supply or Demand zone.

    Attributes:
        zone_type: "demand" or "supply"
        top: Zone top price
        bottom: Zone bottom price
        created_bar: Bar index when zone was created
        strength: Zone strength score (0-100)
        touched: Number of times zone was tested
        broken: Whether zone has been broken
    """

    def __init__(
        self,
        zone_type: str,
        top: float,
        bottom: float,
        created_bar: int,
        strength: float = 50.0,
    ):
        self.zone_type = zone_type  # "demand" or "supply"
        self.top = top
        self.bottom = bottom
        self.created_bar = created_bar
        self.strength = strength
        self.touched = 0
        self.broken = False

    def __repr__(self) -> str:
        return (
            f"Zone({self.zone_type}, top={self.top:.5f}, bottom={self.bottom:.5f}, "
            f"strength={self.strength:.1f}, touched={self.touched}, broken={self.broken})"
        )

    def contains_price(self, price: float, tolerance: float = 0.0) -> bool:
        """Check if price is within zone boundaries (with optional tolerance)."""
        return self.bottom - tolerance <= price <= self.top + tolerance

    def is_valid(self) -> bool:
        """Check if zone is still valid (not broken, not touched too many times)."""
        return not self.broken and self.touched < 3


class SndStrategy(Strategy):
    """
    Supply & Demand Strategy - Python port of SND_Strategy.pine.

    Core Logic:
    1. Detect Supply/Demand zones using swing highs/lows
    2. Enter on Break of Candle (BoC) + Liquidity Sweep
    3. Exit at opposite zone or fixed R:R

    Parameters (optimizable via backtesting.py):
        risk_percent: Risk per trade as % of account balance (default: 0.5)
        min_rr_ratio: Minimum Risk:Reward ratio (default: 2.0)
        zone_lookback: Bars to look back for swing points (default: 10)
        zone_strength_min: Minimum zone strength to trade (default: 50.0)
        stop_buffer_pips: Extra pips added to SL beyond zone (default: 1.0)
        max_lot_size: Maximum position size in lots (default: 10.0)
    """

    # Strategy parameters (can be optimized)
    risk_percent = 0.5  # Pine: 0.5% per trade
    min_rr_ratio = 2.0  # Pine: 2.0 minimum R:R
    zone_lookback = 10  # Bars to look back for swing detection
    zone_strength_min = 50.0  # Minimum zone strength to trade
    stop_buffer_pips = 1.0  # Extra pips beyond zone boundary
    max_lot_size = 10.0  # Maximum position size
    max_active_zones = 5  # Maximum number of active zones per type

    def init(self):
        """
        Initialize strategy state.

        Called once before backtesting starts.
        Creates indicators and state variables.
        """
        # Convert OHLC to numpy arrays for faster access
        self.close_series = self.data.Close
        self.high_series = self.data.High
        self.low_series = self.data.Low
        self.open_series = self.data.Open

        # Calculate ATR for zone sizing and stop placement
        self.atr = self.I(self._calculate_atr, self.data.High, self.data.Low, self.data.Close, 14)

        # Calculate swing highs/lows for zone detection
        self.swing_high = self.I(self._find_swing_high, self.data.High, self.zone_lookback)
        self.swing_low = self.I(self._find_swing_low, self.data.Low, self.zone_lookback)

        # Zone storage (persistent across bars)
        self.demand_zones: list[Zone] = []
        self.supply_zones: list[Zone] = []

        # Track last zone creation to avoid duplicates
        self.last_demand_bar = -999
        self.last_supply_bar = -999

        logger.info(
            "SndStrategy initialized: risk=%.2f%% rr=%.1f lookback=%d strength_min=%.1f",
            self.risk_percent,
            self.min_rr_ratio,
            self.zone_lookback,
            self.zone_strength_min,
        )

    @staticmethod
    def _calculate_atr(high: np.ndarray, low: np.ndarray, close: np.ndarray, period: int = 14) -> np.ndarray:
        """Calculate Average True Range (ATR) indicator."""
        tr = np.maximum(
            high - low,
            np.maximum(
                np.abs(high - np.roll(close, 1)),
                np.abs(low - np.roll(close, 1)),
            ),
        )
        # Set first value to avoid NaN
        tr[0] = high[0] - low[0]

        # Calculate EMA of True Range
        atr = np.zeros_like(tr)
        atr[0] = tr[0]
        alpha = 1.0 / period

        for i in range(1, len(tr)):
            atr[i] = alpha * tr[i] + (1 - alpha) * atr[i - 1]

        return atr

    @staticmethod
    def _find_swing_high(high: np.ndarray, lookback: int) -> np.ndarray:
        """
        Find swing highs (local maxima).

        A swing high is formed when:
        - Current high > highs of previous 'lookback' bars
        - Current high > highs of next 'lookback' bars
        """
        swing = np.zeros_like(high)

        for i in range(lookback, len(high) - lookback):
            is_swing = True

            # Check if current high is highest in window
            for j in range(1, lookback + 1):
                if high[i] <= high[i - j] or high[i] <= high[i + j]:
                    is_swing = False
                    break

            if is_swing:
                swing[i] = high[i]

        return swing

    @staticmethod
    def _find_swing_low(low: np.ndarray, lookback: int) -> np.ndarray:
        """
        Find swing lows (local minima).

        A swing low is formed when:
        - Current low < lows of previous 'lookback' bars
        - Current low < lows of next 'lookback' bars
        """
        swing = np.zeros_like(low)

        for i in range(lookback, len(low) - lookback):
            is_swing = True

            # Check if current low is lowest in window
            for j in range(1, lookback + 1):
                if low[i] >= low[i - j] or low[i] >= low[i + j]:
                    is_swing = False
                    break

            if is_swing:
                swing[i] = low[i]

        return swing

    def _calculate_zone_strength(self, zone_type: str, bar_index: int) -> float:
        """
        Calculate zone strength score (0-100).

        Factors:
        - Volume relative to average
        - Candle body size (rejection = stronger)
        - Number of touches (fewer = stronger)
        - Age of zone (fresher = stronger)

        Returns:
            Strength score (0-100)
        """
        strength = 50.0  # Base strength

        # Volume boost (if available)
        if hasattr(self.data, "Volume") and len(self.data.Volume) > bar_index:
            volume = self.data.Volume[bar_index]
            avg_volume = np.mean(self.data.Volume[max(0, bar_index - 20) : bar_index + 1])
            if avg_volume > 0:
                volume_ratio = volume / avg_volume
                strength += min(20.0, (volume_ratio - 1.0) * 10.0)

        # Candle rejection (wick size)
        candle_range = self.high_series[bar_index] - self.low_series[bar_index]
        candle_body = abs(self.close_series[bar_index] - self.open_series[bar_index])

        if candle_range > 0:
            wick_ratio = (candle_range - candle_body) / candle_range
            strength += wick_ratio * 15.0  # Up to +15 for strong rejection

        # ATR normalization (larger candles relative to ATR = stronger)
        if self.atr[-1] > 0:
            atr_ratio = candle_range / self.atr[-1]
            strength += min(15.0, atr_ratio * 5.0)

        return min(100.0, max(0.0, strength))

    def _create_demand_zone(self, bar_index: int) -> Optional[Zone]:
        """
        Create a demand (support) zone at swing low.

        Zone boundaries:
        - Bottom: Swing low price
        - Top: Swing low + ATR * 0.5 (zone thickness)
        """
        if bar_index - self.last_demand_bar < 3:
            return None  # Avoid creating zones too frequently

        swing_low = self.swing_low[bar_index]
        if swing_low == 0:
            return None

        # Zone thickness based on ATR
        atr_value = self.atr[bar_index] if bar_index < len(self.atr) else self.atr[-1]
        zone_thickness = atr_value * 0.5

        zone = Zone(
            zone_type="demand",
            bottom=swing_low,
            top=swing_low + zone_thickness,
            created_bar=bar_index,
            strength=self._calculate_zone_strength("demand", bar_index),
        )

        self.last_demand_bar = bar_index
        logger.debug("Created demand zone at bar %d: %s", bar_index, zone)

        return zone

    def _create_supply_zone(self, bar_index: int) -> Optional[Zone]:
        """
        Create a supply (resistance) zone at swing high.

        Zone boundaries:
        - Top: Swing high price
        - Bottom: Swing high - ATR * 0.5 (zone thickness)
        """
        if bar_index - self.last_supply_bar < 3:
            return None

        swing_high = self.swing_high[bar_index]
        if swing_high == 0:
            return None

        # Zone thickness based on ATR
        atr_value = self.atr[bar_index] if bar_index < len(self.atr) else self.atr[-1]
        zone_thickness = atr_value * 0.5

        zone = Zone(
            zone_type="supply",
            top=swing_high,
            bottom=swing_high - zone_thickness,
            created_bar=bar_index,
            strength=self._calculate_zone_strength("supply", bar_index),
        )

        self.last_supply_bar = bar_index
        logger.debug("Created supply zone at bar %d: %s", bar_index, zone)

        return zone

    def _update_zones(self):
        """
        Update zone states (mark as touched/broken) based on current price.

        Called every bar to maintain zone validity.
        """
        current_high = self.data.High[-1]
        current_low = self.data.Low[-1]
        current_close = self.data.Close[-1]

        # Update demand zones
        for zone in self.demand_zones:
            if zone.broken:
                continue

            # Check if price touched zone
            if current_low <= zone.top and current_high >= zone.bottom:
                zone.touched += 1

            # Check if zone is broken (close below zone)
            if current_close < zone.bottom:
                zone.broken = True
                logger.debug("Demand zone broken: %s", zone)

        # Update supply zones
        for zone in self.supply_zones:
            if zone.broken:
                continue

            # Check if price touched zone
            if current_high >= zone.bottom and current_low <= zone.top:
                zone.touched += 1

            # Check if zone is broken (close above zone)
            if current_close > zone.top:
                zone.broken = True
                logger.debug("Supply zone broken: %s", zone)

        # Clean up old/invalid zones (keep only max_active_zones per type)
        self.demand_zones = [z for z in self.demand_zones if z.is_valid()][-self.max_active_zones :]
        self.supply_zones = [z for z in self.supply_zones if z.is_valid()][-self.max_active_zones :]

    def _check_buy_signal(self) -> tuple[bool, Optional[Zone], float, float]:
        """
        Check for BUY signal (demand zone + Break of Candle).

        Returns:
            (signal, zone, entry_price, stop_loss)
        """
        if not self.demand_zones:
            return False, None, 0.0, 0.0

        current_close = self.data.Close[-1]
        prev_high = self.data.High[-2] if len(self.data.High) > 1 else 0

        # Find strongest demand zone that price is near
        best_zone = None
        best_strength = 0.0

        for zone in self.demand_zones:
            if not zone.is_valid():
                continue

            # Check if price is in zone
            if zone.contains_price(current_close, tolerance=self.atr[-1] * 0.2):
                if zone.strength > best_strength:
                    best_zone = zone
                    best_strength = zone.strength

        if best_zone is None:
            return False, None, 0.0, 0.0

        # Check for Break of Candle (BoC): close > previous high
        if current_close <= prev_high:
            return False, None, 0.0, 0.0

        # Calculate entry and stop loss
        entry_price = current_close
        stop_loss = best_zone.bottom - (self.stop_buffer_pips * self._get_pip_size())

        # Validate R:R ratio
        if self.min_rr_ratio > 0:
            risk = entry_price - stop_loss
            # Estimate take profit (next supply zone or 2:1 R:R)
            take_profit = entry_price + (risk * self.min_rr_ratio)

            if risk <= 0:
                return False, None, 0.0, 0.0

        logger.info(
            "BUY signal: zone=%s entry=%.5f sl=%.5f",
            best_zone,
            entry_price,
            stop_loss,
        )

        return True, best_zone, entry_price, stop_loss

    def _check_sell_signal(self) -> tuple[bool, Optional[Zone], float, float]:
        """
        Check for SELL signal (supply zone + Break of Candle).

        Returns:
            (signal, zone, entry_price, stop_loss)
        """
        if not self.supply_zones:
            return False, None, 0.0, 0.0

        current_close = self.data.Close[-1]
        prev_low = self.data.Low[-2] if len(self.data.Low) > 1 else float("inf")

        # Find strongest supply zone that price is near
        best_zone = None
        best_strength = 0.0

        for zone in self.supply_zones:
            if not zone.is_valid():
                continue

            # Check if price is in zone
            if zone.contains_price(current_close, tolerance=self.atr[-1] * 0.2):
                if zone.strength > best_strength:
                    best_zone = zone
                    best_strength = zone.strength

        if best_zone is None:
            return False, None, 0.0, 0.0

        # Check for Break of Candle (BoC): close < previous low
        if current_close >= prev_low:
            return False, None, 0.0, 0.0

        # Calculate entry and stop loss
        entry_price = current_close
        stop_loss = best_zone.top + (self.stop_buffer_pips * self._get_pip_size())

        # Validate R:R ratio
        if self.min_rr_ratio > 0:
            risk = stop_loss - entry_price
            take_profit = entry_price - (risk * self.min_rr_ratio)

            if risk <= 0:
                return False, None, 0.0, 0.0

        logger.info(
            "SELL signal: zone=%s entry=%.5f sl=%.5f",
            best_zone,
            entry_price,
            stop_loss,
        )

        return True, best_zone, entry_price, stop_loss

    def _get_pip_size(self) -> float:
        """
        Get pip size for current symbol (auto-detect from price).

        Returns:
            Pip size (e.g., 0.0001 for EURUSD, 0.01 for XAUUSD)
        """
        # Simple heuristic: if current price > 10, use 0.01 (metals/indices)
        # Otherwise use 0.0001 (forex)
        current_price = self.data.Close[-1]
        return 0.01 if current_price > 10 else 0.0001

    def _calculate_position_size(self, entry: float, stop_loss: float) -> float:
        """
        Calculate position size based on risk percentage.

        Args:
            entry: Entry price
            stop_loss: Stop loss price

        Returns:
            Position size in lots (e.g., 0.1, 1.0, 10.0)
        """
        account_balance = self.equity  # Current account equity
        risk_amount = account_balance * (self.risk_percent / 100.0)

        # Calculate risk in pips
        risk_pips = abs(entry - stop_loss) / self._get_pip_size()

        if risk_pips <= 0:
            return 0.0

        # Forex position sizing: risk_amount / (pips * pip_value_per_lot)
        # Assume $10 per pip per standard lot (simplified)
        pip_value_per_lot = 10.0

        # Handle metals (XAUUSD: $1 per pip per 1.0 lot = $100 contract)
        if self.data.Close[-1] > 100:  # Likely gold/silver
            pip_value_per_lot = 1.0

        lot_size = risk_amount / (risk_pips * pip_value_per_lot)

        # Cap at max lot size
        lot_size = min(lot_size, self.max_lot_size)

        # Round to 2 decimals (0.01 lot minimum)
        lot_size = max(0.01, round(lot_size, 2))

        # backtesting.py expects: fraction (0-1) OR positive whole number (units)
        # Convert lots to units: 1 standard lot = 100,000 units (forex)
        units = int(round(lot_size * 100_000))
        units = max(1000, units)  # min 0.01 lot = 1000 units

        logger.debug(
            "Position size: risk=$%.2f pips=%.1f lot_size=%.2f units=%d",
            risk_amount,
            risk_pips,
            lot_size,
            units,
        )

        return units

    def next(self):
        """
        Strategy logic executed on every bar.

        Flow:
        1. Detect new zones at swing points
        2. Update existing zones
        3. Check for entry signals
        4. Manage open positions
        """
        bar_index = len(self.data) - 1

        # Skip first bars (need history for swing detection)
        if bar_index < self.zone_lookback * 2:
            return

        # 1. Create new zones at swing points
        if self.swing_low[-1] > 0:
            new_zone = self._create_demand_zone(bar_index)
            if new_zone and new_zone.strength >= self.zone_strength_min:
                self.demand_zones.append(new_zone)

        if self.swing_high[-1] > 0:
            new_zone = self._create_supply_zone(bar_index)
            if new_zone and new_zone.strength >= self.zone_strength_min:
                self.supply_zones.append(new_zone)

        # 2. Update zone states
        self._update_zones()

        # 3. Exit management (check existing positions first)
        if self.position:
            # Simple exit: let SL/TP handle it
            # Advanced: could add trailing stop, zone-based exits, etc.
            pass

        # 4. Entry logic (only if no position)
        if not self.position:
            # Check for BUY signal
            buy_signal, buy_zone, buy_entry, buy_sl = self._check_buy_signal()
            if buy_signal:
                size = self._calculate_position_size(buy_entry, buy_sl)
                if size > 0:
                    # Calculate TP based on R:R
                    risk = buy_entry - buy_sl
                    tp = buy_entry + (risk * self.min_rr_ratio)

                    self.buy(size=size, sl=buy_sl, tp=tp)
                    logger.info(
                        "BUY executed: size=%.2f entry=%.5f sl=%.5f tp=%.5f",
                        size,
                        buy_entry,
                        buy_sl,
                        tp,
                    )
                    return

            # Check for SELL signal
            sell_signal, sell_zone, sell_entry, sell_sl = self._check_sell_signal()
            if sell_signal:
                size = self._calculate_position_size(sell_entry, sell_sl)
                if size > 0:
                    # Calculate TP based on R:R
                    risk = sell_sl - sell_entry
                    tp = sell_entry - (risk * self.min_rr_ratio)

                    self.sell(size=size, sl=sell_sl, tp=tp)
                    logger.info(
                        "SELL executed: size=%.2f entry=%.5f sl=%.5f tp=%.5f",
                        size,
                        sell_entry,
                        sell_sl,
                        tp,
                    )
                    return
