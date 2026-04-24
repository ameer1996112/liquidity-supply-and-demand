from __future__ import annotations

from types import SimpleNamespace

from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from src.api_ctrader import router


class _FakeResponse:
    def __init__(self, data):
        self.data = data


class _FakeQuery:
    def __init__(self, rows: list[dict]):
        self._rows = rows
        self._filters: list[tuple[str, object]] = []
        self._updates: dict | None = None
        self._limit: int | None = None

    def select(self, *_args, **_kwargs):
        return self

    def update(self, updates: dict):
        self._updates = updates
        return self

    def eq(self, key: str, value):
        self._filters.append((key, value))
        return self

    def limit(self, value: int):
        self._limit = value
        return self

    def execute(self):
        matched = [
            row
            for row in self._rows
            if all(row.get(key) == value for key, value in self._filters)
        ]
        if self._limit is not None:
            matched = matched[: self._limit]
        if self._updates is not None:
            for row in matched:
                row.update(self._updates)
        return _FakeResponse(matched)


class _FakeSupabase:
    def __init__(self, rows: list[dict]):
        self._rows = rows

    def table(self, table_name: str):
        assert table_name == "broker_profiles"
        return _FakeQuery(self._rows)


def _make_client(monkeypatch, rows: list[dict]) -> TestClient:
    app = FastAPI()
    app.include_router(router)
    monkeypatch.setattr("src.api_ctrader._get_supabase", lambda: _FakeSupabase(rows))
    monkeypatch.setattr(
        "src.api_ctrader.get_settings",
        lambda: SimpleNamespace(admin_api_key=""),
    )
    return TestClient(app)


def test_ctrader_test_profile_marks_stale_refresh_token_as_reconnect_needed(monkeypatch) -> None:
    rows = [
        {
            "id": 12,
            "venue": "ctrader",
            "token": "stale-refresh-token",
            "connection_status": "connected",
            "connection_error": None,
            "last_tested_at": None,
        }
    ]
    client = _make_client(monkeypatch, rows)

    def _raise_access_denied(_refresh_token: str):
        raise HTTPException(
            status_code=400,
            detail="cTrader token refresh error: Access denied. Make sure the credentials are valid.",
        )

    monkeypatch.setattr("src.api_ctrader._refresh_access_token", _raise_access_denied)

    response = client.post("/api/ctrader/profiles/12/test")

    assert response.status_code == 400
    assert response.json()["detail"] == (
        "cTrader authorization expired or was revoked. Click Connect cTrader again to authorize this profile."
    )
    assert rows[0]["connection_status"] == "error"
    assert rows[0]["connection_error"] == response.json()["detail"]
