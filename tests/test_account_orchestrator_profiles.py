from __future__ import annotations

import sys
import types
from typing import Any

from src.adapters.execution import router
from src.core import broker_profiles
from src.services.account_orchestrator import AccountOrchestrator


class _CapturedAdapter:
    def __init__(self, **kwargs: Any) -> None:
        self.kwargs = kwargs


class _FakeResponse:
    def __init__(self, data: list[dict[str, Any]]) -> None:
        self.data = data


class _FakeQuery:
    def __init__(self, rows: list[dict[str, Any]]) -> None:
        self._rows = rows
        self._filters: list[tuple[str, Any]] = []

    def select(self, *_args: Any, **_kwargs: Any) -> "_FakeQuery":
        return self

    def eq(self, key: str, value: Any) -> "_FakeQuery":
        self._filters.append((key, value))
        return self

    def execute(self) -> _FakeResponse:
        matched = [
            row for row in self._rows
            if all(row.get(key) == value for key, value in self._filters)
        ]
        return _FakeResponse(matched)


class _FakeSupabase:
    def __init__(self, rows: list[dict[str, Any]]) -> None:
        self._rows = rows

    def table(self, table_name: str) -> _FakeQuery:
        assert table_name == "broker_profiles"
        return _FakeQuery(self._rows)


class _Settings:
    supabase_url = "https://example.supabase.co"
    supabase_service_role_key = "service-role-key"
    supabase_key = ""
    broker_profiles_json = ""
    get_accounts: list[dict[str, Any]] = []
    meta_api_token = ""
    risk_percent = 1.0
    trinity_max_positions = 3
    run_mode = "LIVE"


class _OrchestratorResponse:
    def __init__(self, data: Any) -> None:
        self.data = data


class _OrchestratorNotQuery:
    def __init__(self, query: "_OrchestratorQuery") -> None:
        self._query = query

    def is_(self, key: str, value: Any) -> "_OrchestratorQuery":
        if value == "null":
            self._query._not_null_keys.add(key)
        return self._query


class _OrchestratorQuery:
    def __init__(self, rows: list[dict[str, Any]]) -> None:
        self._rows = rows
        self._filters: list[tuple[str, Any]] = []
        self._not_null_keys: set[str] = set()
        self._selected_fields: list[str] | None = None
        self._order_key: str | None = None
        self._order_desc = False
        self._limit: int | None = None
        self._single = False

    @property
    def not_(self) -> _OrchestratorNotQuery:
        return _OrchestratorNotQuery(self)

    def select(self, *args: Any, **_kwargs: Any) -> "_OrchestratorQuery":
        if not args:
            self._selected_fields = None
            return self

        raw_fields: list[str] = []
        for arg in args:
            if isinstance(arg, str):
                raw_fields.extend(field.strip() for field in arg.split(","))
        filtered_fields = [field for field in raw_fields if field and field != "*"]
        self._selected_fields = filtered_fields or None
        return self

    def eq(self, key: str, value: Any) -> "_OrchestratorQuery":
        self._filters.append((key, value))
        return self

    def order(self, key: str, desc: bool = False) -> "_OrchestratorQuery":
        self._order_key = key
        self._order_desc = desc
        return self

    def limit(self, value: int) -> "_OrchestratorQuery":
        self._limit = value
        return self

    def single(self) -> "_OrchestratorQuery":
        self._single = True
        return self

    def maybe_single(self) -> "_OrchestratorQuery":
        self._single = True
        return self

    def execute(self) -> _OrchestratorResponse:
        matched = [
            row for row in self._rows
            if all(row.get(key) == value for key, value in self._filters)
            and all(row.get(key) is not None for key in self._not_null_keys)
        ]

        if self._order_key is not None:
            matched = sorted(
                matched,
                key=lambda row: row.get(self._order_key) or "",
                reverse=self._order_desc,
            )

        if self._limit is not None:
            matched = matched[: self._limit]

        if self._selected_fields is not None:
            matched = [
                {field: row.get(field) for field in self._selected_fields}
                for row in matched
            ]

        if self._single:
            return _OrchestratorResponse(matched[0] if matched else None)
        return _OrchestratorResponse(matched)


class _OrchestratorSupabase:
    def __init__(self, tables: dict[str, list[dict[str, Any]]]) -> None:
        self._tables = tables

    def table(self, table_name: str) -> _OrchestratorQuery:
        return _OrchestratorQuery(self._tables.get(table_name, []))


class _SnapshotAdapter:
    def get_account_information(self) -> dict[str, Any]:
        return {
            "balance": 1250.5,
            "equity": 1264.0,
            "platform": "cTrader",
            "server": "Spotware Demo",
            "leverage": 200,
        }

    def get_open_positions(self) -> list[dict[str, Any]]:
        return [{"id": "1"}, {"id": "2"}]


def _make_profile(profile_id: int, **overrides: Any) -> dict[str, Any]:
    profile = {
        "id": profile_id,
        "name": f"Profile {profile_id}",
        "venue": "metaapi_mt5",
        "meta_api_account_id": f"account-{profile_id}",
        "token": f"token-{profile_id}",
        "token_env_key": None,
        "api_key": None,
        "api_secret": None,
        "risk_pct": 1.0,
        "max_positions": 3,
        "run_mode": "LIVE",
        "evaluation_mode": False,
        "evaluation_phase": "phase1",
        "consistency_enabled": None,
        "is_active": True,
        "selected_for_trading": True,
    }
    profile.update(overrides)
    return profile


def test_resolve_profile_adapter_uses_ctrader_for_ctrader_profiles(monkeypatch) -> None:
    monkeypatch.setattr(router, "CTraderAdapter", _CapturedAdapter)
    monkeypatch.setattr(router, "MetaApiAdapter", _CapturedAdapter)

    adapter = router.resolve_profile_adapter(
        {
            "name": "cTrader Profile",
            "venue": "ctrader",
            "token": "refresh-token",
            "account_id": "ctrader-account",
            "run_mode": "LIVE",
        }
    )

    assert isinstance(adapter, _CapturedAdapter)
    assert adapter.kwargs == {
        "refresh_token": "refresh-token",
        "ctid_trader_account_id": "ctrader-account",
        "account_name": "cTrader Profile",
        "is_live": True,
    }


def test_resolve_profile_adapter_uses_metaapi_for_metaapi_profiles(monkeypatch) -> None:
    monkeypatch.setattr(router, "MetaApiAdapter", _CapturedAdapter)

    adapter = router.resolve_profile_adapter(
        {
            "name": "MetaApi Profile",
            "venue": "metaapi",
            "token": "meta-token",
            "meta_api_account_id": "meta-account",
            "region": "new-york",
        }
    )

    assert isinstance(adapter, _CapturedAdapter)
    assert adapter.kwargs == {
        "token": "meta-token",
        "account_id": "meta-account",
        "account_name": "MetaApi Profile",
        "region": "new-york",
    }


def test_get_active_profiles_returns_only_selected_active_profiles(monkeypatch) -> None:
    rows = [
        _make_profile(1, selected_for_trading=True),
        _make_profile(2, selected_for_trading=False),
        _make_profile(3, is_active=False, selected_for_trading=True),
    ]
    fake_supabase_module = types.SimpleNamespace(create_client=lambda *_args, **_kwargs: _FakeSupabase(rows))

    monkeypatch.setattr(broker_profiles, "get_settings", lambda: _Settings())
    monkeypatch.setattr(broker_profiles, "coerce_profiles", lambda profiles: profiles)
    monkeypatch.setitem(sys.modules, "supabase", fake_supabase_module)

    profiles = broker_profiles.get_active_profiles()

    assert [profile["id"] for profile in profiles] == [1]
    assert profiles[0]["name"] == "Profile 1"


def test_get_account_comparison_uses_ctrader_snapshot_positions(monkeypatch) -> None:
    profile = _make_profile(
        7,
        name="cTrader Snapshot",
        venue="ctrader",
        token="refresh-token",
        account_id="ctrader-123",
        meta_api_account_id=None,
        connection_status="connected",
    )
    client = _OrchestratorSupabase(
        {
            "account_strategies": [],
            "broker_profiles": [profile],
            "account_status_snapshots": [
                {
                    "broker_profile_id": 7,
                    "snapshot_time": "2026-04-23T10:15:00+00:00",
                }
            ],
            "trading_signals": [],
        }
    )
    captured_profiles: list[dict[str, Any]] = []

    def _resolve_profile_adapter(profile_data: dict[str, Any]) -> _SnapshotAdapter:
        captured_profiles.append(profile_data)
        return _SnapshotAdapter()

    monkeypatch.setattr(router, "resolve_profile_adapter", _resolve_profile_adapter)

    comparison = AccountOrchestrator(client).get_account_comparison()

    assert len(comparison) == 1
    assert len(captured_profiles) == 1
    assert captured_profiles[0]["id"] == profile["id"]
    assert captured_profiles[0]["venue"] == "ctrader"
    assert captured_profiles[0]["token"] == "refresh-token"
    assert captured_profiles[0]["account_id"] == "ctrader-123"
    assert comparison[0]["account_name"] == "cTrader Snapshot"
    assert comparison[0]["platform_type"] == "cTrader"
    assert comparison[0]["balance"] == 1250.5
    assert comparison[0]["equity"] == 1264.0
    assert comparison[0]["open_positions"] == 2
    assert comparison[0]["active_positions"] == 2
    assert comparison[0]["last_sync_time"] == "2026-04-23T10:15:00+00:00"
