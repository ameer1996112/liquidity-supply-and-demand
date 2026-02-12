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
    Represents a Supply or Demand zone (Pine Script SND_Core.Zone port).

    This is a faithful port of the Pine Script Zone type with all fields
    required for liquidity-based institutional trading logic.

    Core Attributes:
        zone_type: "demand" or "supply"
        top: Zone top price
        bottom: Zone bottom price
        created_bar: Bar index when zone was created
        active: Trading status
        is_historical: Created during backfill scan

    Liquidity Structure:
        liquidity_price: Inducement level
        liquidity_bar_index: Bar where inducement detected
        liquidity_valid: 3-candle pivot confirmed
        liquidity_swept: Inducement taken by price
        liquidity_swept_bar_index: Bar when inducement swept
        caused_sweep: Zone impulse triggered the sweep
        structure_sweep_level: Target HIGH (demand) or LOW (supply)
        liq_high_price: For demand: target; For supply: inducement
        liq_high_bar: Bar index of liq_high
        liq_low_price: For supply: target; For demand: inducement
        liq_low_bar: Bar index of liq_low
        liq_source: Detection method ("PIVOT", "FALLBACK_SCAN", "LOW_FIRST_BACKWARD")
        target_swept: Target swept (must happen AFTER inducement)
        target_swept_bar_index: Bar when target swept
        leg_candle_count: Count of directional candles in leg
        push_high_price: For demand: push HIGH before retracement
        push_high_bar: Bar index of push high
        inactive_reason: Reason zone was invalidated

    Trading State:
        last_entry_bar: Zone used for trade
        mitigated: Zone broken before setup complete
        mitigation_time: When mitigated
        left_zone: Price left zone after touch
        left_with_bearish: Left with bearish candle (demand zones)
        primed: Zone ready for entry on next valid candle
        primed_bar: Bar index when primed
        primed_wick_level: Deepest wick of priming candle (for flip SL)
        primed_ref_close: Close of priming candle (for BoC)
        primed_ref_high: High of priming candle (for BoC)
        primed_ref_low: Low of priming candle (for BoC)
        was_touched: True when touched by wick
        touch_count: Number of times touched
        last_touch_bar: Bar index of last touch
        touched_pre_sweep: Touched BEFORE liquidity swept (THE INDUCEMENT RULE)

    Quality Metrics (V6/V7 AI Features):
        base_quality: Quality of base construction (0-100)
        departure_strength: Strength of departure from zone (0-100)
        liquidity_distance: Distance from zone to liquidity in pips (0-100)
        liquidity_spread: Spread between inducement and target in pips (0-100)
        return_strength: Strength of return to zone after sweep (0-100)
        is_accuracy: Accuracy zone flag (high-precision)
        score: Zone Quality Score (0-100)
        grade: Zone Grade ("A+", "A", "B+", "B", "C+", "C")

    Reference: SND_Core.pine lines 19-84
    """

    def __init__(
        self,
        zone_type: str,
        top: float,
        bottom: float,
        created_bar: int,
        strength: float = 50.0,
        zone_id: int = 0,
        is_historical: bool = False,
    ):
        # Core attributes
        self.id = zone_id
        self.zone_type = zone_type  # "demand" or "supply"
        self.top = top
        self.bottom = bottom
        self.created_bar = created_bar
        self.active = True
        self.is_historical = is_historical
        self.start_time: Optional[int] = None

        # Liquidity structure
        self.liquidity_price: Optional[float] = None
        self.liquidity_bar_index: Optional[int] = None
        self.liquidity_valid: bool = False
        self.liquidity_swept: bool = False
        self.liquidity_swept_bar_index: Optional[int] = None
        self.caused_sweep: bool = False
        self.liquidity_candle_count: int = 0
        self.structure_sweep_level: Optional[float] = None
        self.structure_sweep_level_bar: Optional[int] = None
        self.liq_high_price: Optional[float] = None
        self.liq_high_bar: Optional[int] = None
        self.liq_high_time: Optional[int] = None
        self.liq_low_price: Optional[float] = None
        self.liq_low_bar: Optional[int] = None
        self.liq_low_time: Optional[int] = None
        self.liq_source: Optional[str] = None  # "PIVOT" | "FALLBACK_SCAN" | "LOW_FIRST_BACKWARD"
        self.target_swept: bool = False
        self.target_swept_bar_index: Optional[int] = None
        self.leg_candle_count: int = 0
        self.push_high_price: Optional[float] = None
        self.push_high_bar: Optional[int] = None
        self.inactive_reason: Optional[str] = None

        # Trading state
        self.last_entry_bar: Optional[int] = None
        self.mitigated: bool = False
        self.mitigation_time: Optional[int] = None
        self.left_zone: bool = False
        self.left_with_bearish: bool = False
        self.primed: bool = False
        self.primed_bar: Optional[int] = None
        self.primed_wick_level: Optional[float] = None
        self.primed_ref_close: Optional[float] = None
        self.primed_ref_high: Optional[float] = None
        self.primed_ref_low: Optional[float] = None
        self.was_touched: bool = False
        self.touch_count: int = 0
        self.last_touch_bar: Optional[int] = None
        self.touched_pre_sweep: bool = False

        # Quality metrics (V6/V7 AI features)
        self.base_quality: float = 50.0
        self.departure_strength: float = 50.0
        self.liquidity_distance: float = 0.0
        self.liquidity_spread: float = 0.0
        self.return_strength: float = 0.0
        self.is_accuracy: bool = False
        self.score: float = strength  # Use provided strength as initial score
        self.grade: str = "C"  # Default grade

        # Legacy fields (for backward compatibility)
        self.strength = strength
        self.touched = 0  # Alias for touch_count
        self.broken = False  # Alias for !active

    def __repr__(self) -> str:
        return (
            f"Zone(id={self.id}, {self.zone_type}, top={self.top:.5f}, bottom={self.bottom:.5f}, "
            f"score={self.score:.1f}, grade={self.grade}, liq_swept={self.liquidity_swept}, "
            f"target_swept={self.target_swept}, touched={self.touch_count}, active={self.active})"
        )

    def contains_price(self, price: float, tolerance: float = 0.0) -> bool:
        """Check if price is within zone boundaries (with optional tolerance)."""
        return self.bottom - tolerance <= price <= self.top + tolerance

    def is_valid(self) -> bool:
        """
        Check if zone is still valid for trading.

        Valid if:
        - Active (not broken/mitigated/invalidated)
        - Not touched too many times (< 3)
        - Not touched before sweep (inducement rule)
        """
        return self.active and not self.touched_pre_sweep and self.touch_count < 3


class SndStrategy(Strategy):
    """
    Supply & Demand Strategy - Python port of SND_Strategy.pine with AI Guardian.

    Core Logic:
    1. Detect Supply/Demand zones using swing highs/lows
    2. Enter on Break of Candle (BoC) + AI Guardian filters
    3. Exit at opposite zone or fixed R:R

    AI Guardian Features (Pine Script v5.1):
    - Liquidity Sweep Detection: Confirms institutional liquidity grab before reversal
    - Arrival Type Analysis: Filters slow/grinding arrivals (Compression)
    - Market Structure Break: Validates BOS/CHoCH patterns

    Parameters (optimizable via backtesting.py):
        risk_percent: Risk per trade as % of account balance (default: 0.5)
        min_rr_ratio: Minimum Risk:Reward ratio (default: 2.0)
        zone_lookback: Bars to look back for swing points (default: 10)
        zone_strength_min: Minimum zone strength to trade (default: 50.0)
        stop_buffer_pips: Extra pips added to SL beyond zone (default: 1.0)
        max_lot_size: Maximum position size in lots (default: 10.0)

        # AI Guardian filters (new)
        require_liquidity_sweep: Require liquidity sweep before entry (default: False)
        reject_compression_arrival: Reject slow arrivals (default: True)
        require_structure_break: Require market structure break (default: False)
    """

    # Strategy parameters (can be optimized)
    risk_percent = 0.5  # Pine: 0.5% per trade
    min_rr_ratio = 2.0  # Pine: 2.0 minimum R:R
    zone_lookback = 10  # Bars to look back for swing detection
    zone_strength_min = 50.0  # Minimum zone strength to trade
    stop_buffer_pips = 1.0  # Extra pips beyond zone boundary
    max_lot_size = 10.0  # Maximum position size
    max_active_zones = 5  # Maximum number of active zones per type
    max_bars_in_trade = 0  # Max bars before auto-exit (0=disabled, Pine default: varies by timeframe)

    # AI Guardian filters (Pine Script v5.1 features)
    require_liquidity_sweep = False  # Require liquidity sweep before entry (default: off for flexibility)
    reject_compression_arrival = True  # Reject slow/grinding arrivals (default: on for quality)
    require_structure_break = False  # Require market structure break (default: off)

    # Liquidity Detection Parameters (Phase 2)
    liq_pivot_len = 2  # Williams Fractal period (2 = 3-candle pivot)
    liq_max_distance_pips = 15.0  # Max distance for liquidity (forex: 15, gold: 300)
    liq_entry_max_dist = 50.0  # Max zone-to-liq distance at entry

    # Zone Quality Parameters (Phase 1)
    ai_quality_threshold = 60  # Minimum AI score (0-100)
    min_entry_grade = "C+"  # Minimum grade (A+, A, B+, B, C+, C)
    min_return_strength = 0  # Minimum return strength (0-100, 0=disabled)

    # Entry Model Selection (Phase 3)
    entry_model = "AUTO"  # "FLIP", "DIR_CLOSE", "BOC", or "AUTO"

    # Symbol information (for symbol-specific logic)
    symbol = "EURUSD"  # Default symbol, should be set during init

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

    @staticmethod
    def _find_pivot_high(high: np.ndarray, period: int = 2) -> np.ndarray:
        """
        Detect swing highs using Williams Fractals (for liquidity detection).

        A pivot high is formed when:
        - high[i] > high[i-period:i] (higher than all previous 'period' bars)
        - high[i] > high[i+1:i+period+1] (higher than all next 'period' bars)

        This is stricter than basic swing detection and is used for identifying
        liquidity levels (inducement/target) rather than zone creation.

        Args:
            high: Array of high prices
            period: Number of bars on each side to compare (default: 2)
                   period=2 means 5-candle pattern: [left2, left1, CENTER, right1, right2]

        Returns:
            Array of pivot high prices (0 where no pivot detected)

        Reference:
            Pine Script: SND_Strategy.pine liquidity scanning functions
            ta.pivothigh() with period=2 (default for liquidity detection)
        """
        pivot = np.zeros_like(high)

        # Need at least 'period' bars on each side
        for i in range(period, len(high) - period):
            is_pivot = True

            # Check if current high is greater than all bars in window
            # Left side: high[i] > high[i-period:i]
            for j in range(1, period + 1):
                if high[i] <= high[i - j]:
                    is_pivot = False
                    break

            # Right side: high[i] > high[i+1:i+period+1]
            if is_pivot:
                for j in range(1, period + 1):
                    if high[i] <= high[i + j]:
                        is_pivot = False
                        break

            if is_pivot:
                pivot[i] = high[i]

        return pivot

    @staticmethod
    def _find_pivot_low(low: np.ndarray, period: int = 2) -> np.ndarray:
        """
        Detect swing lows using Williams Fractals (for liquidity detection).

        A pivot low is formed when:
        - low[i] < low[i-period:i] (lower than all previous 'period' bars)
        - low[i] < low[i+1:i+period+1] (lower than all next 'period' bars)

        This is stricter than basic swing detection and is used for identifying
        liquidity levels (inducement/target) rather than zone creation.

        Args:
            low: Array of low prices
            period: Number of bars on each side to compare (default: 2)
                   period=2 means 5-candle pattern: [left2, left1, CENTER, right1, right2]

        Returns:
            Array of pivot low prices (0 where no pivot detected)

        Reference:
            Pine Script: SND_Strategy.pine liquidity scanning functions
            ta.pivotlow() with period=2 (default for liquidity detection)
        """
        pivot = np.zeros_like(low)

        # Need at least 'period' bars on each side
        for i in range(period, len(low) - period):
            is_pivot = True

            # Check if current low is less than all bars in window
            # Left side: low[i] < low[i-period:i]
            for j in range(1, period + 1):
                if low[i] >= low[i - j]:
                    is_pivot = False
                    break

            # Right side: low[i] < low[i+1:i+period+1]
            if is_pivot:
                for j in range(1, period + 1):
                    if low[i] >= low[i + j]:
                        is_pivot = False
                        break

            if is_pivot:
                pivot[i] = low[i]

        return pivot

    @staticmethod
    def _is_makuchaku_pivot_high(high: np.ndarray, idx: int) -> bool:
        """
        Check if bar at index is a Makuchaku 3-candle pivot high (STRICT).

        Makuchaku pivot high: high[idx] > high[idx-1] AND high[idx] > high[idx+1]

        This is STRICTER than Williams Fractals - requires only 1 bar on each side
        instead of 2. Used for tighter liquidity level detection.

        Args:
            high: Array of high prices
            idx: Bar index to check

        Returns:
            True if bar is a 3-candle pivot high, False otherwise

        Reference:
            Pine Script: SND_Core.pine lines 562-567 (makuchakuPivotHigh helper)
        """
        # Need at least 1 bar on each side
        if idx < 1 or idx >= len(high) - 1:
            return False

        # 3-candle pattern: [left, CENTER, right]
        # CENTER must be higher than BOTH neighbors
        return high[idx] > high[idx - 1] and high[idx] > high[idx + 1]

    @staticmethod
    def _is_makuchaku_pivot_low(low: np.ndarray, idx: int) -> bool:
        """
        Check if bar at index is a Makuchaku 3-candle pivot low (STRICT).

        Makuchaku pivot low: low[idx] < low[idx-1] AND low[idx] < low[idx+1]

        This is STRICTER than Williams Fractals - requires only 1 bar on each side
        instead of 2. Used for tighter liquidity level detection.

        Args:
            low: Array of low prices
            idx: Bar index to check

        Returns:
            True if bar is a 3-candle pivot low, False otherwise

        Reference:
            Pine Script: SND_Core.pine lines 568-571 (makuchakuPivotLow helper)
        """
        # Need at least 1 bar on each side
        if idx < 1 or idx >= len(low) - 1:
            return False

        # 3-candle pattern: [left, CENTER, right]
        # CENTER must be lower than BOTH neighbors
        return low[idx] < low[idx - 1] and low[idx] < low[idx + 1]

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

    def _calculate_zone_score(self, zone: Zone, bar_index: int) -> float:
        """
        Calculate comprehensive zone quality score (0-100) matching Pine Script logic.

        Scoring Components (each worth 20 points max):
        1. Trend Alignment: Zone aligned with trend direction
        2. Strength of Move: Accuracy/leg count from zone
        3. Base Quality: Number of candles in zone base
        4. Liquidity: Presence and sweep status
        5. Freshness: Session timing and touch count

        Args:
            zone: Zone object to score
            bar_index: Current bar index for context

        Returns:
            Score from 0-100

        Reference:
            Pine Script: SND_Core.pine lines 147-215 (calc_zone_score)
        """
        score = 0.0

        # 1. TREND ALIGNMENT (20 pts max)
        # Zone aligned with trend gets full points
        if zone.zone_type == "demand" and self._is_uptrend(bar_index):
            score += 20.0
        elif zone.zone_type == "supply" and self._is_downtrend(bar_index):
            score += 20.0
        # No points for counter-trend zones

        # 2. STRENGTH OF MOVE (20 pts max)
        # Accuracy zones (single strong candle) = 20 pts
        # Multi-leg zones (3+ candles) = 15 pts
        # Simple zones = 10 pts
        if zone.is_accuracy:
            score += 20.0
        elif zone.leg_candle_count >= 3:
            score += 15.0
        else:
            score += 10.0

        # 3. BASE QUALITY (20 pts max)
        # Fewer candles in base = better quality
        # 1-2 candles = 20 pts (tight base)
        # 3-4 candles = 10 pts (acceptable)
        # 5+ candles = 5 pts (loose base)
        base_candle_count = getattr(zone, "base_candle_count", 2)  # Default to 2 if not set
        if base_candle_count <= 2:
            score += 20.0
        elif base_candle_count <= 4:
            score += 10.0
        else:
            score += 5.0

        # 4. LIQUIDITY (20 pts max)
        # Liquidity swept = 20 pts (best - institutional grab confirmed)
        # Liquidity present = 10 pts (good - setup exists)
        # No liquidity = 0 pts
        if zone.liquidity_swept:
            score += 20.0
        elif zone.liquidity_valid:
            score += 10.0

        # 5. FRESHNESS (20 pts max)
        # Session bonus: London/NY = 10 pts, Asia = 5 pts
        # Touch bonus: Fresh zone (0 touches) = 10 pts
        session_score = self._get_session_score(bar_index)
        score += session_score

        # Touch count penalty (fewer touches = fresher)
        if zone.touch_count == 0:
            score += 10.0
        elif zone.touch_count == 1:
            score += 5.0
        # No points for 2+ touches

        return min(100.0, max(0.0, score))

    def _get_grade_from_score(self, score: float) -> str:
        """
        Convert numeric score (0-100) to letter grade.

        Grade Scale:
        - A+ (90-100): Exceptional quality
        - A  (80-89): High quality
        - B+ (70-79): Good quality
        - B  (60-69): Acceptable quality
        - C+ (50-59): Marginal quality
        - C  (<50): Poor quality

        Args:
            score: Numeric score (0-100)

        Returns:
            Letter grade string

        Reference:
            Pine Script: SND_Core.pine lines 116-128
        """
        if score >= 90.0:
            return "A+"
        elif score >= 80.0:
            return "A"
        elif score >= 70.0:
            return "B+"
        elif score >= 60.0:
            return "B"
        elif score >= 50.0:
            return "C+"
        else:
            return "C"

    def _is_uptrend(self, bar_index: int) -> bool:
        """
        Check if price is in an uptrend at given bar.

        Simple trend detection using 20-period moving average:
        - Uptrend: Close > MA(20)

        Args:
            bar_index: Bar index to check

        Returns:
            True if uptrend, False otherwise
        """
        if bar_index < 20:
            return True  # Not enough data, assume neutral/up

        # Calculate 20-period SMA
        lookback_start = max(0, bar_index - 20)
        ma_20 = np.mean(self.close_series[lookback_start : bar_index + 1])

        return self.close_series[bar_index] > ma_20

    def _is_downtrend(self, bar_index: int) -> bool:
        """
        Check if price is in a downtrend at given bar.

        Simple trend detection using 20-period moving average:
        - Downtrend: Close < MA(20)

        Args:
            bar_index: Bar index to check

        Returns:
            True if downtrend, False otherwise
        """
        if bar_index < 20:
            return False  # Not enough data, assume neutral

        # Calculate 20-period SMA
        lookback_start = max(0, bar_index - 20)
        ma_20 = np.mean(self.close_series[lookback_start : bar_index + 1])

        return self.close_series[bar_index] < ma_20

    def _get_session_score(self, bar_index: int) -> float:
        """
        Calculate session bonus score based on time of day.

        Forex sessions (UTC):
        - London: 07:00 - 16:00 (10 pts - high liquidity)
        - New York: 12:00 - 21:00 (10 pts - high liquidity)
        - Asia: 00:00 - 09:00 (5 pts - lower liquidity)
        - Other: 21:00 - 00:00 (5 pts - low liquidity)

        Args:
            bar_index: Bar index to check

        Returns:
            Session score (5 or 10 points)

        Note:
            Currently returns default 10 pts as we don't have timestamp data.
            TODO: Extract hour from candle timestamps when available.
        """
        # TODO: Extract hour from self.data.index[bar_index] if timestamps available
        # For now, assume London/NY session (best quality)
        return 10.0

    def _calculate_base_quality(self, zone: Zone, bar_index: int) -> float:
        """
        Calculate base quality metric (0-100): % of decisive candles in zone base.

        Analyzes the candles that form the zone base (the consolidation before
        the impulse move). Higher quality bases have more decisive candles
        (large bodies, low indecision).

        Indecision = candle body < 30% of candle range (small body, long wicks)

        Args:
            zone: Zone to analyze
            bar_index: Current bar index

        Returns:
            Quality score 0-100 (100 = all decisive candles)

        Reference:
            Pine Script: SND_Core.pine lines 315-375 (calc_base_quality)
        """
        # Look back at last 5 candles before zone creation
        base_start = max(0, zone.created_bar - 5)
        base_end = zone.created_bar

        if base_end <= base_start:
            return 50.0  # Default if not enough data

        indecisive_count = 0
        total_count = base_end - base_start

        for i in range(base_start, base_end):
            candle_range = self.high_series[i] - self.low_series[i]
            candle_body = abs(self.close_series[i] - self.open_series[i])

            # Check for indecision (body < 30% of range)
            if candle_range > 0 and (candle_body / candle_range) < 0.3:
                indecisive_count += 1

        # Quality = (1 - indecisive_ratio) * 100
        indecisive_ratio = indecisive_count / total_count if total_count > 0 else 0
        quality = (1.0 - indecisive_ratio) * 100.0

        return quality

    def _calculate_departure_strength(self, zone: Zone, bar_index: int) -> float:
        """
        Calculate departure strength (0-100): How aggressively price left the zone.

        Analyzes the first 3 candles after zone creation to measure the strength
        of the impulse move away from the zone. Stronger departures indicate
        stronger institutional interest.

        Factors:
        - Body size relative to ATR (50% weight)
        - Volume relative to average (50% weight)

        Args:
            zone: Zone to analyze
            bar_index: Current bar index

        Returns:
            Strength score 0-100 (100 = strongest departure)

        Reference:
            Pine Script: SND_Core.pine lines 377-425 (calc_departure_strength)
        """
        # Analyze first 3 candles after zone creation
        dep_start = zone.created_bar + 1
        dep_end = min(len(self.close_series), zone.created_bar + 4)

        # Need at least 1 bar after zone creation
        if dep_end <= dep_start or dep_start >= len(self.close_series):
            return 50.0  # Default if not enough data yet

        body_score = 0.0
        volume_score = 0.0
        count = 0

        for i in range(dep_start, dep_end):
            # Bounds check for all arrays
            if i >= len(self.high_series) or i >= len(self.low_series) or i >= len(self.close_series) or i >= len(self.atr):
                break

            candle_range = self.high_series[i] - self.low_series[i]
            candle_body = abs(self.close_series[i] - self.open_series[i])

            # Body size score (normalized by ATR)
            if self.atr[i] > 0:
                body_ratio = candle_body / self.atr[i]
                body_score += min(100.0, body_ratio * 50.0)

            # Volume score (if available)
            if hasattr(self.data, "Volume") and len(self.data.Volume) > i:
                avg_volume = np.mean(self.data.Volume[max(0, i - 20) : i + 1])
                if avg_volume > 0:
                    volume_ratio = self.data.Volume[i] / avg_volume
                    volume_score += min(100.0, volume_ratio * 50.0)

            count += 1

        # Average scores
        avg_body = body_score / count if count > 0 else 0
        avg_volume = volume_score / count if count > 0 else 0

        # Combined score (50% body, 50% volume)
        strength = (avg_body * 0.5) + (avg_volume * 0.5)

        return min(100.0, strength)

    def _calculate_liquidity_distance(self, zone: Zone) -> float:
        """
        Calculate liquidity distance metric (0-100): Proximity to liquidity level.

        Measures how close the zone is to the identified liquidity (inducement) level.
        Closer zones are more likely to be respected as institutions hunt that liquidity.

        Formula: 100 × (1 - distance_pips / max_distance)
        Max distance = 50 pips for forex, 300 pips for gold

        Args:
            zone: Zone with liquidity data

        Returns:
            Distance score 0-100 (100 = very close, 0 = very far)

        Reference:
            Pine Script: SND_Core.pine lines 427-459 (calc_liquidity_distance)
        """
        if not zone.liquidity_valid or zone.liquidity_price is None:
            return 0.0  # No liquidity = 0 score

        # Calculate distance from zone to liquidity in price
        if zone.zone_type == "demand":
            distance = abs(zone.top - zone.liquidity_price)
        else:  # supply
            distance = abs(zone.bottom - zone.liquidity_price)

        # Convert to pips using symbol-aware pip size
        pip_size = self._get_pip_size()
        distance_pips = distance / pip_size

        # Max acceptable distance (symbol-specific: 50 pips forex, 300 pips gold)
        max_distance_pips = self._get_liq_max_distance_pips()

        # Score decreases linearly with distance
        if distance_pips >= max_distance_pips:
            return 0.0

        score = 100.0 * (1.0 - distance_pips / max_distance_pips)
        return max(0.0, score)

    def _calculate_liquidity_spread(self, zone: Zone) -> float:
        """
        Calculate liquidity spread metric (0-100): Width of inducement-target band.

        Measures the distance between the inducement level (where price sweeps)
        and the target level (where price should reach). Wider spreads indicate
        larger liquidity pools and stronger setups.

        Formula: MIN(|target - inducement| in pips, 100)

        Args:
            zone: Zone with liquidity data

        Returns:
            Spread score 0-100 (100 = wide spread)

        Reference:
            Pine Script: SND_Core.pine lines 461-488 (calc_liquidity_spread)
        """
        if not zone.liquidity_valid:
            return 0.0

        if zone.liq_high_price is None or zone.liq_low_price is None:
            return 0.0

        # Distance between high and low liquidity levels
        spread = abs(zone.liq_high_price - zone.liq_low_price)

        # Convert to pips
        pip_size = 0.0001
        spread_pips = spread / pip_size

        # Score is simply the spread in pips (capped at 100)
        return min(100.0, spread_pips)

    def _calculate_return_strength(self, zone: Zone, bar_index: int) -> float:
        """
        Calculate return strength (0-100): Speed and aggression of return after sweep.

        Analyzes the candles between liquidity sweep and zone touch (priming) to
        measure how aggressively price returned to the zone. Faster, more aggressive
        returns indicate stronger institutional interest.

        Factors:
        - Body % (large bodies = strong)
        - RVOL (high volume = strong)
        - Speed bonus (fewer candles = faster)

        Args:
            zone: Zone with sweep and prime data
            bar_index: Current bar index

        Returns:
            Strength score 0-100 (100 = strongest return)

        Reference:
            Pine Script: SND_Core.pine lines 490-551 (calc_return_strength)
        """
        if not zone.liquidity_swept or not zone.primed:
            return 0.0  # No sweep or prime yet

        if zone.liquidity_swept_bar_index is None or zone.primed_bar is None:
            return 0.0

        # Analyze candles between sweep and prime
        return_start = zone.liquidity_swept_bar_index + 1
        return_end = min(zone.primed_bar, len(self.close_series) - 1)

        if return_end <= return_start or return_start >= len(self.close_series):
            return 50.0  # Not enough data yet

        candle_count = return_end - return_start
        body_score = 0.0
        volume_score = 0.0

        for i in range(return_start, return_end + 1):
            # Bounds check
            if i >= len(self.high_series) or i >= len(self.low_series) or i >= len(self.close_series):
                break

            candle_range = self.high_series[i] - self.low_series[i]
            candle_body = abs(self.close_series[i] - self.open_series[i])

            # Body % score
            if candle_range > 0:
                body_pct = candle_body / candle_range
                body_score += body_pct * 50.0

            # Volume score (if available)
            if hasattr(self.data, "Volume") and len(self.data.Volume) > i:
                avg_volume = np.mean(self.data.Volume[max(0, i - 20) : i + 1])
                if avg_volume > 0:
                    volume_ratio = self.data.Volume[i] / avg_volume
                    volume_score += min(50.0, volume_ratio * 25.0)

        # Average scores
        avg_body = body_score / candle_count if candle_count > 0 else 0
        avg_volume = volume_score / candle_count if candle_count > 0 else 0

        # Speed bonus (fewer candles = faster return)
        speed_bonus = max(0.0, 20.0 - candle_count)

        strength = avg_body + avg_volume + speed_bonus
        return min(100.0, strength)

    def _update_zone_quality_metrics(self, zone: Zone, bar_index: int) -> None:
        """
        Update all quality metrics and recalculate zone score/grade.

        Should be called whenever zone state changes (liquidity swept, primed, etc.)
        to keep quality metrics and score up to date.

        Args:
            zone: Zone to update
            bar_index: Current bar index
        """
        # Calculate V6/V7 AI quality metrics
        zone.base_quality = self._calculate_base_quality(zone, bar_index)
        zone.departure_strength = self._calculate_departure_strength(zone, bar_index)
        zone.liquidity_distance = self._calculate_liquidity_distance(zone)
        zone.liquidity_spread = self._calculate_liquidity_spread(zone)
        zone.return_strength = self._calculate_return_strength(zone, bar_index)

        # Recalculate comprehensive score
        zone.score = self._calculate_zone_score(zone, bar_index)

        # Update grade
        zone.grade = self._get_grade_from_score(zone.score)

    def _get_symbol_type(self) -> str:
        """
        Detect symbol type from symbol name and price range.

        Symbol Types:
        - metal: Gold (XAU), Silver (XAG)
        - index: Indices (NAS, SPX, US30, DAX, FTSE)
        - jpy_pair: JPY pairs (USDJPY, EURJPY, etc.)
        - crypto: Cryptocurrencies (BTC, ETH, XRP)
        - forex: Standard forex pairs (EURUSD, GBPUSD, etc.)

        Returns:
            Symbol type string

        Reference:
            Pine Script: Symbol-specific logic (various sections)
        """
        symbol = self.symbol.upper()

        # Check metals FIRST (before checking USD to avoid XAUUSD matching forex)
        if any(metal in symbol for metal in ['XAU', 'XAG', 'GOLD', 'SILVER']):
            return 'metal'

        # Check crypto BEFORE forex
        if any(crypto in symbol for crypto in ['BTC', 'ETH', 'XRP', 'LTC', 'ADA']):
            return 'crypto'

        # Check indices
        if any(index in symbol for index in ['NAS', 'SPX', 'US30', 'DAX', 'FTSE', 'NDX']):
            return 'index'

        # Check JPY pairs
        if 'JPY' in symbol:
            return 'jpy_pair'

        # Default to forex
        return 'forex'

    def _get_lot_size(self) -> float:
        """
        Get lot size (contract size) based on symbol type.

        Lot Sizes:
        - Forex: 100,000 (standard lot)
        - JPY pairs: 100,000 (standard lot)
        - Metals: 100 oz per lot (XAUUSD = 100 oz gold)
        - Crypto: 1 (1 BTC/ETH per lot)
        - Indices: 1 (1 contract per lot)

        Returns:
            Lot size for position sizing calculations

        Reference:
            Pine Script: Position sizing logic (implicit in calculations)
        """
        symbol_type = self._get_symbol_type()

        if symbol_type == 'forex' or symbol_type == 'jpy_pair':
            return 100000  # Standard forex lot
        elif symbol_type == 'metal':
            return 100  # Gold/Silver: 100 oz per lot
        elif symbol_type == 'crypto':
            return 1  # 1 BTC/ETH per lot
        elif symbol_type == 'index':
            return 1  # 1 contract per lot
        else:
            return 100000  # Default to forex

    def _get_pip_size(self) -> float:
        """
        Get pip size based on symbol type.

        Pip Sizes:
        - Forex (non-JPY): 0.0001 (4th decimal)
        - JPY pairs: 0.01 (2nd decimal)
        - Metals (Gold/Silver): 0.01
        - Indices: 1.0 (1 point = 1 pip)
        - Crypto: 1.0 (1 dollar = 1 pip)

        Returns:
            Pip size for distance calculations

        Reference:
            Pine Script: Pip size logic (implicit in calculations)
        """
        symbol_type = self._get_symbol_type()

        if symbol_type == 'jpy_pair':
            return 0.01  # JPY pairs: 0.01 = 1 pip
        elif symbol_type == 'metal':
            return 0.01  # Gold/Silver: 0.01 = 1 pip
        elif symbol_type == 'index':
            return 1.0  # Indices: 1 point = 1 pip
        elif symbol_type == 'crypto':
            return 1.0  # Crypto: 1 dollar = 1 pip
        else:
            return 0.0001  # Forex: 0.0001 = 1 pip

    def _get_liq_max_distance_pips(self) -> float:
        """
        Get maximum distance in pips for liquidity detection.

        Max Distances:
        - Forex: 15 pips
        - JPY pairs: 15 pips (already in 0.01 units)
        - Metals (Gold): 300 pips
        - Indices: 50 points
        - Crypto: 200 pips

        Returns:
            Max distance in pips for liquidity scanning

        Reference:
            Pine Script: Liquidity scanning parameters
        """
        symbol_type = self._get_symbol_type()

        if symbol_type == 'metal':
            return 300.0  # Gold: 300 pips max
        elif symbol_type == 'index':
            return 50.0  # Indices: 50 points max
        elif symbol_type == 'crypto':
            return 200.0  # Crypto: 200 pips max
        else:
            return 15.0  # Forex/JPY: 15 pips max

    def _get_tp_ratio(self, sl_pips: float) -> float:
        """
        Get TP ratio based on symbol type and SL distance.

        TP Ratio Rules (from Pine Script):
        - Indices: Fixed 4.0
        - Metals (Gold):
          - SL ≤ 50 pips: 4.5
          - SL ≤ 100 pips: 3.0
          - SL ≤ 150 pips: 2.5
          - SL ≤ 200 pips: 2.0
          - SL > 200 pips: 1.5
        - Forex/JPY:
          - SL ≤ 3 pips: 4.5
          - SL ≤ 7 pips: 3.0
          - SL ≤ 11 pips: 2.5
          - SL > 11 pips: 2.0

        Args:
            sl_pips: Stop loss distance in pips

        Returns:
            TP ratio multiplier

        Reference:
            Pine Script: SND_Strategy.pine lines 542-775 (SL/TP rules)
        """
        symbol_type = self._get_symbol_type()

        if symbol_type == 'index':
            return 4.0  # Fixed for indices

        elif symbol_type == 'metal':
            # Gold SL-based rules
            if sl_pips <= 50:
                return 4.5
            elif sl_pips <= 100:
                return 3.0
            elif sl_pips <= 150:
                return 2.5
            elif sl_pips <= 200:
                return 2.0
            else:
                return 1.5

        else:  # forex, jpy_pair, crypto
            # Forex/JPY SL-based rules
            if sl_pips <= 3:
                return 4.5
            elif sl_pips <= 7:
                return 3.0
            elif sl_pips <= 11:
                return 2.5
            else:
                return 2.0

    def _scan_demand_liquidity(self, zone: Zone, current_bar: int) -> None:
        """
        Scan for inducement and target liquidity levels for demand zones.

        Demand Zone Liquidity Logic:
        1. STEP A: Find lowest valid 3-candle pivot LOW (inducement)
           - Scan from zone creation forward to current bar
           - Must be within max distance (15 pips forex, 300 pips gold)
           - Use Makuchaku 3-candle pivot detection (stricter)

        2. STEP B: Find ABSOLUTE highest HIGH (target)
           - Scan range: [zone creation ... inducement bar]
           - Store as structure_sweep_level (must sweep this for entry)

        Sets:
        - zone.liq_low_price: Inducement level (must sweep first)
        - zone.liq_low_bar: Bar index of inducement
        - zone.liq_high_price: Target level (must sweep after inducement)
        - zone.liq_high_bar: Bar index of target
        - zone.structure_sweep_level: Target HIGH (for entry validation)
        - zone.liquidity_valid: True if both inducement and target found
        - zone.liq_source: "PIVOT" (detection method)

        Args:
            zone: Demand zone to scan
            current_bar: Current bar index (scan up to this bar)

        Reference:
            Pine Script: SND_Strategy.pine lines 1633-1766 (scan_demand_liq)
        """
        # Skip if liquidity already scanned
        if zone.liquidity_valid or zone.liquidity_price is not None:
            return

        pip_size = self._get_pip_size()
        max_distance_pips = self._get_liq_max_distance_pips()

        # STEP A: Find inducement (lowest pivot LOW forward of zone)
        inducement_bar = None
        inducement_price = None

        scan_start = zone.created_bar + 1
        scan_end = min(current_bar, len(self.low_series) - 2)  # Need 1 bar ahead for pivot

        pivot_count = 0
        for i in range(scan_start, scan_end + 1):
            # Check if this is a 3-candle Makuchaku pivot low (STRICT)
            if self._is_makuchaku_pivot_low(self.low_series, i):
                pivot_count += 1
                pivot_low = self.low_series[i]

                # Check distance from zone bottom (inducement can be within max distance)
                # For demand: inducement is typically below the zone bottom (classic),
                # but can also be above if it's a retracement low before returning to zone
                distance_from_bottom = abs(pivot_low - zone.bottom)
                distance_pips = distance_from_bottom / pip_size

                if distance_pips <= max_distance_pips:
                    # Found valid inducement (take the lowest one)
                    if inducement_price is None or pivot_low < inducement_price:
                        inducement_price = pivot_low
                        inducement_bar = i
                        logger.debug(
                            "Demand zone %d: Valid inducement candidate at bar %d (pivot=%.5f zone_bottom=%.5f distance=%.1f pips)",
                            getattr(zone, "id", 0), i, pivot_low, zone.bottom, distance_pips
                        )
                else:
                    logger.debug(
                        "Demand zone %d: Pivot %d too far (distance=%.1f pips > max=%.1f pips)",
                        getattr(zone, "id", 0), i, distance_pips, max_distance_pips
                    )

        if inducement_price is None:
            # No valid inducement found
            logger.info(
                "Demand zone %d: No valid inducement found (scanned bars %d-%d, found %d pivots, pip_size=%.5f, max_dist=%.1f pips, zone_top=%.5f)",
                getattr(zone, "id", 0),
                scan_start,
                scan_end,
                pivot_count,
                pip_size,
                max_distance_pips,
                zone.top,
            )
            return

        # STEP B: Find target (absolute highest HIGH before inducement)
        target_high = None
        target_bar = None

        for i in range(zone.created_bar, inducement_bar):
            if target_high is None or self.high_series[i] > target_high:
                target_high = self.high_series[i]
                target_bar = i

        if target_high is None:
            # Should not happen, but handle gracefully
            logger.warning(
                "Demand zone %d: Found inducement but no target HIGH (zone_bar=%d, inducement_bar=%d)",
                getattr(zone, "id", 0),
                zone.created_bar,
                inducement_bar,
            )
            return

        # Store liquidity data
        zone.liq_low_price = inducement_price
        zone.liq_low_bar = inducement_bar
        zone.liq_high_price = target_high
        zone.liq_high_bar = target_bar
        zone.structure_sweep_level = target_high  # Must sweep this HIGH for entry
        zone.liquidity_valid = True
        zone.liquidity_price = inducement_price  # Primary inducement level
        zone.liquidity_bar_index = inducement_bar
        zone.liq_source = "PIVOT"

        logger.debug(
            "Demand zone %d: Liquidity found - inducement=%.5f at bar %d, target=%.5f at bar %d (distance=%.1f pips)",
            getattr(zone, "id", 0),
            inducement_price,
            inducement_bar,
            target_high,
            target_bar,
            abs(target_high - inducement_price) / pip_size,
        )

    def _scan_supply_liquidity(self, zone: Zone, current_bar: int) -> None:
        """
        Scan for inducement and target liquidity levels for supply zones.

        Supply Zone Liquidity Logic:
        1. STEP A: Find highest valid 3-candle pivot HIGH (inducement)
           - Scan from zone creation forward to current bar
           - Must be within max distance (15 pips forex, 300 pips gold)
           - Use Makuchaku 3-candle pivot detection (stricter)

        2. STEP B: Find ABSOLUTE lowest LOW (target)
           - Scan range: [zone creation ... inducement bar]
           - Store as structure_sweep_level (must sweep this for entry)

        Sets:
        - zone.liq_high_price: Inducement level (must sweep first)
        - zone.liq_high_bar: Bar index of inducement
        - zone.liq_low_price: Target level (must sweep after inducement)
        - zone.liq_low_bar: Bar index of target
        - zone.structure_sweep_level: Target LOW (for entry validation)
        - zone.liquidity_valid: True if both inducement and target found
        - zone.liq_source: "PIVOT" (detection method)

        Args:
            zone: Supply zone to scan
            current_bar: Current bar index (scan up to this bar)

        Reference:
            Pine Script: SND_Strategy.pine lines 1768-1901 (scan_supply_liq)
        """
        # Skip if liquidity already scanned
        if zone.liquidity_valid or zone.liquidity_price is not None:
            return

        pip_size = self._get_pip_size()
        max_distance_pips = self._get_liq_max_distance_pips()

        # STEP A: Find inducement (highest pivot HIGH forward of zone)
        inducement_bar = None
        inducement_price = None

        scan_start = zone.created_bar + 1
        scan_end = min(current_bar, len(self.high_series) - 2)  # Need 1 bar ahead for pivot

        pivot_count = 0
        for i in range(scan_start, scan_end + 1):
            # Check if this is a 3-candle Makuchaku pivot high (STRICT)
            if self._is_makuchaku_pivot_high(self.high_series, i):
                pivot_count += 1
                pivot_high = self.high_series[i]

                # Check distance from zone top (inducement can be within max distance)
                # For supply: inducement is typically above the zone top (classic),
                # but can also be below if it's a retracement high before returning to zone
                distance_from_top = abs(pivot_high - zone.top)
                distance_pips = distance_from_top / pip_size

                if distance_pips <= max_distance_pips:
                    # Found valid inducement (take the highest one)
                    if inducement_price is None or pivot_high > inducement_price:
                        inducement_price = pivot_high
                        inducement_bar = i
                        logger.debug(
                            "Supply zone %d: Valid inducement candidate at bar %d (pivot=%.5f zone_top=%.5f distance=%.1f pips)",
                            getattr(zone, "id", 0), i, pivot_high, zone.top, distance_pips
                        )
                else:
                    logger.debug(
                        "Supply zone %d: Pivot %d too far (distance=%.1f pips > max=%.1f pips)",
                        getattr(zone, "id", 0), i, distance_pips, max_distance_pips
                    )

        if inducement_price is None:
            # No valid inducement found
            logger.info(
                "Supply zone %d: No valid inducement found (scanned bars %d-%d, found %d pivots, pip_size=%.5f, max_dist=%.1f pips, zone_bottom=%.5f)",
                getattr(zone, "id", 0),
                scan_start,
                scan_end,
                pivot_count,
                pip_size,
                max_distance_pips,
                zone.bottom,
            )
            return

        # STEP B: Find target (absolute lowest LOW before inducement)
        target_low = None
        target_bar = None

        for i in range(zone.created_bar, inducement_bar):
            if target_low is None or self.low_series[i] < target_low:
                target_low = self.low_series[i]
                target_bar = i

        if target_low is None:
            # Should not happen, but handle gracefully
            logger.warning(
                "Supply zone %d: Found inducement but no target LOW (zone_bar=%d, inducement_bar=%d)",
                getattr(zone, "id", 0),
                zone.created_bar,
                inducement_bar,
            )
            return

        # Store liquidity data
        zone.liq_high_price = inducement_price
        zone.liq_high_bar = inducement_bar
        zone.liq_low_price = target_low
        zone.liq_low_bar = target_bar
        zone.structure_sweep_level = target_low  # Must sweep this LOW for entry
        zone.liquidity_valid = True
        zone.liquidity_price = inducement_price  # Primary inducement level
        zone.liquidity_bar_index = inducement_bar
        zone.liq_source = "PIVOT"

        logger.debug(
            "Supply zone %d: Liquidity found - inducement=%.5f at bar %d, target=%.5f at bar %d (distance=%.1f pips)",
            getattr(zone, "id", 0),
            inducement_price,
            inducement_bar,
            target_low,
            target_bar,
            abs(inducement_price - target_low) / pip_size,
        )

    def _check_demand_sweeps(self, zone: Zone, bar_index: int) -> None:
        """
        Check for inducement and target sweeps for demand zones.

        Demand Zone Sweep Logic:
        1. Inducement Sweep: low <= liq_low_price + tolerance (0.5 pip)
           - Price must take liquidity BELOW the inducement level
           - Sets: zone.liquidity_swept = True

        2. Target Sweep: high >= liq_high_price - tolerance (0.5 pip)
           - Price must reach target HIGH (structure sweep)
           - Requires: inducement swept FIRST (institutional sequence)
           - Sets: zone.target_swept = True

        The order matters: Inducement → Target (not vice versa!)

        Args:
            zone: Demand zone to check
            bar_index: Current bar index

        Reference:
            Pine Script: SND_Strategy.pine lines 1906-1937 (check_demand_sweeps)
        """
        if not zone.liquidity_valid:
            return  # No liquidity to sweep

        pip_size = self._get_pip_size()
        tolerance = 0.5 * pip_size  # 0.5 pip tolerance for sweep confirmation

        current_low = self.low_series[bar_index]
        current_high = self.high_series[bar_index]

        # Check inducement sweep (low touches/breaks inducement level)
        if not zone.liquidity_swept:
            if current_low <= zone.liq_low_price + tolerance:
                zone.liquidity_swept = True
                zone.liquidity_swept_bar_index = bar_index
                logger.info(
                    "Demand zone %d: Inducement swept at bar %d (low=%.5f, inducement=%.5f)",
                    getattr(zone, "id", 0),
                    bar_index,
                    current_low,
                    zone.liq_low_price,
                )

        # Check target sweep (high reaches target HIGH) - ONLY AFTER inducement swept
        if zone.liquidity_swept and not zone.target_swept:
            if current_high >= zone.liq_high_price - tolerance:
                zone.target_swept = True
                zone.target_swept_bar_index = bar_index
                logger.info(
                    "Demand zone %d: Target swept at bar %d (high=%.5f, target=%.5f) - SETUP COMPLETE",
                    getattr(zone, "id", 0),
                    bar_index,
                    current_high,
                    zone.liq_high_price,
                )

    def _check_supply_sweeps(self, zone: Zone, bar_index: int) -> None:
        """
        Check for inducement and target sweeps for supply zones.

        Supply Zone Sweep Logic:
        1. Inducement Sweep: high >= liq_high_price - tolerance (0.5 pip)
           - Price must take liquidity ABOVE the inducement level
           - Sets: zone.liquidity_swept = True

        2. Target Sweep: low <= liq_low_price + tolerance (0.5 pip)
           - Price must reach target LOW (structure sweep)
           - Requires: inducement swept FIRST (institutional sequence)
           - Sets: zone.target_swept = True

        The order matters: Inducement → Target (not vice versa!)

        Args:
            zone: Supply zone to check
            bar_index: Current bar index

        Reference:
            Pine Script: SND_Strategy.pine lines 1939-1970 (check_supply_sweeps)
        """
        if not zone.liquidity_valid:
            return  # No liquidity to sweep

        pip_size = self._get_pip_size()
        tolerance = 0.5 * pip_size  # 0.5 pip tolerance for sweep confirmation

        current_low = self.low_series[bar_index]
        current_high = self.high_series[bar_index]

        # Check inducement sweep (high touches/breaks inducement level)
        if not zone.liquidity_swept:
            if current_high >= zone.liq_high_price - tolerance:
                zone.liquidity_swept = True
                zone.liquidity_swept_bar_index = bar_index
                logger.info(
                    "Supply zone %d: Inducement swept at bar %d (high=%.5f, inducement=%.5f)",
                    getattr(zone, "id", 0),
                    bar_index,
                    current_high,
                    zone.liq_high_price,
                )

        # Check target sweep (low reaches target LOW) - ONLY AFTER inducement swept
        if zone.liquidity_swept and not zone.target_swept:
            if current_low <= zone.liq_low_price + tolerance:
                zone.target_swept = True
                zone.target_swept_bar_index = bar_index
                logger.info(
                    "Supply zone %d: Target swept at bar %d (low=%.5f, target=%.5f) - SETUP COMPLETE",
                    getattr(zone, "id", 0),
                    bar_index,
                    current_low,
                    zone.liq_low_price,
                )

    def _check_pre_sweep_touch(self, zone: Zone, bar_index: int) -> None:
        """
        THE INDUCEMENT RULE: Check if zone is touched BEFORE liquidity sweep.

        This is the core institutional trading logic that separates real zones
        from fake zones. Price should NOT touch the zone until AFTER the
        liquidity grab (sweep) occurs. If touched before sweep = FAKE zone.

        Institutional Sequence:
        1. Zone forms (accumulation)
        2. Price moves away to grab liquidity (sweep)
        3. THEN price returns to zone (smart money entry)

        If step 3 happens before step 2, it's retail behavior (FAKE).

        Args:
            zone: Zone to check
            bar_index: Current bar index

        Reference:
            Pine Script: Institutional trading principles (implicit in entry validation)
        """
        if zone.touched_pre_sweep:
            return  # Already marked as fake

        # Skip if liquidity already swept (rule no longer applies)
        if zone.liquidity_swept:
            return

        # Check if zone is touched on current bar
        zone_touched = self._is_zone_touched(zone, bar_index)

        if zone_touched:
            # Zone touched BEFORE sweep = FAKE (invalidate immediately)
            zone.touched_pre_sweep = True
            zone.active = False
            zone.inactive_reason = "Touched before liquidity sweep (INDUCEMENT RULE VIOLATION)"

            logger.warning(
                "Zone %d INVALIDATED: Touched at bar %d BEFORE liquidity sweep (inducement rule) - FAKE ZONE",
                getattr(zone, "id", 0),
                bar_index,
            )

    def _is_zone_touched(self, zone: Zone, bar_index: int) -> bool:
        """
        Check if current candle touches zone (wick or body).

        Demand zone: Touched if low <= zone.top
        Supply zone: Touched if high >= zone.bottom

        Args:
            zone: Zone to check
            bar_index: Current bar index

        Returns:
            True if zone touched, False otherwise
        """
        if zone.zone_type == "demand":
            # Demand zone touched if price goes down into zone
            return self.low_series[bar_index] <= zone.top
        else:  # supply
            # Supply zone touched if price goes up into zone
            return self.high_series[bar_index] >= zone.bottom

    def _check_zone_priming(self, zone: Zone, bar_index: int) -> None:
        """
        Check if zone becomes "primed" (ready for entry on next valid candle).

        Priming occurs when:
        1. Zone is touched (wick or body enters zone)
        2. Close is OUTSIDE zone (rejection in direction)
        3. All validations pass (liquidity swept, not touched pre-sweep, etc.)

        When primed, stores reference levels for Break of Candle (BoC) entry:
        - primed_ref_close: Close of priming candle
        - primed_ref_high: High of priming candle
        - primed_ref_low: Low of priming candle

        Args:
            zone: Zone to check
            bar_index: Current bar index

        Reference:
            Pine Script: Entry model logic (implicit in various entry functions)
        """
        if zone.primed:
            return  # Already primed

        # Check if zone is touched on this bar
        if not self._is_zone_touched(zone, bar_index):
            return

        # Update touch tracking
        zone.was_touched = True
        zone.touch_count += 1
        zone.last_touch_bar = bar_index

        # Check if close is OUTSIDE zone (rejection)
        current_close = self.close_series[bar_index]

        if zone.zone_type == "demand":
            # Demand: Close should be ABOVE zone top (bullish rejection)
            if current_close > zone.top:
                zone.primed = True
                zone.primed_bar = bar_index
                zone.primed_ref_close = current_close
                zone.primed_ref_high = self.high_series[bar_index]
                zone.primed_ref_low = self.low_series[bar_index]
                logger.info(
                    "Demand zone %d: PRIMED at bar %d (close=%.5f above zone top=%.5f)",
                    getattr(zone, "id", 0),
                    bar_index,
                    current_close,
                    zone.top,
                )
        else:  # supply
            # Supply: Close should be BELOW zone bottom (bearish rejection)
            if current_close < zone.bottom:
                zone.primed = True
                zone.primed_bar = bar_index
                zone.primed_ref_close = current_close
                zone.primed_ref_high = self.high_series[bar_index]
                zone.primed_ref_low = self.low_series[bar_index]
                logger.info(
                    "Supply zone %d: PRIMED at bar %d (close=%.5f below zone bottom=%.5f)",
                    getattr(zone, "id", 0),
                    bar_index,
                    current_close,
                    zone.bottom,
                )

    def _check_flip_entry(self, zone: Zone, bar_index: int) -> bool:
        """
        Check for FLIP entry model: Retracement + wick rejection.

        FLIP Entry Conditions:
        1. Zone is primed (touched and rejected on previous bar)
        2. Wick touched zone boundary on previous bar
        3. Close rejected (closed outside zone)
        4. Current bar breaks wick level (confirming direction)

        This is the most conservative entry model - waits for clear rejection
        and confirmation before entering.

        Args:
            zone: Zone to check
            bar_index: Current bar index

        Returns:
            True if FLIP entry conditions met, False otherwise

        Reference:
            Pine Script: FLIP entry model logic
        """
        if not zone.primed:
            return False

        if bar_index - zone.primed_bar != 1:
            return False  # Must be immediately after priming bar

        # Check wick rejection and confirmation
        if zone.zone_type == "demand":
            # Demand FLIP: Previous bar's low touched zone, current bar breaks above wick
            wick_level = min(zone.primed_ref_low, zone.top)
            if self.close_series[bar_index] > wick_level:
                logger.info(
                    "Demand zone %d: FLIP ENTRY at bar %d (close=%.5f breaks wick=%.5f)",
                    getattr(zone, "id", 0),
                    bar_index,
                    self.close_series[bar_index],
                    wick_level,
                )
                return True
        else:  # supply
            # Supply FLIP: Previous bar's high touched zone, current bar breaks below wick
            wick_level = max(zone.primed_ref_high, zone.bottom)
            if self.close_series[bar_index] < wick_level:
                logger.info(
                    "Supply zone %d: FLIP ENTRY at bar %d (close=%.5f breaks wick=%.5f)",
                    getattr(zone, "id", 0),
                    bar_index,
                    self.close_series[bar_index],
                    wick_level,
                )
                return True

        return False

    def _check_dir_close_entry(self, zone: Zone, bar_index: int) -> bool:
        """
        Check for DIR_CLOSE entry model: Directional body close outside zone.

        DIR_CLOSE Entry Conditions:
        1. Zone is touched on current bar (wick or body)
        2. Body closes OUTSIDE zone in direction (immediate rejection)

        This is the most aggressive entry model - enters immediately on
        strong directional close without waiting for confirmation.

        Args:
            zone: Zone to check
            bar_index: Current bar index

        Returns:
            True if DIR_CLOSE entry conditions met, False otherwise

        Reference:
            Pine Script: DIR_CLOSE entry model logic
        """
        # Check if zone touched on current bar
        if not self._is_zone_touched(zone, bar_index):
            return False

        current_close = self.close_series[bar_index]

        if zone.zone_type == "demand":
            # Demand DIR_CLOSE: Touched zone AND closed above zone top
            if current_close > zone.top:
                logger.info(
                    "Demand zone %d: DIR_CLOSE ENTRY at bar %d (touched and closed above zone)",
                    getattr(zone, "id", 0),
                    bar_index,
                )
                return True
        else:  # supply
            # Supply DIR_CLOSE: Touched zone AND closed below zone bottom
            if current_close < zone.bottom:
                logger.info(
                    "Supply zone %d: DIR_CLOSE ENTRY at bar %d (touched and closed below zone)",
                    getattr(zone, "id", 0),
                    bar_index,
                )
                return True

        return False

    def _check_boc_entry(self, zone: Zone, bar_index: int) -> bool:
        """
        Check for BREAK_CANDLE (BoC) entry model: Break of priming candle reference.

        BoC Entry Conditions:
        1. Zone is primed (touched and rejected on previous bar)
        2. Current bar breaks priming candle's high/low (structure break)

        This is a balanced entry model - waits for priming but enters on
        structure break rather than just close.

        Args:
            zone: Zone to check
            bar_index: Current bar index

        Returns:
            True if BoC entry conditions met, False otherwise

        Reference:
            Pine Script: BREAK_CANDLE (BoC) entry model logic
        """
        if not zone.primed:
            return False

        # BoC can trigger on priming bar or after
        if bar_index < zone.primed_bar:
            return False

        if zone.zone_type == "demand":
            # Demand BoC: Current bar breaks above priming candle high
            if self.close_series[bar_index] > zone.primed_ref_high:
                logger.info(
                    "Demand zone %d: BOC ENTRY at bar %d (close=%.5f breaks primed high=%.5f)",
                    getattr(zone, "id", 0),
                    bar_index,
                    self.close_series[bar_index],
                    zone.primed_ref_high,
                )
                return True
        else:  # supply
            # Supply BoC: Current bar breaks below priming candle low
            if self.close_series[bar_index] < zone.primed_ref_low:
                logger.info(
                    "Supply zone %d: BOC ENTRY at bar %d (close=%.5f breaks primed low=%.5f)",
                    getattr(zone, "id", 0),
                    bar_index,
                    self.close_series[bar_index],
                    zone.primed_ref_low,
                )
                return True

        return False

    def _validate_entry_conditions(self, zone: Zone, bar_index: int) -> tuple[bool, str]:
        """
        Comprehensive entry validation matching Pine Script validate_entry_conditions().

        Checks all conditions required for a valid trade entry. Returns both
        a boolean result and a string explaining the rejection reason if entry
        is not allowed.

        Validation Checks (in order):
        1. Zone is active (not broken/invalidated)
        2. Zone has valid liquidity structure
        3. Zone NOT touched before sweep (THE INDUCEMENT RULE)
        4. Inducement liquidity swept
        5. Target liquidity swept (both sweeps required)
        6. Liquidity distance within acceptable range
        7. Zone not used yet (one trade per zone)
        8. Zone not mitigated
        9. Zone age < 24 hours (configurable)
        10. AI Quality Score >= threshold (if enabled)
        11. Zone grade >= minimum grade (if enabled)
        12. Return strength >= minimum (if enabled)

        Args:
            zone: Zone to validate
            bar_index: Current bar index

        Returns:
            Tuple of (can_enter: bool, rejection_reason: str)

        Reference:
            Pine Script: validate_entry_conditions() function
        """
        # 1. Zone active
        if not zone.active:
            return False, f"Zone inactive: {zone.inactive_reason or 'unknown reason'}"

        # 2. Liquidity structure valid
        if not zone.liquidity_valid:
            return False, "No valid liquidity structure"

        # 3. THE INDUCEMENT RULE: Zone must NOT be touched before sweep
        if zone.touched_pre_sweep:
            return False, "Touched before liquidity sweep (INDUCEMENT RULE VIOLATION) - FAKE ZONE"

        # 4. Inducement swept
        if not zone.liquidity_swept:
            return False, "Inducement not swept yet"

        # 5. Target swept (both sweeps required for institutional setup)
        if not zone.target_swept:
            return False, "Target not swept yet (waiting for structure break)"

        # 6. Liquidity distance check (zone should be near liquidity)
        if self.require_liquidity_sweep:
            distance = zone.liquidity_distance
            if distance < 10.0:  # Arbitrary threshold, should be configurable
                return False, f"Liquidity too far from zone (distance score={distance:.1f})"

        # 7. Zone not used yet (one trade per zone)
        if zone.last_entry_bar is not None:
            return False, "Zone already used for entry"

        # 8. Zone not mitigated
        if zone.mitigated:
            return False, "Zone mitigated (broken before entry)"

        # 9. Zone age check (24 hours @ 5m = 288 bars)
        max_age_bars = 288  # TODO: Make configurable based on timeframe
        zone_age = bar_index - zone.created_bar
        if zone_age > max_age_bars:
            return False, f"Zone too old ({zone_age} bars > {max_age_bars} max)"

        # 10. AI Quality Score check (if threshold set)
        if hasattr(self, "ai_quality_threshold") and self.ai_quality_threshold > 0:
            if zone.score < self.ai_quality_threshold:
                return False, f"AI score {zone.score:.1f} < threshold {self.ai_quality_threshold}"

        # 11. Grade filter (if enabled)
        if hasattr(self, "min_entry_grade"):
            grade_value = self._get_grade_value(zone.grade)
            min_value = self._get_grade_value(self.min_entry_grade)
            if grade_value < min_value:
                return False, f"Grade {zone.grade} < minimum {self.min_entry_grade}"

        # 12. Return strength check (if enabled)
        if hasattr(self, "min_return_strength") and self.min_return_strength > 0:
            if zone.return_strength < self.min_return_strength:
                return False, f"Return strength {zone.return_strength:.1f} < minimum {self.min_return_strength}"

        # All checks passed!
        return True, "All validation checks passed"

    def _get_grade_value(self, grade: str) -> int:
        """
        Convert letter grade to numeric value for comparison.

        Grade values:
        - A+ = 6 (highest)
        - A  = 5
        - B+ = 4
        - B  = 3
        - C+ = 2
        - C  = 1 (lowest)

        Args:
            grade: Letter grade string

        Returns:
            Numeric grade value
        """
        grade_map = {
            "A+": 6,
            "A": 5,
            "B+": 4,
            "B": 3,
            "C+": 2,
            "C": 1,
        }
        return grade_map.get(grade, 1)  # Default to C if unknown

    def _check_liquidity_distance(self, zone: Zone) -> bool:
        """
        Check if liquidity is within acceptable distance from zone.

        Uses the liquidity_distance metric calculated earlier. Higher score
        means closer proximity (better setup).

        Args:
            zone: Zone to check

        Returns:
            True if liquidity distance acceptable, False otherwise
        """
        # Distance score >= 10 is acceptable (roughly < 45 pips for forex)
        return zone.liquidity_distance >= 10.0

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
        Check for BUY signal (demand zone + Break of Candle + AI Guardian filters).

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

        # === AI GUARDIAN FILTERS (Pine Script v5.1) ===

        # Filter 1: Liquidity Sweep (optional)
        if self.require_liquidity_sweep:
            if not self._detect_liquidity_sweep("demand"):
                logger.debug("BUY signal REJECTED: No liquidity sweep detected")
                return False, None, 0.0, 0.0

        # Filter 2: Arrival Type (reject compression)
        if self.reject_compression_arrival:
            arrival_type = self._assess_arrival_type()
            if arrival_type == "Compression":
                logger.debug("BUY signal REJECTED: Compression arrival (slow/grinding)")
                return False, None, 0.0, 0.0

        # Filter 3: Market Structure Break (optional)
        if self.require_structure_break:
            if not self._detect_structure_break("demand"):
                logger.debug("BUY signal REJECTED: No market structure break")
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
            "BUY signal ACCEPTED: zone=%s entry=%.5f sl=%.5f",
            best_zone,
            entry_price,
            stop_loss,
        )

        return True, best_zone, entry_price, stop_loss

    def _check_sell_signal(self) -> tuple[bool, Optional[Zone], float, float]:
        """
        Check for SELL signal (supply zone + Break of Candle + AI Guardian filters).

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

        # === AI GUARDIAN FILTERS (Pine Script v5.1) ===

        # Filter 1: Liquidity Sweep (optional)
        if self.require_liquidity_sweep:
            if not self._detect_liquidity_sweep("supply"):
                logger.debug("SELL signal REJECTED: No liquidity sweep detected")
                return False, None, 0.0, 0.0

        # Filter 2: Arrival Type (reject compression)
        if self.reject_compression_arrival:
            arrival_type = self._assess_arrival_type()
            if arrival_type == "Compression":
                logger.debug("SELL signal REJECTED: Compression arrival (slow/grinding)")
                return False, None, 0.0, 0.0

        # Filter 3: Market Structure Break (optional)
        if self.require_structure_break:
            if not self._detect_structure_break("supply"):
                logger.debug("SELL signal REJECTED: No market structure break")
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
            "SELL signal ACCEPTED: zone=%s entry=%.5f sl=%.5f",
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

    def _detect_liquidity_sweep(self, zone_type: str, lookback: int = 10) -> bool:
        """
        Detect if liquidity was swept before tapping the zone.

        Logic (from Pine Utils.pine:197-203):
        - Demand zones: Check if current low swept below the lowest low of lookback period
        - Supply zones: Check if current high swept above the highest high of lookback period

        This indicates institutional liquidity grab before reversal (bullish signal).

        Args:
            zone_type: "demand" or "supply"
            lookback: Number of bars to check for liquidity (default: 10)

        Returns:
            True if liquidity sweep detected
        """
        if len(self.data.Low) < lookback + 1 or len(self.data.High) < lookback + 1:
            return False

        current_high = self.data.High[-1]
        current_low = self.data.Low[-1]

        # Get lookback high/low (excluding current bar)
        lookback_high = max(self.data.High[-lookback - 1 : -1])
        lookback_low = min(self.data.Low[-lookback - 1 : -1])

        if zone_type == "demand":
            # For demand zones: price swept below the lookback low (sell-side liquidity taken)
            swept = current_low <= lookback_low
            if swept:
                logger.debug(
                    "Liquidity SWEEP detected (demand): low=%.5f <= lookback_low=%.5f",
                    current_low,
                    lookback_low,
                )
            return swept
        else:
            # For supply zones: price swept above the lookback high (buy-side liquidity taken)
            swept = current_high >= lookback_high
            if swept:
                logger.debug(
                    "Liquidity SWEEP detected (supply): high=%.5f >= lookback_high=%.5f",
                    current_high,
                    lookback_high,
                )
            return swept

    def _assess_arrival_type(self) -> str:
        """
        Assess the arrival type (how price arrived at the zone).

        Logic (from Pine Utils.pine:210-220):
        - Compare average candle body size (last 3 candles) to ATR
        - Aggressive: ratio > 1.5 (fast, impulsive arrival - GOOD for reversals)
        - Compression: ratio < 0.8 (slow, grinding arrival - BAD, likely to fail)
        - Normal: ratio between 0.8 and 1.5

        Returns:
            "Aggressive", "Normal", or "Compression"
        """
        if len(self.data.Close) < 3 or len(self.atr) < 1:
            return "Normal"

        # Calculate average body size of last 3 candles
        body_sizes = []
        for i in range(1, 4):
            if len(self.data.Close) > i:
                body_size = abs(self.data.Close[-i] - self.data.Open[-i])
                body_sizes.append(body_size)

        if not body_sizes:
            return "Normal"

        avg_body_size = np.mean(body_sizes)
        atr_value = self.atr[-1]

        if atr_value <= 0:
            return "Normal"

        ratio = avg_body_size / atr_value

        if ratio > 1.5:
            arrival = "Aggressive"
        elif ratio < 0.8:
            arrival = "Compression"
        else:
            arrival = "Normal"

        logger.debug(
            "Arrival type: %s (avg_body=%.5f, atr=%.5f, ratio=%.2f)",
            arrival,
            avg_body_size,
            atr_value,
            ratio,
        )

        return arrival

    def _detect_structure_break(self, zone_type: str, lookback: int = 20) -> bool:
        """
        Detect market structure break (BOS/CHoCH).

        Logic (from Pine Utils.pine:237-245):
        - Check if current close has broken and closed beyond a key structural level
        - Structural level = swing high/low from lookback period
        - Demand: bullish break (close above structural high)
        - Supply: bearish break (close below structural low)

        Args:
            zone_type: "demand" or "supply"
            lookback: Bars to look back for structural level (default: 20)

        Returns:
            True if structure was broken
        """
        if len(self.data.Close) < lookback + 1:
            return False

        current_close = self.data.Close[-1]

        if zone_type == "demand":
            # Bullish structure break: close above the structural high
            structure_level = max(self.data.High[-lookback - 1 : -1])
            broken = current_close > structure_level
            if broken:
                logger.debug(
                    "Structure BREAK detected (demand): close=%.5f > structure_high=%.5f",
                    current_close,
                    structure_level,
                )
            return broken
        else:
            # Bearish structure break: close below the structural low
            structure_level = min(self.data.Low[-lookback - 1 : -1])
            broken = current_close < structure_level
            if broken:
                logger.debug(
                    "Structure BREAK detected (supply): close=%.5f < structure_low=%.5f",
                    current_close,
                    structure_level,
                )
            return broken

    def _calculate_position_size(self, entry: float, stop_loss: float) -> float:
        """
        Calculate position size based on risk percentage.

        Risk-based formula: units = risk_amount / |entry - stop_loss|
        So if SL is hit, loss = units * |entry - sl| = risk_amount.

        Args:
            entry: Entry price
            stop_loss: Stop loss price

        Returns:
            Position size in units (for backtesting.py: integer units)
        """
        account_balance = self.equity
        risk_amount = account_balance * (self.risk_percent / 100.0)

        risk_per_unit = abs(entry - stop_loss)
        if risk_per_unit <= 0:
            return 0.0

        # units = risk_amount / risk_per_unit
        # e.g. $250 risk / $5 SL distance = 50 oz (gold) or 50k units (forex)
        units = risk_amount / risk_per_unit

        current_price = self.data.Close[-1]
        pip_size = self._get_pip_size()

        # For forex: 1 unit = 1 base currency. Backtesting uses units directly.
        # For gold: 1 unit = 1 oz. Min 1 oz.
        if current_price > 100:  # Metals (XAUUSD, etc.) - 1 lot = 100 oz
            units = max(1, int(round(units)))
            max_by_lots = int(self.max_lot_size * 100)  # 10 lots = 1000 oz
        else:  # Forex - 1 lot = 100,000 units
            units = max(1000, int(round(units)))  # Min 0.01 lot = 1000 units
            max_by_lots = int(self.max_lot_size * 100_000)

        # Cap by max lot size and margin (95% of equity at 50:1)
        max_by_margin = int(account_balance / current_price * 0.95 * 50)
        units = min(units, max_by_lots, max(1, max_by_margin))

        logger.debug(
            "Position size: risk=$%.2f risk_per_unit=%.5f units=%d",
            risk_amount,
            risk_per_unit,
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
                # Assign unique ID
                new_zone.id = len(self.demand_zones) + 1
                self.demand_zones.append(new_zone)
                logger.debug("Created demand zone %d at bar %d", new_zone.id, bar_index)

        if self.swing_high[-1] > 0:
            new_zone = self._create_supply_zone(bar_index)
            if new_zone and new_zone.strength >= self.zone_strength_min:
                # Assign unique ID
                new_zone.id = len(self.supply_zones) + 1
                self.supply_zones.append(new_zone)
                logger.debug("Created supply zone %d at bar %d", new_zone.id, bar_index)

        # 2. Update zone states (INSTITUTIONAL LOGIC INTEGRATION)
        # Scan for liquidity, check sweeps, enforce inducement rule, check priming
        for zone in self.demand_zones:
            if not zone.active:
                continue

            # 2A. Liquidity scanning (find inducement + target levels)
            if not zone.liquidity_valid:
                self._scan_demand_liquidity(zone, bar_index)

            # 2B. Sweep detection (check if inducement/target swept)
            if zone.liquidity_valid:
                self._check_demand_sweeps(zone, bar_index)

            # 2C. THE INDUCEMENT RULE (invalidate zones touched before sweep)
            if zone.liquidity_valid and not zone.liquidity_swept:
                self._check_pre_sweep_touch(zone, bar_index)

            # 2D. Zone priming (check if zone ready for entry)
            if zone.target_swept and not zone.primed:
                self._check_zone_priming(zone, bar_index)

            # 2E. Update quality metrics when state changes (and enough bars passed)
            if zone.primed and zone.liquidity_swept and (bar_index - zone.created_bar >= 3):
                self._update_zone_quality_metrics(zone, bar_index)

        for zone in self.supply_zones:
            if not zone.active:
                continue

            # 2A. Liquidity scanning
            if not zone.liquidity_valid:
                self._scan_supply_liquidity(zone, bar_index)

            # 2B. Sweep detection
            if zone.liquidity_valid:
                self._check_supply_sweeps(zone, bar_index)

            # 2C. THE INDUCEMENT RULE
            if zone.liquidity_valid and not zone.liquidity_swept:
                self._check_pre_sweep_touch(zone, bar_index)

            # 2D. Zone priming
            if zone.target_swept and not zone.primed:
                self._check_zone_priming(zone, bar_index)

            # 2E. Update quality metrics (and enough bars passed)
            if zone.primed and zone.liquidity_swept and (bar_index - zone.created_bar >= 3):
                self._update_zone_quality_metrics(zone, bar_index)

        # 2F. Legacy zone updates (for compatibility)
        self._update_zones()

        # 3. Exit management (check existing positions first)
        if self.position:
            # Check max bars in trade (time-based exit like Pine Script)
            # Position has no entry_bar; get it from the earliest active trade
            if self.max_bars_in_trade > 0 and self.trades:
                entry_bar = min(t.entry_bar for t in self.trades)
                bars_in_trade = bar_index - entry_bar
                if bars_in_trade >= self.max_bars_in_trade:
                    logger.info(
                        "Exiting position at bar %d: max bars reached (%d >= %d)",
                        bar_index,
                        bars_in_trade,
                        self.max_bars_in_trade
                    )
                    self.position.close()
            # Simple exit: let SL/TP handle it
            # Advanced: could add trailing stop, zone-based exits, etc.

        # 4. Entry logic (only if no position) - ENHANCED WITH INSTITUTIONAL LOGIC
        if not self.position:
            # Log how many zones are being checked
            active_demand_zones = [z for z in self.demand_zones if z.active]
            active_supply_zones = [z for z in self.supply_zones if z.active]

            if len(active_demand_zones) > 0 or len(active_supply_zones) > 0:
                logger.info(
                    "Bar %d: Checking entry conditions (%d demand zones, %d supply zones)",
                    bar_index,
                    len(active_demand_zones),
                    len(active_supply_zones)
                )

            # Check demand zones for BUY signals (use enhanced institutional validation)
            for zone in self.demand_zones:
                if not zone.active:
                    continue

                # 4A. Comprehensive entry validation (12-point checklist)
                can_enter, rejection_reason = self._validate_entry_conditions(zone, bar_index)
                if not can_enter:
                    # Log rejection at INFO level for visibility
                    logger.info(
                        "Demand zone %d REJECTED: %s (primed=%s swept=%s target_swept=%s score=%.1f grade=%s)",
                        zone.id,
                        rejection_reason,
                        zone.primed,
                        zone.liquidity_swept,
                        zone.target_swept,
                        zone.score,
                        zone.grade,
                    )
                    continue

                # 4B. Check entry models (FLIP, DIR_CLOSE, BoC)
                entry_triggered = False
                entry_model = None

                # Try BoC entry (most common - break of priming candle)
                boc_result = self._check_boc_entry(zone, bar_index)
                if boc_result:
                    entry_triggered = True
                    entry_model = "BOC"
                    logger.info("Zone %d: BOC entry triggered", zone.id)

                # Try FLIP entry (conservative - wick rejection + confirmation)
                elif self._check_flip_entry(zone, bar_index):
                    entry_triggered = True
                    entry_model = "FLIP"
                    logger.info("Zone %d: FLIP entry triggered", zone.id)

                # Try DIR_CLOSE entry (aggressive - immediate directional close)
                elif self._check_dir_close_entry(zone, bar_index):
                    entry_triggered = True
                    entry_model = "DIR_CLOSE"
                    logger.info("Zone %d: DIR_CLOSE entry triggered", zone.id)

                if not entry_triggered:
                    logger.info(
                        "Zone %d: No entry model triggered (primed=%s primed_bar=%s current_bar=%s)",
                        zone.id,
                        zone.primed,
                        zone.primed_bar if zone.primed else None,
                        bar_index
                    )
                    continue

                # 4C. Entry confirmed - calculate size and levels
                buy_entry = self.data.Close[-1]  # Current close
                buy_sl = zone.bottom - (self.stop_buffer_pips * self._get_pip_size())  # Below zone with buffer

                # Calculate SL distance in pips for dynamic TP
                sl_pips = (buy_entry - buy_sl) / self._get_pip_size()

                # Get symbol-specific TP ratio
                tp_ratio = self._get_tp_ratio(sl_pips)

                size = self._calculate_position_size(buy_entry, buy_sl)
                if size > 0:
                    # Calculate TP based on symbol-specific ratio
                    risk = buy_entry - buy_sl
                    tp = buy_entry + (risk * tp_ratio)

                    # Mark zone as used
                    zone.last_entry_bar = bar_index

                    try:
                        # Place BUY order with SL/TP (executes on next bar's open)
                        self.buy(size=size, sl=buy_sl, tp=tp)

                        logger.info(
                            "BUY order placed via %s: zone=%d score=%.1f grade=%s size=%.4f entry=%.5f sl=%.5f tp=%.5f (R:R=%.1f)",
                            entry_model,
                            zone.id,
                            zone.score,
                            zone.grade,
                            size,
                            buy_entry,
                            buy_sl,
                            tp,
                            tp_ratio,
                        )
                    except Exception as e:
                        logger.error("BUY order failed: %s", e, exc_info=True)
                    return

            # Check supply zones for SELL signals
            for zone in self.supply_zones:
                if not zone.active:
                    continue

                # 4A. Comprehensive entry validation
                can_enter, rejection_reason = self._validate_entry_conditions(zone, bar_index)
                if not can_enter:
                    # Log rejection at INFO level for visibility
                    logger.info(
                        "Supply zone %d REJECTED: %s (primed=%s swept=%s target_swept=%s score=%.1f grade=%s)",
                        zone.id,
                        rejection_reason,
                        zone.primed,
                        zone.liquidity_swept,
                        zone.target_swept,
                        zone.score,
                        zone.grade,
                    )
                    continue

                # 4B. Check entry models
                entry_triggered = False
                entry_model = None

                if self._check_boc_entry(zone, bar_index):
                    entry_triggered = True
                    entry_model = "BOC"
                    logger.info("Zone %d: BOC entry triggered", zone.id)
                elif self._check_flip_entry(zone, bar_index):
                    entry_triggered = True
                    entry_model = "FLIP"
                    logger.info("Zone %d: FLIP entry triggered", zone.id)
                elif self._check_dir_close_entry(zone, bar_index):
                    entry_triggered = True
                    entry_model = "DIR_CLOSE"
                    logger.info("Zone %d: DIR_CLOSE entry triggered", zone.id)

                if not entry_triggered:
                    logger.info(
                        "Zone %d: No entry model triggered (primed=%s primed_bar=%s current_bar=%s)",
                        zone.id,
                        zone.primed,
                        zone.primed_bar if zone.primed else None,
                        bar_index
                    )
                    continue

                # 4C. Entry confirmed
                sell_entry = self.data.Close[-1]
                sell_sl = zone.top + (self.stop_buffer_pips * self._get_pip_size())  # Above zone with buffer

                sl_pips = (sell_sl - sell_entry) / self._get_pip_size()
                tp_ratio = self._get_tp_ratio(sl_pips)

                size = self._calculate_position_size(sell_entry, sell_sl)
                if size > 0:
                    risk = sell_sl - sell_entry
                    tp = sell_entry - (risk * tp_ratio)

                    zone.last_entry_bar = bar_index

                    try:
                        # Place SELL order with SL/TP (executes on next bar's open)
                        self.sell(size=size, sl=sell_sl, tp=tp)
                        logger.info(
                            "SELL order placed via %s: zone=%d score=%.1f grade=%s size=%.4f entry=%.5f sl=%.5f tp=%.5f (R:R=%.1f)",
                            entry_model,
                            zone.id,
                            zone.score,
                            zone.grade,
                            size,
                            sell_entry,
                            sell_sl,
                            tp,
                            tp_ratio,
                        )
                    except Exception as e:
                        logger.error("SELL order failed: %s", e, exc_info=True)
                    return
