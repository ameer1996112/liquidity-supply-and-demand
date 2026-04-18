from __future__ import annotations

from src.services.optimizer_survival_scoring import classify_pair_result


def test_classify_pair_result_rejects_failed_forward_gate() -> None:
    decision = classify_pair_result(
        forward_metrics={
            "max_drawdown_pct": 6.4,
            "max_daily_loss_pct": 2.1,
            "net_profit": 400,
            "profit_factor": 1.2,
            "total_trades": 20,
        },
        stress_metrics=[{"status": "passed", "metrics": {"max_drawdown_pct": 5.9}}],
        pair_dd_limit=6.0,
        pair_daily_limit=3.0,
    )

    assert decision["status"] == "REJECT"
    assert "forward" in decision["reason"].lower()


def test_classify_pair_result_reduces_risk_when_stress_breaks_tolerance() -> None:
    decision = classify_pair_result(
        forward_metrics={
            "max_drawdown_pct": 4.5,
            "max_daily_loss_pct": 1.8,
            "net_profit": 900,
            "profit_factor": 1.35,
            "total_trades": 26,
        },
        stress_metrics=[{"status": "failed", "metrics": {"max_drawdown_pct": 6.5}}],
        pair_dd_limit=6.0,
        pair_daily_limit=3.0,
    )

    assert decision["status"] == "REDUCE_RISK"
    assert "stress" in decision["reason"].lower()


def test_classify_pair_result_passes_when_forward_and_stress_gates_hold() -> None:
    decision = classify_pair_result(
        forward_metrics={
            "max_drawdown_pct": 4.2,
            "max_daily_loss_pct": 1.4,
            "net_profit": 1250,
            "profit_factor": 1.4,
            "total_trades": 32,
        },
        stress_metrics=[
            {"status": "passed", "metrics": {"max_drawdown_pct": 5.4}},
            {"status": "passed", "metrics": {"max_drawdown_pct": 5.8}},
        ],
        pair_dd_limit=6.0,
        pair_daily_limit=3.0,
    )

    assert decision["status"] == "PASS"
    assert "passed" in decision["reason"].lower()
