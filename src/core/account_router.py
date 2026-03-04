"""
Account routing foundation (Sprint 2.3).

AccountRouter
─────────────
Pure utility: given a signal payload, decides which account it targets and
which transport queue key to use.  For now the only rule is "default account",
but the class is the extension point for future rule-based / tag-based routing.

AccountRouterObserver
─────────────────────
Observer that fires on SIGNAL_RECEIVED.  It logs the routing decision and
validates that ``_account_id`` is set on the event payload.  The actual
stamping of ``_account_id`` onto the *live* payload dict happens earlier, in
``WorkerSubject.process_signal`` via the optional ``account_router`` parameter
(defence-in-depth: also handles legacy messages that bypass the API layer).

Queue partitioning
──────────────────
  "default" account → queue key "trading_queue"   (unchanged behaviour)
  any other account → queue key "trading_queue:<account_id>"

Single-account deployments always resolve to "default", so they see zero
behavioural change.
"""

from __future__ import annotations

import logging
from typing import Any, Dict

logger = logging.getLogger(__name__)

# ── Constants ─────────────────────────────────────────────────────────────────

DEFAULT_ACCOUNT_ID: str = "default"
DEFAULT_QUEUE_KEY:  str = "trading_queue"


# ── AccountRouter ─────────────────────────────────────────────────────────────

class AccountRouter:
    """Resolves the target account and queue key for a signal payload.

    Rules (in priority order):
      1. ``_account_id`` already on the payload (set by API layer)
      2. ``account_id`` field in the payload (explicit from webhook caller)
      3. Fall back to ``"default"``

    Extend this class to add DB-backed rule lookup, tag matching, etc.
    This class has NO dependency on the observers package to avoid
    circular imports.
    """

    def resolve_account_id(self, payload: Dict[str, Any]) -> str:
        """Return the account_id that should process this signal."""
        return (
            payload.get("_account_id")
            or payload.get("account_id")
            or DEFAULT_ACCOUNT_ID
        )

    def queue_key_for(self, account_id: str) -> str:
        """Return the Redis queue key for the given account_id.

        The default account uses the legacy ``trading_queue`` key so that
        single-account deployments require no configuration change.
        """
        if not account_id or account_id == DEFAULT_ACCOUNT_ID:
            return DEFAULT_QUEUE_KEY
        return f"{DEFAULT_QUEUE_KEY}:{account_id}"

    def resolve_queue_key(self, payload: Dict[str, Any]) -> str:
        """Convenience: resolve account_id then return its queue key."""
        return self.queue_key_for(self.resolve_account_id(payload))
