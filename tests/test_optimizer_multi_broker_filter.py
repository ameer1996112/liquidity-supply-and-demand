from __future__ import annotations

import json

from scripts.optimizer import robust_broker_filter


def broker_row(**overrides):
    row = {
        "status": "completed",
        "net_profit": 500.0,
        "profit_factor": 1.08,
        "total_trades": 18,
        "max_drawdown_pct": 3.0,
    }
    row.update(overrides)
    return row


def result_row(**broker_overrides):
    brokers = {
        "vantage": broker_row(),
        "oanda": broker_row(),
        "fxcm": broker_row(),
    }
    for broker, overrides in broker_overrides.items():
        if overrides is None:
            brokers.pop(broker, None)
        else:
            brokers[broker] = broker_row(**overrides)
    return {
        "status": "completed",
        "params": {"risk_per_trade_pct": 0.5},
        "brokers": brokers,
    }


def test_multi_broker_filter_passes_only_when_all_required_brokers_pass() -> None:
    passed, rejected = robust_broker_filter.evaluate_broker_candidates(
        {"USDCAD": result_row()},
        required_brokers=["vantage", "oanda", "fxcm"],
    )

    assert list(passed) == ["USDCAD"]
    assert rejected == {}


def test_multi_broker_filter_rejects_missing_broker() -> None:
    passed, rejected = robust_broker_filter.evaluate_broker_candidates(
        {"USDCAD": result_row(fxcm=None)},
        required_brokers=["vantage", "oanda", "fxcm"],
    )

    assert passed == {}
    assert rejected["USDCAD"]["fxcm"] == ["missing_broker"]


def test_multi_broker_filter_rejects_failed_or_weak_broker_metrics() -> None:
    passed, rejected = robust_broker_filter.evaluate_broker_candidates(
        {
            "USDCAD": result_row(oanda={"status": "failed"}),
            "EURUSD": result_row(fxcm={"profit_factor": 1.01, "total_trades": 4}),
        },
        required_brokers=["vantage", "oanda", "fxcm"],
    )

    assert passed == {}
    assert rejected["USDCAD"]["oanda"] == ["status=failed"]
    assert "pf=1.01 < 1.05" in rejected["EURUSD"]["fxcm"]
    assert "trades=4 < 10" in rejected["EURUSD"]["fxcm"]


def test_multi_broker_filter_uses_stronger_thresholds_for_365d() -> None:
    passed, rejected = robust_broker_filter.evaluate_broker_candidates(
        {"USDCAD": result_row()},
        required_brokers=["vantage", "oanda", "fxcm"],
        backtest_range="365d",
    )

    assert passed == {}
    assert "pf=1.08 < 1.1" in rejected["USDCAD"]["vantage"]
    assert "trades=18 < 30" in rejected["USDCAD"]["vantage"]


def test_multi_broker_filter_writes_passed_and_rejected_files(tmp_path) -> None:
    input_path = tmp_path / "broker_check.json"
    passed_path = tmp_path / "robust_broker_passed.json"
    rejected_path = tmp_path / "robust_broker_rejected.json"
    input_path.write_text(
        json.dumps(
            {
                "USDCAD": result_row(),
                "NAS100": result_row(oanda={"net_profit": -1}),
            }
        )
    )

    robust_broker_filter.main(
        input_path=input_path,
        output_passed_path=passed_path,
        output_rejected_path=rejected_path,
        required_brokers=["vantage", "oanda", "fxcm"],
    )

    passed = json.loads(passed_path.read_text())
    rejected = json.loads(rejected_path.read_text())
    assert list(passed) == ["USDCAD"]
    assert "NAS100" in rejected


def test_multi_broker_cli_writes_outputs(tmp_path) -> None:
    input_path = tmp_path / "broker_check.json"
    input_path.write_text(json.dumps({"USDCAD": result_row()}))

    robust_broker_filter.cli(
        [
            "--input",
            str(input_path),
            "--brokers",
            "vantage,oanda,fxcm",
            "--output-passed",
            str(tmp_path / "passed.json"),
            "--output-rejected",
            str(tmp_path / "rejected.json"),
        ]
    )

    assert (tmp_path / "passed.json").exists()
    assert (tmp_path / "rejected.json").exists()
