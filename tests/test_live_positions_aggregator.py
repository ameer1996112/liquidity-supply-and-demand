from __future__ import annotations

from typing import Any

from src.services.live_positions_aggregator import LivePositionsAggregator


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
    def __init__(self, broker_profiles: list[dict[str, Any]]) -> None:
        self._broker_profiles = broker_profiles

    def table(self, table_name: str) -> _FakeQuery:
        assert table_name == "broker_profiles"
        return _FakeQuery(self._broker_profiles)


class _MetaApiAdapter:
    def __init__(self) -> None:
        self.positions = [
            {
                "id": "m-1",
                "symbol": "GBPUSD",
                "type": "POSITION_TYPE_BUY",
                "volume": 0.81,
                "openPrice": 1.35058,
                "currentPrice": 1.35208,
                "sl": 1.349,
                "tp": 1.355,
                "profit": 121.45,
                "swap": -1.2,
                "commission": -4.8,
                "time": "2026-04-23T09:00:00+00:00",
                "comment": "meta-live",
            }
        ]

    def get_open_positions(self) -> list[dict[str, Any]]:
        return list(self.positions)

    def get_account_status(self) -> dict[str, Any]:
        return {
            "balance": 10000.0,
            "equity": 10250.0,
            "margin": 350.0,
            "freeMargin": 9900.0,
            "marginLevel": 2928.0,
            "open_positions": 1,
        }


class _CTraderAdapter:
    def __init__(self) -> None:
        self.positions = [
            {
                "id": "c-1",
                "symbol": "XAUUSD",
                "type": "SELL",
                "volume": 0.2,
                "openPrice": 3340.5,
                "currentPrice": 3335.2,
                "sl": 3352.0,
                "tp": 3310.0,
                "profit": 106.0,
                "swap": 0.0,
                "commission": -2.5,
                "time": "2026-04-23T09:05:00+00:00",
                "comment": "ctrader-live",
            }
        ]

    def get_open_positions(self) -> list[dict[str, Any]]:
        return list(self.positions)

    def get_account_information(self) -> dict[str, Any]:
        return {
            "balance": 5000.0,
            "equity": 5100.0,
            "margin": None,
            "freeMargin": None,
            "platform": "cTrader",
        }


class _FailingAdapter:
    def get_open_positions(self) -> list[dict[str, Any]]:
        raise RuntimeError("broker timeout")

    def get_account_information(self) -> dict[str, Any]:
        raise RuntimeError("broker timeout")


def _make_profile(profile_id: int, **overrides: Any) -> dict[str, Any]:
    profile = {
        "id": profile_id,
        "name": f"Profile {profile_id}",
        "venue": "metaapi_mt5",
        "run_mode": "LIVE",
        "is_active": True,
        "selected_for_trading": True,
        "token": f"token-{profile_id}",
        "meta_api_account_id": f"account-{profile_id}",
    }
    profile.update(overrides)
    return profile


def test_aggregate_open_positions_merges_metaapi_and_ctrader_profiles() -> None:
    profiles = [
        _make_profile(1, name="Meta Live", venue="metaapi_mt5"),
        _make_profile(2, name="cTrader Live", venue="ctrader", account_id="ct-2"),
        _make_profile(3, name="Demo Profile", run_mode="DEMO"),
        _make_profile(4, name="Inactive Profile", is_active=False),
        _make_profile(5, name="Crypto Profile", venue="binance"),
    ]

    def _resolve_adapter(profile: dict[str, Any]) -> Any:
        if profile["name"] == "Meta Live":
            return _MetaApiAdapter()
        if profile["name"] == "cTrader Live":
            return _CTraderAdapter()
        raise AssertionError(f"Unexpected profile: {profile['name']}")

    aggregator = LivePositionsAggregator(_FakeSupabase(profiles), adapter_resolver=_resolve_adapter)

    loaded_profiles = aggregator.load_eligible_profiles()
    result = aggregator.aggregate_open_positions(loaded_profiles)

    assert [profile.name for profile in loaded_profiles] == ["Meta Live", "cTrader Live"]
    assert result.healthy_profiles == 2
    assert result.failed_profiles == 0
    assert len(result.positions) == 2

    positions_by_account = {position.account_name: position for position in result.positions}

    meta_position = positions_by_account["Meta Live"]
    assert meta_position.venue == "metaapi_mt5"
    assert meta_position.side == "buy"
    assert meta_position.size == 0.81
    assert meta_position.entry_price == 1.35058
    assert meta_position.profit == 121.45

    ctrader_position = positions_by_account["cTrader Live"]
    assert ctrader_position.venue == "ctrader"
    assert ctrader_position.side == "sell"
    assert ctrader_position.symbol == "XAUUSD"
    assert ctrader_position.size == 0.2
    assert ctrader_position.current_price == 3335.2


def test_aggregate_open_positions_tolerates_partial_profile_failures() -> None:
    profiles = [
        _make_profile(10, name="Broken Meta", venue="metaapi_mt5"),
        _make_profile(11, name="Healthy cTrader", venue="ctrader", account_id="ct-11"),
    ]

    def _resolve_adapter(profile: dict[str, Any]) -> Any:
        if profile["name"] == "Broken Meta":
            return _FailingAdapter()
        if profile["name"] == "Healthy cTrader":
            return _CTraderAdapter()
        raise AssertionError(f"Unexpected profile: {profile['name']}")

    aggregator = LivePositionsAggregator(_FakeSupabase(profiles), adapter_resolver=_resolve_adapter)

    result = aggregator.aggregate_open_positions()

    assert result.healthy_profiles == 1
    assert result.failed_profiles == 1
    assert len(result.errors) == 1
    assert result.errors[0].account_name == "Broken Meta"
    assert result.errors[0].operation == "positions"
    assert [position.account_name for position in result.positions] == ["Healthy cTrader"]


def test_aggregate_account_status_sums_healthy_accounts() -> None:
    profiles = [
        _make_profile(20, name="Meta Live", venue="metaapi"),
        _make_profile(21, name="cTrader Live", venue="ctrader", account_id="ct-21"),
    ]

    def _resolve_adapter(profile: dict[str, Any]) -> Any:
        if profile["name"] == "Meta Live":
            return _MetaApiAdapter()
        if profile["name"] == "cTrader Live":
            return _CTraderAdapter()
        raise AssertionError(f"Unexpected profile: {profile['name']}")

    aggregator = LivePositionsAggregator(_FakeSupabase(profiles), adapter_resolver=_resolve_adapter)

    result = aggregator.aggregate_account_status()

    assert result.healthy_profiles == 2
    assert result.failed_profiles == 0
    assert len(result.accounts) == 2
    assert result.totals == {
        "balance": 15000.0,
        "equity": 15350.0,
        "margin": 350.0,
        "free_margin": 9900.0,
        "open_positions": 2.0,
    }

    accounts_by_name = {account.account_name: account for account in result.accounts}
    assert accounts_by_name["Meta Live"].open_positions == 1
    assert accounts_by_name["cTrader Live"].open_positions == 1
    assert accounts_by_name["cTrader Live"].venue == "ctrader"
