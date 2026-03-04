"""
AuditorObserver — writes an audit log entry for every pipeline event.

Enriches each entry with the ``correlation_id`` so all events for a single
signal run can be correlated in the ``trade_events`` table.
"""

import logging

from src.core.observers.base import Observer, TradeEvent
from src.services.trade_events import log_event

logger = logging.getLogger(__name__)


class AuditorObserver(Observer):
    """Persists a ``trade_events`` row for SIGNAL_RECEIVED, ORDER_SUBMITTED, and ERROR.

    Uses the fire-and-forget ``log_event`` helper — same semantics as the
    rest of the codebase.  Import is at module level so it is patchable in tests.
    """

    def on_event(self, event: TradeEvent) -> None:
        try:
            log_event(
                None,
                f"observer.{event.event_type.lower()}",
                "observer.auditor",
                {
                    "correlation_id": event.correlation_id,
                    "symbol": event.payload.get("symbol", "UNKNOWN"),
                    **{k: v for k, v in event.metadata.items() if k != "symbol"},
                },
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("AuditorObserver.on_event failed: %s", exc)
