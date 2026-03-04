"""
Sprint 4.3: Memory retrieval for AI Guardian.

Retrieves top-k similar past trade reflections for a given signal context.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from config import get_settings

logger = logging.getLogger(__name__)


def _get_embedding(text: str) -> Optional[List[float]]:
    """Create embedding via OpenAI."""
    try:
        from openai import OpenAI
        import os
        s = get_settings()
        api_key = (s.ai_api_key.get_secret_value() if hasattr(s.ai_api_key, "get_secret_value") else str(s.ai_api_key or "")) or os.getenv("OPENAI_API_KEY", "")
        if not api_key:
            return None
        client = OpenAI(api_key=api_key)
        resp = client.embeddings.create(model="text-embedding-3-small", input=text)
        return resp.data[0].embedding
    except Exception as e:
        logger.warning("Memory retrieval embedding failed: %s", e)
        return None


def retrieve_similar_reflections(
    supabase: Any,
    payload: Dict[str, Any],
    k: int = 3,
) -> List[Dict[str, Any]]:
    """
    Retrieve top-k similar past trade reflections for a signal.

    Args:
        supabase: Supabase client
        payload: Incoming signal payload (symbol, side, zone_type, entry_model, etc.)
        k: Number of reflections to return

    Returns:
        List of reflection dicts with content, outcome, reasons, what_to_improve
    """
    if not supabase:
        return []
    s = get_settings()
    if not getattr(s, "memory_enabled", False):
        return []

    query_text = (
        f"{payload.get('zone_type', 'demand')} zone {payload.get('side', '')} "
        f"entry using {payload.get('entry_model', '')} model. "
        f"Symbol {payload.get('symbol', '')}"
    ).strip()

    embedding = _get_embedding(query_text)
    if not embedding:
        return []

    try:
        resp = supabase.rpc(
            "match_trade_reflections",
            {"query_embedding": embedding, "match_count": k},
        ).execute()
        rows = resp.data or []
        logger.info("Memory retrieval: %d similar reflections for %s", len(rows), payload.get("symbol", ""))
        return rows
    except Exception as e:
        logger.warning("Memory retrieval RPC failed: %s", e)
        return []


def format_reflections_for_prompt(reflections: List[Dict[str, Any]]) -> str:
    """Format retrieved reflections for inclusion in AI prompt."""
    if not reflections:
        return ""
    lines = ["Similar past situations:"]
    for i, r in enumerate(reflections, 1):
        outcome = r.get("outcome", "")
        reasons = r.get("reasons") or ""
        improve = r.get("what_to_improve") or ""
        r_mult = r.get("r_multiple")
        r_str = f" (R={r_mult})" if r_mult is not None else ""
        lines.append(f"  {i}. Outcome: {outcome}{r_str}. {reasons} {improve}".strip())
    return "\n".join(lines)
