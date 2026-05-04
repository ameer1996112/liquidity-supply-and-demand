from scripts.optimizer.nested_walk_forward_runner import evaluate_walk_forward


def test_nested_walk_forward_rejects_catastrophic_fold() -> None:
    report = evaluate_walk_forward(
        "USDJPY",
        [
            {"status": "passed", "profit_factor": 1.2, "net_profit": 100, "max_drawdown_pct": 2.0},
            {"status": "passed", "profit_factor": 0.8, "net_profit": -20, "max_drawdown_pct": 7.0},
            {"status": "passed", "profit_factor": 1.2, "net_profit": 100, "max_drawdown_pct": 2.0},
        ],
        {"safe_max_dd_pct": 5.0, "safe_daily_loss_pct": 2.0, "max_loss_pct": 10.0},
    )

    assert report["status"] == "rejected"
    assert "catastrophic_fold" in report["rejection_reasons"]
