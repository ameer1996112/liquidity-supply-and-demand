"""Agent event logger — writes structured events to Redis for the Agentic View UI.

Redis key: agent:events (sorted set, score=epoch timestamp)
Max events retained: 50
Event TTL: 24 hours (86400s) — applied on the sorted set key after each write.

Event types:
  - trade_executed   (green)
  - trade_rejected   (orange)
  - jira_ticket      (orange)
  - pr_sync          (blue)
  - exception        (red)
  - guard_activated  (yellow)
  - kill_switch      (red)
"""

from __future__ import annotations

import json
import logging
import time
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

AGENT_EVENTS_KEY = "agent:events"
MAX_EVENTS = 50
EVENT_TTL = 86400  # 24 hours


def log_agent_event(
    redis_client,
    event_type: str,
    message: str,
    *,
    jira_key: Optional[str] = None,
    symbol: Optional[str] = None,
    account: Optional[str] = None,
    extra: Optional[Dict[str, Any]] = None,
) -> None:
    """Write a structured event to the agent:events Redis sorted set.

    Args:
        redis_client: Redis client instance
        event_type: One of trade_executed, trade_rejected, jira_ticket, pr_sync,
                    exception, guard_activated, kill_switch
        message: Human-readable description
        jira_key: Optional Jira ticket key (e.g. DEV-42)
        symbol: Optional trading symbol (e.g. XAUUSD)
        account: Optional account name
        extra: Optional extra fields to include in the event JSON
    """
    try:
        now = time.time()
        event: Dict[str, Any] = {
            "type": event_type,
            "message": message,
            "timestamp": now,
        }
        if jira_key:
            event["jira_key"] = jira_key
        if symbol:
            event["symbol"] = symbol
        if account:
            event["account"] = account
        if extra:
            event.update(extra)

        payload = json.dumps(event)
        # Add to sorted set (score = timestamp for chronological ordering)
        redis_client.zadd(AGENT_EVENTS_KEY, {payload: now})
        # Keep only the most recent MAX_EVENTS entries
        redis_client.zremrangebyrank(AGENT_EVENTS_KEY, 0, -(MAX_EVENTS + 1))
        # Refresh TTL on every write
        redis_client.expire(AGENT_EVENTS_KEY, EVENT_TTL)
    except Exception as exc:
        logger.debug("log_agent_event failed (non-critical): %s", exc)


def get_agent_events(redis_client, limit: int = 50) -> list[Dict[str, Any]]:
    """Fetch the most recent agent events from Redis (newest first).

    Returns:
        List of event dicts, ordered newest-first.
    """
    try:
        raw_events = redis_client.zrevrange(AGENT_EVENTS_KEY, 0, limit - 1, withscores=True)
        events = []
        for payload, score in raw_events:
            try:
                evt = json.loads(payload)
                # Ensure timestamp is always present (use score as fallback)
                evt.setdefault("timestamp", score)
                events.append(evt)
            except (json.JSONDecodeError, TypeError):
                continue
        return events
    except Exception as exc:
        logger.warning("get_agent_events failed: %s", exc)
        return []
