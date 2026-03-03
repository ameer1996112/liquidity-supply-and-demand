"""
Consumer-side payload validation (P0-3) — defense-in-depth.

Validates a raw queue message *after* dequeue, before any processing.
The API already validates at ingest time; this guard catches anything that
bypassed the API (manual pushes, migrations, bugs, future transports).

On failure
----------
  - Dead-letters the raw message via the SignalTransport
  - Fires a best-effort audit log event (event_type="consumer_validation_failed")
  - Returns None so the worker loop skips execution for this message

On success
----------
  - Returns the parsed dict (same object that process_trade() expects)

Error codes
-----------
  INVALID_JSON     — raw message cannot be parsed as JSON
  SCHEMA_VIOLATION — parsed dict fails EntryWebhookPayload / ExitWebhookPayload
"""

import hashlib
import json
import logging
from typing import Any, Dict, Optional

from pydantic import ValidationError

from src.core.signal import validate_webhook_payload

logger = logging.getLogger(__name__)


def _payload_hash(payload_str: str) -> str:
    """Deterministic SHA-256 hex digest of the raw message (first 16 chars shown)."""
    return hashlib.sha256(payload_str.encode("utf-8", errors="replace")).hexdigest()[:16]


def validate_dequeued_message(
    payload_str: str,
    transport,  # SignalTransport — typed loosely to avoid circular import
    *,
    log_event_fn=None,
) -> Optional[Dict[str, Any]]:
    """Parse and validate a raw queue message.

    Parameters
    ----------
    payload_str:
        The raw string popped from the queue.
    transport:
        A ``SignalTransport`` instance used to dead-letter invalid messages.
    log_event_fn:
        Optional callable with signature ``(signal_id, event_type, stage, metadata)``
        for audit logging.  Defaults to ``src.services.trade_events.log_event``.

    Returns
    -------
    dict | None
        Parsed payload on success, ``None`` if the message should be skipped.
    """
    if log_event_fn is None:
        from src.services.trade_events import log_event
        log_event_fn = log_event

    phash = _payload_hash(payload_str)

    # ── Step 1: JSON parse ────────────────────────────────────────────────────
    try:
        data = json.loads(payload_str)
    except (json.JSONDecodeError, ValueError) as exc:
        error_code = "INVALID_JSON"
        reason = f"{error_code}: {exc}"
        logger.error(
            "Consumer validation failed [%s] hash=%s | %s",
            error_code, phash, exc,
        )
        _reject(payload_str, reason, error_code, phash, transport, log_event_fn)
        return None

    # ── Step 2: Schema validation (same models as API ingest) ─────────────────
    try:
        validate_webhook_payload(data)
    except (ValidationError, ValueError) as exc:
        error_code = "SCHEMA_VIOLATION"
        reason = f"{error_code}: {str(exc)[:300]}"
        symbol = data.get("symbol", "?") if isinstance(data, dict) else "?"
        logger.error(
            "Consumer validation failed [%s] hash=%s symbol=%s | %s",
            error_code, phash, symbol, exc,
        )
        _reject(payload_str, reason, error_code, phash, transport, log_event_fn)
        return None

    return data


def _reject(
    payload_str: str,
    reason: str,
    error_code: str,
    phash: str,
    transport,
    log_event_fn,
) -> None:
    """Dead-letter the message and emit an audit event.  Never raises."""
    try:
        transport.dead_letter(payload_str, reason)
    except Exception as exc:  # noqa: BLE001
        logger.warning("dead_letter call failed: %s", exc)

    try:
        log_event_fn(
            None,
            "consumer_validation_failed",
            "consumer_validator",
            {
                "error_code": error_code,
                "payload_hash": phash,
                "reason": reason[:500],
            },
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("audit log for consumer_validation_failed failed: %s", exc)
