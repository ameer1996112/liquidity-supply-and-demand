"""Tests for the /api/tickets endpoints — Jira proxy version.

Mocks the `requests` HTTP library so no real Jira API calls are made.
"""
import json
import uuid
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch
import pytest
from fastapi.testclient import TestClient


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture
def client():
    import os
    os.environ.setdefault("JIRA_BASE_URL", "https://test.atlassian.net")
    os.environ.setdefault("JIRA_EMAIL", "test@example.com")
    os.environ.setdefault("JIRA_API_TOKEN", "fake-token")
    os.environ.setdefault("JIRA_PROJECT_KEY", "DEV")
    os.environ.setdefault("JIRA_TASK_TYPE_ID", "10003")
    from src.api import app
    return TestClient(app, raise_server_exceptions=True)


def _jira_issue(key="DEV-1", summary="Test ticket", status="To Do", labels=None):
    """Return a minimal Jira issue dict."""
    return {
        "key": key,
        "fields": {
            "summary": summary,
            "status": {"name": status},
            "priority": {"name": "Medium"},
            "labels": labels or ["type:task"],
            "assignee": None,
            "created": datetime.now(timezone.utc).isoformat(),
            "updated": datetime.now(timezone.utc).isoformat(),
            "description": None,
            "issuetype": {"name": "Task"},
        },
    }


# ── GET /api/tickets ──────────────────────────────────────────────────────────

def test_list_tickets_empty(client):
    with patch("src.api_tickets.requests.get") as mock:
        mock.return_value.status_code = 200
        mock.return_value.json.return_value = {"issues": [], "total": 0}
        mock.return_value.raise_for_status = lambda: None
        resp = client.get("/api/tickets")
    assert resp.status_code == 200
    assert resp.json()["tickets"] == []


def test_list_tickets_returns_results(client):
    issue = _jira_issue(key="DEV-2", summary="NAS100 departure bug")
    with patch("src.api_tickets.requests.get") as mock:
        mock.return_value.status_code = 200
        mock.return_value.json.return_value = {"issues": [issue]}
        mock.return_value.raise_for_status = lambda: None
        resp = client.get("/api/tickets")
    assert resp.status_code == 200
    data = resp.json()
    assert data["count"] == 1
    assert data["tickets"][0]["title"] == "NAS100 departure bug"
    assert data["tickets"][0]["id"] == "DEV-2"


# ── POST /api/tickets ─────────────────────────────────────────────────────────

def test_create_ticket(client):
    issue = _jira_issue(key="DEV-3", summary="Fix SL bug", labels=["type:bug"])

    def _mock_get(url, **kwargs):
        m = MagicMock()
        m.raise_for_status = lambda: None
        # Dedup search returns empty; full fetch returns the created issue
        if "/search" in url:
            m.json.return_value = {"issues": []}
        else:
            m.json.return_value = issue
        return m

    def _mock_post(url, **kwargs):
        m = MagicMock()
        m.raise_for_status = lambda: None
        m.json.return_value = {"key": "DEV-3", "self": "https://test.atlassian.net/..."}
        return m

    with patch("src.api_tickets.requests.get", side_effect=_mock_get), \
         patch("src.api_tickets.requests.post", side_effect=_mock_post):
        resp = client.post("/api/tickets", json={"title": "Fix SL bug", "type": "bug"})

    assert resp.status_code == 201
    assert resp.json()["id"] == "DEV-3"


def test_create_ticket_invalid_type(client):
    resp = client.post("/api/tickets", json={"title": "Bad type", "type": "epic"})
    assert resp.status_code == 422


def test_create_ticket_missing_title(client):
    resp = client.post("/api/tickets", json={"type": "task"})
    assert resp.status_code == 422


def test_create_ticket_idempotent(client):
    """Same title → returns existing issue (200) without creating a duplicate."""
    issue = _jira_issue(key="DEV-4", summary="Fix signal dashboard display bug")

    with patch("src.api_tickets.requests.get") as mock:
        mock.return_value.raise_for_status = lambda: None
        mock.return_value.json.return_value = {"issues": [issue]}
        resp = client.post("/api/tickets", json={"title": "Fix signal dashboard display bug"})

    assert resp.status_code == 200
    assert resp.json()["id"] == "DEV-4"


# ── GET /api/tickets/{id} ─────────────────────────────────────────────────────

def test_get_ticket(client):
    issue = _jira_issue(key="DEV-5", summary="Specific ticket")
    with patch("src.api_tickets.requests.get") as mock:
        mock.return_value.raise_for_status = lambda: None
        mock.return_value.json.return_value = issue
        resp = client.get("/api/tickets/DEV-5")
    assert resp.status_code == 200
    assert resp.json()["title"] == "Specific ticket"


def test_get_ticket_not_found(client):
    import requests as req
    err = req.HTTPError(response=MagicMock(status_code=404))
    with patch("src.api_tickets.requests.get") as mock:
        mock.return_value.raise_for_status.side_effect = err
        resp = client.get("/api/tickets/DEV-999")
    assert resp.status_code == 404


# ── PATCH /api/tickets/{id} ───────────────────────────────────────────────────

def test_patch_ticket_status(client):
    issue = _jira_issue(key="DEV-1", status="In Progress")

    def _mock_get(url, **kwargs):
        m = MagicMock()
        m.raise_for_status = lambda: None
        if "/transitions" in url:
            m.json.return_value = {"transitions": [
                {"id": "21", "to": {"name": "In Progress"}}
            ]}
        else:
            m.json.return_value = issue
        return m

    with patch("src.api_tickets.requests.get", side_effect=_mock_get), \
         patch("src.api_tickets.requests.put") as mock_put, \
         patch("src.api_tickets.requests.post") as mock_post:
        mock_put.return_value.raise_for_status = lambda: None
        mock_post.return_value.raise_for_status = lambda: None
        mock_post.return_value.json.return_value = {}
        resp = client.patch("/api/tickets/DEV-1", json={"status": "in_progress"})

    assert resp.status_code == 200
    assert resp.json()["status"] == "in_progress"


def test_patch_ticket_invalid_status(client):
    resp = client.patch("/api/tickets/DEV-1", json={"status": "wontfix"})
    assert resp.status_code == 422


def test_patch_ticket_no_fields(client):
    resp = client.patch("/api/tickets/DEV-1", json={})
    assert resp.status_code == 400


# ── POST /api/tickets/{id}/ai-update ─────────────────────────────────────────

def test_ai_update_appends_changelog(client):
    issue = _jira_issue(key="DEV-1", status="In Progress")

    def _mock_get(url, **kwargs):
        m = MagicMock()
        m.raise_for_status = lambda: None
        if "/transitions" in url:
            m.json.return_value = {"transitions": [
                {"id": "21", "to": {"name": "In Progress"}}
            ]}
        else:
            m.json.return_value = issue
        return m

    with patch("src.api_tickets.requests.get", side_effect=_mock_get), \
         patch("src.api_tickets.requests.post") as mock_post:
        mock_post.return_value.raise_for_status = lambda: None
        mock_post.return_value.json.return_value = {}
        resp = client.post("/api/tickets/DEV-1/ai-update", json={
            "new_status": "in_progress",
            "summary_of_work": "Started fixing departure calc",
        })

    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert data["new_status"] == "in_progress"


def test_ai_update_invalid_status(client):
    resp = client.post("/api/tickets/DEV-1/ai-update", json={
        "new_status": "archived",
        "summary_of_work": "some work",
    })
    assert resp.status_code == 422


# ── DELETE /api/tickets/{id} ──────────────────────────────────────────────────

def test_delete_ticket_archives(client):
    def _mock_get(url, **kwargs):
        m = MagicMock()
        m.raise_for_status = lambda: None
        m.json.return_value = {"transitions": [
            {"id": "31", "to": {"name": "Done"}}
        ]}
        return m

    with patch("src.api_tickets.requests.get", side_effect=_mock_get), \
         patch("src.api_tickets.requests.post") as mock_post:
        mock_post.return_value.raise_for_status = lambda: None
        mock_post.return_value.json.return_value = {}
        resp = client.delete("/api/tickets/DEV-1")

    assert resp.status_code == 200
    assert resp.json()["archived"] is True
