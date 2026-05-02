from scripts.optimizer.forward_test_tracker import summarize_forward_tests


def test_forward_test_does_not_promote_low_sample_size() -> None:
    report = summarize_forward_tests(
        [
            {"date": "2026-05-01", "symbol": "USDCAD", "profit_loss": 10, "rule_breach": False}
            for _ in range(5)
        ],
        symbol="USDCAD",
    )

    assert report["status"] == "WATCH_ONLY"
    assert "minimum_20_trades_not_met" in report["rejection_reasons"]
