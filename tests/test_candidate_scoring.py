from scripts.optimizer.candidate_scoring import score_candidate


def test_candidate_scoring_penalizes_weak_recent_30d() -> None:
    strong = score_candidate(
        "USDCAD",
        windows={
            "365d": {"profit_factor": 1.4, "net_profit": 2000, "max_drawdown_pct": 3, "total_trades": 100},
            "90d": {"profit_factor": 1.3, "net_profit": 500, "max_drawdown_pct": 2, "total_trades": 30},
            "30d": {"profit_factor": 1.2, "net_profit": 100, "max_drawdown_pct": 1, "total_trades": 10},
        },
    )
    weak_recent = score_candidate(
        "USDCAD",
        windows={
            "365d": {"profit_factor": 1.8, "net_profit": 5000, "max_drawdown_pct": 2, "total_trades": 100},
            "90d": {"profit_factor": 1.4, "net_profit": 700, "max_drawdown_pct": 2, "total_trades": 30},
            "30d": {"profit_factor": 0.98, "net_profit": -10, "max_drawdown_pct": 3, "total_trades": 4},
        },
    )

    assert weak_recent["final_score"] < strong["final_score"]
    assert "weak_recent_30d" in weak_recent["penalties"]
