"""
src/pipeline/idempotency.py

Atomic trade-key deduplication.

Two-layer guard:
  1. Redis SETNX  — sub-millisecond; prevents parallel workers claiming the same key
  2. Supabase DB  — persistent guard; survives Redis flushes and worker restarts

Rule: claim_trade_key MUST be called before exists_trade_key.
If Redis is unavailable the DB check is the authority (fail-open for Redis, fail-closed via DB
unique constraint).
"""
from __future__ import annotations

from typing import Optional

from config.logging_config import get_logger

logger = get_logger("trinity.pipeline.idempotency")


def claim_trade_key(
    trade_key: str,
    broker_profile_id: Optional[int] = None,
    ttl: int = 300,
) -> bool:
    """Atomically claim *trade_key* via Redis SETNX.

    Returns True  → this worker has exclusive rights to process the signal.
    Returns False → another worker already holds the key (duplicate — skip).

    *ttl* is the lock expiry in seconds (default 5 min). A crashed worker
    will release the lock after TTL so retries are not permanently blocked.

    If Redis is unreachable, returns True so the DB-level unique constraint
    acts as the hard safety net.
    """
    if not trade_key or not str(trade_key).strip():
        return True  # No key → allow (no idempotency protection possible)
    try:
        from src.adapters.redis_queue import get_redis as _get_redis
        _redis = _get_redis()
        bp_part = str(broker_profile_id) if broker_profile_id is not None else "none"
        lock_key = f"trade_lock:{trade_key.strip()}:{bp_part}"
        acquired = _redis.set(lock_key, "1", nx=True, ex=ttl)
        return bool(acquired)
    except Exception as e:
        logger.warning(
            "Trade key claim (Redis SETNX) failed: %s — falling back to DB check", e
        )
        return True  # Allow; DB unique constraint is the arbiter


def exists_trade_key(
    trade_key: str,
    broker_profile_id: Optional[int] = None,
) -> bool:
    """True if a row already exists for *trade_key* (and optional *broker_profile_id*).

    Used as a secondary check after claim_trade_key to catch races that slip
    past Redis (e.g. after a Redis flush or across process restarts).
    """
    if not trade_key or not str(trade_key).strip():
        return False
    try:
        import src.adapters.supabase as _sb_mod
        sb = _sb_mod.supabase
        if not sb:
            return False
        q = (
            sb.table("trading_signals")
            .select("id")
            .eq("trade_key", trade_key.strip())
            .limit(1)
        )
        if broker_profile_id is not None:
            q = q.eq("broker_profile_id", broker_profile_id)
        else:
            q = q.is_("broker_profile_id", "null")
        r = q.execute()
        return len(r.data) > 0
    except Exception as e:
        logger.warning("Idempotency DB check failed: %s", e)
        return False
