from __future__ import annotations

import asyncio
import sys
from types import SimpleNamespace

from src.services.metaapi_streaming_service import _DealHandler, _run_streaming


class _FakeTable:
    def __init__(self, rows: list[dict]) -> None:
        self._rows = rows
        self._select_columns: str | None = None
        self._updates: list[dict] = []
        self._filters: list[tuple[str, object]] = []

    @property
    def updates(self) -> list[dict]:
        return self._updates

    def select(self, columns: str):
        self._select_columns = columns
        return self

    def update(self, data: dict):
        self._updates.append(data)
        return self

    def eq(self, column: str, value):
        self._filters.append((column, value))
        return self

    def execute(self):
        rows = list(self._rows)
        for column, value in self._filters:
            rows = [row for row in rows if row.get(column) == value]
        self._filters = []
        return SimpleNamespace(data=rows)


class _FakeSupabase:
    def __init__(self, rows: list[dict]) -> None:
        self.table_obj = _FakeTable(rows)

    def table(self, name: str) -> _FakeTable:
        assert name == "trading_signals"
        return self.table_obj


def test_streaming_close_uses_broker_deal_time_for_close_timestamps():
    deal_time = "2026-04-27T06:05:00+00:00"
    sb = _FakeSupabase(
        [
            {
                "id": 478,
                "status": "OPEN",
                "exit_time": None,
                "closed_at": None,
                "broker_order_id": "89146771",
            }
        ]
    )

    asyncio.run(
        _DealHandler(sb).handle_deal(
            {
                "entryType": "DEAL_ENTRY_OUT",
                "positionId": "89146771",
                "profit": -127.64,
                "swap": 0,
                "commission": 0,
                "time": deal_time,
            }
        )
    )

    update = sb.table_obj.updates[-1]
    assert update["exit_time"] == deal_time
    assert update["closed_at"] == deal_time
    assert update["updated_at"] != deal_time


def test_streaming_close_skips_already_closed_row_with_realized_pnl():
    original_close = "2026-04-27T06:05:00+00:00"
    sb = _FakeSupabase(
        [
            {
                "id": 478,
                "status": "CLOSED",
                "exit_time": original_close,
                "closed_at": original_close,
                "broker_order_id": "89146771",
                "pnl_usd": 420.0,
                "pnl": 420.0,
            }
        ]
    )

    asyncio.run(
        _DealHandler(sb).handle_deal(
            {
                "entryType": "DEAL_ENTRY_OUT",
                "positionId": "89146771",
                "profit": 1126.76,
                "swap": 0,
                "commission": -0.4,
                "time": "2026-04-27T06:07:00+00:00",
            }
        )
    )

    assert sb.table_obj.updates == []


def test_streaming_stores_net_broker_pnl_including_commission_and_swap():
    sb = _FakeSupabase(
        [
            {
                "id": 515,
                "status": "OPEN",
                "exit_time": None,
                "closed_at": None,
                "broker_order_id": "89822150",
            }
        ]
    )

    asyncio.run(
        _DealHandler(sb).handle_deal(
            {
                "entryType": "DEAL_ENTRY_OUT",
                "positionId": "89822150",
                "profit": -77.76,
                "swap": -0.20,
                "commission": -0.40,
                "time": "2026-04-30T05:31:45.436Z",
            }
        )
    )

    update = sb.table_obj.updates[-1]
    assert update["pnl_usd"] == -78.36
    assert update["pnl"] == -78.36
    assert update["commission"] == -0.40
    assert update["swap"] == -0.20


def test_streaming_waits_for_deploying_account_before_subscribe(monkeypatch):
    class FakeConnection:
        def add_synchronization_listener(self, listener) -> None:
            self.listener = listener

        async def connect(self) -> None:
            pass

        async def wait_synchronized(self) -> None:
            raise asyncio.CancelledError()

        async def close(self) -> None:
            pass

    class FakeAccount:
        def __init__(self) -> None:
            self.state = "DEPLOYING"
            self.deploy_called = False
            self.wait_deployed_called = False
            self.wait_connected_called = False
            self.connection = FakeConnection()

        async def deploy(self) -> None:
            self.deploy_called = True

        async def wait_deployed(self) -> None:
            self.wait_deployed_called = True
            self.state = "DEPLOYED"

        async def wait_connected(self) -> None:
            self.wait_connected_called = True

        def get_streaming_connection(self) -> FakeConnection:
            return self.connection

    account = FakeAccount()

    class FakeAccountApi:
        async def get_account(self, account_id: str) -> FakeAccount:
            return account

    class FakeMetaApi:
        def __init__(self, token: str) -> None:
            self.metatrader_account_api = FakeAccountApi()

        def close(self) -> None:
            pass

    monkeypatch.setitem(
        sys.modules,
        "metaapi_cloud_sdk",
        SimpleNamespace(MetaApi=FakeMetaApi, SynchronizationListener=object),
    )

    asyncio.run(_run_streaming("token", "account-id", object()))

    assert account.deploy_called is False
    assert account.wait_deployed_called is True
    assert account.wait_connected_called is True
