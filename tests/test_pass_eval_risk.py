from src.worker import (
    _get_account_safety_state,
    _get_pair_performance_state,
    _get_same_day_trade_count,
)


class _FakeResponse:
    def __init__(self, data):
        self.data = data


class _FakeQuery:
    def __init__(self, rows):
        self._rows = list(rows)

    def select(self, *_args, **_kwargs):
        return self

    def eq(self, field, value):
        self._rows = [row for row in self._rows if row.get(field) == value]
        return self

    def gte(self, *_args, **_kwargs):
        return self

    def in_(self, field, values):
        self._rows = [row for row in self._rows if row.get(field) in values]
        return self

    def order(self, *_args, **_kwargs):
        return self

    def limit(self, n):
        self._rows = self._rows[:n]
        return self

    def execute(self):
        return _FakeResponse(self._rows)


class _FakeSupabase:
    def __init__(self, rows):
        self._rows = rows

    def table(self, _name):
        return _FakeQuery(self._rows)


def test_same_day_trade_count_for_symbol_uses_recent_trade_rows() -> None:
    sb = _FakeSupabase(
        [
            {"symbol": "EURUSD", "status": "closed"},
            {"symbol": "EURUSD", "status": "executed"},
            {"symbol": "GBPUSD", "status": "closed"},
        ]
    )

    count = _get_same_day_trade_count("EURUSD", sb)

    assert count == 2


def test_pair_performance_state_becomes_weak_after_recent_losses() -> None:
    sb = _FakeSupabase(
        [
            {"symbol": "EURUSD", "status": "closed", "pnl_usd": -50},
            {"symbol": "EURUSD", "status": "CLOSED", "pnl_usd": -30},
            {"symbol": "EURUSD", "status": "closed", "pnl_usd": 10},
        ]
    )

    state = _get_pair_performance_state("EURUSD", sb)

    assert state == "weak"


def test_account_safety_state_maps_drawdown_pressure() -> None:
    state = _get_account_safety_state(
        allowed=True,
        risk_multiplier=0.5,
        daily_pnl=-1200.0,
        account_balance=50000.0,
        current_equity=48800.0,
        max_drawdown_pct=8.0,
    )

    assert state == "defensive"
