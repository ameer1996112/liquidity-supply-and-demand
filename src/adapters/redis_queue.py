"""Redis queue: client and queue name for webhook producer and worker consumer."""

import logging
from typing import Any

logger = logging.getLogger(__name__)

QUEUE_NAME = "trading_queue"
_redis: Any = None


def get_redis():
    """Lazy Redis client from config redis_url."""
    global _redis
    if _redis is None:
        import redis
        from config import get_settings
        _redis = redis.from_url(get_settings().redis_url, decode_responses=True)
    return _redis


def reset_redis_client() -> None:
    """Drop the cached Redis client so next get_redis() creates a new connection. Use after connection errors."""
    global _redis
    _redis = None
    logger.info("Redis client reset (reconnect on next use)")


def ping_redis() -> bool:
    """Return True if Redis is reachable."""
    try:
        get_redis().ping()
        return True
    except Exception:  # noqa: BLE001
        return False


def push_payload(payload_str: str) -> None:
    """Push JSON payload to queue (used by API). Falls back to dead-letter on Redis failure."""
    try:
        get_redis().rpush(QUEUE_NAME, payload_str)
        logger.info(f"Queued payload to Redis (len={len(payload_str)})")
    except Exception as e:
        logger.error(f"❌ Redis push failed: {e}. Saving to dead-letter queue.", exc_info=True)
        # Fallback: save signal to dead-letter queue so it's not lost
        try:
            push_dead_letter(payload_str, f"Redis push failed: {e}")
            logger.warning(f"✅ Payload saved to dead-letter queue for manual retry")
        except Exception as dl_error:
            logger.critical(f"❌ CRITICAL: Failed to save to dead-letter: {dl_error}", exc_info=True)
            # Last resort: re-raise to trigger Railway restart (fail-fast)
            raise


def blpop_queue(timeout: int = 5):
    """Blocking pop from queue (used by worker). Returns (key, payload_str) or None."""
    return get_redis().blpop(QUEUE_NAME, timeout=timeout)


# ── Dead Letter Queue ──────────────────────────────────────

DEAD_LETTER_QUEUE = "trading_dead_letter"


def push_dead_letter(payload_str: str, error: str, attempt: int = 1) -> None:
    """Push a failed payload to the dead-letter queue with error metadata."""
    import json
    import time

    envelope = json.dumps({
        "id": f"dl-{int(time.time() * 1000)}",
        "payload": json.loads(payload_str) if isinstance(payload_str, str) else payload_str,
        "error": str(error)[:500],
        "attempt": attempt,
        "failed_at": time.time(),
    })
    get_redis().rpush(DEAD_LETTER_QUEUE, envelope)
    logger.warning("Dead-lettered payload (attempt %d): %s", attempt, str(error)[:120])


def get_dead_letters(limit: int = 50) -> list:
    """Read dead-letter items without removing them."""
    import json

    items = get_redis().lrange(DEAD_LETTER_QUEUE, 0, limit - 1)
    return [json.loads(i) for i in items]


def pop_dead_letter_by_id(dl_id: str):
    """Remove a specific dead letter by its id and return it."""
    import json

    r = get_redis()
    items = r.lrange(DEAD_LETTER_QUEUE, 0, -1)
    for raw in items:
        parsed = json.loads(raw)
        if parsed.get("id") == dl_id:
            r.lrem(DEAD_LETTER_QUEUE, 1, raw)
            return parsed
    return None
