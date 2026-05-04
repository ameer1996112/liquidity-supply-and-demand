from scripts.optimizer.models import BacktestResult
from scripts.optimizer.parallel_runner import _result_metrics
from scripts.optimizer.result_truth import ResultTruth


def test_parallel_runner_preserves_validation_result_truth() -> None:
    truth = ResultTruth.production(
        stage="validation",
        params={"risk_per_trade_pct": 0.5},
        requested_symbol="USDCAD",
        requested_broker="VANTAGE",
        requested_range="365d",
        source_params_digest="abc123",
    )
    for check in (
        "symbol_loaded",
        "broker_loaded",
        "strategy_tester_range_selected",
        "params_applied",
        "frozen_params_applied",
        "dialog_params_matched",
        "tv_recalculated",
        "result_hash_captured",
        "metrics_tab_selected",
        "source_params_digest_preserved",
    ):
        truth.record(check, "ok")
    result = BacktestResult(
        symbol="USDCAD",
        params={"risk_per_trade_pct": 0.5},
        total_trades=60,
        profit_factor=1.25,
        net_profit=1000,
        max_drawdown=100,
        max_drawdown_pct=2.0,
        result_truth=truth,
    )

    payload = _result_metrics(result, worker_id=7)

    assert payload["result_truth"]["stage"] == "validation"
    assert payload["result_truth"]["source_params_digest"] == "abc123"
    assert payload["trust_status"] == "trusted"
