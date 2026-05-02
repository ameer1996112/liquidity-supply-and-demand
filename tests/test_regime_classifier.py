import json

from scripts.optimizer.regime_classifier import classify_regime, load_manual_snapshots


def test_regime_classifier_uses_manual_state_when_price_data_missing(tmp_path) -> None:
    manual = tmp_path / "manual_market_state.json"
    manual.write_text(
        json.dumps(
            {
                "USDCAD": {
                    "regimes": ["RANGING", "LOW_VOLATILITY"],
                    "confidence": 0.72,
                    "spread_state": "SESSION_OK",
                }
            }
        )
    )

    snapshots = load_manual_snapshots(manual)

    assert snapshots["USDCAD"].regimes == ["RANGING", "LOW_VOLATILITY"]
    assert snapshots["USDCAD"].confidence == 0.72


def test_regime_classifier_detects_trend_and_volatility_from_ohlc() -> None:
    candles = [
        {"close": 100 + i, "high": 101 + i, "low": 99 + i}
        for i in range(40)
    ]

    snapshot = classify_regime("NAS100", candles=candles)

    assert "TRENDING_UP" in snapshot.regimes
    assert snapshot.confidence > 0
