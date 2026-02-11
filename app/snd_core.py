"""
SND_Core - Logic kernel ported from SND_Core.pine.

Contains: Zone dataclass, scoring logic, AI features.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

import numpy as np

from app.snd_utils import is_na


@dataclass
class Zone:
    """Zone dataclass - core structure for demand/supply zones."""

    id: int
    top: float
    bottom: float
    active: bool = True
    created_bar_index: int = 0
    is_historical: bool = False
    start_time: int = 0

    # Liquidity
    liquidity_price: float = np.nan
    liquidity_bar_index: int = -1
    liquidity_valid: bool = False
    liquidity_swept: bool = False
    liquidity_swept_bar_index: int = -1
    caused_sweep: bool = False
    liquidity_candle_count: int = 0
    structure_sweep_level: float = np.nan
    structure_sweep_level_bar: int = -1
    liq_high_price: float = np.nan
    liq_high_bar: int = -1
    liq_high_time: int = 0
    liq_low_price: float = np.nan
    liq_low_bar: int = -1
    liq_low_time: int = 0
    liq_source: str = ""
    target_swept: bool = False
    target_swept_bar_index: int = -1
    leg_candle_count: int = 0
    push_high_price: float = np.nan
    push_high_bar: int = -1
    inactive_reason: str = ""

    # Trading
    last_entry_bar: int = -1
    mitigated: bool = False
    mitigation_time: int = 0
    left_zone: bool = False
    left_with_bearish: bool = False
    primed: bool = False
    primed_bar: int = -1
    primed_wick_level: float = np.nan
    primed_ref_close: float = np.nan
    primed_ref_high: float = np.nan
    primed_ref_low: float = np.nan
    was_touched: bool = False
    touch_count: int = 0
    last_touch_bar: int = -1
    touched_pre_sweep: bool = False

    # V6/V7 scores
    base_quality: float = 50.0
    departure_strength: float = 50.0
    liquidity_distance: float = 50.0
    liquidity_spread: float = 50.0
    return_strength: float = 50.0
    is_accuracy: bool = False
    score: float = 0.0
    grade: str = "C"


def get_grade_from_score(score: float) -> str:
    """Convert 0-100 score to grade."""
    if score >= 90:
        return "A+"
    if score >= 80:
        return "A"
    if score >= 70:
        return "B+"
    if score >= 60:
        return "B"
    if score >= 50:
        return "C+"
    return "C"


def get_grade_value(grade: str) -> int:
    """Convert grade to numeric for comparison."""
    grades = {"A+": 6, "A": 5, "B+": 4, "B": 3, "C+": 2, "C": 1}
    return grades.get(grade, 0)


def calculate_zone_score(
    is_demand: bool,
    top: float,
    bottom: float,
    base_idx: int,
    leg_candles: int,
    has_liquidity: bool,
    is_liquidity_sweep: bool,
    candles_in_base: int,
    is_accuracy: bool,
    is_uptrend: bool,
    is_downtrend: bool,
    zone_time: int,
) -> float:
    """Calculate zone quality score (0-100)."""
    score = 0.0

    # 1. TREND ALIGNMENT (20 pts)
    if is_demand and is_uptrend:
        score += 20
    elif not is_demand and is_downtrend:
        score += 20

    # 2. STRENGTH OF MOVE (20 pts)
    if is_accuracy:
        score += 20
    elif leg_candles >= 3:
        score += 15
    else:
        score += 10

    # 3. BASE QUALITY (20 pts)
    zone_size = top - bottom
    if candles_in_base <= 2 and zone_size > 0:
        score += 20
    elif candles_in_base <= 4:
        score += 10
    else:
        score += 5

    # 4. LIQUIDITY (20 pts)
    if is_liquidity_sweep:
        score += 20
    elif has_liquidity:
        score += 10

    # 5. TIME & FRESHNESS (20 pts)
    zone_hour = (zone_time // 3600) % 24
    is_london = 7 <= zone_hour <= 10
    is_ny = 13 <= zone_hour <= 16
    score += 10 if (is_london or is_ny) else 5
    score += 10

    return min(score, 100.0)


def is_makuchaku_pvt_low(src_low: list, idx: int) -> bool:
    """3-candle pivot low: low[idx+1] < low[idx] and low[idx+1] < low[idx+2]."""
    n = len(src_low)
    if idx + 2 >= n:
        return False
    m = src_low[idx + 1]
    return m < src_low[idx] and m < src_low[idx + 2]


def is_makuchaku_pvt_high(src_high: list, idx: int) -> bool:
    """3-candle pivot high."""
    n = len(src_high)
    if idx + 2 >= n:
        return False
    m = src_high[idx + 1]
    return m > src_high[idx] and m > src_high[idx + 2]
