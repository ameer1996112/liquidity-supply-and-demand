from __future__ import annotations

import json
import os
import subprocess
import sys

import pytest

from scripts.optimizer.models import BacktestResult
from scripts.optimizer.optimizer import (
    deployment_candidate_score,
    futures_result_pass_prop_gate,
    params_pass_prop_safety_gate,
)
from scripts.optimizer import robust_filter


SAFE_PARAMS = {
    "risk_per_trade_pct": 0.5,
    "max_daily_loss_pct": 3.0,
    "daily_kill_pct": 3.5,
    "total_kill_pct": 6.5,
    "max_trades_per_day": 3,
}


def result(**overrides) -> BacktestResult:
    values = {
        "symbol": "USDCAD",
        "params": dict(SAFE_PARAMS),
        "net_profit": 1500.0,
        "total_trades": 60,
        "profit_factor": 1.22,
        "max_drawdown": 1100.0,
        "max_drawdown_pct": 5.5,
        "score": 12.5,
    }
    values.update(overrides)
    return BacktestResult(**values)


def test_deployment_candidate_score_accepts_strong_single_window_result() -> None:
    assert deployment_candidate_score(result(), dd_limit=8.0) == 12.5


def test_deployment_candidate_score_rejects_weak_single_window_results() -> None:
    weak = BacktestResult(
        symbol="NAS100",
        params={},
        net_profit=900.0,
        total_trades=80,
        profit_factor=1.06,
        max_drawdown_pct=3.2,
        score=14.0,
    )

    assert deployment_candidate_score(weak, dd_limit=8.0) == 0.0


def test_deployment_candidate_score_rejects_negative_net_profit() -> None:
    assert deployment_candidate_score(result(net_profit=-1), dd_limit=8.0) == 0.0


def test_deployment_candidate_score_rejects_too_few_trades() -> None:
    assert deployment_candidate_score(result(total_trades=39), dd_limit=8.0) == 0.0


def test_deployment_candidate_score_uses_safe_drawdown_buffer() -> None:
    result = BacktestResult(
        symbol="USDCAD",
        params={},
        net_profit=2200.0,
        total_trades=90,
        profit_factor=1.32,
        max_drawdown_pct=7.0,
        score=18.0,
    )

    assert deployment_candidate_score(result, dd_limit=10.0) == 0.0


def test_params_pass_prop_safety_gate_accepts_safe_values() -> None:
    ok, reasons = params_pass_prop_safety_gate(SAFE_PARAMS)

    assert ok is True
    assert reasons == []


@pytest.mark.parametrize(
    ("key", "value", "expected"),
    [
        ("risk_per_trade_pct", 0.51, "risk_per_trade_pct too high"),
        ("max_daily_loss_pct", 3.1, "max_daily_loss_pct too high"),
        ("daily_kill_pct", 3.6, "daily_kill_pct too high"),
        ("total_kill_pct", 6.6, "total_kill_pct too high"),
        ("max_trades_per_day", 4, "max_trades_per_day too high"),
    ],
)
def test_params_pass_prop_safety_gate_rejects_aggressive_values(
    key: str,
    value: float,
    expected: str,
) -> None:
    params = dict(SAFE_PARAMS)
    params[key] = value

    ok, reasons = params_pass_prop_safety_gate(params)

    assert ok is False
    assert any(reason.startswith(expected) for reason in reasons)


def test_futures_profile_uses_dollar_drawdown_gate() -> None:
    future = result(symbol="NQ", max_drawdown=1199, max_drawdown_pct=20.0)

    ok, reasons = futures_result_pass_prop_gate(future, profile="topstep_50k")

    assert ok is True
    assert reasons == []


def test_futures_profile_rejects_missing_or_excessive_dollar_drawdown() -> None:
    missing = result(symbol="MNQ", max_drawdown=0, max_drawdown_pct=1.0)
    excessive = result(symbol="MNQ", max_drawdown=1500, max_drawdown_pct=1.0)

    assert futures_result_pass_prop_gate(missing, profile="topstep_50k")[0] is False
    ok, reasons = futures_result_pass_prop_gate(excessive, profile="topstep_50k")
    assert ok is False
    assert reasons == ["max_drawdown_usd=1500.0 > safe_max_loss_usd=1200.0"]


def test_robust_filter_requires_all_windows_to_pass() -> None:
    all_results = {
        "365d": {
            "USDCAD": {
                "status": "completed",
                "net_profit": 7517,
                "profit_factor": 1.31,
                "total_trades": 125,
                "max_drawdown_pct": 6.0,
                "params": dict(SAFE_PARAMS),
            },
            "NAS100": {
                "status": "completed",
                "net_profit": 100,
                "profit_factor": 1.06,
                "total_trades": 80,
                "max_drawdown_pct": 7.13,
                "params": {},
            },
        },
        "90d": {
            "USDCAD": {
                "status": "completed",
                "net_profit": 1200,
                "profit_factor": 1.18,
                "total_trades": 28,
                "max_drawdown_pct": 3.2,
                "params": dict(SAFE_PARAMS),
            },
            "NAS100": {
                "status": "completed",
                "net_profit": 200,
                "profit_factor": 1.16,
                "total_trades": 25,
                "max_drawdown_pct": 3.1,
                "params": {},
            },
        },
        "30d": {
            "USDCAD": {
                "status": "completed",
                "net_profit": 250,
                "profit_factor": 1.08,
                "total_trades": 8,
                "max_drawdown_pct": 1.4,
                "params": dict(SAFE_PARAMS),
            },
            "NAS100": {
                "status": "completed",
                "net_profit": -20,
                "profit_factor": 0.98,
                "total_trades": 6,
                "max_drawdown_pct": 1.8,
                "params": {},
            },
        },
    }

    passed, rejected = robust_filter.evaluate_candidates(all_results)

    assert [candidate["symbol"] for candidate in passed] == ["USDCAD"]
    assert passed[0]["params"] == SAFE_PARAMS
    assert set(passed[0]["windows"]) == {"365d", "90d", "30d"}
    assert "NAS100" in rejected
    assert "30d" in rejected["NAS100"]
    assert any("net_profit" in reason for reason in rejected["NAS100"]["30d"])


def test_robust_filter_rejects_missing_symbol_and_missing_params() -> None:
    valid = {
        "status": "completed",
        "net_profit": 1000,
        "profit_factor": 1.25,
        "total_trades": 60,
        "max_drawdown_pct": 2.0,
        "params": dict(SAFE_PARAMS),
    }
    all_results = {
        "365d": {"USDCAD": dict(valid), "EURUSD": {**valid, "params": {}}},
        "90d": {"USDCAD": dict(valid), "EURUSD": dict(valid)},
        "30d": {"EURUSD": dict(valid)},
    }

    passed, rejected = robust_filter.evaluate_candidates(all_results)

    assert passed == []
    assert rejected["USDCAD"]["30d"] == ["missing_window"]
    assert "missing_params" in rejected["EURUSD"]["365d"]


@pytest.mark.parametrize(
    ("field", "value", "reason"),
    [
        ("status", "failed", "status=failed"),
        ("profit_factor", 1.01, "pf=1.01 < 1.2"),
        ("max_drawdown_pct", 6.6, "dd=6.6 > 6.5"),
        ("total_trades", 49, "trades=49 < 50"),
    ],
)
def test_robust_filter_rejects_weak_365d_metrics(
    field: str,
    value: object,
    reason: str,
) -> None:
    valid = {
        "status": "completed",
        "net_profit": 1000,
        "profit_factor": 1.25,
        "total_trades": 60,
        "max_drawdown_pct": 2.0,
        "params": dict(SAFE_PARAMS),
    }
    weak = dict(valid)
    weak[field] = value

    _passed, rejected = robust_filter.evaluate_candidates(
        {
            "365d": {"USDCAD": weak},
            "90d": {"USDCAD": dict(valid)},
            "30d": {"USDCAD": dict(valid)},
        }
    )

    assert reason in rejected["USDCAD"]["365d"]


def test_robust_filter_main_writes_passed_and_rejected_candidates(tmp_path) -> None:
    files = {}
    for window in ("365d", "90d", "30d"):
        path = tmp_path / f"{window}.json"
        files[window] = path
        path.write_text(
            json.dumps(
                {
                    "results": {
                        "USDCAD": {
                            "status": "completed",
                            "net_profit": 1000,
                            "profit_factor": 1.25,
                            "total_trades": 60,
                            "max_drawdown_pct": 2.0,
                            "params": dict(SAFE_PARAMS),
                        },
                        "NAS100": {
                            "status": "completed",
                            "net_profit": -1,
                            "profit_factor": 0.9,
                            "total_trades": 60,
                            "max_drawdown_pct": 2.0,
                            "params": dict(SAFE_PARAMS),
                        }
                    }
                }
            )
        )
    output_path = tmp_path / "robust_passed.json"
    rejected_path = tmp_path / "robust_rejected.json"

    robust_filter.main(files=files, output_passed_path=output_path, output_rejected_path=rejected_path)

    payload = json.loads(output_path.read_text())
    assert list(payload) == ["USDCAD"]
    assert payload["USDCAD"]["params"] == SAFE_PARAMS
    assert set(payload["USDCAD"]["windows"]) == {"365d", "90d", "30d"}
    rejected = json.loads(rejected_path.read_text())
    assert "NAS100" in rejected


def test_robust_filter_direct_script_runs_without_pythonpath(tmp_path) -> None:
    for window in ("365d", "90d", "30d"):
        (tmp_path / f"{window}.json").write_text(
            json.dumps(
                {
                    "USDCAD": {
                        "status": "completed",
                        "net_profit": 1000,
                        "profit_factor": 1.25,
                        "total_trades": 60,
                        "max_drawdown_pct": 2.0,
                        "params": dict(SAFE_PARAMS),
                    }
                }
            )
        )
    env = dict(os.environ)
    env.pop("PYTHONPATH", None)

    result = subprocess.run(
        [
            sys.executable,
            "scripts/optimizer/robust_filter.py",
            "--results-dir",
            str(tmp_path),
            "--file-365d",
            "365d.json",
            "--file-90d",
            "90d.json",
            "--file-30d",
            "30d.json",
        ],
        cwd=robust_filter.RESULTS_DIR.parent.parent,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert (tmp_path / "robust_passed.json").exists()


def test_robust_filter_cli_uses_named_input_files(tmp_path) -> None:
    for window in ("365d", "90d", "30d"):
        (tmp_path / f"{window}.json").write_text(
            json.dumps(
                {
                    "USDCAD": {
                        "status": "completed",
                        "net_profit": 1000,
                        "profit_factor": 1.25,
                        "total_trades": 60,
                        "max_drawdown_pct": 2.0,
                        "params": dict(SAFE_PARAMS),
                    }
                }
            )
        )
    robust_filter.cli(
        [
            "--results-dir",
            str(tmp_path),
            "--file-365d",
            "365d.json",
            "--file-90d",
            "90d.json",
            "--file-30d",
            "30d.json",
            "--output-passed",
            "passed.json",
            "--output-rejected",
            "rejected.json",
        ]
    )

    assert (tmp_path / "passed.json").exists()
    assert (tmp_path / "rejected.json").exists()


def test_load_results_rejects_missing_file(tmp_path) -> None:
    with pytest.raises(FileNotFoundError):
        robust_filter.load_results(tmp_path / "missing.json")
