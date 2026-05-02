from scripts.optimizer.parameter_stability_tester import evaluate_stability, generate_neighbor_params


def test_parameter_stability_rejects_isolated_exact_fit_params() -> None:
    report = evaluate_stability(
        "USDCAD",
        original={"profit_factor": 1.5, "max_drawdown_pct": 2.0},
        neighbor_results=[
            {"net_profit": -10, "profit_factor": 0.9, "max_drawdown_pct": 5.0}
            for _ in range(20)
        ],
    )

    assert report["status"] == "rejected"
    assert "profitable_neighbor_rate_below_0.40" in report["rejection_reasons"]


def test_generate_neighbor_params_changes_numeric_values() -> None:
    variants = generate_neighbor_params({"risk_reward_ratio": 3.0, "trading_start_hour": 7}, limit=6)

    assert len(variants) == 6
    assert any(row["risk_reward_ratio"] != 3.0 for row in variants)
