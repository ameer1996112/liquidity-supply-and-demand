"""
Signal transport abstraction — decouples queue I/O from Redis primitives.

Implementations:
  RedisTransport    — delegates to src.adapters.redis_queue (production)
  InMemoryTransport — thread-safe deque (tests, no Redis required)

Factory:
  get_transport()   — returns the singleton configured by SIGNAL_TRANSPORT env var
  set_transport(t)  — override for tests (call reset_transport() in tearDown)
"""

import json
import logging
import time
from abc import ABC, abstractmethod
from collections import deque
from threading import Lock
from typing import Optional, Tuple

logger = logging.getLogger(__name__)


class SignalTransport(ABC):
    """Queue contract used by the API (enqueue) and worker (dequeue)."""

    @abstractmethod
    def enqueue(self, payload_str: str) -> None:
        """Push a JSON payload string onto the signal queue.

        Implementations should handle fallback (e.g. dead-letter on failure).
        """
        ...

    @abstractmethod
    def dequeue(self, timeout: int = 5) -> Optional[Tuple[str, str]]:
        """Blocking pop.  Returns *(queue_name, payload_str)* or ``None`` on timeout."""
        ...

    @abstractmethod
    def dead_letter(self, payload_str: str, error: str, attempt: int = 1) -> None:
        """Move a failed payload to the dead-letter queue with metadata."""
        ...

    @abstractmethod
    def ping(self) -> bool:
        """Return ``True`` if the transport backend is reachable."""
        ...

    @abstractmethod
    def reset(self) -> None:
        """Drop cached connections so the next operation reconnects."""
        ...


# ── Redis (production) ───────────────────────────────────────────────────────


class RedisTransport(SignalTransport):
    """Thin wrapper around the existing ``redis_queue`` helpers.

    All behaviour (dead-letter fallback on enqueue failure, etc.) is preserved
    because we delegate to the same functions the codebase already uses.
    """

    def enqueue(self, payload_str: str) -> None:
        from src.adapters.redis_queue import push_payload
        push_payload(payload_str)

    def dequeue(self, timeout: int = 5) -> Optional[Tuple[str, str]]:
        from src.adapters.redis_queue import blpop_queue
        return blpop_queue(timeout=timeout)

    def dead_letter(self, payload_str: str, error: str, attempt: int = 1) -> None:
        from src.adapters.redis_queue import push_dead_letter
        push_dead_letter(payload_str, error, attempt)

    def ping(self) -> bool:
        from src.adapters.redis_queue import ping_redis
        return ping_redis()

    def reset(self) -> None:
        from src.adapters.redis_queue import reset_redis_client
        reset_redis_client()


# ── In-memory (tests) ────────────────────────────────────────────────────────


class InMemoryTransport(SignalTransport):
    """Thread-safe, zero-dependency transport for unit/integration tests."""

    def __init__(self) -> None:
        self._queue: deque[str] = deque()
        self._dead_letters: list[dict] = []
        self._lock = Lock()

    def enqueue(self, payload_str: str) -> None:
        with self._lock:
            self._queue.append(payload_str)

    def dequeue(self, timeout: int = 5) -> Optional[Tuple[str, str]]:
        with self._lock:
            if self._queue:
                return ("memory_queue", self._queue.popleft())
        return None

    def dead_letter(self, payload_str: str, error: str, attempt: int = 1) -> None:
        try:
            payload_data = json.loads(payload_str) if isinstance(payload_str, str) else payload_str
        except (json.JSONDecodeError, ValueError):
            payload_data = {"_raw": payload_str[:500] if isinstance(payload_str, str) else str(payload_str)[:500]}
        envelope = {
            "id": f"dl-{int(time.time() * 1000)}",
            "payload": payload_data,
            "error": str(error)[:500],
            "attempt": attempt,
            "failed_at": time.time(),
        }
        with self._lock:
            self._dead_letters.append(envelope)

    def ping(self) -> bool:
        return True

    def reset(self) -> None:
        pass

    # ── Test helpers ──────────────────────────────────────────────────────

    @property
    def dead_letters(self) -> list[dict]:
        with self._lock:
            return list(self._dead_letters)

    @property
    def queue_size(self) -> int:
        with self._lock:
            return len(self._queue)


# ── Factory / singleton ──────────────────────────────────────────────────────

_transport: Optional[SignalTransport] = None


def get_transport() -> SignalTransport:
    """Return the singleton ``SignalTransport`` configured by ``SIGNAL_TRANSPORT``."""
    global _transport
    if _transport is None:
        from config import get_settings
        kind = getattr(get_settings(), "signal_transport", "redis")
        if kind == "memory":
            _transport = InMemoryTransport()
            logger.info("SignalTransport: InMemoryTransport (test mode)")
        else:
            _transport = RedisTransport()
            logger.info("SignalTransport: RedisTransport (production)")
    return _transport


def set_transport(transport: SignalTransport) -> None:
    """Inject a transport (use in tests to avoid Redis)."""
    global _transport
    _transport = transport


def reset_transport() -> None:
    """Clear the cached singleton so the next ``get_transport()`` creates a fresh one."""
    global _transport
    _transport = None
