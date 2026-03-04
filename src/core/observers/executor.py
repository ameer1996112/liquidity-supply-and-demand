"""
ExecutorObserver — stub for P1 paper/live execution extraction.

Currently execution lives entirely inside ``process_trade`` (``src/logic.py``).
This stub marks the future seam point: when P1 extracts paper/live execution
into this observer, it will handle ORDER_SUBMITTED events and post back
POSITION_UPDATED events.
"""

import logging

from src.core.observers.base import Observer, TradeEvent

logger = logging.getLogger(__name__)


class ExecutorObserver(Observer):
    """Receives ORDER_SUBMITTED events (execution is inside process_trade today).

    Stub: logs a debug line and does nothing else.
    Future: will call the broker adapter and emit POSITION_UPDATED.
    """

    def on_event(self, event: TradeEvent) -> None:
        logger.debug(
            "ExecutorObserver received %s | correlation_id=%s | symbol=%s",
            event.event_type,
            event.correlation_id,
            event.payload.get("symbol", "UNKNOWN"),
        )
