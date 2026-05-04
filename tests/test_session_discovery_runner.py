from scripts.optimizer.session_discovery_runner import evaluate_session_discovery


def test_session_discovery_selects_best_trusted_session() -> None:
    report = evaluate_session_discovery(
        "USDJPY",
        {
            "asia": {
                "net_profit": 100,
                "profit_factor": 1.05,
                "total_trades": 20,
                "max_drawdown_pct": 1.0,
                "safe_max_dd_pct": 5.0,
                "result_truth": {"status": "trusted"},
            },
            "london": {
                "net_profit": 500,
                "profit_factor": 1.4,
                "total_trades": 30,
                "max_drawdown_pct": 2.0,
                "safe_max_dd_pct": 5.0,
                "result_truth": {"status": "trusted"},
            },
        },
        min_trades=10,
    )

    assert report["status"] == "passed"
    assert report["best_session"] == "london"
    assert report["sessions"]["london"]["status"] == "passed"
