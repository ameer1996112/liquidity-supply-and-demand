from __future__ import annotations

from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.api_rules import router


class _Query:
    def __init__(self, table: "_Table") -> None:
        self.table = table
        self.filters: dict[str, Any] = {}

    def select(self, *_args: Any, **_kwargs: Any) -> "_Query":
        return self

    def order(self, *_args: Any, **_kwargs: Any) -> "_Query":
        return self

    def limit(self, *_args: Any, **_kwargs: Any) -> "_Query":
        return self

    def in_(self, key: str, values: list[Any]) -> "_Query":
        self.filters[key] = values
        return self

    def eq(self, key: str, value: Any) -> "_Query":
        self.filters[key] = value
        return self

    def insert(self, data: dict[str, Any]) -> "_Query":
        self.table.insert_payload = dict(data)
        self.table.rows.append(dict(data))
        self.table.result_rows = [dict(data)]
        return self

    def update(self, updates: dict[str, Any]) -> "_Query":
        target_symbol = self.filters.get("symbol")
        updated: list[dict[str, Any]] = []
        for row in self.table.rows:
            if target_symbol is None or row.get("symbol") == target_symbol:
                row.update(updates)
                updated.append(dict(row))
        self.table.result_rows = updated
        return self

    def delete(self) -> "_Query":
        target_symbol = self.filters.get("symbol")
        deleted = [row for row in self.table.rows if row.get("symbol") == target_symbol]
        self.table.rows = [row for row in self.table.rows if row.get("symbol") != target_symbol]
        self.table.result_rows = deleted
        return self

    def execute(self) -> Any:
        if self.table.result_rows is not None:
            data = self.table.result_rows
            self.table.result_rows = None
            return type("Result", (), {"data": data})()

        target_symbol = self.filters.get("symbol")
        target_status = self.filters.get("status")
        if target_symbol is None:
            data = [dict(row) for row in self.table.rows]
        else:
            data = [dict(row) for row in self.table.rows if row.get("symbol") == target_symbol]
        if isinstance(target_status, list):
            data = [dict(row) for row in data if row.get("status") in target_status]
        elif target_status is not None:
            data = [dict(row) for row in data if row.get("status") == target_status]
        return type("Result", (), {"data": data})()


class _Table:
    def __init__(self, rows: list[dict[str, Any]]) -> None:
        self.rows = rows
        self.result_rows: list[dict[str, Any]] | None = None
        self.insert_payload: dict[str, Any] | None = None

    def select(self, *_args: Any, **_kwargs: Any) -> _Query:
        return _Query(self).select()

    def insert(self, data: dict[str, Any]) -> _Query:
        return _Query(self).insert(data)

    def update(self, updates: dict[str, Any]) -> _Query:
        return _Query(self).update(updates)

    def delete(self) -> _Query:
        return _Query(self).delete()


class _SupabaseStub:
    def __init__(self, rule_rows: list[dict[str, Any]], suggestion_rows: list[dict[str, Any]] | None = None) -> None:
        self.rules = _Table(rule_rows)
        self.suggestions = _Table(suggestion_rows or [])

    def table(self, name: str) -> _Table:
        if name == "symbol_risk_rules":
            return self.rules
        if name == "symbol_risk_rule_suggestions":
            return self.suggestions
        raise AssertionError(f"Unexpected table: {name}")


@pytest.fixture()
def rules_client(monkeypatch: pytest.MonkeyPatch) -> tuple[TestClient, _SupabaseStub]:
    app = FastAPI()
    app.include_router(router)
    stub = _SupabaseStub([])
    monkeypatch.setattr("src.api_rules._get_supabase", lambda: stub)
    monkeypatch.setattr("src.services.redis_cache.invalidate_symbol_rules_cache", lambda: None, raising=False)
    return TestClient(app), stub


def test_list_symbol_rules_applies_backend_defaults(rules_client: tuple[TestClient, _SupabaseStub]) -> None:
    client, stub = rules_client
    stub.rules.rows = [
        {
            "symbol": "EURUSD",
            "max_lot_size": 2.0,
            "risk_percent": 0.5,
            "pip_size": 0.0001,
            "pip_value_per_lot": 10.0,
            "max_positions": 3,
            "enabled": True,
            "min_lot_size": None,
            "lot_step": None,
            "stop_loss_buffer_pips": None,
        }
    ]

    response = client.get("/api/rules/symbols")

    assert response.status_code == 200
    rule = response.json()["rules"][0]["active_rule"]
    assert rule["min_lot_size"] == 0.01
    assert rule["lot_step"] == 0.01
    assert rule["stop_loss_buffer_pips"] == 1.0


def test_existing_rows_without_new_columns_use_defaults(rules_client: tuple[TestClient, _SupabaseStub]) -> None:
    client, stub = rules_client
    stub.rules.rows = [
        {
            "symbol": "GBPUSD",
            "max_lot_size": 1.0,
            "risk_percent": 0.5,
            "pip_size": 0.0001,
            "pip_value_per_lot": 10.0,
            "max_positions": 2,
            "enabled": True,
        }
    ]

    response = client.get("/api/rules/symbols")

    assert response.status_code == 200
    rule = response.json()["rules"][0]["active_rule"]
    assert rule["min_lot_size"] == 0.01
    assert rule["lot_step"] == 0.01
    assert rule["stop_loss_buffer_pips"] == 1.0


def test_create_symbol_rule_rejects_min_lot_above_max(rules_client: tuple[TestClient, _SupabaseStub]) -> None:
    client, _stub = rules_client

    response = client.post(
        "/api/rules/symbols",
        json={
            "symbol": "XAUUSD",
            "max_lot_size": 0.1,
            "min_lot_size": 0.2,
            "lot_step": 0.01,
            "risk_percent": 0.5,
            "pip_size": 0.01,
            "pip_value_per_lot": 100.0,
            "stop_loss_buffer_pips": 1.0,
            "max_positions": 1,
            "enabled": True,
        },
    )

    assert response.status_code == 422


def test_create_symbol_rule_normalizes_symbol(rules_client: tuple[TestClient, _SupabaseStub]) -> None:
    client, stub = rules_client

    response = client.post(
        "/api/rules/symbols",
        json={
            "symbol": "eurusd",
            "max_lot_size": 1.5,
            "min_lot_size": 0.01,
            "lot_step": 0.01,
            "risk_percent": 0.5,
            "pip_size": 0.0001,
            "pip_value_per_lot": 10.0,
            "stop_loss_buffer_pips": 1.0,
            "max_positions": 2,
            "enabled": True,
        },
    )

    assert response.status_code == 201
    assert response.json()["rule"]["symbol"] == "EURUSD"
    assert stub.rules.insert_payload is not None
    assert stub.rules.insert_payload["symbol"] == "EURUSD"


def test_list_symbol_rules_returns_active_rule_with_latest_suggestion(
    rules_client: tuple[TestClient, _SupabaseStub]
) -> None:
    client, stub = rules_client
    stub.rules.rows = [
        {
            "symbol": "EURUSD",
            "max_lot_size": 2.0,
            "risk_percent": 0.5,
            "pip_size": 0.0001,
            "pip_value_per_lot": 10.0,
            "min_lot_size": 0.01,
            "lot_step": 0.01,
            "stop_loss_buffer_pips": 1.0,
            "max_positions": 3,
            "enabled": True,
        }
    ]
    stub.suggestions.rows = [
        {
            "id": 1,
            "symbol": "EURUSD",
            "suggested_risk_percent": 0.4,
            "suggested_max_lot_size": 1.5,
            "suggested_pip_size": 0.0001,
            "suggested_pip_value_per_lot": 10.0,
            "status": "pending",
        }
    ]

    response = client.get("/api/rules/symbols")

    assert response.status_code == 200
    row = response.json()["rules"][0]
    assert row["active_rule"]["risk_percent"] == 0.5
    assert row["latest_suggestion"]["suggested_risk_percent"] == 0.4
    assert row["suggestion_status"] == "pending"
    assert row["has_pending_changes"] is True


def test_approve_suggestion_updates_only_optimizer_owned_fields(
    rules_client: tuple[TestClient, _SupabaseStub]
) -> None:
    client, stub = rules_client
    stub.rules.rows = [
        {
            "symbol": "XAUUSD",
            "risk_percent": 0.5,
            "max_lot_size": 1.0,
            "pip_size": 0.01,
            "pip_value_per_lot": 100.0,
            "min_lot_size": 0.01,
            "lot_step": 0.01,
            "stop_loss_buffer_pips": 2.0,
            "max_positions": 1,
            "enabled": True,
        }
    ]
    stub.suggestions.rows = [
        {
            "id": 7,
            "symbol": "XAUUSD",
            "suggested_risk_percent": 0.3,
            "suggested_max_lot_size": 0.5,
            "suggested_pip_size": 0.01,
            "suggested_pip_value_per_lot": 90.0,
            "status": "pending",
        }
    ]

    response = client.post("/api/rules/symbols/XAUUSD/approve-suggestion")

    assert response.status_code == 200
    active = response.json()["rule"]
    assert active["risk_percent"] == 0.3
    assert active["max_lot_size"] == 0.5
    assert active["pip_value_per_lot"] == 90.0
    assert active["min_lot_size"] == 0.01
    assert active["lot_step"] == 0.01
    assert active["stop_loss_buffer_pips"] == 2.0


def test_reject_suggestion_marks_pending_row_rejected(
    rules_client: tuple[TestClient, _SupabaseStub]
) -> None:
    client, stub = rules_client
    stub.suggestions.rows = [
        {
            "id": 9,
            "symbol": "GBPUSD",
            "suggested_risk_percent": 0.2,
            "suggested_max_lot_size": 1.0,
            "suggested_pip_size": 0.0001,
            "suggested_pip_value_per_lot": 10.0,
            "status": "pending",
        }
    ]

    response = client.post("/api/rules/symbols/GBPUSD/reject-suggestion")

    assert response.status_code == 200
    assert stub.suggestions.rows[0]["status"] == "rejected"
