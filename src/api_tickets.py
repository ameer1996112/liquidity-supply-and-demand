"""Tickets API — Jira-backed proxy with AI changelog support.

Forwards ticket CRUD to real Jira (project DEV at ameer1996112.atlassian.net)
while exposing the same FastAPI routes so all AI skills / workflows work unchanged.

Routes:
  GET    /api/tickets                → list non-archived issues
  POST   /api/tickets                → create issue in Jira (idempotent by title)
  GET    /api/tickets/active-sprint  → return active sprint id
  GET    /api/tickets/{id}           → get issue by Jira issue key or DB id
  PATCH  /api/tickets/{id}           → update status/priority/etc
  POST   /api/tickets/{id}/ai-update → append AI changelog comment + transition
  DELETE /api/tickets/{id}           → close/archive issue in Jira
"""

import base64
import logging
import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import requests
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/tickets", tags=["tickets"])

# ── Jira config ───────────────────────────────────────────────────────────────

_JIRA_BASE = os.getenv("JIRA_BASE_URL", "https://ameer1996112.atlassian.net")
_JIRA_EMAIL = os.getenv("JIRA_EMAIL", "")
_JIRA_TOKEN = os.getenv("JIRA_API_TOKEN", "")
_JIRA_PROJECT = os.getenv("JIRA_PROJECT_KEY", "DEV")
_JIRA_TASK_TYPE_ID = os.getenv("JIRA_TASK_TYPE_ID", "10003")

# Map our internal type/status to Jira
_TYPE_TO_LABEL: Dict[str, str] = {
    "bug": "bug",
    "feature": "feature",
    "task": "task",
}
_STATUS_TO_TRANSITION: Dict[str, str] = {
    "todo": "11",         # "To Do"   — Jira default transition ID
    "in_progress": "21",  # "In Progress"
    "done": "31",         # "Done"
}
_JIRA_STATUS_MAP: Dict[str, str] = {
    "To Do": "todo",
    "In Progress": "in_progress",
    "Done": "done",
}


def _auth() -> str:
    raw = f"{_JIRA_EMAIL}:{_JIRA_TOKEN}"
    return "Basic " + base64.b64encode(raw.encode()).decode()


def _headers() -> Dict[str, str]:
    return {
        "Authorization": _auth(),
        "Content-Type": "application/json",
        "Accept": "application/json",
    }


def _jira_get(path: str, params: Dict = None) -> Any:
    url = f"{_JIRA_BASE}/rest/api/3{path}"
    r = requests.get(url, headers=_headers(), params=params or {}, timeout=10)
    r.raise_for_status()
    return r.json()


def _jira_post(path: str, body: Dict) -> Any:
    url = f"{_JIRA_BASE}/rest/api/3{path}"
    r = requests.post(url, headers=_headers(), json=body, timeout=10)
    r.raise_for_status()
    return r.json()


def _jira_put(path: str, body: Dict) -> Any:
    url = f"{_JIRA_BASE}/rest/api/3{path}"
    r = requests.put(url, headers=_headers(), json=body, timeout=10)
    r.raise_for_status()


def _jira_to_ticket(issue: Dict) -> Dict:
    """Convert a raw Jira issue dict to our internal ticket format."""
    fields = issue.get("fields", {})
    status_name = fields.get("status", {}).get("name", "To Do")
    our_status = _JIRA_STATUS_MAP.get(status_name, "todo")
    labels = fields.get("labels", [])
    priority_name = (fields.get("priority") or {}).get("name", "Medium")
    our_priority = priority_name.lower() if priority_name.lower() in ("low", "medium", "high", "critical") else "medium"

    # Extract AI changelog from issue description custom field (stored as label)
    ai_changelog: List[Dict] = []
    description = fields.get("description") or {}
    # We store AI changelog entries as Jira comments tagged [AI-LOG]
    # Parsed lazily in ai-update endpoint

    return {
        "id": issue["key"],           # e.g. DEV-7 — used as the ticket "id"
        "ticket_id": issue["key"],
        "title": fields.get("summary", ""),
        "description": _extract_plain_text(description),
        "type": _extract_type_from_labels(labels),
        "status": our_status,
        "priority": our_priority,
        "assignee": (fields.get("assignee") or {}).get("displayName"),
        "signal_id": None,
        "sprint_id": _extract_sprint_id(fields),
        "labels": [l for l in labels if not l.startswith("type:")],
        "parent_id": None,
        "rank": 0,
        "story_points": fields.get("story_points"),
        "ai_changelog": ai_changelog,
        "created_at": fields.get("created", datetime.now(timezone.utc).isoformat()),
        "updated_at": fields.get("updated", datetime.now(timezone.utc).isoformat()),
    }


def _extract_plain_text(adf: Any) -> Optional[str]:
    """Extract plain text from Atlassian Document Format."""
    if not adf or not isinstance(adf, dict):
        return None
    text_parts = []
    for block in adf.get("content", []):
        for inline in block.get("content", []):
            if inline.get("type") == "text":
                text_parts.append(inline.get("text", ""))
    return " ".join(text_parts) or None


def _extract_type_from_labels(labels: List[str]) -> str:
    for l in labels:
        if l.startswith("type:"):
            return l.split(":", 1)[1]
    return "task"


def _extract_sprint_id(fields: Dict) -> Optional[int]:
    """Extract sprint id from Jira fields (custom field)."""
    for key, val in fields.items():
        if "sprint" in key.lower() and isinstance(val, dict):
            return val.get("id")
        if "sprint" in key.lower() and isinstance(val, list) and val:
            return val[-1].get("id") if isinstance(val[-1], dict) else None
    return None


def _make_description_adf(text: str) -> Dict:
    """Wrap plain text in Atlassian Document Format."""
    return {
        "type": "doc",
        "version": 1,
        "content": [
            {
                "type": "paragraph",
                "content": [{"type": "text", "text": text}],
            }
        ],
    }


# ── Pydantic models (kept compatible with existing skill calls) ────────────────

class CreateTicketRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=500)
    description: Optional[str] = None
    type: str = Field("task", pattern="^(bug|feature|task)$")
    status: str = Field("todo", pattern="^(todo|in_progress|done)$")
    priority: str = Field("medium", pattern="^(low|medium|high|critical)$")
    assignee: Optional[str] = None
    signal_id: Optional[int] = None
    sprint_id: Optional[int] = None


class PatchTicketRequest(BaseModel):
    title: Optional[str] = Field(None, min_length=1, max_length=500)
    description: Optional[str] = None
    type: Optional[str] = Field(None, pattern="^(bug|feature|task)$")
    status: Optional[str] = Field(None, pattern="^(todo|in_progress|done|archived)$")
    priority: Optional[str] = Field(None, pattern="^(low|medium|high|critical)$")
    assignee: Optional[str] = None
    signal_id: Optional[int] = None
    sprint_id: Optional[int] = None


class AiUpdateRequest(BaseModel):
    new_status: str = Field(..., pattern="^(todo|in_progress|done)$")
    summary_of_work: str = Field(..., min_length=1, max_length=2000)
    agent: str = Field("antigravity", max_length=100)


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("")
def list_tickets(
    status: Optional[str] = Query(None),
    type: Optional[str] = Query(None),
    priority: Optional[str] = Query(None),
    limit: int = Query(100, ge=1, le=500),
):
    """List non-archived Jira issues for the DEV project."""
    # Build JQL
    jql_parts = [f"project = {_JIRA_PROJECT}", "statusCategory != Done OR status != Done"]
    if status and status != "archived":
        jira_status = {
            "todo": "\"To Do\"",
            "in_progress": "\"In Progress\"",
            "done": "\"Done\"",
        }.get(status)
        if jira_status:
            jql_parts = [f"project = {_JIRA_PROJECT}", f"status = {jira_status}"]
    if status == "archived":
        jql_parts = [f"project = {_JIRA_PROJECT}", "status = Done"]

    jql = " AND ".join(jql_parts) + " ORDER BY created DESC"

    try:
        data = _jira_get("/search", {
            "jql": jql,
            "maxResults": limit,
            "fields": "summary,status,priority,labels,assignee,created,updated,description,issuetype",
        })
        issues = [_jira_to_ticket(i) for i in data.get("issues", [])]
        return {"tickets": issues, "count": len(issues)}
    except Exception as exc:
        logger.error("Failed to list Jira issues: %s", exc)
        return {"tickets": [], "count": 0}


@router.get("/active-sprint")
def get_active_sprint():
    """Return the active sprint id and name, or null if none is active.

    Queries Jira's agile board for the active sprint.
    """
    try:
        # Get all boards for the project
        boards = _jira_get("/board", {"projectKeyOrId": _JIRA_PROJECT, "type": "scrum"})
        board_list = boards.get("values", [])
        if not board_list:
            # Try kanban
            boards = _jira_get("/board", {"projectKeyOrId": _JIRA_PROJECT})
            board_list = boards.get("values", [])
        if not board_list:
            return {"sprint_id": None, "name": None}

        board_id = board_list[0]["id"]
        sprints = _jira_get(f"/board/{board_id}/sprint", {"state": "active"})
        sprint_list = sprints.get("values", [])
        if sprint_list:
            s = sprint_list[0]
            return {"sprint_id": s["id"], "name": s["name"]}
    except Exception as exc:
        logger.warning("Could not fetch active sprint from Jira: %s", exc)
    return {"sprint_id": None, "name": None}


@router.post("", status_code=201)
def create_ticket(body: CreateTicketRequest):
    """Create a Jira issue. Idempotent: same title → returns existing issue."""
    title = body.title.strip()

    # ── Idempotency check ──────────────────────────────────────────────────
    try:
        search = _jira_get("/search", {
            "jql": f'project = {_JIRA_PROJECT} AND summary ~ "{title}" AND statusCategory != Done',
            "fields": "summary,status,priority,labels,assignee,created,updated,description",
            "maxResults": 5,
        })
        for issue in search.get("issues", []):
            if issue["fields"]["summary"].strip().lower() == title.lower():
                logger.info("Idempotent create_ticket: returning existing %s", issue["key"])
                return JSONResponse(status_code=200, content=_jira_to_ticket(issue))
    except Exception as exc:
        logger.warning("Dedup check failed, proceeding with create: %s", exc)

    # ── Build labels ───────────────────────────────────────────────────────
    labels = [f"type:{body.type}"]
    if body.priority != "medium":
        labels.append(f"priority:{body.priority}")

    # ── Create in Jira ─────────────────────────────────────────────────────
    issue_body: Dict[str, Any] = {
        "fields": {
            "project": {"key": _JIRA_PROJECT},
            "summary": title,
            "issuetype": {"id": _JIRA_TASK_TYPE_ID},
            "labels": labels,
        }
    }
    if body.description:
        issue_body["fields"]["description"] = _make_description_adf(body.description)

    try:
        created = _jira_post("/issue", issue_body)
        key = created["key"]

        # Transition to requested status if not "todo"
        if body.status != "todo":
            _transition_issue(key, body.status)

        # Fetch full issue to return
        full = _jira_get(f"/issue/{key}")
        ticket = _jira_to_ticket(full)
        return JSONResponse(status_code=201, content=ticket)
    except requests.HTTPError as exc:
        logger.error("Jira create failed: %s — %s", exc, exc.response.text if exc.response else "")
        raise HTTPException(status_code=502, detail=f"Jira error: {exc}")


@router.get("/{ticket_id}")
def get_ticket(ticket_id: str):
    """Fetch a single Jira issue by key (e.g. DEV-7)."""
    try:
        issue = _jira_get(f"/issue/{ticket_id}")
        return _jira_to_ticket(issue)
    except requests.HTTPError as exc:
        if exc.response is not None and exc.response.status_code == 404:
            raise HTTPException(status_code=404, detail="Ticket not found")
        raise HTTPException(status_code=502, detail=f"Jira error: {exc}")


@router.patch("/{ticket_id}")
def patch_ticket(ticket_id: str, body: PatchTicketRequest):
    """Update a Jira issue (status, title, labels)."""
    updates: Dict[str, Any] = {k: v for k, v in body.model_dump().items() if v is not None}
    if not updates:
        raise HTTPException(status_code=400, detail="No fields to update")

    fields_payload: Dict[str, Any] = {}
    if "title" in updates:
        fields_payload["summary"] = updates["title"]
    if "description" in updates:
        fields_payload["description"] = _make_description_adf(updates["description"])
    if "type" in updates or "priority" in updates:
        # Rebuild labels
        try:
            current = _jira_get(f"/issue/{ticket_id}", {"fields": "labels"})
            old_labels = current["fields"].get("labels", [])
        except Exception:
            old_labels = []
        new_labels = [l for l in old_labels if not l.startswith("type:") and not l.startswith("priority:")]
        if "type" in updates:
            new_labels.append(f"type:{updates['type']}")
        if "priority" in updates and updates["priority"] != "medium":
            new_labels.append(f"priority:{updates['priority']}")
        fields_payload["labels"] = new_labels

    try:
        if fields_payload:
            _jira_put(f"/issue/{ticket_id}", {"fields": fields_payload})
        if "status" in updates:
            _transition_issue(ticket_id, updates["status"])
        issue = _jira_get(f"/issue/{ticket_id}")
        return _jira_to_ticket(issue)
    except requests.HTTPError as exc:
        if exc.response is not None and exc.response.status_code == 404:
            raise HTTPException(status_code=404, detail="Ticket not found")
        raise HTTPException(status_code=502, detail=f"Jira error: {exc}")


@router.post("/{ticket_id}/ai-update")
def ai_update_ticket(ticket_id: str, body: AiUpdateRequest):
    """AI skill endpoint — add a comment to Jira and transition the issue status."""
    # Post a comment with AI log marker
    comment_body = {
        "body": _make_description_adf(
            f"[AI-LOG] {body.agent} → {body.new_status}\n\n{body.summary_of_work}"
        )
    }
    try:
        _jira_post(f"/issue/{ticket_id}/comment", comment_body)
        _transition_issue(ticket_id, body.new_status)

        # Fetch current status to report old vs new
        issue = _jira_get(f"/issue/{ticket_id}", {"fields": "status"})
        new_status_name = issue["fields"]["status"]["name"]

        logger.info("AI updated Jira issue %s → %s (%s)", ticket_id, body.new_status, body.agent)
        return {
            "status": "ok",
            "ticket_id": ticket_id,
            "new_status": body.new_status,
            "jira_status": new_status_name,
            "changelog_entries": 1,
        }
    except requests.HTTPError as exc:
        if exc.response is not None and exc.response.status_code == 404:
            raise HTTPException(status_code=404, detail="Ticket not found")
        raise HTTPException(status_code=502, detail=f"Jira error: {exc}")


@router.delete("/{ticket_id}")
def delete_ticket(ticket_id: str):
    """Transition the issue to Done (archive = close in Jira)."""
    try:
        _transition_issue(ticket_id, "done")
        return {"status": "ok", "ticket_id": ticket_id, "archived": True}
    except requests.HTTPError as exc:
        if exc.response is not None and exc.response.status_code == 404:
            raise HTTPException(status_code=404, detail="Ticket not found")
        raise HTTPException(status_code=502, detail=f"Jira error: {exc}")


# ── Helpers ───────────────────────────────────────────────────────────────────

def _transition_issue(key: str, our_status: str) -> None:
    """Transition a Jira issue to the matching status.

    Fetches available transitions first so IDs stay accurate even if Jira
    workflow is customised.
    """
    target_name = {"todo": "To Do", "in_progress": "In Progress", "done": "Done"}.get(our_status)
    if not target_name:
        return
    try:
        data = _jira_get(f"/issue/{key}/transitions")
        for t in data.get("transitions", []):
            if t["to"]["name"] == target_name:
                _jira_post(f"/issue/{key}/transitions", {"transition": {"id": t["id"]}})
                return
        logger.warning("No transition to '%s' found for issue %s", target_name, key)
    except Exception as exc:
        logger.warning("Transition failed for %s → %s: %s", key, our_status, exc)
