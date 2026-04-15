from src.adapters.execution.router import get_adapter


def test_router_metaapi_profile_defaults_to_metaapi():
    adapter = get_adapter(profile={"name": "acc", "token": "t", "meta_api_account_id": "a"})
    assert adapter.__class__.__name__ == "MetaApiAdapter"


def test_router_binance_profile_selects_binance_adapter():
    adapter = get_adapter(profile={"venue": "binance", "name": "acc", "api_key": "k", "api_secret": "s"})
    assert adapter.__class__.__name__ == "BinanceAdapter"


def test_router_bybit_profile_selects_bybit_adapter():
    adapter = get_adapter(profile={"venue": "bybit", "name": "acc", "api_key": "k", "api_secret": "s"})
    assert adapter.__class__.__name__ == "BybitAdapter"

