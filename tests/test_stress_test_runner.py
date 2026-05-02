from scripts.optimizer.stress_test_runner import evaluate_stress_tests


def test_stress_test_rejects_spread_fragile_candidate() -> None:
    report = evaluate_stress_tests(
        "XAUUSD",
        base_metrics={"net_profit": 1000, "profit_factor": 1.2, "max_drawdown_pct": 3.0},
        stress_metrics={"spread_increase": {"net_profit": -50, "profit_factor": 0.95}},
        profile={"safe_max_dd_pct": 6.5},
    )

    assert report["status"] == "rejected"
    assert "spread_increase_pf_below_1.0" in report["rejection_reasons"]


def test_stress_test_marks_unavailable_without_trade_list() -> None:
    report = evaluate_stress_tests(
        "USDCAD",
        base_metrics={"net_profit": 1000, "profit_factor": 1.2, "max_drawdown_pct": 3.0},
        stress_metrics={},
        profile={"safe_max_dd_pct": 6.5},
    )

    assert report["status"] == "watch_only"
    assert "trade_list_unavailable" in report["warnings"]
