"""
AccountRouterObserver — validates and logs the account routing decision.

Kept separate from src.core.account_router to avoid circular imports
(account_router.py must not import from the observers package).
"""

from __future__ import annotations

import logging
from typing import Optional

from src.core.account_router import DEFAULT_ACCOUNT_ID, AccountRouter
from src.core.observers.base import SIGNAL_RECEIVED, Observer, TradeEvent

logger = logging.getLogger(__name__)


class AccountRouterObserver(Observer):
    """Fires on SIGNAL_RECEIVED; logs the routing decision.

    The live-payload stamping (``payload["_account_id"] = ...``) is performed
    by ``WorkerSubject`` via its ``account_router`` parameter *before* this
    observer fires, so ``event.payload["_account_id"]`` is already set here.
    This observer is purely informational — it never alters control flow.
    """

    def __init__(self, router: Optional[AccountRouter] = None) -> None:
        self._router = router or AccountRouter()

    def on_event(self, event: TradeEvent) -> None:
        if event.event_type != SIGNAL_RECEIVED:
            return
        try:
            account_id = event.payload.get("_account_id", DEFAULT_ACCOUNT_ID)
            queue_key = self._router.queue_key_for(account_id)
            logger.debug(
                "AccountRouter: signal routed | account=%s | queue=%s | correlation_id=%s",
                account_id,
                queue_key,
                event.correlation_id,
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("AccountRouterObserver.on_event failed: %s", exc)
