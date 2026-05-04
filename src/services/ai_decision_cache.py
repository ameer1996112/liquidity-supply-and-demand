"""
AI decision cache for repeated optimizer/debate evaluations.

Cache key = hash(strategy_version + prompt_version + model + signal_hash + candle_context_hash)
"""

from __future__ import annotations

import hashlib
import json
import logging
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

STRATEGY_VERSION = "snd_v1"
PROMPT_VERSION = "ensemble_v1"


def _hash_str(s: str) -> str:
    return hashlib.sha256(s.encode()).hexdigest()[:32]


def build_cache_key(
    signal_hash: str,
    candle_context_hash: str,
    model: str = "",
) -> str:
    """Build cache key from components."""
    parts = f"{STRATEGY_VERSION}|{PROMPT_VERSION}|{model}|{signal_hash}|{candle_context_hash}"
    return _hash_str(parts)


def cache_get(supabase: Any, cache_key: str) -> Optional[Dict[str, Any]]:
    """Get cached decision. Returns None if miss."""
    if not supabase:
        return None
    try:
        resp = (
            supabase.table("ai_decision_cache")
            .select("decision_json")
            .eq("cache_key", cache_key)
            .limit(1)
            .execute()
        )
        if resp.data and len(resp.data) > 0:
            return resp.data[0].get("decision_json")
    except Exception as e:
        logger.debug("ai_decision_cache get failed: %s", e)
    return None


def cache_set(
    supabase: Any,
    cache_key: str,
    decision_json: Dict[str, Any],
    *,
    transcript_hash: str = "",
    token_estimate: int = 0,
    cost_estimate: float = 0,
) -> bool:
    """Store decision in cache. Upsert on key."""
    if not supabase:
        return False
    try:
        row = {
            "cache_key": cache_key,
            "decision_json": decision_json,
            "transcript_hash": transcript_hash or None,
            "token_estimate": token_estimate,
            "cost_estimate": cost_estimate,
        }
        supabase.table("ai_decision_cache").upsert(
            row,
            on_conflict="cache_key",
        ).execute()
        return True
    except Exception as e:
        logger.warning("ai_decision_cache set failed: %s", e)
        return False


def signal_hash(payload: Dict[str, Any]) -> str:
    """Stable hash of signal payload for cache key."""
    canonical = {
        "symbol": payload.get("symbol"),
        "side": payload.get("side"),
        "entry": payload.get("entry"),
        "sl": payload.get("sl"),
        "tp": payload.get("tp"),
        "zone_id": payload.get("zone_id"),
        "score": payload.get("score"),
        "entry_model": payload.get("entry_model"),
    }
    return _hash_str(json.dumps(canonical, sort_keys=True))


def candle_context_hash(candles_slice: list) -> str:
    """Hash of recent candle context (e.g. last 10 OHLC)."""
    if not candles_slice:
        return _hash_str("")
    canonical = [
        {"o": c.get("open"), "h": c.get("high"), "l": c.get("low"), "c": c.get("close")}
        for c in candles_slice[-10:]
    ]
    return _hash_str(json.dumps(canonical, sort_keys=True))
