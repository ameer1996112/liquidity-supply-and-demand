from scripts.optimizer.candidate_decay_controller import evaluate_candidate_decay


def test_latest_30d_failure_downgrades_active_candidate() -> None:
    decision = evaluate_candidate_decay(
        {
            "symbol": "USDJPY",
            "state": "ACTIVE",
            "latest_30d_status": "failed",
            "latest_90d_status": "passed",
            "forward_pf": 1.2,
            "forward_trade_count": 30,
        }
    )

    assert decision["new_state"] == "WATCH_ONLY"
    assert "latest_30d_validation_failed" in decision["reasons"]


def test_one_bad_day_does_not_trigger_reoptimization() -> None:
    decision = evaluate_candidate_decay(
        {
            "symbol": "USDJPY",
            "state": "ACTIVE",
            "bad_day_count": 1,
            "latest_30d_status": "passed",
            "latest_90d_status": "passed",
            "forward_pf": 1.2,
            "forward_trade_count": 30,
        }
    )

    assert decision["new_state"] == "ACTIVE"
    assert "one_bad_day_is_not_decay" in decision["reasons"]
