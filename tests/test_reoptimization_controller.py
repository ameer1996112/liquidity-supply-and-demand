from scripts.optimizer.reoptimization_controller import should_reoptimize


def test_reoptimization_requires_verified_decay_not_single_loss() -> None:
    decision = should_reoptimize(
        {
            "symbol": "USDJPY",
            "state": "ACTIVE",
            "bad_day_count": 1,
            "verified_decay_reasons": [],
        }
    )

    assert decision["decision"] == "do_not_reoptimize"
    assert "no_verified_decay" in decision["reasons"]

    decision = should_reoptimize(
        {
            "symbol": "USDJPY",
            "state": "WATCH_ONLY",
            "verified_decay_reasons": ["latest_30d_validation_failed", "forward_pf_below_1_after_30_trades"],
        }
    )

    assert decision["decision"] == "reoptimize"
