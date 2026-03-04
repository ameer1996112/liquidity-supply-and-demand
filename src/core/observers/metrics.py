"""
MetricsObserver — stub for P2 pipeline metrics / latency instrumentation.

Reserved for P0-4 (pipeline latency instrumentation) where timestamps at
each hop will be stored here and forwarded to the TCA metrics table.
"""

import logging

from src.core.observers.base import Observer, TradeEvent

logger = logging.getLogger(__name__)


class MetricsObserver(Observer):
    """Receives all events for latency/throughput measurement (not yet implemented).

    Stub: logs a debug line and does nothing else.
    Future: will record hop timestamps and write to ``tca_execution_metrics``.
    """

    def on_event(self, event: TradeEvent) -> None:
        logger.debug(
            "MetricsObserver received %s | correlation_id=%s | ts=%.3f",
            event.event_type,
            event.correlation_id,
            event.timestamp,
        )
