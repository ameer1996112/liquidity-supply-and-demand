from unittest.mock import patch, MagicMock

from src.adapters.execution.router import get_adapter
from src.adapters.execution.ctrader_adapter import CTraderAdapter
from src.adapters.execution.interfaces import OrderRequest, CloseRequest


def test_router_metaapi_profile_defaults_to_metaapi():
    adapter = get_adapter(profile={"name": "acc", "token": "t", "meta_api_account_id": "a"})
    assert adapter.__class__.__name__ == "MetaApiAdapter"


def test_router_binance_profile_selects_binance_adapter():
    adapter = get_adapter(profile={"venue": "binance", "name": "acc", "api_key": "k", "api_secret": "s"})
    assert adapter.__class__.__name__ == "BinanceAdapter"


def test_router_bybit_profile_selects_bybit_adapter():
    adapter = get_adapter(profile={"venue": "bybit", "name": "acc", "api_key": "k", "api_secret": "s"})
    assert adapter.__class__.__name__ == "BybitAdapter"


def test_router_ctrader_profile_selects_ctrader_adapter():
    adapter = get_adapter(profile={
        "venue": "ctrader",
        "name": "prop-demo",
        "token": "refresh-tok-123",
        "meta_api_account_id": "12345",
    })
    assert isinstance(adapter, CTraderAdapter)
    assert adapter.ctid_trader_account_id == 12345
    assert adapter.host == "demo.ctraderapi.com"


def test_router_ctrader_live_mode():
    adapter = get_adapter(profile={
        "venue": "ctrader",
        "token": "tok",
        "meta_api_account_id": "999",
        "run_mode": "LIVE",
    })
    assert isinstance(adapter, CTraderAdapter)
    assert adapter.host == "live.ctraderapi.com"


def test_router_ctrader_missing_token_falls_through():
    """cTrader profile without token should NOT select CTraderAdapter."""
    mock_settings = MagicMock()
    mock_settings.execution_mode = ""
    mock_settings.run_mode = "DRY_RUN"
    mock_settings.live_trading_enabled = False
    adapter = get_adapter(
        run_mode="DRY_RUN",
        settings=mock_settings,
        profile={"venue": "ctrader", "meta_api_account_id": "123"},
    )
    # Falls through to single-account logic → DryRunAdapter
    assert adapter.__class__.__name__ == "DryRunAdapter"


def test_ctrader_submit_order_invalid_side():
    """Invalid side should return failed without hitting the network."""
    adapter = CTraderAdapter(refresh_token="tok", ctid_trader_account_id="123")
    result = adapter.submit_order(OrderRequest(
        client_order_id="test-1",
        symbol="EURUSD",
        side="invalid",
        size=0.01,
    ))
    assert result.status == "failed"
    assert "Invalid side" in result.message


def test_ctrader_submit_order_zero_volume():
    adapter = CTraderAdapter(refresh_token="tok", ctid_trader_account_id="123")
    result = adapter.submit_order(OrderRequest(
        client_order_id="test-2",
        symbol="EURUSD",
        side="buy",
        size=0.0,
    ))
    assert result.status == "failed"
    assert "Invalid volume" in result.message


def test_ctrader_close_order_missing_broker_id():
    adapter = CTraderAdapter(refresh_token="tok", ctid_trader_account_id="123")
    result = adapter.close_order(CloseRequest(
        client_order_id="test-3",
        symbol="EURUSD",
    ))
    assert result.status == "failed"
    assert "broker_order_id" in result.message

