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


def push_payload(payload_str: str) -> None:
    """Push JSON payload to queue (used by API)."""
    get_redis().rpush(QUEUE_NAME, payload_str)


def blpop_queue(timeout: int = 5):
    """Blocking pop from queue (used by worker). Returns (key, payload_str) or None."""
    return get_redis().blpop(QUEUE_NAME, timeout=timeout)
