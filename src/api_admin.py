"""Admin API -- Dead letter queue management + system health."""

import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException

from src.adapters.redis_queue import (
    DEAD_LETTER_QUEUE,
    get_dead_letters,
    get_redis,
    pop_dead_letter_by_id,
    push_payload,
)
from src.services.trade_events import log_event

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/admin", tags=["admin"])

# ── Lazy Supabase ────────────────────────────────────────────

from src.adapters.supabase_api import get_api_supabase as _get_supabase


# ── Endpoints ────────────────────────────────────────────────


@router.get("/dead-letters")
def list_dead_letters(limit: int = 50):
    """List dead-letter queue items (without removing them)."""
    items = get_dead_letters(limit=limit)
    return {"items": items, "count": len(items)}


@router.post("/dead-letters/{dl_id}/retry")
def retry_dead_letter(dl_id: str):
    """Pop a dead-letter item and re-queue it for processing."""
    import json

    item = pop_dead_letter_by_id(dl_id)
    if not item:
        raise HTTPException(status_code=404, detail="Dead letter not found")

    payload = item.get("payload", {})
    push_payload(json.dumps(payload))
    log_event(None, "dead_letter_retried", "admin", {"dl_id": dl_id})
    return {"status": "requeued", "dl_id": dl_id}


@router.get("/health")
def system_health():
    """System health overview: DLQ count, queue depth, Redis status."""
    r = get_redis()
    dlq_count = r.llen(DEAD_LETTER_QUEUE)
    queue_depth = r.llen("trading_queue")

    return {
        "dead_letter_count": dlq_count,
        "queue_depth": queue_depth,
        "redis_connected": True,
    }


@router.get("/events")
def list_trade_events(
    signal_id: Optional[int] = None,
    event_type: Optional[str] = None,
    limit: int = 50,
):
    """Query the trade_events audit trail."""
    sb = _get_supabase()
    query = (
        sb.table("trade_events")
        .select("*")
        .order("created_at", desc=True)
        .limit(limit)
    )
    if signal_id is not None:
        query = query.eq("signal_id", signal_id)
    if event_type:
        query = query.eq("event_type", event_type)
    result = query.execute()
    return {"events": result.data or [], "count": len(result.data or [])}
