from scripts.optimizer.asset_classifier import classify_asset


def test_asset_classifier_maps_symbols_correctly() -> None:
    assert classify_asset("EURUSD") == "forex"
    assert classify_asset("OANDA:XAUUSD") == "metal"
    assert classify_asset("NAS100") == "index_cfd"
    assert classify_asset("MNQ") == "futures_index"
    assert classify_asset("GCZ2026") == "futures_metal"
    assert classify_asset("MCL") == "futures_energy"
    assert classify_asset("6E") == "futures_fx"
    assert classify_asset("DOGEUSD") == "crypto"
    assert classify_asset("UNKNOWN") == "unknown"
