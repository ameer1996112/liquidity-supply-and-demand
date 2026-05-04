import json

from scripts.optimizer.trade_export_ingestor import ingest_trade_export


def test_trade_export_ingestor_requires_trade_level_fields(tmp_path) -> None:
    path = tmp_path / "trades.json"
    path.write_text(
        json.dumps(
            [
                {
                    "symbol": "USDJPY",
                    "broker": "vantage",
                    "params_hash": "abc123",
                    "entry_time": "2026-04-01T08:30:00Z",
                    "exit_time": "2026-04-01T09:15:00Z",
                    "direction": "short",
                    "profit_usd": 125.0,
                    "profit_r": 2.5,
                    "max_drawdown_usd": 60.0,
                    "session": "london",
                    "spread": 0.8,
                    "slippage": 0.2,
                },
                {"symbol": "XAUUSD"},
            ]
        )
    )

    report = ingest_trade_export(path)

    assert report["status"] == "watch_only"
    assert report["precision"] == "approximate"
    assert len(report["trades"]) == 1
    assert "broker" in report["rejected_rows"][0]["missing_fields"]
