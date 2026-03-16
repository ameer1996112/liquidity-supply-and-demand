"""
Sprint 3.4: Strategy graduation pipeline — shadow vs actual outcome metrics.

Tracks what AI would have blocked vs what happened.
Computes win-rate / drawdown delta for graduation readiness.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class ShadowMetrics:
    """Shadow vs actual outcome metrics."""

    sample_size: int
    sample_size_ai_blocked: int  # trades that ran but AI would have blocked
    sample_size_ai_allowed: int

    win_rate_actual: float  # overall executed win rate
    win_rate_if_blocked: float  # win rate of trades AI would have blocked
    win_rate_if_allowed: float  # win rate of trades AI allowed

    total_pnl_actual: float
    total_pnl_if_blocked: float  # pnl from trades AI would have blocked
    total_pnl_if_allowed: float

    edge_pct: float  # win_rate_if_allowed - win_rate_if_blocked (positive = AI adds value)
    pnl_edge_usd: float  # pnl_if_allowed - pnl_if_blocked (positive = blocking bad trades helped)


def _parse_ai_would_have_blocked(ai_reasoning: Any) -> bool:
    """Extract ai_would_have_blocked from ai_reasoning JSON. Fallback: check decision_trace for ai_shadow_override."""
    if not ai_reasoning:
        return False
    if isinstance(ai_reasoning, str):
        try:
            data = json.loads(ai_reasoning)
        except json.JSONDecodeError:
            return False
    else:
        data = ai_reasoning
    if not isinstance(data, dict):
        return False
    if data.get("ai_would_have_blocked") is True:
        return True
    trace = data.get("decision_trace") or {}
    rules = trace.get("rules") or []
    return any(
        str(r.get("rule_id", "")).lower() == "ai_shadow_override"
        for r in rules
        if isinstance(r, dict)
    )


def compute_shadow_metrics(
    supabase: Any,
    *,
    account_id: Optional[str] = None,
    min_days: int = 7,
) -> ShadowMetrics:
    """
    Compute shadow vs actual metrics from closed trades with ai_reasoning.

    Uses trading_signals where status='closed' and outcome in ('win','loss').
    """
    if not supabase:
        return ShadowMetrics(
            sample_size=0,
            sample_size_ai_blocked=0,
            sample_size_ai_allowed=0,
            win_rate_actual=0.0,
            win_rate_if_blocked=0.0,
            win_rate_if_allowed=0.0,
            total_pnl_actual=0.0,
            total_pnl_if_blocked=0.0,
            total_pnl_if_allowed=0.0,
            edge_pct=0.0,
            pnl_edge_usd=0.0,
        )

    try:
        from datetime import datetime, timedelta, timezone

        since = (datetime.now(timezone.utc) - timedelta(days=min_days)).isoformat()
        q = (
            supabase.table("trading_signals")
            .select("id, outcome, pnl_usd, ai_reasoning")
            .in_("status", ["CLOSED", "closed"])
            .in_("outcome", ["win", "loss"])
            .gte("created_at", since)
        )
        if account_id:
            q = q.eq("account_id", account_id)
        resp = q.execute()
        rows = resp.data or []
    except Exception as e:
        logger.warning("Failed to fetch shadow metrics: %s", e)
        return ShadowMetrics(
            sample_size=0,
            sample_size_ai_blocked=0,
            sample_size_ai_allowed=0,
            win_rate_actual=0.0,
            win_rate_if_blocked=0.0,
            win_rate_if_allowed=0.0,
            total_pnl_actual=0.0,
            total_pnl_if_blocked=0.0,
            total_pnl_if_allowed=0.0,
            edge_pct=0.0,
            pnl_edge_usd=0.0,
        )

    blocked: List[Dict[str, Any]] = []
    allowed: List[Dict[str, Any]] = []
    for r in rows:
        outcome = (r.get("outcome") or "").lower()
        if outcome not in ("win", "loss"):
            continue
        pnl = float(r.get("pnl_usd") or 0)
        would_block = _parse_ai_would_have_blocked(r.get("ai_reasoning"))
        row = {"outcome": outcome, "pnl": pnl}
        if would_block:
            blocked.append(row)
        else:
            allowed.append(row)

    n_blocked = len(blocked)
    n_allowed = len(allowed)
    n_total = n_blocked + n_allowed

    def win_rate(rows: List[Dict]) -> float:
        if not rows:
            return 0.0
        wins = sum(1 for r in rows if r.get("outcome") == "win")
        return (wins / len(rows)) * 100.0

    def total_pnl(rows: List[Dict]) -> float:
        return sum(r.get("pnl", 0) for r in rows)

    wr_actual = win_rate(blocked + allowed) if n_total else 0.0
    wr_blocked = win_rate(blocked) if n_blocked else 0.0
    wr_allowed = win_rate(allowed) if n_allowed else 0.0
    pnl_blocked = total_pnl(blocked)
    pnl_allowed = total_pnl(allowed)
    pnl_actual = pnl_blocked + pnl_allowed

    # Edge: if we had blocked (AI said no), we'd have avoided pnl_blocked. If pnl_blocked < 0, blocking was good.
    # Win rate edge: wr_allowed - wr_blocked. Positive = AI allows better trades.
    edge_pct = wr_allowed - wr_blocked if (n_blocked and n_allowed) else 0.0
    pnl_edge_usd = pnl_allowed - (0 if n_blocked == 0 else (pnl_blocked / n_blocked * n_total))  # simplified: net benefit of blocking
    pnl_edge_usd = pnl_allowed - pnl_blocked  # blocking those trades would have saved pnl_blocked (if negative)

    return ShadowMetrics(
        sample_size=n_total,
        sample_size_ai_blocked=n_blocked,
        sample_size_ai_allowed=n_allowed,
        win_rate_actual=round(wr_actual, 2),
        win_rate_if_blocked=round(wr_blocked, 2),
        win_rate_if_allowed=round(wr_allowed, 2),
        total_pnl_actual=round(pnl_actual, 2),
        total_pnl_if_blocked=round(pnl_blocked, 2),
        total_pnl_if_allowed=round(pnl_allowed, 2),
        edge_pct=round(edge_pct, 2),
        pnl_edge_usd=round(pnl_edge_usd, 2),
    )


def check_graduation_readiness(
    metrics: ShadowMetrics,
    min_sample_size: int,
    min_edge_pct: float,
) -> Dict[str, Any]:
    """
    Check if ready to enable enforce mode.

    Returns dict with ready, reason, metrics.
    """
    reasons: List[str] = []
    if metrics.sample_size < min_sample_size:
        reasons.append(
            f"Sample size {metrics.sample_size} < {min_sample_size} (need more shadow data)"
        )
    if metrics.edge_pct < min_edge_pct:
        reasons.append(
            f"Win-rate edge {metrics.edge_pct}% < {min_edge_pct}% (AI block group underperforms)"
        )
    ready = len(reasons) == 0
    return {
        "ready": ready,
        "reason": "; ".join(reasons) if reasons else "Ready to graduate",
        "metrics": {
            "sample_size": metrics.sample_size,
            "sample_size_ai_blocked": metrics.sample_size_ai_blocked,
            "sample_size_ai_allowed": metrics.sample_size_ai_allowed,
            "win_rate_actual": metrics.win_rate_actual,
            "win_rate_if_blocked": metrics.win_rate_if_blocked,
            "win_rate_if_allowed": metrics.win_rate_if_allowed,
            "edge_pct": metrics.edge_pct,
            "pnl_edge_usd": metrics.pnl_edge_usd,
        },
        "thresholds": {
            "min_sample_size": min_sample_size,
            "min_edge_pct": min_edge_pct,
        },
    }
