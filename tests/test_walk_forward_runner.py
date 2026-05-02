from scripts.optimizer.walk_forward_runner import evaluate_walk_forward


def test_walk_forward_rejects_low_pass_rate() -> None:
    report = evaluate_walk_forward(
        "USDCAD",
        [
            {"status": "passed", "profit_factor": 1.2, "net_profit": 100, "max_drawdown_pct": 2},
            {"status": "failed", "profit_factor": 0.8, "net_profit": -200, "max_drawdown_pct": 7},
            {"status": "failed", "profit_factor": 1.1, "net_profit": 50, "max_drawdown_pct": 2},
        ],
        profile={"safe_max_dd_pct": 6.5, "safe_daily_loss_pct": 3.0},
    )

    assert report["status"] == "rejected"
    assert "fold_pass_rate_below_0.60" in report["rejection_reasons"]


def test_walk_forward_passes_stable_folds() -> None:
    report = evaluate_walk_forward(
        "USDCAD",
        [
            {"status": "passed", "profit_factor": 1.2, "net_profit": 100, "max_drawdown_pct": 2},
            {"status": "passed", "profit_factor": 1.15, "net_profit": 80, "max_drawdown_pct": 3},
            {"status": "passed", "profit_factor": 1.12, "net_profit": 50, "max_drawdown_pct": 2},
        ],
        profile={"safe_max_dd_pct": 6.5, "safe_daily_loss_pct": 3.0},
    )

    assert report["status"] == "passed"
