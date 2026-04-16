from __future__ import annotations

from types import SimpleNamespace

import pytest


class _FakeQuery:
    def __init__(self, rows: list[dict]):
        self._rows = list(rows)

    def select(self, *_args, **_kwargs):
        return self

    def eq(self, key: str, value):
        self._rows = [row for row in self._rows if row.get(key) == value]
        return self

    def limit(self, n: int):
        self._rows = self._rows[:n]
        return self

    def execute(self):
        return SimpleNamespace(data=self._rows)


class _FakeSupabase:
    def __init__(self, strategy_rows: list[dict]):
        self._strategy_rows = strategy_rows

    def table(self, table_name: str):
        assert table_name == "strategy_configs"
        return _FakeQuery(self._strategy_rows)


def _strategy_row(**overrides: object) -> dict:
    row = {
        "id": 7,
        "slug": "liq_sd_v1",
        "name": "Liquidity",
        "version": 1,
        "is_active": True,
        "config": {
            "name": "Liquidity",
            "signal_filters": {"symbols": ["EURUSD"], "sessions": ["london"]},
            "risk": {"name": "balanced", "risk_percent": 0.5, "min_rr_ratio": 1.5},
            "ai": {"mode": "shadow", "debate": {"enabled": True, "rounds": 1, "min_confidence": 60}},
            "execution_routing": [],
        },
    }
    row.update(overrides)
    return row


def test_resolve_strategy_rejects_unknown_slug():
    from src.services.strategy_registry import UnknownStrategyError, resolve_strategy_or_raise

    with pytest.raises(UnknownStrategyError):
        resolve_strategy_or_raise(
            supabase=_FakeSupabase([]),
            strategy_id="liq_sd_v1",
            strategy_version="1",
        )


def test_resolve_strategy_rejects_inactive_strategy():
    from src.services.strategy_registry import InactiveStrategyError, resolve_strategy_or_raise

    with pytest.raises(InactiveStrategyError):
        resolve_strategy_or_raise(
            supabase=_FakeSupabase([_strategy_row(is_active=False)]),
            strategy_id="liq_sd_v1",
            strategy_version="1",
        )


def test_resolve_strategy_rejects_version_mismatch():
    from src.services.strategy_registry import StrategyVersionMismatchError, resolve_strategy_or_raise

    with pytest.raises(StrategyVersionMismatchError):
        resolve_strategy_or_raise(
            supabase=_FakeSupabase([_strategy_row(version=2)]),
            strategy_id="liq_sd_v1",
            strategy_version="1",
        )


def test_resolve_strategy_returns_typed_strategy():
    from src.services.strategy_registry import resolve_strategy_or_raise

    resolved = resolve_strategy_or_raise(
        supabase=_FakeSupabase([_strategy_row()]),
        strategy_id="liq_sd_v1",
        strategy_version="1",
    )

    assert resolved.record_id == 7
    assert resolved.strategy_id == "liq_sd_v1"
    assert resolved.strategy_version == "1"
    assert resolved.name == "Liquidity"
    assert resolved.is_active is True
    assert resolved.config.name == "Liquidity"
