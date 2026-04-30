from __future__ import annotations

import asyncio
from types import SimpleNamespace

from src.services.metaapi_streaming_service import _DealHandler


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


def test_streaming_replay_without_deal_time_does_not_refresh_closed_timestamp():
    original_close = "2026-04-27T06:05:00+00:00"
    sb = _FakeSupabase(
        [
            {
                "id": 478,
                "status": "CLOSED",
                "exit_time": original_close,
                "closed_at": original_close,
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
            }
        )
    )

    update = sb.table_obj.updates[-1]
    assert "exit_time" not in update
    assert "closed_at" not in update
    assert update["pnl_usd"] == -127.64


def test_streaming_stores_broker_profit_separately_from_commission():
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
                "swap": 0,
                "commission": -0.40,
                "time": "2026-04-30T05:31:45.436Z",
            }
        )
    )

    update = sb.table_obj.updates[-1]
    assert update["pnl_usd"] == -77.76
    assert update["pnl"] == -77.76
    assert update["commission"] == -0.40
