from src.core.risk_engine import calculate_max_position_size, calculate_position_size_with_spread


def test_calculate_position_size_with_spread_rejects_disabled_symbol() -> None:
    payload = {"symbol": "EURUSD", "entry": 1.1000, "sl": 1.0980, "side": "buy"}

    result = calculate_position_size_with_spread(
        payload=payload,
        account_balance=10000.0,
        risk_percent=0.5,
        symbol_overrides={
            "enabled": False,
            "risk_percent": 0.5,
            "max_lot_size": 2.0,
            "min_lot_size": 0.01,
            "lot_step": 0.01,
            "pip_size": 0.0001,
            "pip_value_per_lot": 10.0,
            "stop_loss_buffer_pips": 1.0,
        },
    )

    assert result["rejected"] is True
    assert result["rejection_reason"] == "symbol_disabled"


def test_calculate_max_position_size_rounds_to_lot_step() -> None:
    lots = calculate_max_position_size(
        {"symbol": "EURUSD", "entry": 1.1000, "sl": 1.0990, "side": "buy"},
        account_balance=10000.0,
        risk_percent=0.5,
        symbol_overrides={
            "enabled": True,
            "risk_percent": 0.5,
            "max_lot_size": 10.0,
            "min_lot_size": 0.10,
            "lot_step": 0.10,
            "pip_size": 0.0001,
            "pip_value_per_lot": 10.0,
            "stop_loss_buffer_pips": 1.0,
        },
    )

    assert round(lots, 2) == lots
    assert abs((lots / 0.10) - round(lots / 0.10)) < 1e-9
    assert lots >= 0.10


def test_calculate_position_size_with_spread_uses_override_buffer() -> None:
    payload = {"symbol": "EURUSD", "entry": 1.1000, "sl": 1.0990, "side": "buy"}

    no_buffer = calculate_position_size_with_spread(
        payload=payload,
        account_balance=10000.0,
        risk_percent=0.5,
        symbol_overrides={
            "enabled": True,
            "risk_percent": 0.5,
            "max_lot_size": 10.0,
            "min_lot_size": 0.01,
            "lot_step": 0.01,
            "pip_size": 0.0001,
            "pip_value_per_lot": 10.0,
            "stop_loss_buffer_pips": 0.0,
        },
    )
    with_buffer = calculate_position_size_with_spread(
        payload=payload,
        account_balance=10000.0,
        risk_percent=0.5,
        symbol_overrides={
            "enabled": True,
            "risk_percent": 0.5,
            "max_lot_size": 10.0,
            "min_lot_size": 0.01,
            "lot_step": 0.01,
            "pip_size": 0.0001,
            "pip_value_per_lot": 10.0,
            "stop_loss_buffer_pips": 2.0,
        },
    )

    assert no_buffer["rejected"] is False
    assert with_buffer["rejected"] is False
    assert with_buffer["effective_sl_pips"] > no_buffer["effective_sl_pips"]
    assert with_buffer["lots"] < no_buffer["lots"]
