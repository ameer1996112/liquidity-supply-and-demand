"""
rubric_engine.py — Phase 6 Four-Dimension Rubric Engine

Composite scoring gate that sits in front of the Trading Council.
Replaces the interim score_signal API with the production score_trade API.

Dimensions (max points):
  1. Liquidity Context     max=35  — departure_strength + kill_zone
  2. Zone Quality          max=25  — return_strength (inverted) + candles_to_return
  3. Structural Alignment  max=25  — premium_discount directional alignment
  4. Account & Environment max=15  — daily drawdown linear decay

Hard vetoes (composite_score=0, proceed=False):
  - sweep_candle_close == True
  - session == 0  (Sydney — illiquid session)
  - account_state["daily_drawdown_pct"] > 0.80
  - news_block == True  OR  time_to_news_minutes < 30

gate_status:
  - "blocked"  : composite < rubric_council_gate (70)
  - "shadow"   : rubric_council_gate <= composite < rubric_exec_gate (78)
  - "execute"  : composite >= rubric_exec_gate (78)
  - "disabled" : rubric_engine_enabled=False feature flag

Usage:
    from src.rubric_engine import score_trade
    result = score_trade(payload, account_state)
    if not result.proceed:
        # skip Trading Council
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, Optional

from config.settings import get_settings

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────
# Kill-zone lookup: 0→0, 1→5, 2→10
# ─────────────────────────────────────────────
_KILL_ZONE_PTS = {0: 0.0, 1: 5.0, 2: 10.0}

# Bars-since-sweep lookup: threshold → pts (max=10 pts)
_BARS_SWEEP_LOOKUP = [
    (2, 10),
    (5, 6),
    (10, 3),
]
_BARS_SWEEP_DEFAULT = 0


# ─────────────────────────────────────────────
# Result dataclass
# ─────────────────────────────────────────────

@dataclass
class RubricResult:
    composite_score: float                    # 0-100
    dimension_scores: Dict[str, float] = field(default_factory=dict)
    hard_veto: bool = False                   # True if any hard veto fired
    vetoed_by: Optional[str] = None          # veto name or None
    ev_score: Optional[float] = None         # (composite/100) * rr * (1 - dd_pct)
    proceed: bool = True                      # False = skip council entirely
    gate_status: str = "blocked"             # "blocked" | "shadow" | "execute" | "disabled"
    # Legacy shims (keep score_signal compatible)
    veto_reason: Optional[str] = None        # alias for vetoed_by
    fires_council: bool = False              # composite >= council_gate
    can_block: bool = False                  # composite >= exec_gate


# ─────────────────────────────────────────────
# Dimension scorers
# ─────────────────────────────────────────────

def _score_departure(payload: Dict[str, Any]) -> float:
    """Dimension 1a: Departure strength contribution (0-25 pts)."""
    raw = payload.get("departure_strength")
    if raw is None:
        return 0.0
    try:
        val = float(raw)
        # Scale: 0-100 → 0-25 pts (weight 0.25)
        return max(0.0, min(25.0, val * 0.25))
    except (TypeError, ValueError):
        return 0.0


def _score_kill_zone(payload: Dict[str, Any]) -> float:
    """Dimension 1b: Kill zone alignment contribution (0-10 pts)."""
    kz = payload.get("kill_zone")
    if kz is None:
        return 0.0
    try:
        kz_int = int(float(kz))
        return _KILL_ZONE_PTS.get(kz_int, 0.0)
    except (TypeError, ValueError):
        return 0.0


def _score_liquidity_context(payload: Dict[str, Any]) -> float:
    """Dimension 1: Liquidity Context (max 35 pts).

    = departure_strength * 0.25  +  kill_zone_lookup
    """
    return _score_departure(payload) + _score_kill_zone(payload)


def _score_return_strength(payload: Dict[str, Any]) -> float:
    """Dimension 2a: Return strength inverted (0-15 pts).

    Slow return (high raw) = strong demand = good.
    Fast impulsive return (low raw) = weak zone = bad. Inverted.
    Formula: (100 - raw) * 0.15, clamped 0-15.
    """
    raw = payload.get("return_strength")
    if raw is None:
        return 0.0
    try:
        val = float(raw)
        val = max(0.0, min(100.0, val))
        rubric = (100.0 - val) * 0.15
        return max(0.0, min(15.0, rubric))
    except (TypeError, ValueError):
        return 0.0


def _score_bars_since_sweep(payload: Dict[str, Any]) -> float:
    """Dimension 2b: Candles since sweep lookup (0-10 pts).

    Lookup table (bars → pts):
      ≤ 2  → 10 pts
      ≤ 5  → 6  pts
      ≤ 10 → 3  pts
      > 10 → 0  pts
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
        return float(raw)
    except (TypeError, ValueError):
        return 0.0


def _score_zone_quality(payload: Dict[str, Any]) -> float:
    """Dimension 2: Zone Quality (max 25 pts).

    = return_strength_inverted (0-15) + bars_since_sweep_pts (0-10), clamped to 25.
    """
    rs = _score_return_strength(payload)
    bs = _score_bars_since_sweep(payload)
    return min(25.0, rs + bs)


def _score_premium_discount(payload: Dict[str, Any]) -> float:
    """Dimension 3: Premium/Discount directional alignment (0-25 pts).

    BUY trade:  pd >= 0.5 → price in discount = 25, else 0
    SELL trade: pd <= 0.5 → price in premium = 25, else 0
    """
    raw_pd = payload.get("premium_discount")
    side = str(payload.get("side") or "buy").strip().lower()

    if raw_pd is None:
        return 0.0
    try:
        pd = float(raw_pd)
        pd = max(0.0, min(1.0, pd))

        if side in ("buy", "long"):
            return 25.0 if pd >= 0.5 else 0.0
        elif side in ("sell", "short"):
            return 25.0 if pd <= 0.5 else 0.0
        return 0.0
    except (TypeError, ValueError):
        return 0.0


def _score_account_environment(account_state: Optional[Dict[str, Any]], payload: Dict[str, Any]) -> float:
    """Dimension 4: Account & Environment (max 15 pts).

    Linear: 0% DD → 15 pts, 80% DD → 0 pts.
    Formula: max(0, 15 * (1 - dd_pct / 0.8)), capped at dd_pct=0.8.
    """
    dd_pct = (
        (account_state or {}).get("daily_drawdown_pct")
        or payload.get("daily_drawdown_pct")
        or 0.0
    )
    try:
        dd = float(dd_pct)
        dd = max(0.0, min(0.8, dd))  # cap at 0.8
        return max(0.0, 15.0 * (1.0 - dd / 0.8))
    except (TypeError, ValueError):
        return 0.0


# ─────────────────────────────────────────────
# EV formula
# ─────────────────────────────────────────────

def _compute_ev(payload: Dict[str, Any], composite: float, account_state: Optional[Dict[str, Any]] = None) -> Optional[float]:
    """EV score = (composite/100) * rr * (1 - dd_pct).

    Uses default_estimated_rr from settings when rr not in payload.
    dd_pct prefers account_state, falls back to payload, then 0.0.
    """
    s = get_settings()

    rr = payload.get("rr_ratio") or payload.get("rr") or s.default_estimated_rr
    dd_pct = (
        (account_state or {}).get("daily_drawdown_pct")
        or payload.get("daily_drawdown_pct")
        or 0.0
    )
    try:
        rr_f = float(rr)
        dd_f = float(dd_pct)
        dd_f = max(0.0, min(1.0, dd_f))
        return (composite / 100.0) * rr_f * (1.0 - dd_f)
    except (TypeError, ValueError):
        return None


# ─────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────

def score_trade(payload: Dict[str, Any], account_state: Optional[Dict[str, Any]] = None) -> RubricResult:
    """Score a signal through the 4-dimension rubric. Main Phase 6 API.

    Returns RubricResult with composite_score, dimension_scores, hard_veto,
    vetoed_by, ev_score, proceed, gate_status.

    Hard vetoes short-circuit all scoring and return composite_score=0, proceed=False.

    Args:
        payload: Signal payload dict (from Pine webhook + Phase 5 parsing)
        account_state: Per-account state dict with daily_drawdown_pct, balance, equity
    """
    s = get_settings()

    # ── Feature flag bypass ────────────────────────────────────
    if not s.rubric_engine_enabled:
        return RubricResult(
            composite_score=0.0,
            dimension_scores={},
            proceed=True,
            gate_status="disabled",
        )

    # ── Hard vetoes (checked before dimension scoring) ─────────
    sweep_candle_close = payload.get("sweep_candle_close")
    if sweep_candle_close is True or str(sweep_candle_close).lower() == "true":
        logger.info("Rubric hard veto: sweep_candle_close=True")
        return RubricResult(
            composite_score=0.0,
            hard_veto=True,
            vetoed_by="sweep_candle_close",
            veto_reason="sweep_candle_close=True — candle closed through sweep level",
            proceed=False,
            gate_status="blocked",
        )

    session = payload.get("session")
    if session is not None:
        try:
            if int(float(session)) == 0:
                logger.info("Rubric hard veto: session=0 (Sydney)")
                return RubricResult(
                    composite_score=0.0,
                    hard_veto=True,
                    vetoed_by="sydney_session",
                    veto_reason="session=0 — Sydney session is illiquid",
                    proceed=False,
                    gate_status="blocked",
                )
        except (TypeError, ValueError):
            pass

    dd_pct_val = (
        (account_state or {}).get("daily_drawdown_pct")
        or payload.get("daily_drawdown_pct")
        or 0.0
    )
    try:
        dd_pct_f = float(dd_pct_val)
    except (TypeError, ValueError):
        dd_pct_f = 0.0

    if dd_pct_f > 0.80:
        logger.info("Rubric hard veto: daily_drawdown_pct=%.3f > 0.80", dd_pct_f)
        return RubricResult(
            composite_score=0.0,
            hard_veto=True,
            vetoed_by="drawdown_exceeded",
            veto_reason=f"daily_drawdown_pct={dd_pct_f:.3f} > 80%",
            proceed=False,
            gate_status="blocked",
        )

    news_block = payload.get("news_block")
    time_to_news = payload.get("time_to_news_minutes", 999)
    try:
        time_to_news_f = float(time_to_news)
    except (TypeError, ValueError):
        time_to_news_f = 999.0

    if news_block is True or str(news_block).lower() == "true" or time_to_news_f < 30:
        logger.info("Rubric hard veto: news_block=%s time_to_news_minutes=%.1f", news_block, time_to_news_f)
        return RubricResult(
            composite_score=0.0,
            hard_veto=True,
            vetoed_by="news_proximity",
            veto_reason=f"news_block={news_block}, time_to_news_minutes={time_to_news_f}",
            proceed=False,
            gate_status="blocked",
        )

    # ── Dimension scoring ──────────────────────────────────────
    d1 = _score_liquidity_context(payload)
    d2 = _score_zone_quality(payload)
    d3 = _score_premium_discount(payload)
    d4 = _score_account_environment(account_state, payload)

    composite = d1 + d2 + d3 + d4
    composite = max(0.0, min(100.0, composite))

    dimension_scores = {
        "liquidity_context": round(d1, 4),
        "zone_quality": round(d2, 4),
        "structural_alignment": round(d3, 4),
        "account_environment": round(d4, 4),
    }

    # ── gate_status logic ──────────────────────────────────────
    if composite < s.rubric_council_gate:
        gate_status = "blocked"
        proceed = False
    elif composite < s.rubric_exec_gate:
        gate_status = "shadow"
        proceed = True
    else:
        gate_status = "execute"
        proceed = True

    # ── EV formula ─────────────────────────────────────────────
    ev = _compute_ev(payload, composite, account_state)

    result = RubricResult(
        composite_score=round(composite, 4),
        dimension_scores=dimension_scores,
        hard_veto=False,
        vetoed_by=None,
        veto_reason=None,
        ev_score=round(ev, 6) if ev is not None else None,
        proceed=proceed,
        gate_status=gate_status,
        fires_council=composite >= s.rubric_council_gate,
        can_block=composite >= s.rubric_exec_gate,
    )

    logger.debug(
        "Rubric: composite=%.1f gate=%s [liq=%.1f zone=%.1f align=%.1f env=%.1f]",
        composite, gate_status, d1, d2, d3, d4,
    )
    return result


def score_signal(payload: Dict[str, Any]) -> RubricResult:
    """Legacy shim — calls score_trade with no account_state. Backward compat."""
    return score_trade(payload, account_state=None)
