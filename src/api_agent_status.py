"""FastAPI router: /api/agent/status — Agentic View operational state.

Returns AI agent's recent operational events:
  - Jira ticket creations
  - Trade executions / rejections
  - Guard activations
  - Exceptions

Data source: Redis sorted set `agent:events` (written by agent_events.log_agent_event).
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException

router = APIRouter(prefix="/api/agent", tags=["agent"])
logger = logging.getLogger(__name__)


def _get_redis():
    from src.adapters.redis_queue import get_redis
    return get_redis()


@router.get("/status")
def get_agent_status(limit: int = 50) -> Dict[str, Any]:
    """Return AI agent operational state and recent event feed.

    Query params:
        limit (int): Max events to return, default 50, max 100

    Response:
        status: "active" | "degraded" (degraded if Redis is unavailable)
        event_count: number of events returned
        last_event_at: ISO timestamp of most recent event (null if none)
        events: list of event objects ordered newest-first
    """
    limit = min(limit, 100)  # Cap at 100 for performance

    try:
        redis_client = _get_redis()
    except Exception as exc:
        logger.warning("agent/status: Redis unavailable — %s", exc)
        raise HTTPException(status_code=503, detail="Redis unavailable") from exc

    from src.services.agent_events import get_agent_events
    events = get_agent_events(redis_client, limit=limit)

    last_event_at: Optional[str] = None
    if events:
        ts = events[0].get("timestamp")
        if ts:
            try:
                last_event_at = datetime.fromtimestamp(float(ts), tz=timezone.utc).isoformat()
            except (TypeError, ValueError, OSError):
                last_event_at = None

    # Humanise timestamps
    enriched: List[Dict[str, Any]] = []
    for evt in events:
        e = dict(evt)
        ts = e.get("timestamp")
        if ts:
            try:
                e["timestamp_iso"] = datetime.fromtimestamp(
                    float(ts), tz=timezone.utc
                ).isoformat()
            except (TypeError, ValueError, OSError):
                e["timestamp_iso"] = None
        enriched.append(e)

    return {
        "status": "active",
        "event_count": len(enriched),
        "last_event_at": last_event_at,
        "events": enriched,
    }
