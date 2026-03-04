"""
RiskObserver — stub for P1 risk-decision fan-out.

Currently a no-op.  Reserved for P1-1 (dialectical debate guardrail) where
the risk evaluation result will be emitted as a RISK_DECIDED event and this
observer will record it for analytics.
"""

import logging

from src.core.observers.base import Observer, TradeEvent

logger = logging.getLogger(__name__)


class RiskObserver(Observer):
    """Receives RISK_DECIDED events (not yet emitted — P1-1 work).

    Stub: logs a debug line and does nothing else.
    """

    def on_event(self, event: TradeEvent) -> None:
        logger.debug(
            "RiskObserver received %s | correlation_id=%s",
            event.event_type,
            event.correlation_id,
        )
