"""
Sprint 4.3: Reflection + Memory loop.

Creates trade post-mortem records when positions close.
Stores reflections with embeddings for similarity retrieval.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from config import get_settings

logger = logging.getLogger(__name__)


def _compute_r_multiple(
    entry: float,
    sl: float,
    tp: float,
    exit_price: float,
    side: str,
) -> Optional[float]:
    """Compute R-multiple: (exit - entry) / (tp - entry) for buy, (entry - exit) / (entry - tp) for sell."""
    if not entry or not sl or not tp or not exit_price:
        return None
    risk = abs(entry - sl)
    if risk <= 0:
        return None
    side_lower = (side or "buy").lower()
    if side_lower == "buy":
        pnl_r = (exit_price - entry) / risk
    else:
        pnl_r = (entry - exit_price) / risk
    return round(float(pnl_r), 4)


def _build_reflection_content(signal: Dict[str, Any], reasons: str, what_to_improve: str) -> str:
    """Build searchable text for embedding."""
    parts = [
        f"Symbol: {signal.get('symbol', '')}",
        f"Side: {signal.get('side', '')}",
        f"Zone type: {signal.get('zone_type', 'demand')}",
        f"Entry model: {signal.get('entry_model', '')}",
        f"Outcome: {signal.get('outcome', '')}",
        f"Score: {signal.get('score', '')}",
    ]
    if reasons:
        parts.append(f"Reasons: {reasons}")
    if what_to_improve:
        parts.append(f"Improvements: {what_to_improve}")
    return "\n".join(parts)


def _get_embedding(text: str) -> Optional[List[float]]:
    """Create embedding via OpenAI. Returns None if disabled or fails."""
    try:
        from openai import OpenAI
        import os
        s = get_settings()
        api_key = (s.ai_api_key.get_secret_value() if hasattr(s.ai_api_key, "get_secret_value") else str(s.ai_api_key or "")) or os.getenv("OPENAI_API_KEY", "")
        if not api_key:
            return None
        client = OpenAI(api_key=api_key)
        resp = client.embeddings.create(
            model="text-embedding-3-small",
            input=text,
        )
        return resp.data[0].embedding
    except Exception as e:
        logger.warning("Reflection embedding failed: %s", e)
        return None


def create_reflection_on_close(
    supabase: Any,
    trade_id: int,
    signal: Optional[Dict[str, Any]] = None,
    *,
    reasons: str = "",
    what_to_improve: str = "",
) -> Optional[Dict[str, Any]]:
    """
    Create a trade post-mortem record when a position closes.

    Args:
        supabase: Supabase client
        trade_id: trading_signals.id
        signal: Full signal row (optional; fetched if not provided)
        reasons: Why it won/lost
        what_to_improve: Lessons / improvements

    Returns:
        Inserted reflection row or None if skipped/failed
    """
    if not supabase:
        return None
    s = get_settings()
    if not getattr(s, "memory_enabled", False):
        return None

    if not signal:
        try:
            resp = supabase.table("trading_signals").select("*").eq("id", trade_id).single().execute()
            signal = resp.data
        except Exception as e:
            logger.warning("Reflection: failed to fetch signal %s: %s", trade_id, e)
            return None

    if not signal:
        return None

    outcome = (signal.get("outcome") or signal.get("status") or "").lower()
    if outcome not in ("win", "loss", "breakeven"):
        outcome = "breakeven"

    entry = float(signal.get("entry") or 0)
    sl = float(signal.get("sl") or 0)
    tp = float(signal.get("tp") or 0)
    exit_price = float(signal.get("exit_price") or signal.get("close_price") or 0)
    side = signal.get("side", "buy")

    r_multiple = _compute_r_multiple(entry, sl, tp, exit_price, side)
    max_adverse_excursion = signal.get("mae_pips") or signal.get("max_adverse_excursion")

    content = _build_reflection_content(signal, reasons, what_to_improve)
    embedding = _get_embedding(content)

    row = {
        "trade_id": trade_id,
        "outcome": outcome,
        "r_multiple": r_multiple,
        "max_adverse_excursion": float(max_adverse_excursion) if max_adverse_excursion is not None else None,
        "reasons": reasons or None,
        "what_to_improve": what_to_improve or None,
        "content": content,
    }
    if embedding is not None:
        row["embedding"] = embedding

    try:
        # Upsert to handle duplicate close events
        resp = supabase.table("trade_reflections").upsert(
            row,
            on_conflict="trade_id",
        ).execute()
        if resp.data and len(resp.data) > 0:
            logger.info("Reflection created for trade %s (outcome=%s, r=%.2f)", trade_id, outcome, r_multiple or 0)
            return resp.data[0]
    except Exception as e:
        logger.warning("Reflection insert failed for trade %s: %s", trade_id, e)
    return None


def create_reflection_on_close_safe(
    supabase: Any,
    trade_id: int,
    signal: Optional[Dict[str, Any]] = None,
    **kwargs: Any,
) -> None:
    """
    Safe wrapper that never raises. Call from watchdog, account_sync, etc.
    """
    try:
        create_reflection_on_close(supabase, trade_id, signal, **kwargs)
    except Exception as e:
        logger.warning("Reflection on close failed (non-fatal): %s", e)
