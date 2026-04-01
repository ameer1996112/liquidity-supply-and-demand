"""
LiquidityScorer — Fast composite confidence scorer for 1-candle liquidity trades.

Decision latency target: < 100ms (all data pre-cached or from payload).

Score components (max ~190 raw pts, normalized to 0–100):
  1. Zone Quality   (from Pine payload)   — up to 100 pts
  2. Market Context (60s MetaAPI cache)   — up to 70 pts
  3. Historical Win Rate (Supabase query) — up to 20 pts

Minimum score to execute: 70 / 100
"""

from __future__ import annotations

import logging
from typing import Optional

logger = logging.getLogger("trinity.liquidity_scorer")

# ---------------------------------------------------------------------------
# Score thresholds
# ---------------------------------------------------------------------------
MIN_EXECUTE_SCORE = 70   # Trades scoring below this are rejected
_RAW_MAX = 190           # Sum of all possible raw points (for normalization)

# ---------------------------------------------------------------------------
# Component weights
# ---------------------------------------------------------------------------

def _score_zone_quality(payload: dict) -> tuple[int, dict]:
    """Component 1: Zone quality from Pine payload fields. Max 100 pts."""
    pts = 0
    breakdown: dict = {}

    # Sweep → Touch bars (how quickly price reacted after sweep)
    stb = payload.get("sweep_to_touch_bars")
    if stb is not None:
        try:
            stb = int(stb)
            if stb == 0:
                pts += 30; breakdown["sweep_to_touch"] = 30
            elif stb == 1:
                pts += 15; breakdown["sweep_to_touch"] = 15
            else:
                breakdown["sweep_to_touch"] = 0
        except (ValueError, TypeError):
            breakdown["sweep_to_touch"] = 0
    else:
        breakdown["sweep_to_touch"] = 0

    # Peak → Touch bars (distance from structural extreme to zone touch)
    ptb = payload.get("peak_to_touch_bars")
    if ptb is not None:
        try:
            ptb = int(ptb)
            if ptb <= 3:
                pts += 20; breakdown["peak_to_touch"] = 20
            elif ptb <= 6:
                pts += 10; breakdown["peak_to_touch"] = 10
            else:
                breakdown["peak_to_touch"] = 0
        except (ValueError, TypeError):
            breakdown["peak_to_touch"] = 0
    else:
        breakdown["peak_to_touch"] = 0

    # Liquidity source quality
    liq_source = str(payload.get("liq_source") or "").upper()
    if "PIVOT" in liq_source:
        pts += 15; breakdown["liq_source"] = 15
    else:
        breakdown["liq_source"] = 0

    # Zone grade
    zone_grade = str(payload.get("zone_grade") or "").upper()
    if zone_grade == "A":
        pts += 15; breakdown["zone_grade"] = 15
    elif zone_grade == "B":
        pts += 5; breakdown["zone_grade"] = 5
    else:
        breakdown["zone_grade"] = 0

    # AI score
    ai = payload.get("ai_score") or payload.get("score")
    if ai is not None:
        try:
            ai = float(ai)
            if ai >= 70:
                pts += 20; breakdown["ai_score"] = 20
            elif ai >= 55:
                pts += 10; breakdown["ai_score"] = 10
            else:
                breakdown["ai_score"] = 0
        except (ValueError, TypeError):
            breakdown["ai_score"] = 0
    else:
        breakdown["ai_score"] = 0

    return pts, breakdown


def _score_market_context(payload: dict, market_cache: dict) -> tuple[int, dict]:
    """Component 2: Market context from pre-cached MetaAPI data. Max 70 pts."""
    pts = 0
    breakdown: dict = {}

    # 200 EMA alignment — from cache, or fall back to payload trend field
    # trend: 1=bullish (demand ok), -1=bearish (supply ok), 0=neutral
    ema_aligned = market_cache.get("ema_aligned")
    if ema_aligned is None:
        # Cache not yet wired — use Pine's trend feature as proxy
        trend = payload.get("trend")
        side = str(payload.get("side") or "").lower()
        if trend is not None:
            try:
                tv = int(trend)
                ema_aligned = (tv == 1 and side == "buy") or (tv == -1 and side == "sell")
            except (ValueError, TypeError):
                ema_aligned = False
    if ema_aligned is True:
        pts += 25; breakdown["ema_aligned"] = 25
    else:
        breakdown["ema_aligned"] = 0

    # ATR-normalized zone size in optimal range (0.1 – 0.5 ATR = good)
    zone_atr_ok = market_cache.get("zone_atr_ok")
    if zone_atr_ok is True:
        pts += 15; breakdown["zone_atr"] = 15
    else:
        breakdown["zone_atr"] = 0

    # Trading session quality
    session_prime = market_cache.get("session_prime")
    if session_prime is True:
        pts += 20; breakdown["session"] = 20
    else:
        # Partial: session from payload (0=Asia,1=London,2=NY,3=Sydney)
        session_val = payload.get("session")
        if session_val is not None:
            try:
                sv = int(session_val)
                if sv in (1, 2):  # London or NY
                    pts += 20; breakdown["session"] = 20
                else:
                    breakdown["session"] = 0
            except (ValueError, TypeError):
                breakdown["session"] = 0
        else:
            breakdown["session"] = 0

    # Day of week (Monday/Tuesday historically better)
    day_prime = market_cache.get("day_prime")
    if day_prime is True:
        pts += 10; breakdown["day_quality"] = 10
    else:
        breakdown["day_quality"] = 0

    return pts, breakdown


def _score_historical(win_rate: Optional[float]) -> tuple[int, dict]:
    """Component 3: Historical win rate bonus. Max 20 pts."""
    if win_rate is None:
        return 0, {"historical_win_rate": 0}
    if win_rate >= 50.0:
        return 20, {"historical_win_rate": 20}
    if win_rate >= 40.0:
        return 10, {"historical_win_rate": 10}
    return 0, {"historical_win_rate": 0}


class LiquidityScorer:
    """
    Composite confidence scorer for 1-candle liquidity setups.

    Usage:
        scorer = LiquidityScorer()
        result = scorer.score(payload, market_cache, win_rate=35.0)
        if scorer.should_execute(result["score"]):
            ...
    """

    def score(
        self,
        payload: dict,
        market_cache: Optional[dict] = None,
        win_rate: Optional[float] = None,
    ) -> dict:
        """
        Compute composite confidence score.

        Returns dict with keys:
          - score (int, 0–100)
          - raw (int)
          - breakdown (dict of component scores)
          - execute (bool)
          - reason (str, for logging)
        """
        if market_cache is None:
            market_cache = {}

        c1_pts, c1_bd = _score_zone_quality(payload)
        c2_pts, c2_bd = _score_market_context(payload, market_cache)
        c3_pts, c3_bd = _score_historical(win_rate)

        raw = c1_pts + c2_pts + c3_pts
        normalized = int((raw / _RAW_MAX) * 100)
        execute = normalized >= MIN_EXECUTE_SCORE

        breakdown = {**c1_bd, **c2_bd, **c3_bd}

        logger.debug(
            "LiquidityScorer | symbol=%s side=%s raw=%d score=%d execute=%s | %s",
            payload.get("symbol"), payload.get("side"), raw, normalized, execute, breakdown
        )

        return {
            "score": normalized,
            "raw": raw,
            "breakdown": breakdown,
            "execute": execute,
            "reason": f"liquidity_score={normalized}/100 (raw={raw}/{_RAW_MAX})"
                      + ("" if execute else f" — below threshold {MIN_EXECUTE_SCORE}"),
        }

    def should_execute(self, score: int) -> bool:
        return score >= MIN_EXECUTE_SCORE

    # ------------------------------------------------------------------
    # Hard gates — binary checks, independent of scoring
    # These match the Pine hard gates but give the backend a second check
    # ------------------------------------------------------------------

    @staticmethod
    def passes_hard_gates(payload: dict) -> tuple[bool, str]:
        """
        Returns (True, "") if all hard gates pass.
        Returns (False, reason) if any gate fails.

        These gates mirror the Pine-side hard gates. If Pine is correctly
        configured, signals failing these should never reach the backend.
        But we keep them here as a safety net.
        """
        # Primed check
        primed = payload.get("primed")
        if primed is False:
            return False, "hard_gate: primed=false"

        # Zone found (zone_id present and valid)
        zone_id = payload.get("zone_id")
        if zone_id is None:
            return False, "hard_gate: zone_id missing (zone not found)"

        # Leg candle count
        lcc = payload.get("liq_candle_count")
        if lcc is not None:
            try:
                if int(lcc) != 1:
                    return True, ""  # Not a 1-candle liq — skip liq-specific gates
            except (ValueError, TypeError):
                pass

        # Caused sweep
        if payload.get("caused_sweep") is False:
            return False, "hard_gate: zone did not cause sweep"

        return True, ""
