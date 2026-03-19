"""
Circuit breaker for external services (e.g. MetaApi).
Uses Redis so worker, API, and watchdog share the same state.

Supports per-account circuit breakers for multi-account isolation:
  - Each account gets its own Redis key so one account's rate limit
    doesn't block other accounts.
  - Legacy global key still works as a fallback.
"""

from __future__ import annotations

import logging
from typing import Optional

logger = logging.getLogger(__name__)

# Redis key templates — per-account isolation
_CIRCUIT_KEY_PREFIX = "trading:circuit_breaker:metaapi"
METAAPI_CIRCUIT_KEY = _CIRCUIT_KEY_PREFIX  # global (legacy)
# TTL seconds (e.g. 5 min) so breaker auto-resets after rate limit cools down
DEFAULT_TTL = 300


def _account_key(account_name: Optional[str] = None) -> str:
    """Return Redis key for the given account (or global fallback)."""
    if account_name:
        return f"{_CIRCUIT_KEY_PREFIX}:{account_name}"
    return METAAPI_CIRCUIT_KEY


def is_metaapi_circuit_open(account_name: Optional[str] = None) -> bool:
    """True if MetaApi circuit breaker is open for a specific account (or globally).

    Checks the per-account key first, then falls back to the global key.
    """
    try:
        from src.adapters.redis_queue import get_redis
        r = get_redis()
        # Check account-specific breaker
        if account_name and r.get(_account_key(account_name)) == "1":
            return True
        # Check global breaker (backward-compat)
        return r.get(METAAPI_CIRCUIT_KEY) == "1"
    except Exception as exc:  # noqa: BLE001
        logger.debug("Circuit breaker check failed (fail-open): %s", exc)
        return False


def set_metaapi_circuit_open(ttl_seconds: int = DEFAULT_TTL, account_name: Optional[str] = None) -> None:
    """Open the MetaApi circuit breaker for ttl_seconds (default 5 min).

    When account_name is provided, only that account is blocked.
    """
    key = _account_key(account_name)
    try:
        from src.adapters.redis_queue import get_redis
        r = get_redis()
        r.setex(key, ttl_seconds, "1")
        label = f"account={account_name}" if account_name else "GLOBAL"
        logger.warning("MetaApi circuit breaker OPEN for %s seconds (%s)", ttl_seconds, label)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Failed to set circuit breaker: %s", exc)


def reset_metaapi_circuit(account_name: Optional[str] = None, reset_all: bool = False) -> None:
    """Close the circuit breaker (allow MetaApi calls again).

    When reset_all=True, deletes all keys matching the prefix (global + per-account).
    """
    try:
        from src.adapters.redis_queue import get_redis
        r = get_redis()
        if reset_all:
            # Delete all circuit breaker keys (global + per-account)
            keys = list(r.scan_iter(match=f"{_CIRCUIT_KEY_PREFIX}*"))
            for k in keys:
                r.delete(k)
            logger.info("MetaApi circuit breaker RESET (all %d keys cleared)", len(keys))
        else:
            key = _account_key(account_name)
            r.delete(key)
            label = f"account={account_name}" if account_name else "GLOBAL"
            logger.info("MetaApi circuit breaker RESET (%s)", label)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Failed to reset circuit breaker: %s", exc)
