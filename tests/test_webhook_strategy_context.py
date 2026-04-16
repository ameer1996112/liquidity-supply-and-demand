from __future__ import annotations

import pytest

from src.services.strategy_config import validate_strategy_config
from src.services.strategy_registry import (
    InactiveStrategyError,
    ResolvedStrategy,
)
from src.services.webhook_strategy_context import (
    StrategyContextError,
    build_received_signal_row,
    resolve_and_stamp_strategy_context,
)


def _resolved_strategy() -> ResolvedStrategy:
    return ResolvedStrategy(
        record_id=7,
        strategy_id="liq_sd_v1",
        strategy_version="1",
        name="Liquidity",
        config=validate_strategy_config(
            {
                "name": "Liquidity",
                "signal_filters": {"symbols": ["EURUSD"], "sessions": ["london"]},
                "risk": {"name": "balanced", "risk_percent": 0.5, "min_rr_ratio": 1.5},
                "ai": {"mode": "shadow", "debate": {"enabled": True, "rounds": 1, "min_confidence": 60}},
                "execution_routing": [],
            }
        ),
        is_active=True,
    )


def _base_payload() -> dict:
    return {
        "strategy_id": "liq_sd_v1",
        "strategy_version": "1",
        "symbol": "EURUSD",
        "side": "buy",
        "entry": 1.10,
        "sl": 1.09,
        "tp": 1.12,
        "size": 1.0,
        "account_balance": 50000,
    }


def test_resolve_and_stamp_strategy_context_rejects_inactive_strategy():
    payload = _base_payload()

    with pytest.raises(StrategyContextError) as exc:
        resolve_and_stamp_strategy_context(
            payload,
            resolver=lambda **_kwargs: (_ for _ in ()).throw(InactiveStrategyError("liq_sd_v1")),
        )

    assert exc.value.detail == "inactive_strategy"


def test_resolve_and_stamp_strategy_context_adds_trusted_fields():
    payload = _base_payload()

    stamped = resolve_and_stamp_strategy_context(
        payload,
        resolver=lambda **_kwargs: _resolved_strategy(),
    )

    assert stamped["strategy_id"] == "liq_sd_v1"
    assert stamped["strategy_version"] == "1"
    assert stamped["strategy_name"] == "Liquidity"
    assert stamped["strategy_config_id"] == 7
    assert stamped["strategy_config_snapshot"]["name"] == "Liquidity"


def test_build_received_signal_row_includes_strategy_fields():
    row = build_received_signal_row(
        {
            **_base_payload(),
            "strategy_name": "Liquidity",
            "strategy_config_id": 7,
        },
        run_mode="LIVE",
        account_id="default",
        receipt_id="receipt-1",
        account_balance=50000.0,
    )

    assert row["status"] == "received"
    assert row["strategy_id"] == "liq_sd_v1"
    assert row["strategy_version"] == "1"
    assert row["strategy_name"] == "Liquidity"
    assert row["strategy_config_id"] == 7
