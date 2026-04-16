from __future__ import annotations

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import config

from src.core.guard_rails.prop_guard import check_signal_guards


class _FakeQuery:
    def __init__(self, rows: list[dict]) -> None:
        self._rows = rows
        self.filters: list[tuple[str, str, object]] = []

    def select(self, *_args, **_kwargs):
        return self

    def in_(self, column: str, values):
        self.filters.append(("in", column, tuple(values)))
        return self

    @property
    def not_(self):
        return self

    def is_(self, column: str, value):
        self.filters.append(("not_is", column, value))
        return self

    def order(self, column: str, desc: bool = False):
        self.filters.append(("order", column, desc))
        return self

    def limit(self, value: int):
        self.filters.append(("limit", "__limit__", value))
        return self

    def eq(self, column: str, value):
        self.filters.append(("eq", column, value))
        return self

    def execute(self):
        rows = list(self._rows)
        for op, column, value in self.filters:
            if op == "eq":
                rows = [row for row in rows if row.get(column) == value]
            elif op == "in":
                rows = [row for row in rows if row.get(column) in value]
            elif op == "not_is":
                rows = [row for row in rows if row.get(column) is not None]

        order_ops = [f for f in self.filters if f[0] == "order"]
        if order_ops:
            _, column, desc = order_ops[-1]
            rows = sorted(rows, key=lambda row: row.get(column), reverse=bool(desc))

        limit_ops = [f for f in self.filters if f[0] == "limit"]
        if limit_ops:
            rows = rows[: int(limit_ops[-1][2])]

        return SimpleNamespace(data=rows)


class _FakeSupabase:
    def __init__(self, rows: list[dict]) -> None:
        self._rows = rows
        self.last_query: _FakeQuery | None = None

    def table(self, _name: str) -> _FakeQuery:
        self.last_query = _FakeQuery(self._rows)
        return self.last_query


def _settings(**overrides):
    base = {
        "evaluation_mode": True,
        "evaluation_phase": "phase1",
        "min_rr_ratio": 0.0,
        "max_consecutive_losses": 2,
        "consec_loss_pause_hours": 4.0,
    }
    base.update(overrides)
    return SimpleNamespace(**base)


def test_check_signal_guards_uses_latest_account_trades_for_loss_pause(monkeypatch):
    now = datetime.now(timezone.utc)
    rows = [
        {
            "broker_profile_id": "acct-1",
            "account_name": "ACG-1",
            "status": "closed",
            "outcome": "loss",
            "pnl_usd": -50.0,
            "exit_time": (now - timedelta(minutes=30)).isoformat(),
        },
        {
            "broker_profile_id": "acct-1",
            "account_name": "ACG-1",
            "status": "closed",
            "outcome": "win",
            "pnl_usd": 35.0,
            "exit_time": (now - timedelta(hours=1)).isoformat(),
        },
        {
            "broker_profile_id": "acct-1",
            "account_name": "ACG-1",
            "status": "closed",
            "outcome": "loss",
            "pnl_usd": -25.0,
            "exit_time": (now - timedelta(hours=2)).isoformat(),
        },
    ]
    sb = _FakeSupabase(rows)
    monkeypatch.setattr(config, "get_settings", lambda: _settings())

    allowed, reason = check_signal_guards(
        {"rr_ratio": 2.0},
        sb,
        profile={"id": "acct-1", "name": "ACG-1"},
    )

    assert allowed is True
    assert reason is None
    assert sb.last_query is not None
    assert ("eq", "broker_profile_id", "acct-1") in sb.last_query.filters
