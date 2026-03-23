"""Tickets API — Jira-style task/bug tracker with AI changelog support.

Follows the same pattern as api_alerts.py / api_rules.py.
Table: project_tickets  (see migrations/057_project_tickets.sql)
"""

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from src.adapters.supabase_api import (
    get_api_supabase,
    reset_api_supabase,
    is_supabase_connection_error,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/tickets", tags=["tickets"])

_TABLE = "project_tickets"
_TABLE_MISSING_MSG = "Could not find the table"
_PGRST205 = "PGRST205"


def _is_table_missing(exc: BaseException) -> bool:
    msg = str(exc)
    if _TABLE_MISSING_MSG in msg or _PGRST205 in msg:
        return True
    if getattr(exc, "args", None) and len(exc.args) > 0:
        first = exc.args[0]
        if isinstance(first, dict) and (
            first.get("code") == _PGRST205
            or _TABLE_MISSING_MSG in str(first.get("message", ""))
        ):
            return True
        if _TABLE_MISSING_MSG in str(first) or _PGRST205 in str(first):
            return True
    return False


# ── Pydantic Models ──────────────────────────────────────────────────────────


class TicketResponse(BaseModel):
    id: str
    title: str
    description: Optional[str] = None
    type: str
    status: str
    priority: str
    assignee: Optional[str] = None
    signal_id: Optional[int] = None
    ai_changelog: List[Dict[str, Any]] = []
    created_at: str
    updated_at: str


class TicketsListResponse(BaseModel):
    tickets: List[TicketResponse]
    count: int


class CreateTicketRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=500)
    description: Optional[str] = None
    type: str = Field("task", pattern="^(bug|feature|task)$")
    status: str = Field("todo", pattern="^(todo|in_progress|done)$")
    priority: str = Field("medium", pattern="^(low|medium|high|critical)$")
    assignee: Optional[str] = None
    signal_id: Optional[int] = None


class PatchTicketRequest(BaseModel):
    title: Optional[str] = Field(None, min_length=1, max_length=500)
    description: Optional[str] = None
    type: Optional[str] = Field(None, pattern="^(bug|feature|task)$")
    status: Optional[str] = Field(None, pattern="^(todo|in_progress|done|archived)$")
    priority: Optional[str] = Field(None, pattern="^(low|medium|high|critical)$")
    assignee: Optional[str] = None
    signal_id: Optional[int] = None


class AiUpdateRequest(BaseModel):
    new_status: str = Field(..., pattern="^(todo|in_progress|done)$")
    summary_of_work: str = Field(..., min_length=1, max_length=2000)
    agent: str = Field("antigravity", max_length=100)


# ── Helpers ──────────────────────────────────────────────────────────────────


def _handle_supabase_error(exc: Exception, op: str) -> None:
    """Log and raise appropriate HTTPException for Supabase errors."""
    if _is_table_missing(exc):
        raise HTTPException(
            status_code=503,
            detail="project_tickets table not found. Run migrations/057_project_tickets.sql in Supabase.",
        ) from exc
    if is_supabase_connection_error(exc):
        reset_api_supabase()
    raise HTTPException(status_code=500, detail=f"Database error during {op}: {exc}")


# ── Endpoints ────────────────────────────────────────────────────────────────


@router.get("", response_model=TicketsListResponse)
def list_tickets(
    status: Optional[str] = Query(None),
    type: Optional[str] = Query(None),
    priority: Optional[str] = Query(None),
    limit: int = Query(100, ge=1, le=500),
):
    """List all non-archived tickets with optional filters."""
    sb = get_api_supabase()
    query = (
        sb.table(_TABLE)
        .select("*")
        .neq("status", "archived")
        .order("created_at", desc=True)
        .limit(limit)
    )
    if status:
        query = query.eq("status", status)
    if type:
        query = query.eq("type", type)
    if priority:
        query = query.eq("priority", priority)

    try:
        resp = query.execute()
        tickets = resp.data or []
    except Exception as exc:
        if _is_table_missing(exc):
            logger.debug("project_tickets table not found: %s", exc)
            return TicketsListResponse(tickets=[], count=0)
        if is_supabase_connection_error(exc):
            reset_api_supabase()
        logger.error("Failed to list tickets: %s", exc)
        return TicketsListResponse(tickets=[], count=0)

    return TicketsListResponse(
        tickets=[TicketResponse(**t) for t in tickets],
        count=len(tickets),
    )


@router.post("", response_model=TicketResponse, status_code=201)
def create_ticket(body: CreateTicketRequest):
    """Create a new ticket."""
    sb = get_api_supabase()
    insert_data: Dict[str, Any] = {
        "title": body.title,
        "description": body.description,
        "type": body.type,
        "status": body.status,
        "priority": body.priority,
        "assignee": body.assignee,
        "signal_id": body.signal_id,
        "ai_changelog": [],
    }
    try:
        resp = sb.table(_TABLE).insert(insert_data).execute()
        if not resp.data:
            raise HTTPException(status_code=500, detail="Insert returned no data")
        return TicketResponse(**resp.data[0])
    except HTTPException:
        raise
    except Exception as exc:
        _handle_supabase_error(exc, "create_ticket")


@router.get("/{ticket_id}", response_model=TicketResponse)
def get_ticket(ticket_id: str):
    """Fetch a single ticket by UUID."""
    sb = get_api_supabase()
    try:
        resp = sb.table(_TABLE).select("*").eq("id", ticket_id).maybe_single().execute()
        if not resp.data:
            raise HTTPException(status_code=404, detail="Ticket not found")
        return TicketResponse(**resp.data)
    except HTTPException:
        raise
    except Exception as exc:
        _handle_supabase_error(exc, "get_ticket")


@router.patch("/{ticket_id}", response_model=TicketResponse)
def patch_ticket(ticket_id: str, body: PatchTicketRequest):
    """Human update: change status, priority, assignee, etc."""
    updates: Dict[str, Any] = {
        k: v for k, v in body.model_dump().items() if v is not None
    }
    if not updates:
        raise HTTPException(status_code=400, detail="No fields to update")

    sb = get_api_supabase()
    try:
        resp = (
            sb.table(_TABLE).update(updates).eq("id", ticket_id).execute()
        )
        if not resp.data:
            raise HTTPException(status_code=404, detail="Ticket not found")
        return TicketResponse(**resp.data[0])
    except HTTPException:
        raise
    except Exception as exc:
        _handle_supabase_error(exc, "patch_ticket")


@router.post("/{ticket_id}/ai-update")
def ai_update_ticket(ticket_id: str, body: AiUpdateRequest):
    """AI skill endpoint — update status and append a changelog entry atomically.

    Called by the `update_jira_ticket` tool when the AI completes work on a task.
    Appends to ai_changelog without overwriting previous entries.
    """
    sb = get_api_supabase()

    # 1. Fetch current ticket to read existing changelog
    try:
        resp = sb.table(_TABLE).select("status, ai_changelog").eq("id", ticket_id).maybe_single().execute()
        if not resp.data:
            raise HTTPException(status_code=404, detail="Ticket not found")
    except HTTPException:
        raise
    except Exception as exc:
        _handle_supabase_error(exc, "ai_update_ticket/fetch")

    current = resp.data
    old_status = current["status"]
    existing_changelog: List[Dict[str, Any]] = current.get("ai_changelog") or []

    # 2. Build new changelog entry
    new_entry: Dict[str, Any] = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "agent": body.agent,
        "old_status": old_status,
        "new_status": body.new_status,
        "summary": body.summary_of_work,
    }
    updated_changelog = existing_changelog + [new_entry]

    # 3. Write status + updated changelog
    try:
        resp = (
            sb.table(_TABLE)
            .update({"status": body.new_status, "ai_changelog": updated_changelog})
            .eq("id", ticket_id)
            .execute()
        )
        if not resp.data:
            raise HTTPException(status_code=404, detail="Ticket not found")
    except HTTPException:
        raise
    except Exception as exc:
        _handle_supabase_error(exc, "ai_update_ticket/write")

    logger.info(
        "AI updated ticket %s: %s → %s (%s)",
        ticket_id[:8],
        old_status,
        body.new_status,
        body.agent,
    )
    return {
        "status": "ok",
        "ticket_id": ticket_id,
        "old_status": old_status,
        "new_status": body.new_status,
        "changelog_entries": len(updated_changelog),
    }


@router.delete("/{ticket_id}")
def delete_ticket(ticket_id: str):
    """Soft-delete a ticket by setting status to 'archived'."""
    sb = get_api_supabase()
    try:
        resp = (
            sb.table(_TABLE)
            .update({"status": "archived"})
            .eq("id", ticket_id)
            .execute()
        )
        if not resp.data:
            raise HTTPException(status_code=404, detail="Ticket not found")
    except HTTPException:
        raise
    except Exception as exc:
        _handle_supabase_error(exc, "delete_ticket")

    return {"status": "ok", "ticket_id": ticket_id, "archived": True}
