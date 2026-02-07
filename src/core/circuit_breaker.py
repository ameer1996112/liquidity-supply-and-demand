"""
Circuit breaker for external services (e.g. MetaApi).
Uses Redis so worker, API, and watchdog share the same state.
"""

from __future__ import annotations

import logging
import time
from typing import Optional

logger = logging.getLogger(__name__)

# Redis key: when set, LIVE execution and MetaApi calls should be skipped until TTL or manual reset
METAAPI_CIRCUIT_KEY = "trading:circuit_breaker:metaapi"
# TTL seconds (e.g. 5 min) so breaker auto-resets after rate limit cools down
DEFAULT_TTL = 300


def is_metaapi_circuit_open() -> bool:
    """True if MetaApi circuit breaker is open (should not call MetaApi / skip LIVE execution)."""
    try:
        from src.adapters.redis_queue import get_redis
        r = get_redis()
        return r.get(METAAPI_CIRCUIT_KEY) == "1"
    except Exception as exc:  # noqa: BLE001
        logger.debug("Circuit breaker check failed (fail-open): %s", exc)
        return False


def set_metaapi_circuit_open(ttl_seconds: int = DEFAULT_TTL) -> None:
    """Open the MetaApi circuit breaker for ttl_seconds (default 5 min)."""
    try:
        from src.adapters.redis_queue import get_redis
        r = get_redis()
        r.setex(METAAPI_CIRCUIT_KEY, ttl_seconds, "1")
        logger.warning("MetaApi circuit breaker OPEN for %s seconds", ttl_seconds)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Failed to set circuit breaker: %s", exc)


def reset_metaapi_circuit() -> None:
    """Close the circuit breaker (allow MetaApi calls again)."""
    try:
        from src.adapters.redis_queue import get_redis
        get_redis().delete(METAAPI_CIRCUIT_KEY)
        logger.info("MetaApi circuit breaker RESET")
    except Exception as exc:  # noqa: BLE001
        logger.warning("Failed to reset circuit breaker: %s", exc)
