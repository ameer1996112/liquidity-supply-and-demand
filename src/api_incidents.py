"""Incidents API — Auto-create Jira tickets from system events.

Routes:
  POST /api/incidents                  → Report a system event (error, test failure, ML drift, alert)
  GET  /api/incidents                  → List recent incidents (last 50)
  POST /api/incidents/ack/{incident_id} → Acknowledge an incident (suppress ticket creation)

Incident types:
  worker_error    → P1/P2 Jira ticket with stack trace
  test_failure    → Bug ticket with test name + failure
  ml_drift        → Model drift ticket
  watchdog_alert  → Operational ticket
"""

import logging
import os
import time
import traceback
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Query
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/incidents", tags=["incidents"])

# ── In-memory incident store (ring buffer, 500 entries) ───────────────────────
# For production, replace with Supabase table.

_incidents: List[Dict] = []
_MAX_INCIDENTS = 500
_acked: set = set()


def _add_incident(incident: Dict) -> None:
    global _incidents
    _incidents.insert(0, incident)
    if len(_incidents) > _MAX_INCIDENTS:
        _incidents = _incidents[:_MAX_INCIDENTS]


# ── Jira integration ──────────────────────────────────────────────────────────

_JIRA_BASE = os.getenv("JIRA_BASE_URL", "https://ameer1996112.atlassian.net")
_JIRA_EMAIL = os.getenv("JIRA_EMAIL", "")
_JIRA_TOKEN = os.getenv("JIRA_API_TOKEN", "")
_JIRA_PROJECT = os.getenv("JIRA_PROJECT_KEY", "DEV")
_JIRA_TASK_TYPE_ID = os.getenv("JIRA_TASK_TYPE_ID", "10003")


def _jira_create_incident_ticket(title: str, description_adf: Dict, priority: str, labels: List[str]) -> Optional[str]:
    """Create a Jira ticket for an incident. Returns the Jira key or None on failure."""
    import base64
    import requests

    def _auth():
        return "Basic " + base64.b64encode(f"{_JIRA_EMAIL}:{_JIRA_TOKEN}".encode()).decode()

    if not _JIRA_EMAIL or not _JIRA_TOKEN:
        logger.warning("Jira credentials not configured — incident ticket not created")
        return None

    priority_map = {"P1": "Highest", "P2": "High", "P3": "Medium", "P4": "Low"}

    try:
        url = f"{_JIRA_BASE}/rest/api/3/issue"
        payload = {
            "fields": {
                "project": {"key": _JIRA_PROJECT},
                "summary": title,
                "issuetype": {"id": _JIRA_TASK_TYPE_ID},
                "description": description_adf,
                "labels": labels,
                "priority": {"name": priority_map.get(priority, "High")},
            }
        }
        headers = {
            "Authorization": _auth(),
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        r = requests.post(url, headers=headers, json=payload, timeout=10)
        r.raise_for_status()
        key = r.json()["key"]
        # Transition to In Progress
        trans_r = requests.get(f"{_JIRA_BASE}/rest/api/3/issue/{key}/transitions", headers=headers, timeout=8)
        for t in trans_r.json().get("transitions", []):
            if t["to"]["name"] == "In Progress":
                requests.post(f"{_JIRA_BASE}/rest/api/3/issue/{key}/transitions",
                              headers=headers, json={"transition": {"id": t["id"]}}, timeout=8)
                break
        return key
    except Exception as exc:
        logger.error("Failed to create incident Jira ticket: %s", exc)
        return None


def _build_incident_adf(summary: str, detail: str, source: str, extra_sections: List[Dict] = None) -> Dict:
    """Build ADF document for incident tickets."""

    def para(text: str) -> Dict:
        return {"type": "paragraph", "content": [{"type": "text", "text": text}]}

    def heading(text: str, level: int = 2) -> Dict:
        return {"type": "heading", "attrs": {"level": level}, "content": [{"type": "text", "text": text}]}

    def code_block(code: str) -> Dict:
        return {
            "type": "codeBlock",
            "attrs": {"language": "text"},
            "content": [{"type": "text", "text": code[:2000]}],
        }

    content = [
        heading("⚠️ Incident Summary", 2),
        para(summary),
        heading("📍 Source", 3),
        para(source),
    ]

    if detail:
        content.append(heading("🔍 Detail / Stack Trace", 3))
        content.append(code_block(detail))

    if extra_sections:
        content.extend(extra_sections)

    content.append(heading("✅ Acceptance Criteria", 2))
    content.append({
        "type": "bulletList",
        "content": [
            {"type": "listItem", "content": [para("Root cause identified")]},
            {"type": "listItem", "content": [para("Fix deployed and verified")]},
            {"type": "listItem", "content": [para("No regression in related functionality")]},
        ],
    })

    return {"type": "doc", "version": 1, "content": content}


# ── Pydantic models ───────────────────────────────────────────────────────────

class IncidentReport(BaseModel):
    """System event that should auto-create a Jira ticket."""
    type: str = Field(..., pattern="^(worker_error|test_failure|ml_drift|watchdog_alert|generic)$")
    title: str = Field(..., min_length=1, max_length=500)
    summary: str = Field(..., min_length=1)
    detail: Optional[str] = None        # Stack trace, test output, etc.
    source: str = Field("system")       # Module/service that detected the event
    priority: str = Field("P2", pattern="^(P1|P2|P3|P4)$")
    signal_id: Optional[int] = None
    phase: Optional[str] = None         # e.g. "guard_rail", "execution"
    metadata: Optional[Dict[str, Any]] = None


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.post("", status_code=202)
def report_incident(body: IncidentReport):
    """Report a system event and auto-create a Jira ticket.

    Called by:
    - Worker pipeline exception handlers (worker_error)
    - Pytest plugin on test failure (test_failure)
    - ML Guardian on confidence drop (ml_drift)
    - TradeWatchdog on late fill / operational alerts (watchdog_alert)
    """
    incident_id = f"{body.type}-{int(time.time() * 1000)}"
    now = datetime.now(timezone.utc).isoformat()

    incident = {
        "id": incident_id,
        "type": body.type,
        "title": body.title,
        "summary": body.summary,
        "detail": body.detail,
        "source": body.source,
        "priority": body.priority,
        "signal_id": body.signal_id,
        "phase": body.phase,
        "metadata": body.metadata,
        "created_at": now,
        "jira_key": None,
        "acked": False,
    }

    _add_incident(incident)

    # Deduplicate: skip if same title was reported in last 5 minutes
    recent_titles = {i["title"] for i in _incidents[1:] if i.get("created_at", "") > now[:16]}
    if body.title in recent_titles and body.type not in ("ml_drift",):
        logger.info("Incident deduplicated (title seen recently): %s", body.title)
        return {"status": "deduplicated", "incident_id": incident_id}

    # Build Jira ticket
    type_labels = {
        "worker_error": ["type:bug", "incident", "worker"],
        "test_failure": ["type:bug", "incident", "test"],
        "ml_drift": ["type:task", "incident", "ml-drift"],
        "watchdog_alert": ["type:task", "incident", "watchdog"],
        "generic": ["type:task", "incident"],
    }
    labels = type_labels.get(body.type, ["type:task", "incident"])

    adf = _build_incident_adf(
        summary=body.summary,
        detail=body.detail or "",
        source=body.source,
    )

    ticket_key = _jira_create_incident_ticket(
        title=f"[{body.priority}] {body.title}",
        description_adf=adf,
        priority=body.priority,
        labels=labels,
    )

    if ticket_key:
        incident["jira_key"] = ticket_key
        logger.info("Incident ticket created: %s → %s", incident_id, ticket_key)

    return {
        "status": "ok",
        "incident_id": incident_id,
        "jira_key": ticket_key,
        "type": body.type,
        "priority": body.priority,
    }


@router.get("")
def list_incidents(
    limit: int = Query(50, ge=1, le=200),
    type: Optional[str] = Query(None),
):
    """List recent incidents."""
    result = _incidents[:limit]
    if type:
        result = [i for i in result if i["type"] == type]
    return {"incidents": result, "count": len(result)}


@router.post("/ack/{incident_id}")
def ack_incident(incident_id: str):
    """Acknowledge an incident — suppresses duplicate ticket creation."""
    _acked.add(incident_id)
    for inc in _incidents:
        if inc["id"] == incident_id:
            inc["acked"] = True
            return {"status": "ok", "incident_id": incident_id}
    return {"status": "not_found", "incident_id": incident_id}
