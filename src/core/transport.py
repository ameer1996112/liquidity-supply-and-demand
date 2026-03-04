"""
Signal transport abstraction — decouples queue I/O from Redis primitives.

Implementations:
  RedisTransport    — delegates to src.adapters.redis_queue (production)
  InMemoryTransport — thread-safe multi-queue dict (tests, no Redis required)

Factory:
  get_transport()   — returns the singleton configured by SIGNAL_TRANSPORT env var
  set_transport(t)  — override for tests (call reset_transport() in tearDown)

Per-account partitioning (Sprint 2.3)
──────────────────────────────────────
Both ``enqueue`` and ``dequeue`` now accept optional queue-key arguments:

  enqueue(payload_str, queue_key=None)
    None / "trading_queue" → existing default queue (no change)
    other string           → per-account queue (e.g. "trading_queue:acc-1")

  dequeue(queue_keys=None, timeout=5)
    None / ["trading_queue"] → existing default queue (no change)
    list of keys             → polls all listed queues (Redis: blpop multi-key)

Single-account deployments always pass queue_key=None / queue_keys=None, so
they see exactly zero behaviour change.
"""

import json
import logging
import time
from abc import ABC, abstractmethod
from collections import deque
from threading import Lock
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

_DEFAULT_QUEUE = "trading_queue"


class SignalTransport(ABC):
    """Queue contract used by the API (enqueue) and worker (dequeue)."""

    @abstractmethod
    def enqueue(self, payload_str: str, queue_key: Optional[str] = None) -> None:
        """Push a JSON payload string onto the signal queue.

        ``queue_key=None`` uses the implementation's default queue.
        Implementations should handle fallback (e.g. dead-letter on failure).
        """
        ...

    @abstractmethod
    def dequeue(
        self,
        queue_keys: Optional[List[str]] = None,
        timeout: int = 5,
    ) -> Optional[Tuple[str, str]]:
        """Blocking pop.

        ``queue_keys=None`` polls the implementation's default queue.
        Returns *(queue_name, payload_str)* or ``None`` on timeout.
        """
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

    Default-key calls delegate to the same functions the codebase already
    uses (including dead-letter fallback on enqueue failure).
    Per-account-key calls use direct rpush/blpop with an equivalent fallback.
    """

    def enqueue(self, payload_str: str, queue_key: Optional[str] = None) -> None:
        from src.adapters.redis_queue import QUEUE_NAME, push_payload
        if not queue_key or queue_key == QUEUE_NAME:
            # Existing production path — includes dead-letter fallback
            push_payload(payload_str)
        else:
            # Per-account queue: direct rpush with same fallback pattern
            try:
                from src.adapters.redis_queue import get_redis
                get_redis().rpush(queue_key, payload_str)
                logger.info("Queued payload to %s (len=%d)", queue_key, len(payload_str))
            except Exception as e:  # noqa: BLE001
                logger.error("Redis rpush to %s failed: %s — falling back to dead-letter", queue_key, e)
                try:
                    from src.adapters.redis_queue import push_dead_letter
                    push_dead_letter(payload_str, f"rpush to {queue_key} failed: {e}")
                except Exception as dl_e:
                    logger.critical("Dead-letter fallback also failed: %s", dl_e)
                    raise

    def dequeue(
        self,
        queue_keys: Optional[List[str]] = None,
        timeout: int = 5,
    ) -> Optional[Tuple[str, str]]:
        from src.adapters.redis_queue import QUEUE_NAME, blpop_queue
        if not queue_keys or queue_keys == [QUEUE_NAME]:
            # Existing production path
            return blpop_queue(timeout=timeout)
        # Multi-key blpop (Redis returns (key, value) already)
        from src.adapters.redis_queue import get_redis
        return get_redis().blpop(queue_keys, timeout=timeout)

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

# Key returned inside the dequeue tuple for the default queue (backward compat).
_MEMORY_DEFAULT_RETURNED_KEY = "memory_queue"
_MEMORY_DEFAULT_INTERNAL_KEY = _DEFAULT_QUEUE   # "trading_queue"


class InMemoryTransport(SignalTransport):
    """Thread-safe, zero-dependency transport for unit/integration tests.

    Supports multiple named queues for per-account isolation tests.
    The default queue (queue_key=None) behaves identically to before:
    - dequeue returns ("memory_queue", payload_str)  ← backward compat
    - queue_size counts items across all queues
    """

    def __init__(self) -> None:
        self._queues: Dict[str, deque] = {_MEMORY_DEFAULT_INTERNAL_KEY: deque()}
        self._dead_letters: list = []
        self._lock = Lock()

    def enqueue(self, payload_str: str, queue_key: Optional[str] = None) -> None:
        key = queue_key or _MEMORY_DEFAULT_INTERNAL_KEY
        with self._lock:
            if key not in self._queues:
                self._queues[key] = deque()
            self._queues[key].append(payload_str)

    def dequeue(
        self,
        queue_keys: Optional[List[str]] = None,
        timeout: int = 5,
    ) -> Optional[Tuple[str, str]]:
        keys = queue_keys or [_MEMORY_DEFAULT_INTERNAL_KEY]
        with self._lock:
            for key in keys:
                if key in self._queues and self._queues[key]:
                    item = self._queues[key].popleft()
                    # Preserve "memory_queue" as the returned key for the default
                    # queue so existing tests that assert on that string keep passing.
                    returned_key = (
                        _MEMORY_DEFAULT_RETURNED_KEY
                        if key == _MEMORY_DEFAULT_INTERNAL_KEY
                        else key
                    )
                    return (returned_key, item)
        return None

    def dead_letter(self, payload_str: str, error: str, attempt: int = 1) -> None:
        try:
            payload_data = json.loads(payload_str) if isinstance(payload_str, str) else payload_str
        except (json.JSONDecodeError, ValueError):
            payload_data = {
                "_raw": payload_str[:500] if isinstance(payload_str, str) else str(payload_str)[:500]
            }
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
    def dead_letters(self) -> list:
        with self._lock:
            return list(self._dead_letters)

    @property
    def queue_size(self) -> int:
        """Total items across all queues (default queue only for single-account tests)."""
        with self._lock:
            return sum(len(q) for q in self._queues.values())

    def queue_size_for(self, queue_key: str) -> int:
        """Items in a specific named queue."""
        with self._lock:
            return len(self._queues.get(queue_key, deque()))

    def queue_names(self) -> List[str]:
        """All queue keys that currently hold items."""
        with self._lock:
            return [k for k, q in self._queues.items() if q]


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
