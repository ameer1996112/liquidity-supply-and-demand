from scripts.optimizer.trade_count_anomaly import detect_trade_count_anomaly


def test_detects_large_trade_density_anomaly() -> None:
    anomaly = detect_trade_count_anomaly(
        {
            "365d": {"total_trades": 400},
            "90d": {"total_trades": 15},
            "30d": {"total_trades": 50},
        }
    )

    assert anomaly is not None
    assert anomaly["status"] == "unexplained"
    assert anomaly["high_window"] == "30d"
    assert anomaly["low_window"] == "90d"


def test_explained_trade_count_anomaly_is_accepted() -> None:
    anomaly = detect_trade_count_anomaly(
        {
            "365d": {
                "total_trades": 400,
                "result_truth": {
                    "evidence": {
                        "trade_count_anomaly_explained": {
                            "status": "ok",
                            "details": {"reason": "verified coverage"},
                        }
                    }
                },
            },
            "90d": {"total_trades": 15},
            "30d": {"total_trades": 50},
        }
    )

    assert anomaly is None
