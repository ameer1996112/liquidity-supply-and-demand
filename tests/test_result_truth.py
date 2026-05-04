from scripts.optimizer.result_truth import ResultTruth, params_digest
from scripts.optimizer.robust_filter import pass_window


def _trusted_truth() -> ResultTruth:
    truth = ResultTruth.production(
        stage="trial",
        params={"risk_per_trade_pct": 0.5},
        requested_symbol="USDCAD",
        requested_broker="VANTAGE",
        requested_range="365d",
    )
    for check in (
        "symbol_loaded",
        "broker_loaded",
        "strategy_tester_range_selected",
        "params_applied",
        "dialog_params_matched",
        "tv_recalculated",
        "result_hash_captured",
        "metrics_tab_selected",
    ):
        truth.record(check, "ok")
    return truth


def test_params_digest_is_stable_for_key_order() -> None:
    assert params_digest({"b": 2, "a": 1}) == params_digest({"a": 1, "b": 2})


def test_missing_hash_or_recalc_proof_makes_result_untrusted() -> None:
    truth = _trusted_truth()
    truth.evidence.pop("result_hash_captured")

    payload = truth.to_dict()

    assert payload["trust_status"] == "untrusted"
    assert "result_hash_captured" in payload["missing_evidence"]


def test_failed_range_verification_rejects_result() -> None:
    truth = _trusted_truth()
    truth.record(
        "strategy_tester_range_selected",
        "fail",
        reason="Strategy Tester range did not match requested range",
    )

    payload = truth.to_dict()

    assert payload["trust_status"] == "rejected"
    assert any("strategy_tester_range_selected" in reason for reason in payload["rejection_reasons"])


def test_validate_mode_requires_source_params_digest() -> None:
    truth = ResultTruth.production(
        stage="validation",
        params={"risk_per_trade_pct": 0.5},
        requested_symbol="USDCAD",
        requested_broker="VANTAGE",
        requested_range="365d",
    )

    payload = truth.to_dict()

    assert payload["trust_status"] == "untrusted"
    assert "source_params_digest_preserved" in payload["missing_evidence"]


def test_missing_result_truth_prevents_robust_filter_pass() -> None:
    ok, reasons = pass_window(
        {
            "status": "completed",
            "net_profit": 1000,
            "profit_factor": 1.25,
            "total_trades": 60,
            "max_drawdown_pct": 2.0,
            "params": {"risk_per_trade_pct": 0.5},
        },
        "365d",
    )

    assert ok is False
    assert "missing_result_truth" in reasons
