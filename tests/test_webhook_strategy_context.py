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
            "zone_id": 18126,
            "trade_key": "EURUSD|buy|18126|1713356700000",
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
    assert row["zone_id"] == 18126
    assert row["trade_key"] == "EURUSD|buy|18126|1713356700000"


def test_build_received_signal_row_saves_triggered_zone_snapshot_only_for_entry_zone():
    payload = {
        **_base_payload(),
        "zone_id": "18126",
        "zone_type": "demand",
        "zone_top": "1.101",
        "zone_bottom": "1.099",
        "zone_grade": "A",
        "score": "84.5",
        "entry_model": "DIR_CLOSE",
        "liq_swept": "true",
        "target_swept": "true",
        "caused_sweep": "true",
        "is_accuracy": "false",
        "liquidity_distance_pips": "8.7",
        "liquidity_spread_pips": "22.4",
        "sweep_to_touch_bars": "3",
        "peak_to_touch_bars": "11",
        "liq_source": "MAKUCHAKU_PIVOT",
        "bars_since_zone": "18",
        "rr_ratio": "2.5",
        "sl_pips": "4.2",
        "trade_key": "EURUSD|buy|18126|1713356700000",
    }

    row = build_received_signal_row(
        payload,
        run_mode="LIVE",
        account_id="default",
        receipt_id="receipt-1",
        account_balance=50000.0,
    )

    assert row["zone_id"] == 18126
    assert row["zone_type"] == "demand"
    assert row["zone_top"] == 1.101
    assert row["zone_bottom"] == 1.099
    assert row["liq_swept"] is True
    assert row["target_swept"] is True
    assert row["liquidity_distance_pips"] == 8.7
    assert row["setup_evidence"]["focus_zone"] == {
        "id": 18126,
        "type": "demand",
        "high": 1.101,
        "low": 1.099,
        "label": "Demand #18126",
        "source": "entry_webhook",
    }
    assert row["setup_evidence"]["triggered_zone"]["zone"]["id"] == 18126
    assert row["setup_evidence"]["triggered_zone"]["liquidity"]["swept"] is True
    assert payload["setup_evidence"] == row["setup_evidence"]


def test_build_received_signal_row_does_not_create_zone_snapshot_without_zone_id():
    payload = _base_payload()

    row = build_received_signal_row(
        payload,
        run_mode="LIVE",
        account_id="default",
        receipt_id="receipt-1",
        account_balance=50000.0,
    )

    assert "zone_id" not in row
    assert "setup_evidence" not in row
    assert "setup_evidence" not in payload
