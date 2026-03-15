"""
Board API — Kanban ticket management for AI agents and backend services.

Endpoints:
  POST /api/v1/board/tickets           Create a new ticket
  GET  /api/v1/board/tickets           List all tickets (optional ?status= filter)
  POST /api/v1/board/tickets/{id}/move Move ticket to a new status column
  POST /api/v1/board/agent-update      Log agent activity + optionally move ticket

Used by: Claude Code, worker.py, execution_engine.py, any backend service
that wants to open or update board tickets automatically.
"""

import logging
from datetime import datetime, timezone
from typing import Literal, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from src.adapters.supabase import get_supabase

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/board", tags=["board"])

# ── Types ──────────────────────────────────────────────────────────────────────

TicketType = Literal["bug", "task", "feature", "research"]
Priority = Literal["critical", "high", "medium", "low"]
TicketStatus = Literal["backlog", "todo", "in_progress", "done"]
EventType = Literal["update", "move", "create", "close"]


class CreateTicketRequest(BaseModel):
    type: TicketType
    title: str
    description: Optional[str] = None
    component: str
    priority: Priority
    status: TicketStatus = "backlog"
    agent_name: Optional[str] = "Claude Agent"


class MoveTicketRequest(BaseModel):
    new_status: TicketStatus
    message: Optional[str] = None
    agent_name: Optional[str] = "Claude Agent"


class AgentUpdateRequest(BaseModel):
    ticket_id: str
    message: str
    new_status: Optional[TicketStatus] = None
    agent_name: Optional[str] = "Claude Agent"
    event_type: Optional[EventType] = None


# ── Helpers ────────────────────────────────────────────────────────────────────

_PREFIX_MAP: dict[str, str] = {
    "bug": "BUG",
    "feature": "FEAT",
    "research": "RES",
    "task": "TASK",
}


def _next_ticket_id(supabase, ticket_type: str) -> str:
    prefix = _PREFIX_MAP.get(ticket_type, "TASK")
    resp = (
        supabase.table("project_tickets")
        .select("ticket_id")
        .ilike("ticket_id", f"{prefix}-%")
        .order("ticket_id", desc=True)
        .limit(1)
        .execute()
    )
    rows = resp.data or []
    last_num = int(rows[0]["ticket_id"].split("-")[1]) if rows else 0
    return f"{prefix}-{str(last_num + 1).zfill(3)}"


def _log_agent_event(
    supabase,
    ticket_id: str,
    message: str,
    event_type: str,
    agent_name: str,
) -> None:
    try:
        supabase.table("ticket_agent_events").insert(
            {
                "ticket_id": ticket_id,
                "message": message,
                "event_type": event_type,
                "agent_name": agent_name,
            }
        ).execute()
    except Exception as exc:  # non-fatal
        logger.warning("Failed to log agent event for %s: %s", ticket_id, exc)


# ── Routes ─────────────────────────────────────────────────────────────────────


@router.post("/tickets")
def create_ticket(req: CreateTicketRequest):
    """Create a new ticket and log an agent creation event."""
    supabase = get_supabase()
    ticket_id = _next_ticket_id(supabase, req.type)

    row = {
        "ticket_id": ticket_id,
        "type": req.type,
        "title": req.title,
        "component": req.component,
        "priority": req.priority,
        "status": req.status,
    }
    if req.description:
        row["description"] = req.description

    resp = supabase.table("project_tickets").insert(row).execute()
    if not resp.data:
        raise HTTPException(status_code=500, detail="Failed to insert ticket")

    _log_agent_event(
        supabase,
        ticket_id,
        f"Opened {req.type} ticket: {req.title}",
        "create",
        req.agent_name or "Claude Agent",
    )
    logger.info("Board ticket created: %s — %s", ticket_id, req.title)
    return {"ok": True, "ticket_id": ticket_id, "ticket": resp.data[0]}


@router.get("/tickets")
def list_tickets(status: Optional[str] = None):
    """List all tickets, optionally filtered by status."""
    supabase = get_supabase()
    q = supabase.table("project_tickets").select("*").order("created_at", desc=True)
    if status:
        q = q.eq("status", status)
    resp = q.execute()
    return {"tickets": resp.data or []}


@router.post("/tickets/{ticket_id}/move")
def move_ticket(ticket_id: str, req: MoveTicketRequest):
    """Move a ticket to a new status column."""
    supabase = get_supabase()
    patch: dict = {"status": req.new_status}
    if req.new_status == "done":
        patch["completed_at"] = datetime.now(timezone.utc).isoformat()

    resp = (
        supabase.table("project_tickets")
        .update(patch)
        .eq("ticket_id", ticket_id)
        .execute()
    )
    if not resp.data:
        raise HTTPException(status_code=404, detail=f"Ticket {ticket_id} not found")

    event_type = "close" if req.new_status == "done" else "move"
    message = req.message or f"Moved to {req.new_status.replace('_', ' ')}"
    _log_agent_event(supabase, ticket_id, message, event_type, req.agent_name or "Claude Agent")
    logger.info("Board ticket %s moved to %s", ticket_id, req.new_status)
    return {"ok": True, "ticket_id": ticket_id, "new_status": req.new_status}


@router.post("/agent-update")
def agent_update(req: AgentUpdateRequest):
    """Log agent activity and optionally move a ticket. Mirrors the Next.js endpoint."""
    supabase = get_supabase()

    if req.new_status:
        patch: dict = {"status": req.new_status}
        if req.new_status == "done":
            patch["completed_at"] = datetime.now(timezone.utc).isoformat()
        supabase.table("project_tickets").update(patch).eq("ticket_id", req.ticket_id).execute()

    derived_event = (
        req.event_type
        or ("close" if req.new_status == "done" else "move" if req.new_status else "update")
    )
    _log_agent_event(
        supabase,
        req.ticket_id,
        req.message,
        derived_event,
        req.agent_name or "Claude Agent",
    )
    return {"ok": True, "ticket_id": req.ticket_id, "new_status": req.new_status}
