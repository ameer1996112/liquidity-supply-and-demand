"""
rubric_engine.py — Phase 2 Signal Quality Rubric

Four-dimension composite scoring gate that sits in front of the Trading Council.
Replaces free-entry to the 9-stage LLM pipeline with a structured pre-filter.

Dimensions (weights sum to 1.0):
  1. Departure strength      weight=0.30  — raw 0-100, direct pass-through
  2. Return strength         weight=0.25  — inverted: slow return = good, fast = weak
  3. Premium / Discount      weight=0.25  — directional alignment of price location
  4. Time since sweep        weight=0.20  — bars_since_sweep lookup table

Hard vetoes (composite_score=0, council never fires):
  - sweep_candle_close == True
  - session == 0  (Sydney — illiquid session)

EV formula (informational):
  ev_score = (composite / 100) * rr * (1 - dd_pct)

Usage:
    from src.rubric_engine import score_signal
    result = score_signal(payload)
    if result.hard_veto or result.composite_score < 70:
        # skip Trading Council
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────
# Constants
# ─────────────────────────────────────────────

_COUNCIL_SHADOW_THRESHOLD = 70    # composite_score >= 70 → council fires (shadow mode)
_COUNCIL_BLOCK_THRESHOLD  = 78    # composite_score >= 78 → council can block execution

# Dimension weights (must sum to 1.0)
_W_DEPARTURE   = 0.30
_W_RETURN      = 0.25
_W_PREMIUM_DISC = 0.25
_W_TIME_SWEEP  = 0.20

# Return strength inversion: rubric = (100 - raw) * 0.25  (clamped 0-25)
# Test: raw=30 → (100-30)*0.25 = 17.5 ✓
_RETURN_INVERT_FACTOR = 0.25

# Bars-since-sweep lookup (bars → score out of 10)
_BARS_SWEEP_LOOKUP = [
    (2,  10),
    (5,  6),
    (10, 3),
]
_BARS_SWEEP_DEFAULT = 0


# ─────────────────────────────────────────────
# Result dataclass
# ─────────────────────────────────────────────

@dataclass
class RubricResult:
    composite_score: float
    dimension_scores: Dict[str, float] = field(default_factory=dict)
    hard_veto: bool = False
    veto_reason: Optional[str] = None
    ev_score: Optional[float] = None
    # Convenience flags mirroring thresholds
    fires_council: bool = False       # composite_score >= 70
    can_block: bool = False           # composite_score >= 78


# ─────────────────────────────────────────────
# Dimension scorers
# ─────────────────────────────────────────────

def _score_departure(payload: Dict[str, Any]) -> float:
    """Dimension 1: Departure strength (0-30), direct map from raw 0-100."""
    raw = payload.get("departure_strength")
    if raw is None:
        return 0.0
    try:
        val = float(raw)
        # Scale: raw 0-100 → score 0-30 (weight=0.30)
        return max(0.0, min(30.0, val * _W_DEPARTURE))
    except (TypeError, ValueError):
        return 0.0


def _score_return_strength(payload: Dict[str, Any]) -> float:
    """Dimension 2: Return strength inverted (0-25).

    Slow return (high raw) = strong demand into zone = good.
    Fast impulsive return (low raw) = weak zone = bad. Inverted.

    Formula: rubric = (100 - raw) * 0.25, clamped 0-25.
    Test: raw=30 → (100-30)*0.25 = 17.5 ✓
    """
    raw = payload.get("return_strength")
    if raw is None:
        return 0.0
    try:
        val = float(raw)
        val = max(0.0, min(100.0, val))  # clamp input
        rubric = (100.0 - val) * _RETURN_INVERT_FACTOR
        return max(0.0, min(25.0, rubric))
    except (TypeError, ValueError):
        return 0.0


def _score_premium_discount(payload: Dict[str, Any]) -> float:
    """Dimension 3: Premium/Discount directional alignment (0-25).

    BUY trade:  pd >= 0.5 → price in discount = 25, else 0
    SELL trade: pd <= 0.5 → price in premium = 25, else 0

    pd is clamped to [0, 1] before evaluation to handle Pine bugs.
    """
    raw_pd = payload.get("premium_discount")
    side = str(payload.get("side") or "buy").strip().lower()

    if raw_pd is None:
        return 0.0
    try:
        pd = float(raw_pd)
        pd = max(0.0, min(1.0, pd))  # clamp gracefully

        if side in ("buy", "long"):
            return 25.0 if pd >= 0.5 else 0.0
        elif side in ("sell", "short"):
            return 25.0 if pd <= 0.5 else 0.0
        return 0.0
    except (TypeError, ValueError):
        return 0.0


def _score_bars_since_sweep(payload: Dict[str, Any]) -> float:
    """Dimension 4: Time since sweep via bars_since_sweep (candles_to_return) (0-20).

    Lookup table (bars → score out of 10), scaled by weight=0.20:
      ≤ 2  → 10  (very recent = score=10, weighted=20)
      ≤ 5  → 6   (recent = score=6, weighted=12)
      ≤ 10 → 3   (moderate = score=3, weighted=6)
      > 10 → 0

    Wait — the weight is 0.20, but raw scores go 0-10; 10 * 0.20 = 2.0 which is too low.
    Design intent: dimension max contribution = 20 points to composite.
    So raw score 0-10 → multiply by 2.0 to get 0-20.
    """
    bars = payload.get("candles_to_return") or payload.get("bars_since_sweep")
    if bars is None:
        return 0.0
    try:
        b = int(float(bars))
        raw = _BARS_SWEEP_DEFAULT
        for threshold, score in _BARS_SWEEP_LOOKUP:
            if b <= threshold:
                raw = score
                break
        return float(raw * 2)  # scale 0-10 → 0-20
    except (TypeError, ValueError):
        return 0.0


# ─────────────────────────────────────────────
# EV formula
# ─────────────────────────────────────────────

def _compute_ev(payload: Dict[str, Any], composite: float) -> Optional[float]:
    """EV score = (composite/100) * rr * (1 - dd_pct).

    Returns None if required fields are missing.
    dd_pct should be in [0, 1] (e.g. 0.05 = 5% drawdown).
    rr is the risk/reward ratio (e.g. 2.5).
    """
    rr = payload.get("rr_ratio") or payload.get("rr")
    dd_pct = payload.get("dd_pct") or payload.get("daily_drawdown_pct")
    if rr is None or dd_pct is None:
        return None
    try:
        rr_f = float(rr)
        dd_f = float(dd_pct)
        dd_f = max(0.0, min(1.0, dd_f))  # clamp to [0, 1]
        return (composite / 100.0) * rr_f * (1.0 - dd_f)
    except (TypeError, ValueError):
        return None


# ─────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────

def score_signal(payload: Dict[str, Any]) -> RubricResult:
    """Score a signal payload through the 4-dimension rubric.

    Returns a RubricResult with composite_score (0-100), per-dimension
    scores, hard veto status, and EV score.

    Hard vetoes short-circuit scoring and return composite_score=0:
      - sweep_candle_close == True
      - session == 0 (Sydney session)
    """
    # ── Hard vetoes ───────────────────────────────────────────
    sweep_candle_close = payload.get("sweep_candle_close")
    if sweep_candle_close is True or str(sweep_candle_close).lower() == "true":
        logger.info("Rubric hard veto: sweep_candle_close=True")
        return RubricResult(
            composite_score=0.0,
            hard_veto=True,
            veto_reason="sweep_candle_close=True — candle closed through sweep level",
        )

    session = payload.get("session")
    if session is not None:
        try:
            if int(session) == 0:
                logger.info("Rubric hard veto: session=0 (Sydney)")
                return RubricResult(
                    composite_score=0.0,
                    hard_veto=True,
                    veto_reason="session=0 — Sydney session is illiquid",
                )
        except (TypeError, ValueError):
            pass

    # ── Dimension scoring ─────────────────────────────────────
    d1 = _score_departure(payload)
    d2 = _score_return_strength(payload)
    d3 = _score_premium_discount(payload)
    d4 = _score_bars_since_sweep(payload)

    composite = d1 + d2 + d3 + d4
    # Clamp to [0, 100] in case of floating-point edge cases
    composite = max(0.0, min(100.0, composite))

    dimension_scores = {
        "departure_strength": round(d1, 4),
        "return_strength_inverted": round(d2, 4),
        "premium_discount": round(d3, 4),
        "bars_since_sweep": round(d4, 4),
    }

    ev = _compute_ev(payload, composite)

    result = RubricResult(
        composite_score=round(composite, 4),
        dimension_scores=dimension_scores,
        hard_veto=False,
        veto_reason=None,
        ev_score=round(ev, 6) if ev is not None else None,
        fires_council=composite >= _COUNCIL_SHADOW_THRESHOLD,
        can_block=composite >= _COUNCIL_BLOCK_THRESHOLD,
    )

    logger.debug(
        "Rubric: composite=%.1f [dep=%.1f ret=%.1f pd=%.1f sweep=%.1f] fires=%s can_block=%s",
        composite, d1, d2, d3, d4, result.fires_council, result.can_block,
    )
    return result
