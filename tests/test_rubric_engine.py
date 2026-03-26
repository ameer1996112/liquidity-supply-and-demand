"""
test_rubric_engine.py — Unit tests for src/rubric_engine.py

Covers: hard vetoes, all 4 dimension formulas,
composite formula edge cases, EV formula, out-of-range clamping.
"""

import pytest
from src.rubric_engine import (
    score_signal,
    _score_departure,
    _score_return_strength,
    _score_premium_discount,
    _score_bars_since_sweep,
    _compute_ev,
    RubricResult,
)


# ─────────────────────────────────────────────────────────────────
# Hard vetoes
# ─────────────────────────────────────────────────────────────────

def test_hard_veto_sweep_candle_close_true():
    result = score_signal({"sweep_candle_close": True})
    assert result.hard_veto is True
    assert result.composite_score == 0.0
    assert "sweep_candle_close" in result.veto_reason.lower()


def test_hard_veto_sweep_candle_close_string_true():
    result = score_signal({"sweep_candle_close": "True"})
    assert result.hard_veto is True


def test_hard_veto_sweep_candle_close_false_not_vetoed():
    """sweep_candle_close=False should NOT trigger hard veto."""
    result = score_signal({"sweep_candle_close": False})
    assert result.hard_veto is False


def test_hard_veto_sydney_session():
    result = score_signal({"session": 0})
    assert result.hard_veto is True
    assert result.composite_score == 0.0
    assert "sydney" in result.veto_reason.lower() or "session" in result.veto_reason.lower()


def test_hard_veto_sydney_session_string():
    result = score_signal({"session": "0"})
    assert result.hard_veto is True


def test_non_sydney_session_not_vetoed():
    """session=1 (London) should not trigger hard veto."""
    result = score_signal({"session": 1})
    assert result.hard_veto is False


# ─────────────────────────────────────────────────────────────────
# Dimension 1: Departure strength (0-30)
# ─────────────────────────────────────────────────────────────────

def test_departure_zero_score():
    assert _score_departure({"departure_strength": 0}) == 0.0


def test_departure_max_score():
    assert _score_departure({"departure_strength": 100}) == 30.0


def test_departure_midpoint():
    assert _score_departure({"departure_strength": 50}) == pytest.approx(15.0)


def test_departure_missing_returns_zero():
    assert _score_departure({}) == 0.0


# ─────────────────────────────────────────────────────────────────
# Dimension 2: Return strength inverted (0-25)
# raw=30 → (100-30)*0.25 = 17.5
# ─────────────────────────────────────────────────────────────────

def test_return_strength_inversion_formula():
    """Key test from test plan: raw=30 → rubric=17.5."""
    result = _score_return_strength({"return_strength": 30})
    assert result == pytest.approx(17.5)


def test_return_strength_raw_zero_gives_max():
    """raw=0 (fastest return) → inverted = 25 (maximum score)."""
    result = _score_return_strength({"return_strength": 0})
    assert result == pytest.approx(25.0)


def test_return_strength_raw_100_gives_zero():
    """raw=100 (slowest return) → inverted = 0."""
    result = _score_return_strength({"return_strength": 100})
    assert result == pytest.approx(0.0)


def test_return_strength_missing_returns_zero():
    assert _score_return_strength({}) == 0.0


# ─────────────────────────────────────────────────────────────────
# Dimension 3: Premium/Discount (0-25)
# ─────────────────────────────────────────────────────────────────

def test_premium_discount_buy_above_50_gets_score():
    """BUY + pd=0.6 (discount zone) → score=25."""
    result = _score_premium_discount({"premium_discount": 0.6, "side": "buy"})
    assert result == 25.0


def test_premium_discount_buy_below_50_gets_zero():
    """BUY + pd=0.25 (premium zone) → score=0 (bad alignment)."""
    result = _score_premium_discount({"premium_discount": 0.25, "side": "buy"})
    assert result == 0.0


def test_premium_discount_buy_exactly_50_gets_score():
    """BUY + pd=0.5 (midpoint) → score=25 (pd >= 0.5)."""
    result = _score_premium_discount({"premium_discount": 0.5, "side": "buy"})
    assert result == 25.0


def test_premium_discount_sell_below_50_gets_score():
    """SELL + pd=0.25 (premium zone) → score=25 (good alignment)."""
    result = _score_premium_discount({"premium_discount": 0.25, "side": "sell"})
    assert result == 25.0


def test_premium_discount_sell_above_50_gets_zero():
    """SELL + pd=0.75 (discount zone) → score=0 (bad alignment)."""
    result = _score_premium_discount({"premium_discount": 0.75, "side": "sell"})
    assert result == 0.0


def test_premium_discount_out_of_range_low_clamped():
    """pd=-0.1 clamped to 0.0 — BUY gets 0 (0.0 < 0.5)."""
    result = _score_premium_discount({"premium_discount": -0.1, "side": "buy"})
    assert result == 0.0


def test_premium_discount_out_of_range_high_clamped():
    """pd=1.1 clamped to 1.0 — BUY gets 25 (1.0 >= 0.5)."""
    result = _score_premium_discount({"premium_discount": 1.1, "side": "buy"})
    assert result == 25.0


def test_premium_discount_missing_returns_zero():
    assert _score_premium_discount({"side": "buy"}) == 0.0


# ─────────────────────────────────────────────────────────────────
# Dimension 4: Bars since sweep (0-20)
# ─────────────────────────────────────────────────────────────────

def test_bars_since_sweep_2_gives_max():
    """bars_since_sweep=2 → raw_score=10, scaled=20."""
    result = _score_bars_since_sweep({"candles_to_return": 2})
    assert result == pytest.approx(20.0)


def test_bars_since_sweep_5_gives_12():
    """bars_since_sweep=5 → raw_score=6, scaled=12."""
    result = _score_bars_since_sweep({"candles_to_return": 5})
    assert result == pytest.approx(12.0)


def test_bars_since_sweep_10_gives_6():
    """bars_since_sweep=10 → raw_score=3, scaled=6."""
    result = _score_bars_since_sweep({"candles_to_return": 10})
    assert result == pytest.approx(6.0)


def test_bars_since_sweep_11_gives_zero():
    """bars_since_sweep=11 → raw_score=0, scaled=0."""
    result = _score_bars_since_sweep({"candles_to_return": 11})
    assert result == pytest.approx(0.0)


def test_bars_since_sweep_uses_bars_since_sweep_field():
    """Also works with bars_since_sweep field name."""
    result = _score_bars_since_sweep({"bars_since_sweep": 2})
    assert result == pytest.approx(20.0)


def test_bars_since_sweep_missing_returns_zero():
    assert _score_bars_since_sweep({}) == 0.0


# ─────────────────────────────────────────────────────────────────
# Composite formula edge cases
# ─────────────────────────────────────────────────────────────────

def test_composite_all_zero():
    """All inputs 0 → composite=0."""
    result = score_signal({
        "departure_strength": 0,
        "return_strength": 100,   # inverted: 0
        "premium_discount": 1.0,  # SELL + pd=1.0 → 0
        "side": "sell",           
        "candles_to_return": 100, # > 10 → 0
    })
    assert result.hard_veto is False
    assert result.composite_score == pytest.approx(0.0)


def test_composite_all_max():
    """All inputs at maximum → composite=100.0."""
    result = score_signal({
        "departure_strength": 100,  # → 30
        "return_strength": 0,       # inverted → 25
        "premium_discount": 1.0,
        "side": "buy",              # BUY + pd=1.0 → 25
        "candles_to_return": 1,     # ≤2 → 20
    })
    assert result.hard_veto is False
    assert result.composite_score == pytest.approx(100.0)


def test_fires_council_flag_at_70():
    """composite_score >= 70 → fires_council=True."""
    # We need departure=100(30), return=0(25), pd=buy+1.0(25): total=80, bars=0: 80
    result = score_signal({
        "departure_strength": 100,
        "return_strength": 0,
        "premium_discount": 1.0,
        "side": "buy",
        "candles_to_return": 100,  # no bars score
    })
    assert result.composite_score == pytest.approx(80.0)
    assert result.fires_council is True
    assert result.can_block is True


def test_can_block_flag_requires_78():
    """composite_score = 72 → fires_council=True but can_block=False."""
    # departure=100(30), return=70 → (100-70)*0.25=7.5, pd=buy+1.0(25), bars=2(20) → 30+7.5+25+0=62.5
    # Let's engineer ~72: dep=100(30)+ret=0(25)+pd=buy+1.0(25)=80; no bars → 80 already too high
    # Use dep=50(15)+ret=0(25)+pd=buy+1.0(25)+bars=100(0) = 65: below 70
    # dep=70(21)+ret=0(25)+pd=buy+1.0(25)+bars=100(0) = 71: fires but not can_block
    result = score_signal({
        "departure_strength": 70,
        "return_strength": 0,
        "premium_discount": 1.0,
        "side": "buy",
        "candles_to_return": 100,
    })
    assert result.composite_score == pytest.approx(71.0)
    assert result.fires_council is True
    assert result.can_block is False


# ─────────────────────────────────────────────────────────────────
# EV formula
# ─────────────────────────────────────────────────────────────────

def test_ev_formula_known_values():
    """ev = (composite/100) * rr * (1 - dd_pct)."""
    # composite=80, rr=2.5, dd_pct=0.1 → ev = 0.80 * 2.5 * 0.9 = 1.8
    ev = _compute_ev({"rr_ratio": 2.5, "dd_pct": 0.1}, composite=80.0)
    assert ev == pytest.approx(1.8)


def test_ev_formula_missing_rr_returns_none():
    ev = _compute_ev({"dd_pct": 0.1}, composite=80.0)
    assert ev is None


def test_ev_formula_missing_dd_returns_none():
    ev = _compute_ev({"rr_ratio": 2.5}, composite=80.0)
    assert ev is None


def test_ev_dd_pct_clamped():
    """dd_pct > 1 is clamped to 1 → ev = 0."""
    ev = _compute_ev({"rr_ratio": 2.5, "dd_pct": 1.5}, composite=80.0)
    assert ev == pytest.approx(0.0)
