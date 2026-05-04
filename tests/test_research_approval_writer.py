from scripts.optimizer.research_approval_writer import build_approved_candidates


def _passed_gate(params_hash: str = "abc123") -> dict:
    return {
        "symbol": "USDJPY",
        "broker": "vantage",
        "timeframe": "5m",
        "asset_class": "forex_jpy",
        "params_hash": params_hash,
        "params": {"risk_per_trade_pct": 0.25, "max_trades_per_day": 1},
        "allowed_sessions_utc": [{"name": "asia_london", "start": 0, "end": 9}],
        "scores": {
            "walk_forward_pass_rate_pct": 70,
            "cross_val_median_pf": 1.31,
            "stability_score_pct": 84,
            "prop_survival_score_pct": 72,
        },
        "strategy_fidelity_status": "passed",
        "result_truth_status": "trusted",
        "walk_forward_status": "passed",
        "frozen_validation_status": "passed",
        "parameter_stability_status": "passed",
        "stress_test_status": "passed",
        "prop_survival_status": "passed",
        "broker_filter_status": "passed",
        "human_review_status": "reviewed",
        "anomaly_status": "passed",
    }


def test_approval_requires_every_research_gate() -> None:
    good, rejected = build_approved_candidates([_passed_gate()], generated_at="2026-05-04T02:00:00Z")

    assert "USDJPY" in good["candidates"]
    assert rejected == {}
    assert good["candidates"]["USDJPY"]["candidate_status"] == "RESEARCH_APPROVED"

    bad = _passed_gate()
    bad["result_truth_status"] = "untrusted"
    good, rejected = build_approved_candidates([bad], generated_at="2026-05-04T02:00:00Z")

    assert good["candidates"] == {}
    assert rejected["USDJPY"] == ["result_truth_status=untrusted"]
