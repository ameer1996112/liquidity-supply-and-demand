"""
Observer pattern for the signal processing pipeline (P0-1).

WorkerSubject wraps the existing process_trade function and emits immutable
TradeEvent objects at each pipeline milestone.  Observers are pure side-effect
handlers: they receive events but never affect control flow.

Event lifecycle for a normal signal
------------------------------------
  SIGNAL_RECEIVED  — dequeued, consumer-validated, about to enter process_trade
  ORDER_SUBMITTED  — process_trade returned without raising
  ERROR            — process_trade raised an exception

Reserved for future extraction (not yet emitted):
  SIGNAL_VALIDATED — after all global guards pass
  RISK_DECIDED     — after MAS Council decision
  POSITION_UPDATED — after broker/paper position confirmed filled
"""

import logging
import time
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    # AccountRouter imported only for type-checking to avoid circular imports.
    pass

logger = logging.getLogger(__name__)

# ── Event type constants ──────────────────────────────────────────────────────

SIGNAL_RECEIVED  = "SIGNAL_RECEIVED"
SIGNAL_VALIDATED = "SIGNAL_VALIDATED"   # reserved
RISK_DECIDED     = "RISK_DECIDED"       # reserved
ORDER_SUBMITTED  = "ORDER_SUBMITTED"
POSITION_UPDATED = "POSITION_UPDATED"   # reserved
ERROR            = "ERROR"


# ── Immutable event ───────────────────────────────────────────────────────────

@dataclass(frozen=True)
class TradeEvent:
    """Immutable record of a pipeline milestone.

    Attributes
    ----------
    event_type:
        One of the module-level constants (SIGNAL_RECEIVED, etc.).
    correlation_id:
        UUID hex generated once per signal; links all events for one run.
    payload:
        A shallow copy of the signal payload at the time of emission.
        Treat as read-only — modifying it does not affect the live pipeline.
    timestamp:
        ``time.time()`` at emission.
    metadata:
        Arbitrary key/value context (guard name, ai decision, error text, …).
    """
    event_type:     str
    correlation_id: str
    payload:        Dict[str, Any]
    timestamp:      float
    metadata:       Dict[str, Any] = field(default_factory=dict)


# ── Observer ABC ──────────────────────────────────────────────────────────────

class Observer(ABC):
    """Base class for all pipeline observers.

    Implementations must never raise — wrap all logic in try/except.
    Exceptions in observers are logged and swallowed so they cannot
    interrupt the main processing pipeline.
    """

    @abstractmethod
    def on_event(self, event: TradeEvent) -> None: ...

    @property
    def name(self) -> str:
        return type(self).__name__


# ── Subject ───────────────────────────────────────────────────────────────────

class WorkerSubject:
    """Thin harness around the existing ``process_trade`` function.

    Emits TradeEvents before/after calling ``process_fn`` and fans out to
    all attached observers.  Observers receive events but never affect
    whether the trade executes.

    Usage
    -----
    ::
        subject = WorkerSubject(process_fn=process_trade)
        subject.attach(AuditorObserver())
        subject.attach(MetricsObserver())

        # In the worker loop (replaces: process_trade(payload)):
        subject.process_signal(payload)
    """

    def __init__(
        self,
        process_fn: Callable[[Dict[str, Any]], None],
        observers: Optional[List[Observer]] = None,
        account_router: Optional[Any] = None,  # AccountRouter — typed loosely to avoid circular import
    ) -> None:
        self._process_fn = process_fn
        self._observers: List[Observer] = list(observers or [])
        self._account_router = account_router

    def attach(self, observer: Observer) -> None:
        self._observers.append(observer)

    def detach(self, observer: Observer) -> None:
        self._observers = [o for o in self._observers if o is not observer]

    # ── Main entry point ──────────────────────────────────────────────────

    def process_signal(self, payload: Dict[str, Any]) -> None:
        """Emit SIGNAL_RECEIVED, run process_fn, emit ORDER_SUBMITTED or ERROR."""
        correlation_id = uuid.uuid4().hex

        # Attach correlation_id to the payload so downstream code can reference it.
        payload["_correlation_id"] = correlation_id

        # Account routing: stamp _account_id onto the live payload (defence-in-depth:
        # the API already stamps it before enqueue, but legacy/direct-Redis messages
        # may not have it).
        if self._account_router is not None:
            try:
                account_id = self._account_router.resolve_account_id(payload)
                payload["_account_id"] = account_id
            except Exception as acc_exc:  # noqa: BLE001
                logger.warning("AccountRouter.resolve_account_id failed: %s", acc_exc)

        self._emit(TradeEvent(
            event_type=SIGNAL_RECEIVED,
            correlation_id=correlation_id,
            payload=dict(payload),
            timestamp=time.time(),
            metadata={
                "symbol":   payload.get("symbol", "UNKNOWN"),
                "run_mode": payload.get("run_mode", "PAPER"),
                "side":     payload.get("side", ""),
            },
        ))

        try:
            self._process_fn(payload)

            self._emit(TradeEvent(
                event_type=ORDER_SUBMITTED,
                correlation_id=correlation_id,
                payload=dict(payload),
                timestamp=time.time(),
                metadata={
                    "symbol":   payload.get("symbol", "UNKNOWN"),
                    "run_mode": payload.get("run_mode", "PAPER"),
                },
            ))

        except Exception as exc:
            self._emit(TradeEvent(
                event_type=ERROR,
                correlation_id=correlation_id,
                payload=dict(payload),
                timestamp=time.time(),
                metadata={
                    "symbol": payload.get("symbol", "UNKNOWN"),
                    "error":  str(exc)[:500],
                    "error_type": type(exc).__name__,
                },
            ))
            raise

    # ── Fan-out ───────────────────────────────────────────────────────────

    def _emit(self, event: TradeEvent) -> None:
        for observer in self._observers:
            try:
                observer.on_event(event)
            except Exception as exc:  # noqa: BLE001
                logger.warning(
                    "Observer %s raised on %s (swallowed): %s",
                    observer.name, event.event_type, exc,
                )
