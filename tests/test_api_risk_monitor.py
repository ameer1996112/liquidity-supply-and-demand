from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.api_risk_monitor import router


class _FakeResponse:
    def __init__(self, data):
        self.data = data


class _FakeQuery:
    def __init__(self, table_name: str, rows_by_table: dict[str, list[dict]]):
        self.table_name = table_name
        self.rows = list(rows_by_table.get(table_name, []))

    def select(self, *_args, **_kwargs):
        return self

    def eq(self, key, value):
        self.rows = [row for row in self.rows if row.get(key) == value]
        return self

    def gte(self, *_args, **_kwargs):
        return self

    def in_(self, key, values):
        self.rows = [row for row in self.rows if row.get(key) in values]
        return self

    def order(self, *_args, **_kwargs):
        return self

    def limit(self, n):
        self.rows = self.rows[:n]
        return self

    def execute(self):
        return _FakeResponse(self.rows)


class _FakeSupabase:
    def __init__(self, rows_by_table: dict[str, list[dict]]):
        self.rows_by_table = rows_by_table

    def table(self, table_name: str):
        return _FakeQuery(table_name, self.rows_by_table)


def _fake_settings():
    return SimpleNamespace(
        account_balance=50000.0,
        risk_percent=0.5,
        min_rr_ratio=0.0,
        pine_block_dead_zone=False,
        pine_min_return_strength=0.0,
        run_mode="LIVE",
        trinity_max_positions=3,
        trinity_max_drawdown_pct=8.0,
        trading_kill_switch=False,
        pine_trading_start_hour_local=6,
        pine_trading_end_hour_local=22,
    )


def _fake_supabase_two_accounts():
    return _FakeSupabase(
        {
            "account_strategies": [
                {"account_name": "Eval A", "broker_profile_id": 1},
                {"account_name": "Eval B", "broker_profile_id": 2},
            ],
            "broker_profiles": [
                {
                    "id": 1,
                    "name": "Eval A",
                    "selected_for_trading": True,
                    "is_active": True,
                    "starting_balance": 50000,
                    "evaluation_mode": True,
                    "evaluation_phase": "phase1",
                    "prop_firm_name": "FTMO",
                    "run_mode": "LIVE",
                    "connection_status": "connected",
                },
                {
                    "id": 2,
                    "name": "Eval B",
                    "selected_for_trading": True,
                    "is_active": True,
                    "starting_balance": 100000,
                    "evaluation_mode": True,
                    "evaluation_phase": "phase2",
                    "prop_firm_name": "FundedNext",
                    "run_mode": "LIVE",
                    "connection_status": "connected",
                },
            ],
            "trading_signals": [
                {"broker_profile_id": 1, "account_name": "Eval A", "status": "closed", "pnl_usd": -200},
                {"broker_profile_id": 1, "account_name": "Eval A", "status": "active"},
                {"broker_profile_id": 2, "account_name": "Eval B", "status": "closed", "pnl_usd": 300},
                {"broker_profile_id": 2, "account_name": "Eval B", "status": "executed"},
            ],
            "account_status_snapshots": [
                {"account_name": "Eval A", "balance": 50000},
                {"account_name": "Eval B", "balance": 100000},
            ],
            "symbol_risk_rules": [],
            "system_config": [],
        }
    )


def _fake_supabase_drawdown_split():
    return _FakeSupabase(
        {
            "account_strategies": [
                {"account_name": "Eval A", "broker_profile_id": 1},
                {"account_name": "Eval B", "broker_profile_id": 2},
            ],
            "broker_profiles": [
                {
                    "id": 1,
                    "name": "Eval A",
                    "selected_for_trading": True,
                    "is_active": True,
                    "starting_balance": 50000,
                    "evaluation_mode": True,
                    "evaluation_phase": "phase1",
                    "prop_firm_name": "FTMO",
                    "run_mode": "LIVE",
                    "connection_status": "connected",
                },
                {
                    "id": 2,
                    "name": "Eval B",
                    "selected_for_trading": True,
                    "is_active": True,
                    "starting_balance": 100000,
                    "evaluation_mode": True,
                    "evaluation_phase": "phase2",
                    "prop_firm_name": "FundedNext",
                    "run_mode": "LIVE",
                    "connection_status": "connected",
                },
            ],
            "trading_signals": [
                {"broker_profile_id": 1, "account_name": "Eval A", "status": "closed", "pnl_usd": -1000},
                {"broker_profile_id": 2, "account_name": "Eval B", "status": "closed", "pnl_usd": -500},
            ],
            "account_status_snapshots": [
                {"account_name": "Eval A", "balance": 50000},
                {"account_name": "Eval B", "balance": 100000},
            ],
            "symbol_risk_rules": [],
            "system_config": [],
        }
    )


def test_risk_monitor_returns_summary_and_account_cards(monkeypatch) -> None:
    app = FastAPI()
    app.include_router(router)
    client = TestClient(app)

    monkeypatch.setattr("src.api_risk_monitor.get_supabase", lambda: _fake_supabase_two_accounts())
    monkeypatch.setattr("src.api_risk_monitor.get_settings", _fake_settings)
    monkeypatch.setattr("src.api_risk_monitor.get_redis", lambda: SimpleNamespace(get=lambda *_args, **_kwargs: "0"))
    monkeypatch.setattr("src.api_risk_monitor.is_metaapi_circuit_open", lambda **_kwargs: False)
    monkeypatch.setattr(
        "src.api_risk_monitor.check_safety",
        lambda current_equity, starting_balance, daily_pnl, account_name=None: (True, 1.0, f"{account_name or 'acct'} ok"),
    )

    response = client.get("/api/risk/monitor")

    assert response.status_code == 200
    payload = response.json()
    assert "summary" in payload
    assert "accounts" in payload
    assert len(payload["accounts"]) == 2
    assert payload["summary"]["total_accounts"] == 2


def test_risk_monitor_uses_account_specific_balances_for_drawdown(monkeypatch) -> None:
    app = FastAPI()
    app.include_router(router)
    client = TestClient(app)

    monkeypatch.setattr("src.api_risk_monitor.get_supabase", lambda: _fake_supabase_drawdown_split())
    monkeypatch.setattr("src.api_risk_monitor.get_settings", _fake_settings)
    monkeypatch.setattr("src.api_risk_monitor.get_redis", lambda: SimpleNamespace(get=lambda *_args, **_kwargs: "0"))
    monkeypatch.setattr("src.api_risk_monitor.is_metaapi_circuit_open", lambda **_kwargs: False)
    monkeypatch.setattr(
        "src.api_risk_monitor.check_safety",
        lambda current_equity, starting_balance, daily_pnl, account_name=None: (True, 1.0, f"{account_name or 'acct'} ok"),
    )

    response = client.get("/api/risk/monitor")

    assert response.status_code == 200
    accounts = response.json()["accounts"]
    drawdowns = {row["account_name"]: row["current_drawdown_pct"] for row in accounts}
    assert drawdowns["Eval A"] != drawdowns["Eval B"]


def test_risk_monitor_summary_is_derived_from_account_rows(monkeypatch) -> None:
    app = FastAPI()
    app.include_router(router)
    client = TestClient(app)

    monkeypatch.setattr("src.api_risk_monitor.get_supabase", lambda: _fake_supabase_two_accounts())
    monkeypatch.setattr("src.api_risk_monitor.get_settings", _fake_settings)
    monkeypatch.setattr("src.api_risk_monitor.get_redis", lambda: SimpleNamespace(get=lambda *_args, **_kwargs: "0"))
    monkeypatch.setattr("src.api_risk_monitor.is_metaapi_circuit_open", lambda **_kwargs: False)
    monkeypatch.setattr(
        "src.api_risk_monitor.check_safety",
        lambda current_equity, starting_balance, daily_pnl, account_name=None: (True, 1.0, f"{account_name or 'acct'} ok"),
    )

    response = client.get("/api/risk/monitor")

    payload = response.json()
    account_total = round(sum(row["daily_pnl_usd"] for row in payload["accounts"]), 2)
    assert payload["summary"]["total_daily_pnl_usd"] == account_total
