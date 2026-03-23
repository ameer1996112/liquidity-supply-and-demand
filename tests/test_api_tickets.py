"""Tests for the /api/tickets endpoints.

Pattern follows test_ai_mode_api.py / test_backtests.py:
- Mock Supabase client via monkeypatch
- Use FastAPI TestClient
- No real network calls
"""
import json
import uuid
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch
import pytest
from fastapi.testclient import TestClient


# ── App setup ────────────────────────────────────────────────────────────────

@pytest.fixture
def client():
    """TestClient with Supabase mocked at the supabase_api layer."""
    from src.api import app
    return TestClient(app, raise_server_exceptions=True)


@pytest.fixture
def mock_sb(monkeypatch):
    """Return a MagicMock Supabase client injected into api_tickets."""
    mock = MagicMock()
    monkeypatch.setattr(
        "src.api_tickets.get_api_supabase",
        lambda: mock,
    )
    return mock


def _make_ticket(**overrides):
    """Return a minimal valid ticket dict (as Supabase would return it)."""
    base = {
        "id": str(uuid.uuid4()),
        "title": "Test ticket",
        "description": None,
        "type": "bug",
        "status": "todo",
        "priority": "medium",
        "assignee": None,
        "signal_id": None,
        "ai_changelog": [],
        "created_at": datetime.now(timezone.utc).isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    base.update(overrides)
    return base


# ── GET /api/tickets ─────────────────────────────────────────────────────────

def test_list_tickets_empty(client, mock_sb):
    mock_sb.table.return_value.select.return_value.neq.return_value \
        .order.return_value.limit.return_value.execute.return_value \
        = MagicMock(data=[])

    resp = client.get("/api/tickets")
    assert resp.status_code == 200
    data = resp.json()
    assert data["tickets"] == []
    assert data["count"] == 0


def test_list_tickets_returns_results(client, mock_sb):
    ticket = _make_ticket(title="NAS100 departure bug")
    mock_sb.table.return_value.select.return_value.neq.return_value \
        .order.return_value.limit.return_value.execute.return_value \
        = MagicMock(data=[ticket])

    resp = client.get("/api/tickets")
    assert resp.status_code == 200
    data = resp.json()
    assert data["count"] == 1
    assert data["tickets"][0]["title"] == "NAS100 departure bug"


# ── POST /api/tickets ─────────────────────────────────────────────────────────

def test_create_ticket(client, mock_sb):
    new_ticket = _make_ticket(title="Fix SL bug", type="bug", priority="high")
    mock_sb.table.return_value.insert.return_value.execute.return_value \
        = MagicMock(data=[new_ticket])

    resp = client.post("/api/tickets", json={
        "title": "Fix SL bug",
        "type": "bug",
        "priority": "high",
    })
    assert resp.status_code == 201
    data = resp.json()
    assert data["title"] == "Fix SL bug"
    assert data["type"] == "bug"
    assert data["status"] == "todo"


def test_create_ticket_invalid_type(client, mock_sb):
    resp = client.post("/api/tickets", json={
        "title": "Bad type",
        "type": "epic",  # not allowed
    })
    assert resp.status_code == 422


def test_create_ticket_missing_title(client, mock_sb):
    resp = client.post("/api/tickets", json={"type": "task"})
    assert resp.status_code == 422


# ── GET /api/tickets/{id} ─────────────────────────────────────────────────────

def test_get_ticket(client, mock_sb):
    ticket = _make_ticket(title="Specific ticket")
    ticket_id = ticket["id"]
    mock_sb.table.return_value.select.return_value.eq.return_value \
        .maybe_single.return_value.execute.return_value \
        = MagicMock(data=ticket)

    resp = client.get(f"/api/tickets/{ticket_id}")
    assert resp.status_code == 200
    assert resp.json()["title"] == "Specific ticket"


def test_get_ticket_not_found(client, mock_sb):
    mock_sb.table.return_value.select.return_value.eq.return_value \
        .maybe_single.return_value.execute.return_value \
        = MagicMock(data=None)

    resp = client.get(f"/api/tickets/{uuid.uuid4()}")
    assert resp.status_code == 404


# ── PATCH /api/tickets/{id} ───────────────────────────────────────────────────

def test_patch_ticket_status(client, mock_sb):
    updated = _make_ticket(status="in_progress")
    mock_sb.table.return_value.update.return_value.eq.return_value \
        .execute.return_value = MagicMock(data=[updated])

    resp = client.patch(f"/api/tickets/{updated['id']}", json={"status": "in_progress"})
    assert resp.status_code == 200
    assert resp.json()["status"] == "in_progress"


def test_patch_ticket_invalid_status(client, mock_sb):
    resp = client.patch(f"/api/tickets/{uuid.uuid4()}", json={"status": "wontfix"})
    assert resp.status_code == 422


def test_patch_ticket_no_fields(client, mock_sb):
    resp = client.patch(f"/api/tickets/{uuid.uuid4()}", json={})
    assert resp.status_code == 400


# ── POST /api/tickets/{id}/ai-update ─────────────────────────────────────────

def test_ai_update_appends_changelog(client, mock_sb):
    ticket_id = str(uuid.uuid4())
    existing = {"status": "todo", "ai_changelog": []}
    updated = _make_ticket(id=ticket_id, status="in_progress", ai_changelog=[{
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "agent": "antigravity",
        "old_status": "todo",
        "new_status": "in_progress",
        "summary": "Started fixing departure calc",
    }])

    # First call: fetch current (select)
    mock_sb.table.return_value.select.return_value.eq.return_value \
        .maybe_single.return_value.execute.return_value = MagicMock(data=existing)
    # Second call: write update
    mock_sb.table.return_value.update.return_value.eq.return_value \
        .execute.return_value = MagicMock(data=[updated])

    resp = client.post(f"/api/tickets/{ticket_id}/ai-update", json={
        "new_status": "in_progress",
        "summary_of_work": "Started fixing departure calc",
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert data["new_status"] == "in_progress"
    assert data["old_status"] == "todo"
    assert data["changelog_entries"] == 1


def test_ai_update_invalid_status(client, mock_sb):
    resp = client.post(f"/api/tickets/{uuid.uuid4()}/ai-update", json={
        "new_status": "archived",  # not allowed in ai-update
        "summary_of_work": "some work",
    })
    assert resp.status_code == 422


def test_ai_update_ticket_not_found(client, mock_sb):
    mock_sb.table.return_value.select.return_value.eq.return_value \
        .maybe_single.return_value.execute.return_value = MagicMock(data=None)

    resp = client.post(f"/api/tickets/{uuid.uuid4()}/ai-update", json={
        "new_status": "done",
        "summary_of_work": "Completed task",
    })
    assert resp.status_code == 404


# ── DELETE /api/tickets/{id} ──────────────────────────────────────────────────

def test_delete_ticket_archives(client, mock_sb):
    ticket_id = str(uuid.uuid4())
    archived = _make_ticket(id=ticket_id, status="archived")
    mock_sb.table.return_value.update.return_value.eq.return_value \
        .execute.return_value = MagicMock(data=[archived])

    resp = client.delete(f"/api/tickets/{ticket_id}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["archived"] is True
    assert data["ticket_id"] == ticket_id


def test_delete_ticket_not_found(client, mock_sb):
    mock_sb.table.return_value.update.return_value.eq.return_value \
        .execute.return_value = MagicMock(data=[])

    resp = client.delete(f"/api/tickets/{uuid.uuid4()}")
    assert resp.status_code == 404
