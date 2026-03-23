"""Tickets API — Jira-backed proxy with rich ticket support.

Forwards ticket CRUD to real Jira (project DEV at ameer1996112.atlassian.net)
while exposing the same FastAPI routes so all AI skills / workflows work unchanged.

Upgrades vs v1:
  - Real Jira Priority field (High/Medium/Low/Critical)
  - Story points via customfield_10016
  - Rich ADF descriptions with ## Problem / ## Acceptance Criteria sections
  - Sprint auto-assignment via customfield_10020
  - Proper label cleanup (no raw "priority:X" labels — labels used for type only)
  - Idempotent creation (same title → return existing)

Routes:
  GET    /api/tickets                → list issues
  POST   /api/tickets                → create issue
  GET    /api/tickets/active-sprint  → return active sprint id/name
  GET    /api/tickets/{id}           → get issue by Jira key
  PATCH  /api/tickets/{id}           → update fields
  POST   /api/tickets/{id}/ai-update → AI changelog comment + status transition
  DELETE /api/tickets/{id}           → close/archive (transition to Done)
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
# Agile REST API has a different base path — /rest/agile/1.0 not /rest/api/3
_JIRA_AGILE_BASE = _JIRA_BASE + "/rest/agile/1.0"
_JIRA_EMAIL = os.getenv("JIRA_EMAIL", "")
_JIRA_TOKEN = os.getenv("JIRA_API_TOKEN", "")
_JIRA_PROJECT = os.getenv("JIRA_PROJECT_KEY", "DEV")
_JIRA_TASK_TYPE_ID = os.getenv("JIRA_TASK_TYPE_ID", "10003")

# Timeouts — Jira free-tier JQL can be very slow (30-90s)
_TIMEOUT_READ = int(os.getenv("JIRA_TIMEOUT", "90"))    # JQL search / write ops
_TIMEOUT_FAST = int(os.getenv("JIRA_TIMEOUT_FAST", "20"))  # lightweight reads

# Jira free plan priority names (must match exactly)
_PRIORITY_MAP: Dict[str, str] = {
    "critical": "Highest",
    "high": "High",
    "medium": "Medium",
    "low": "Low",
}
_JIRA_STATUS_MAP: Dict[str, str] = {
    "To Do": "todo",
    "In Progress": "in_progress",
    "Done": "done",
}
# Jira standard custom field IDs
_FIELD_STORY_POINTS = "story_points"   # or customfield_10016 — discovered at startup
_FIELD_SPRINT = "customfield_10020"

# ── Active sprint cache (5-minute TTL) ────────────────────────────────────────
import time as _time_module

_sprint_cache: Dict[str, Any] = {"id": None, "name": None, "ts": 0.0}
_SPRINT_CACHE_TTL = 300  # 5 minutes


def _auth() -> str:
    raw = f"{_JIRA_EMAIL}:{_JIRA_TOKEN}"
    return "Basic " + base64.b64encode(raw.encode()).decode()


def _headers() -> Dict[str, str]:
    return {
        "Authorization": _auth(),
        "Content-Type": "application/json",
        "Accept": "application/json",
    }


def _jira_get(path: str, params: Dict = None, timeout: int = None) -> Any:
    url = f"{_JIRA_BASE}/rest/api/3{path}"
    r = requests.get(url, headers=_headers(), params=params or {}, timeout=timeout or _TIMEOUT_READ)
    r.raise_for_status()
    return r.json()


def _jira_agile_get(path: str, params: Dict = None) -> Any:
    """Call the Jira Agile REST API (/rest/agile/1.0) — used for board/sprint ops."""
    url = f"{_JIRA_AGILE_BASE}{path}"
    r = requests.get(url, headers=_headers(), params=params or {}, timeout=_TIMEOUT_READ)
    r.raise_for_status()
    return r.json()


def _jira_agile_post(path: str, body: Dict) -> Any:
    url = f"{_JIRA_AGILE_BASE}{path}"
    r = requests.post(url, headers=_headers(), json=body, timeout=_TIMEOUT_READ)
    r.raise_for_status()
    return r.json()


def _jira_agile_put(path: str, body: Dict) -> Any:
    """PUT to the Jira Agile REST API — used for updating sprint state."""
    url = f"{_JIRA_AGILE_BASE}{path}"
    r = requests.put(url, headers=_headers(), json=body, timeout=_TIMEOUT_READ)
    r.raise_for_status()
    return r.json()


def _jira_post(path: str, body: Dict, timeout: int = None) -> Any:
    url = f"{_JIRA_BASE}/rest/api/3{path}"
    r = requests.post(url, headers=_headers(), json=body, timeout=timeout or _TIMEOUT_READ)
    r.raise_for_status()
    return r.json()


def _jira_put(path: str, body: Dict) -> Any:
    url = f"{_JIRA_BASE}/rest/api/3{path}"
    r = requests.put(url, headers=_headers(), json=body, timeout=_TIMEOUT_READ)
    r.raise_for_status()


def _get_active_sprint_id() -> Optional[int]:
    """Return the active sprint ID, using a 5-minute cache to avoid repeated Agile API calls."""
    global _sprint_cache
    now = _time_module.time()
    if _sprint_cache["ts"] and (now - _sprint_cache["ts"]) < _SPRINT_CACHE_TTL:
        return _sprint_cache["id"]
    try:
        boards = _jira_agile_get("/board", {"projectKeyOrId": _JIRA_PROJECT, "type": "scrum"})
        board_list = boards.get("values", [])
        if not board_list:
            # Try kanban board
            boards = _jira_agile_get("/board", {"projectKeyOrId": _JIRA_PROJECT})
            board_list = boards.get("values", [])
        if not board_list:
            _sprint_cache = {"id": None, "name": None, "ts": now}
            return None
        board_id = board_list[0]["id"]
        sprints = _jira_agile_get(f"/board/{board_id}/sprint", {"state": "active"})
        sprint_list = sprints.get("values", [])
        if sprint_list:
            s = sprint_list[0]
            _sprint_cache = {"id": s["id"], "name": s["name"], "ts": now}
            return s["id"]
    except Exception as exc:
        logger.warning("Could not fetch active sprint (cache miss): %s", exc)
    _sprint_cache = {"id": None, "name": None, "ts": now}
    return None


def _maybe_autoclose_sprint() -> None:
    """
    Sprint auto-close hook (SPRINT-01): called when any ticket moves to 'done'.

    Checks if all tickets in the active sprint are done. If so:
    1. Closes the active sprint via Jira Agile API
    2. Starts a new sprint (auto-named Sprint N+1)
    3. Clears the sprint cache so the new sprint is picked up
    """
    try:
        sprint_id = _get_active_sprint_id()
        if sprint_id is None:
            return

        # Query Jira for open issues in this sprint
        boards = _jira_agile_get("/board", {"projectKeyOrId": _JIRA_PROJECT})
        board_list = boards.get("values", [])
        if not board_list:
            return
        board_id = board_list[0]["id"]

        open_issues = _jira_agile_get(
            f"/board/{board_id}/sprint/{sprint_id}/issue",
            {"jql": "statusCategory != Done", "maxResults": 1, "fields": "id"},
        )
        open_count = open_issues.get("total", 1)  # Default to 1 (not empty) if API fails

        if open_count > 0:
            return  # There are still open tickets — do nothing

        # All done! Close the sprint.
        logger.info("Sprint %s: all tickets done — auto-closing sprint", sprint_id)
        _jira_agile_put(f"/sprint/{sprint_id}", {"state": "closed"})

        # Start a new sprint (auto-named Sprint N+1)
        sprint_name = _sprint_cache.get("name") or f"Sprint {sprint_id}"
        # Extract number from name like "Sprint 2" → "Sprint 3"
        import re as _re
        match = _re.search(r"\d+", sprint_name)
        if match:
            next_num = int(match.group()) + 1
            new_name = _re.sub(r"\d+", str(next_num), sprint_name, count=1)
        else:
            new_name = f"{sprint_name} (next)"

        _jira_agile_post(f"/sprint", {"name": new_name, "originBoardId": board_id})
        logger.info("Auto-created next sprint: %s", new_name)

        # Clear sprint cache so next request picks up new sprint
        global _sprint_cache
        _sprint_cache = {"id": None, "name": None, "ts": 0.0}

    except Exception as exc:
        # Never crash the ticket update — log and continue silently
        logger.warning("Sprint auto-close check failed (non-fatal): %s", exc)




# ── ADF helpers ───────────────────────────────────────────────────────────────

def _adf_heading(text: str, level: int = 2) -> Dict:
    return {
        "type": "heading",
        "attrs": {"level": level},
        "content": [{"type": "text", "text": text}],
    }


def _adf_paragraph(text: str) -> Dict:
    return {
        "type": "paragraph",
        "content": [{"type": "text", "text": text}],
    }


def _adf_bullet_list(items: List[str]) -> Dict:
    return {
        "type": "bulletList",
        "content": [
            {
                "type": "listItem",
                "content": [{"type": "paragraph", "content": [{"type": "text", "text": item}]}],
            }
            for item in items
        ],
    }


def _build_rich_description(
    problem: str,
    solution: Optional[str] = None,
    files: Optional[List[str]] = None,
    acceptance_criteria: Optional[List[str]] = None,
) -> Dict:
    """Build a rich Atlassian Document Format description with structured sections."""
    content = []

    # Problem section
    content.append(_adf_heading("🔍 Problem", 2))
    content.append(_adf_paragraph(problem))

    # Acceptance Criteria section
    if acceptance_criteria:
        content.append(_adf_heading("✅ Acceptance Criteria", 2))
        content.append(_adf_bullet_list(acceptance_criteria))
    else:
        # Auto-generate basic AC from the problem statement
        content.append(_adf_heading("✅ Acceptance Criteria", 2))
        content.append(_adf_bullet_list([
            "Issue is resolved and verified in the UI / tests",
            "No regression in related functionality",
            "Code reviewed and merged",
        ]))

    # Solution hints
    if solution:
        content.append(_adf_heading("💡 Solution Approach", 2))
        content.append(_adf_paragraph(solution))

    # Referenced files
    if files:
        content.append(_adf_heading("📁 Files", 2))
        content.append(_adf_bullet_list(files))

    return {"type": "doc", "version": 1, "content": content}


def _plain_description(problem: str, solution: Optional[str] = None) -> Dict:
    """Simple one-line ADF for plain text descriptions."""
    return _build_rich_description(problem, solution)


def _extract_plain_text(adf: Any) -> Optional[str]:
    if not adf or not isinstance(adf, dict):
        return None
    parts = []
    def _walk(node):
        if isinstance(node, dict):
            if node.get("type") == "text":
                parts.append(node.get("text", ""))
            for child in node.get("content", []):
                _walk(child)
        elif isinstance(node, list):
            for item in node:
                _walk(item)
    _walk(adf)
    return " ".join(parts).strip() or None


# ── Jira issue → internal ticket ──────────────────────────────────────────────

def _jira_to_ticket(issue: Dict) -> Dict:
    fields = issue.get("fields", {})
    status_name = fields.get("status", {}).get("name", "To Do")
    our_status = _JIRA_STATUS_MAP.get(status_name, "todo")

    labels = fields.get("labels", [])
    type_labels = [l.split(":", 1)[1] for l in labels if l.startswith("type:")]
    our_type = type_labels[0] if type_labels else "task"

    priority_name = (fields.get("priority") or {}).get("name", "Medium")
    reverse_priority = {v: k for k, v in _PRIORITY_MAP.items()}
    our_priority = reverse_priority.get(priority_name, "medium")

    story_points = (
        fields.get("story_points")
        or fields.get("customfield_10016")
        or fields.get("customfield_10028")  # next-gen projects
    )

    sprint_id = _extract_sprint_id(fields)

    return {
        "id": issue["key"],
        "ticket_id": issue["key"],
        "title": fields.get("summary", ""),
        "description": _extract_plain_text(fields.get("description")),
        "type": our_type,
        "status": our_status,
        "priority": our_priority,
        "assignee": (fields.get("assignee") or {}).get("displayName"),
        "signal_id": None,
        "sprint_id": sprint_id,
        "labels": [l for l in labels if not l.startswith("type:")],
        "parent_id": None,
        "rank": 0,
        "story_points": story_points,
        "ai_changelog": [],
        "created_at": fields.get("created", datetime.now(timezone.utc).isoformat()),
        "updated_at": fields.get("updated", datetime.now(timezone.utc).isoformat()),
    }


def _extract_sprint_id(fields: Dict) -> Optional[int]:
    sprint_raw = fields.get(_FIELD_SPRINT)
    if not sprint_raw:
        return None
    if isinstance(sprint_raw, list) and sprint_raw:
        s = sprint_raw[-1]
        return s.get("id") if isinstance(s, dict) else None
    if isinstance(sprint_raw, dict):
        return sprint_raw.get("id")
    return None


def _transition_issue(key: str, our_status: str) -> None:
    target_name = {
        "todo": "To Do",
        "in_progress": "In Progress",
        "done": "Done",
    }.get(our_status)
    if not target_name:
        return
    try:
        data = _jira_get(f"/issue/{key}/transitions")
        for t in data.get("transitions", []):
            if t["to"]["name"] == target_name:
                _jira_post(f"/issue/{key}/transitions", {"transition": {"id": t["id"]}})
                return
        logger.warning("No transition to '%s' found for %s", target_name, key)
    except Exception as exc:
        logger.warning("Transition failed for %s → %s: %s", key, our_status, exc)


# ── Pydantic models ───────────────────────────────────────────────────────────

class CreateTicketRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=500)
    description: Optional[str] = None
    problem: Optional[str] = None              # structured problem statement
    solution: Optional[str] = None             # solution approach hints
    acceptance_criteria: Optional[List[str]] = None
    files: Optional[List[str]] = None          # referenced file paths
    type: str = Field("task", pattern="^(bug|feature|task)$")
    status: str = Field("todo", pattern="^(todo|in_progress|done)$")
    priority: str = Field("medium", pattern="^(low|medium|high|critical)$")
    story_points: Optional[int] = Field(None, ge=1, le=100)
    assignee: Optional[str] = None
    signal_id: Optional[int] = None
    sprint_id: Optional[int] = None


class PatchTicketRequest(BaseModel):
    title: Optional[str] = Field(None, min_length=1, max_length=500)
    description: Optional[str] = None
    type: Optional[str] = Field(None, pattern="^(bug|feature|task)$")
    status: Optional[str] = Field(None, pattern="^(todo|in_progress|done|archived)$")
    priority: Optional[str] = Field(None, pattern="^(low|medium|high|critical)$")
    story_points: Optional[int] = Field(None, ge=1, le=100)
    assignee: Optional[str] = None
    signal_id: Optional[int] = None
    sprint_id: Optional[int] = None


class AiUpdateRequest(BaseModel):
    new_status: str = Field(..., pattern="^(todo|in_progress|done)$")
    summary_of_work: str = Field(..., min_length=1, max_length=2000)
    agent: str = Field("antigravity", max_length=100)


class GsdSyncRequest(BaseModel):
    """GSD phase lifecycle sync — called automatically by gsd-jira-hook.sh."""
    phase_num: str = Field(..., description="Phase number e.g. '1', '2.1'")
    phase_name: str = Field(..., description="Phase name from ROADMAP.md")
    event: str = Field(..., pattern="^(phase_start|plan_execute|phase_complete|phase_skip)$")
    goal: Optional[str] = None
    summary: Optional[str] = None
    ticket_id: Optional[str] = None   # If set, update instead of create


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("")
def list_tickets(
    status: Optional[str] = Query(None),
    type: Optional[str] = Query(None),
    priority: Optional[str] = Query(None),
    limit: int = Query(100, ge=1, le=500),
):
    """List non-archived Jira issues for the DEV project."""
    jql_parts = [f"project = {_JIRA_PROJECT}"]

    if status == "archived":
        jql_parts.append("status = Done")
    elif status:
        jira_status = {"todo": '"To Do"', "in_progress": '"In Progress"', "done": '"Done"'}.get(status)
        if jira_status:
            jql_parts.append(f"status = {jira_status}")
        else:
            jql_parts.append("status != Done")
    else:
        jql_parts.append("status != Done")

    jql = " AND ".join(jql_parts) + " ORDER BY created DESC"

    try:
        data = _jira_get("/search", {
            "jql": jql,
            "maxResults": limit,
            "fields": f"summary,status,priority,labels,assignee,created,updated,description,issuetype,story_points,customfield_10016,{_FIELD_SPRINT}",
        })
        issues = [_jira_to_ticket(i) for i in data.get("issues", [])]
        return {"tickets": issues, "count": len(issues)}
    except Exception as exc:
        logger.error("Failed to list Jira issues: %s", exc)
        return {"tickets": [], "count": 0}


@router.get("/active-sprint")
def get_active_sprint():
    """Return the active sprint id and name from Jira Agile board (cached 5min)."""
    sprint_id = _get_active_sprint_id()
    return {"sprint_id": sprint_id, "name": _sprint_cache.get("name")}


@router.get("/sprints")
def list_sprints(state: Optional[str] = Query(None, description="active|closed|future")):
    """List all Jira sprints for the project."""
    try:
        boards = _jira_agile_get("/board", {"projectKeyOrId": _JIRA_PROJECT})
        board_list = boards.get("values", [])
        if not board_list:
            return {"sprints": [], "board_id": None}
        board_id = board_list[0]["id"]
        params: Dict = {}
        if state:
            params["state"] = state
        sprints = _jira_agile_get(f"/board/{board_id}/sprint", params)
        result = [{
            "id": s["id"],
            "name": s["name"],
            "state": s["state"],
            "start_date": s.get("startDate"),
            "end_date": s.get("endDate"),
            "complete_date": s.get("completeDate"),
        } for s in sprints.get("values", [])]
        return {"sprints": result, "board_id": board_id, "count": len(result)}
    except Exception as exc:
        logger.error("list_sprints failed: %s", exc)
        return {"sprints": [], "board_id": None, "count": 0}


class SprintCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    start_date: Optional[str] = None   # ISO 8601
    end_date: Optional[str] = None
    goal: Optional[str] = None


@router.post("/sprints/start", status_code=201)
def start_sprint(body: SprintCreateRequest):
    """Create a new Jira sprint and start it immediately."""
    try:
        boards = _jira_agile_get("/board", {"projectKeyOrId": _JIRA_PROJECT})
        board_list = boards.get("values", [])
        if not board_list:
            raise HTTPException(status_code=404, detail="No Jira board found for project")
        board_id = board_list[0]["id"]

        # Create the sprint
        sprint_payload: Dict[str, Any] = {
            "name": body.name,
            "originBoardId": board_id,
        }
        if body.start_date:
            sprint_payload["startDate"] = body.start_date
        if body.end_date:
            sprint_payload["endDate"] = body.end_date
        if body.goal:
            sprint_payload["goal"] = body.goal

        created = _jira_agile_post("/sprint", sprint_payload)
        sprint_id = created["id"]

        # Activate the sprint — Jira Agile requires PUT /sprint/{id} to change state
        from datetime import datetime, timezone, timedelta
        now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000+0000")
        default_end = (datetime.now(timezone.utc) + timedelta(days=14)).strftime("%Y-%m-%dT%H:%M:%S.000+0000")
        activate_payload: Dict[str, Any] = {
            "state": "active",
            "startDate": now_iso,
            "endDate": body.end_date or default_end,
        }
        if body.goal:
            activate_payload["goal"] = body.goal
        try:
            _jira_agile_put(f"/sprint/{sprint_id}", activate_payload)
        except Exception as e:
            logger.warning("Could not activate sprint %s: %s — it remains in 'future' state", sprint_id, e)

        # Invalidate cache
        global _sprint_cache
        _sprint_cache = {"id": sprint_id, "name": body.name, "ts": _time_module.time()}

        return {"status": "ok", "sprint_id": sprint_id, "name": body.name}
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("start_sprint failed: %s", exc)
        raise HTTPException(status_code=502, detail=str(exc))


@router.post("/sprints/end")
def end_sprint():
    """Complete (close) the active sprint. Open issues stay in the board."""
    global _sprint_cache
    try:
        sprint_id = _get_active_sprint_id()
        if not sprint_id:
            return {"status": "no_active_sprint"}
        sprint_name = _sprint_cache.get("name", "")
        _jira_agile_post(f"/sprint/{sprint_id}", {"state": "closed"})
        # Invalidate cache
        _sprint_cache = {"id": None, "name": None, "ts": 0.0}
        return {"status": "ok", "closed_sprint_id": sprint_id, "name": sprint_name}
    except Exception as exc:
        logger.error("end_sprint failed: %s", exc)
        raise HTTPException(status_code=502, detail=str(exc))


@router.post("", status_code=201)
def create_ticket(body: CreateTicketRequest):
    """Create a Jira issue with rich description. Idempotent by title."""
    title = body.title.strip()

    # ── Idempotency ────────────────────────────────────────────────────────
    try:
        search = _jira_get("/search", {
            "jql": f'project = {_JIRA_PROJECT} AND summary ~ "{title}" AND status != Done',
            "fields": f"summary,status,priority,labels,assignee,created,updated,description,story_points,customfield_10016,{_FIELD_SPRINT}",
            "maxResults": 5,
        })
        for issue in search.get("issues", []):
            if issue["fields"]["summary"].strip().lower() == title.lower():
                logger.info("Idempotent: returning existing %s", issue["key"])
                return JSONResponse(status_code=200, content=_jira_to_ticket(issue))
    except Exception as exc:
        logger.warning("Dedup check failed, proceeding: %s", exc)

    # ── Build rich description ────────────────────────────────────────────
    problem_text = body.problem or body.description or title
    description_adf = _build_rich_description(
        problem=problem_text,
        solution=body.solution,
        files=body.files,
        acceptance_criteria=body.acceptance_criteria,
    )

    # ── Build fields payload ──────────────────────────────────────────────
    fields: Dict[str, Any] = {
        "project": {"key": _JIRA_PROJECT},
        "summary": title,
        "issuetype": {"id": _JIRA_TASK_TYPE_ID},
        "description": description_adf,
        "labels": [f"type:{body.type}"],
        "priority": {"name": _PRIORITY_MAP.get(body.priority, "Medium")},
    }

    # Story points (try both field IDs — whichever Jira accepts)
    if body.story_points is not None:
        fields["story_points"] = body.story_points
        fields["customfield_10016"] = body.story_points

    # Sprint — auto-assign to active sprint if caller didn't specify one
    effective_sprint_id = body.sprint_id
    if effective_sprint_id is None:
        effective_sprint_id = _get_active_sprint_id()
    if effective_sprint_id is not None:
        fields[_FIELD_SPRINT] = effective_sprint_id

    # ── Create in Jira ────────────────────────────────────────────────────
    try:
        # Remove unknown fields gracefully — Jira returns 400 if a field isn't on the screen
        issue_body = {"fields": fields}
        created = None
        try:
            created = _jira_post("/issue", issue_body)
        except requests.HTTPError as e:
            if e.response is not None and e.response.status_code == 400:
                # Retry without custom fields that might not be on the create screen
                stripped = {k: v for k, v in fields.items()
                            if k not in ("story_points", "customfield_10016", "customfield_10028", _FIELD_SPRINT)}
                created = _jira_post("/issue", {"fields": stripped})
                # Then update story points and sprint separately
                update_fields = {}
                if body.story_points is not None:
                    update_fields["story_points"] = body.story_points
                    update_fields["customfield_10016"] = body.story_points
                if update_fields:
                    try:
                        _jira_put(f"/issue/{created['key']}", {"fields": update_fields})
                    except Exception:
                        pass
                if body.sprint_id is not None:
                    try:
                        _jira_post(f"/board/1/sprint/{body.sprint_id}/issue",
                                   {"issues": [created["key"]]})
                    except Exception:
                        pass
            else:
                raise

        key = created["key"]

        if body.status != "todo":
            _transition_issue(key, body.status)

        full = _jira_get(f"/issue/{key}", {
            "fields": f"summary,status,priority,labels,assignee,created,updated,description,story_points,customfield_10016,{_FIELD_SPRINT}"
        })
        return JSONResponse(status_code=201, content=_jira_to_ticket(full))

    except requests.HTTPError as exc:
        detail = ""
        if exc.response is not None:
            try:
                detail = exc.response.json()
            except Exception:
                detail = exc.response.text
        logger.error("Jira create failed: %s — %s", exc, detail)
        raise HTTPException(status_code=502, detail=f"Jira error: {detail or exc}")


@router.get("/{ticket_id}")
def get_ticket(ticket_id: str):
    """Fetch a single Jira issue by key (e.g. DEV-6)."""
    try:
        issue = _jira_get(f"/issue/{ticket_id}", {
            "fields": f"summary,status,priority,labels,assignee,created,updated,description,story_points,customfield_10016,{_FIELD_SPRINT}"
        })
        return _jira_to_ticket(issue)
    except requests.HTTPError as exc:
        if exc.response is not None and exc.response.status_code == 404:
            raise HTTPException(status_code=404, detail="Ticket not found")
        raise HTTPException(status_code=502, detail=f"Jira error: {exc}")


@router.patch("/{ticket_id}")
def patch_ticket(ticket_id: str, body: PatchTicketRequest):
    """Update a Jira issue."""
    updates = {k: v for k, v in body.model_dump().items() if v is not None}
    if not updates:
        raise HTTPException(status_code=400, detail="No fields to update")

    fields_payload: Dict[str, Any] = {}

    if "title" in updates:
        fields_payload["summary"] = updates["title"]
    if "description" in updates:
        fields_payload["description"] = _plain_description(updates["description"])
    if "priority" in updates:
        fields_payload["priority"] = {"name": _PRIORITY_MAP.get(updates["priority"], "Medium")}
    if "story_points" in updates:
        fields_payload["story_points"] = updates["story_points"]
        fields_payload["customfield_10016"] = updates["story_points"]
    if "type" in updates:
        # Rebuild type label
        try:
            cur = _jira_get(f"/issue/{ticket_id}", {"fields": "labels"})
            old_labels = cur["fields"].get("labels", [])
        except Exception:
            old_labels = []
        new_labels = [l for l in old_labels if not l.startswith("type:")]
        new_labels.append(f"type:{updates['type']}")
        fields_payload["labels"] = new_labels

    try:
        if fields_payload:
            _jira_put(f"/issue/{ticket_id}", {"fields": fields_payload})
        if "status" in updates:
            _transition_issue(ticket_id, updates["status"])
            # ── Sprint auto-close hook (SPRINT-01) ───────────────────────────────
            # When a ticket moves to 'done', check if all sprint tickets are done.
            # If so, close the active sprint and start a new one automatically.
            if updates["status"] == "done":
                _maybe_autoclose_sprint()
        issue = _jira_get(f"/issue/{ticket_id}", {
            "fields": f"summary,status,priority,labels,assignee,created,updated,description,story_points,customfield_10016,{_FIELD_SPRINT}"
        })
        return _jira_to_ticket(issue)
    except requests.HTTPError as exc:
        if exc.response is not None and exc.response.status_code == 404:
            raise HTTPException(status_code=404, detail="Ticket not found")
        raise HTTPException(status_code=502, detail=f"Jira error: {exc}")



@router.post("/{ticket_id}/ai-update")
def ai_update_ticket(ticket_id: str, body: AiUpdateRequest):
    """AI skill: post a structured comment to Jira and transition status."""
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    comment_adf = {
        "type": "doc", "version": 1,
        "content": [
            _adf_heading(f"🤖 AI Update — {body.agent}", 2),
            _adf_paragraph(f"Status: {body.new_status.replace('_', ' ').title()}  ·  {now}"),
            _adf_heading("Summary", 3),
            _adf_paragraph(body.summary_of_work),
        ],
    }
    try:
        _jira_post(f"/issue/{ticket_id}/comment", {"body": comment_adf})
        _transition_issue(ticket_id, body.new_status)
        logger.info("AI updated %s → %s (%s)", ticket_id, body.new_status, body.agent)
        return {
            "status": "ok",
            "ticket_id": ticket_id,
            "new_status": body.new_status,
            "changelog_entries": 1,
        }
    except requests.HTTPError as exc:
        if exc.response is not None and exc.response.status_code == 404:
            raise HTTPException(status_code=404, detail="Ticket not found")
        raise HTTPException(status_code=502, detail=f"Jira error: {exc}")


@router.post("/gsd-sync", status_code=200)
def gsd_sync(body: GsdSyncRequest):
    """GSD phase lifecycle sync endpoint — called by gsd-jira-hook.sh automatically.

    Events:
      phase_start     → Create new ticket (or return existing), transition to in_progress
      plan_execute    → Add a comment noting plan execution is underway
      phase_complete  → Transition to done with summary comment
      phase_skip      → Transition to done with skip note
    """
    phase_label = f"Phase {body.phase_num}: {body.phase_name}"

    # ── phase_start: create or find existing ticket ──────────────────────────
    if body.event == "phase_start":
        existing_id = body.ticket_id
        if not existing_id:
            try:
                result = create_ticket(CreateTicketRequest(
                    title=phase_label,
                    description=body.goal or f"GSD phase {body.phase_num}: {body.phase_name}",
                    type="feature",
                    status="in_progress",
                    priority="medium",
                ))
                existing_id = result.body if hasattr(result, 'body') else (result or {}).get("id", "")  # type: ignore[attr-defined]
                if hasattr(result, 'id'):
                    existing_id = result.id  # type: ignore[attr-defined]
            except Exception as exc:
                logger.warning("gsd-sync phase_start create failed: %s", exc)
                return {"status": "error", "event": body.event, "error": str(exc)}

        # Create via raw Jira to get the key back reliably
        try:
            search = _jira_get("/search", {
                "jql": f'project = {_JIRA_PROJECT} AND summary ~ "{phase_label}" AND status != Done',
                "fields": "summary,status",
                "maxResults": 1,
            })
            issues = search.get("issues", [])
            if issues:
                key = issues[0]["key"]
                _transition_issue(key, "in_progress")
                return {"status": "ok", "event": body.event, "ticket_id": key, "action": "found_updated"}
        except Exception as exc:
            logger.warning("gsd-sync search failed: %s", exc)

        # Create fresh
        try:
            desc = _plain_description(body.goal or f"Automated GSD phase: {body.phase_name}")
            created = _jira_post("/issue", {"fields": {
                "project": {"key": _JIRA_PROJECT},
                "summary": phase_label,
                "issuetype": {"id": _JIRA_TASK_TYPE_ID},
                "description": desc,
                "labels": ["type:feature", "gsd"],
                "priority": {"name": "Medium"},
            }})
            key = created["key"]
            _transition_issue(key, "in_progress")
            return {"status": "ok", "event": body.event, "ticket_id": key, "action": "created"}
        except Exception as exc:
            logger.error("gsd-sync create failed: %s", exc)
            return {"status": "error", "event": body.event, "error": str(exc)}

    # ── plan_execute: comment only ────────────────────────────────────────────
    if body.event == "plan_execute":
        if not body.ticket_id:
            return {"status": "skipped", "reason": "no ticket_id provided for plan_execute"}
        try:
            comment = {
                "type": "doc", "version": 1,
                "content": [
                    _adf_heading("🔄 Plan Executing", 3),
                    _adf_paragraph(body.summary or f"Executing plans for phase {body.phase_num}..."),
                ],
            }
            _jira_post(f"/issue/{body.ticket_id}/comment", {"body": comment})
            return {"status": "ok", "event": body.event, "ticket_id": body.ticket_id}
        except Exception as exc:
            logger.warning("gsd-sync plan_execute comment failed: %s", exc)
            return {"status": "error", "event": body.event, "error": str(exc)}

    # ── phase_complete / phase_skip: close ticket ─────────────────────────────
    if body.event in ("phase_complete", "phase_skip"):
        if not body.ticket_id:
            return {"status": "skipped", "reason": "no ticket_id for close event"}
        emoji = "✅" if body.event == "phase_complete" else "⏭"
        label = "Phase Complete" if body.event == "phase_complete" else "Phase Skipped"
        try:
            now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
            comment = {
                "type": "doc", "version": 1,
                "content": [
                    _adf_heading(f"{emoji} {label} — {body.phase_name}", 2),
                    _adf_paragraph(f"Completed by GSD autonomous workflow at {now}."),
                    *([_adf_heading("Summary", 3), _adf_paragraph(body.summary)] if body.summary else []),
                ],
            }
            _jira_post(f"/issue/{body.ticket_id}/comment", {"body": comment})
            _transition_issue(body.ticket_id, "done")
            return {"status": "ok", "event": body.event, "ticket_id": body.ticket_id, "action": "closed"}
        except Exception as exc:
            logger.error("gsd-sync close failed: %s", exc)
            return {"status": "error", "event": body.event, "error": str(exc)}

    return {"status": "error", "reason": f"Unknown event: {body.event}"}


@router.post("/gsd-sync-epics", status_code=200)
def gsd_sync_epics(phases: List[Dict]):
    """Sync ROADMAP.md phases as Jira epics (called once on project init or roadmap change).

    Body: list of {phase_num, phase_name, goal, requirements} objects.
    Creates or finds an epic per phase, returns {phase_num: ticket_key} mapping.
    """
    results = {}
    for phase in phases:
        phase_num = phase.get("phase_num", "?")
        phase_name = phase.get("phase_name", "Phase")
        goal = phase.get("goal", "")
        title = f"[Epic] Phase {phase_num}: {phase_name}"
        try:
            # Find existing
            search = _jira_get("/search", {
                "jql": f'project = {_JIRA_PROJECT} AND summary ~ "{title}"',
                "fields": "summary",
                "maxResults": 1,
            })
            issues = search.get("issues", [])
            if issues:
                results[phase_num] = issues[0]["key"]
                continue
            # Create
            desc = _plain_description(goal or phase_name)
            created = _jira_post("/issue", {"fields": {
                "project": {"key": _JIRA_PROJECT},
                "summary": title,
                "issuetype": {"id": _JIRA_TASK_TYPE_ID},
                "description": desc,
                "labels": ["type:feature", "gsd", "epic"],
                "priority": {"name": "Medium"},
            }})
            results[phase_num] = created["key"]
        except Exception as exc:
            logger.warning("Failed to sync epic for phase %s: %s", phase_num, exc)
            results[phase_num] = None
    return {"epics": results, "count": len(results)}


@router.delete("/{ticket_id}")
def delete_ticket(ticket_id: str):
    """Transition issue to Done (archive in Jira)."""
    try:
        _transition_issue(ticket_id, "done")
        return {"status": "ok", "ticket_id": ticket_id, "archived": True}
    except requests.HTTPError as exc:
        if exc.response is not None and exc.response.status_code == 404:
            raise HTTPException(status_code=404, detail="Ticket not found")
        raise HTTPException(status_code=502, detail=f"Jira error: {exc}")
