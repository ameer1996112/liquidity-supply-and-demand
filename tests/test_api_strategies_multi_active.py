from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.api_strategies import router


class _FakeResponse:
    def __init__(self, data):
        self.data = data


class _FakeQuery:
    def __init__(self, rows: list[dict]):
        self._rows = rows
        self._filters: list[tuple[str, object]] = []
        self._updates: dict | None = None

    def update(self, updates: dict):
        self._updates = updates
        return self

    def eq(self, key: str, value):
        self._filters.append((key, value))
        return self

    def execute(self):
        matched = [
            row for row in self._rows
            if all(row.get(key) == value for key, value in self._filters)
        ]
        if self._updates is not None:
            for row in matched:
                row.update(self._updates)
        return _FakeResponse(matched)


class _FakeSupabase:
    def __init__(self, rows: list[dict]):
        self.rows = rows

    def table(self, table_name: str):
        assert table_name == "strategy_configs"
        return _FakeQuery(self.rows)


def test_activate_strategy_keeps_other_active_rows(monkeypatch):
    rows = [
        {"id": 1, "slug": "liq_sd_v1", "is_active": True},
        {"id": 2, "slug": "breakout_v1", "is_active": False},
    ]
    fake_supabase = _FakeSupabase(rows)
    monkeypatch.setattr("src.api_strategies._get_supabase", lambda: fake_supabase)

    app = FastAPI()
    app.include_router(router)
    client = TestClient(app)

    response = client.patch("/api/strategies/2/activate?active=true")

    assert response.status_code == 200
    assert rows[0]["is_active"] is True
    assert rows[1]["is_active"] is True
