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
        if target_symbol is None:
            data = [dict(row) for row in self.table.rows]
        else:
            data = [dict(row) for row in self.table.rows if row.get("symbol") == target_symbol]
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
    def __init__(self, rows: list[dict[str, Any]]) -> None:
        self.rules = _Table(rows)

    def table(self, name: str) -> _Table:
        if name != "symbol_risk_rules":
            raise AssertionError(f"Unexpected table: {name}")
        return self.rules


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
    rule = response.json()["rules"][0]
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
    rule = response.json()["rules"][0]
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
