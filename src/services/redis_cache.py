"""
Generic Redis cache helper with TTL support.
Used by worker and API to cache frequently-accessed DB data
(symbol_risk_rules, daily trade counts, etc.) and reduce Supabase query load.
"""

import json
import logging
from typing import Any, Callable, Optional, TypeVar

logger = logging.getLogger(__name__)

T = TypeVar("T")

_redis_client = None


def _get_redis():
    global _redis_client
    if _redis_client is None:
        from src.adapters.redis_queue import get_redis
        _redis_client = get_redis()
    return _redis_client


def cache_get(key: str) -> Optional[Any]:
    """
    Retrieve a cached value by key.
    Returns None if key is missing or Redis is unavailable.
    """
    try:
        r = _get_redis()
        raw = r.get(key)
        if raw is None:
            return None
        return json.loads(raw)
    except Exception as exc:
        logger.debug("cache_get(%s) failed: %s", key, exc)
        return None


def cache_set(key: str, value: Any, ttl_seconds: int = 300) -> bool:
    """
    Store a value in Redis with a TTL.
    Returns True on success, False on failure (non-fatal).
    """
    try:
        r = _get_redis()
        r.setex(key, ttl_seconds, json.dumps(value))
        return True
    except Exception as exc:
        logger.debug("cache_set(%s) failed: %s", key, exc)
        return False


def cache_delete(key: str) -> bool:
    """Invalidate a cache key."""
    try:
        r = _get_redis()
        r.delete(key)
        return True
    except Exception as exc:
        logger.debug("cache_delete(%s) failed: %s", key, exc)
        return False


def cache_get_or_set(
    key: str,
    loader: Callable[[], T],
    ttl_seconds: int = 300,
) -> T:
    """
    Cache-aside pattern:
    1. Try to get from cache.
    2. On miss, call loader(), store result, return it.

    Always falls back to loader() if Redis is unavailable.
    """
    cached = cache_get(key)
    if cached is not None:
        return cached  # type: ignore[return-value]

    value = loader()
    cache_set(key, value, ttl_seconds)
    return value


# ── Domain-specific cache keys ────────────────────────────────────────────────

CACHE_KEYS = {
    "symbol_risk_rules": "cache:symbol_risk_rules",
    "daily_trade_count": "cache:daily_trade_count:{symbol}:{date}",
    "account_balance": "cache:account_balance:{account}",
    "risk_settings": "cache:risk_settings",
}


def get_symbol_risk_rules_cached(ttl_seconds: int = 300) -> list:
    """
    Fetch all symbol_risk_rules from Supabase, cached for ttl_seconds.
    Invalidate with cache_delete(CACHE_KEYS['symbol_risk_rules']).
    """
    key = CACHE_KEYS["symbol_risk_rules"]

    def loader():
        from src.adapters.supabase_api import get_api_supabase
        sb = get_api_supabase()
        try:
            resp = sb.table("symbol_risk_rules").select("*").execute()
            return resp.data or []
        except Exception as exc:
            logger.error("Failed to fetch symbol_risk_rules: %s", exc)
            return []

    return cache_get_or_set(key, loader, ttl_seconds)


def get_daily_trade_count_cached(symbol: str, date_str: str, ttl_seconds: int = 60) -> int:
    """
    Fetch today's trade count for a symbol from Supabase, cached for ttl_seconds.
    Short TTL (60s) since this changes frequently during trading hours.
    """
    key = CACHE_KEYS["daily_trade_count"].format(symbol=symbol.upper(), date=date_str)

    def loader():
        from src.adapters.supabase_api import get_api_supabase
        sb = get_api_supabase()
        try:
            today_start = f"{date_str}T00:00:00"
            resp = (
                sb.table("trading_signals")
                .select("id", count="exact")
                .eq("symbol", symbol.upper())
                .gte("created_at", today_start)
                .in_("status", ["executed", "active", "open", "closed"])
                .execute()
            )
            return resp.count or 0
        except Exception as exc:
            logger.error("Failed to fetch daily trade count for %s: %s", symbol, exc)
            return 0

    return cache_get_or_set(key, loader, ttl_seconds)


def invalidate_symbol_rules_cache() -> None:
    """Call after creating/updating/deleting a symbol_risk_rule."""
    cache_delete(CACHE_KEYS["symbol_risk_rules"])
    logger.debug("Invalidated symbol_risk_rules cache")
