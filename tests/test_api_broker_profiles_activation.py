from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.api_broker_profiles import router


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
            row for row in self._rows
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


def _make_profile(
    profile_id: int,
    *,
    is_active: bool = True,
    selected_for_trading: bool = False,
) -> dict:
    return {
        "id": profile_id,
        "name": f"Profile {profile_id}",
        "venue": "metaapi_mt5",
        "meta_api_account_id": f"meta-account-{profile_id}",
        "token": "x" * 24,
        "api_key": None,
        "api_secret": None,
        "risk_pct": 1.0,
        "max_positions": 3,
        "run_mode": "LIVE",
        "is_active": is_active,
        "selected_for_trading": selected_for_trading,
        "connection_status": "connected",
        "connection_error": None,
        "last_tested_at": None,
        "created_at": None,
        "evaluation_mode": False,
        "evaluation_phase": None,
        "max_daily_loss_pct": None,
        "max_drawdown_pct": None,
        "profit_target": None,
        "consistency_enabled": None,
    }


def _make_client(monkeypatch, rows: list[dict]) -> TestClient:
    app = FastAPI()
    app.include_router(router)
    monkeypatch.setattr("src.api_broker_profiles._get_supabase", lambda: _FakeSupabase(rows))
    return TestClient(app)


def test_activate_broker_profile_keeps_other_selected_profiles(monkeypatch) -> None:
    rows = [
        _make_profile(1, selected_for_trading=True),
        _make_profile(2, selected_for_trading=False),
    ]
    client = _make_client(monkeypatch, rows)

    response = client.post("/api/broker-profiles/2/activate")

    assert response.status_code == 200
    payload = response.json()
    assert payload["id"] == 2
    assert payload["selected_for_trading"] is True
    assert rows[0]["selected_for_trading"] is True
    assert rows[1]["selected_for_trading"] is True


def test_deactivate_broker_profile_only_clears_target_selection(monkeypatch) -> None:
    rows = [
        _make_profile(1, selected_for_trading=True),
        _make_profile(2, selected_for_trading=True),
    ]
    client = _make_client(monkeypatch, rows)

    response = client.put("/api/broker-profiles/2", json={"is_active": False})

    assert response.status_code == 200
    payload = response.json()
    assert payload["id"] == 2
    assert payload["is_active"] is False
    assert payload["selected_for_trading"] is False
    assert rows[0]["is_active"] is True
    assert rows[0]["selected_for_trading"] is True
    assert rows[1]["is_active"] is False
    assert rows[1]["selected_for_trading"] is False
