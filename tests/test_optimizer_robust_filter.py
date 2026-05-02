from __future__ import annotations

import json

import pytest

from scripts.optimizer.models import BacktestResult
from scripts.optimizer.optimizer import deployment_candidate_score
from scripts.optimizer import robust_filter


def test_deployment_candidate_score_rejects_weak_single_window_results() -> None:
    result = BacktestResult(
        symbol="NAS100",
        params={},
        net_profit=900.0,
        total_trades=80,
        profit_factor=1.06,
        max_drawdown_pct=3.2,
        score=14.0,
    )

    assert deployment_candidate_score(result, dd_limit=8.0) == 0.0


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


def test_robust_filter_requires_all_windows_to_pass() -> None:
    all_results = {
        "365d": {
            "USDCAD": {
                "status": "completed",
                "net_profit": 7517,
                "profit_factor": 1.31,
                "total_trades": 125,
                "max_drawdown_pct": 6.0,
                "params": {"risk_per_trade_pct": 0.5},
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
                "params": {"risk_per_trade_pct": 0.5},
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
                "params": {"risk_per_trade_pct": 0.5},
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
    assert passed[0]["params"] == {"risk_per_trade_pct": 0.5}
    assert "NAS100" in rejected
    assert "30d" in rejected["NAS100"]
    assert any("net_profit" in reason for reason in rejected["NAS100"]["30d"])


def test_robust_filter_main_writes_passed_candidates(tmp_path, monkeypatch) -> None:
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
                            "params": {"risk_per_trade_pct": 0.5},
                        }
                    }
                }
            )
        )
    output_path = tmp_path / "robust_passed.json"

    robust_filter.main(files=files, output_path=output_path)

    payload = json.loads(output_path.read_text())
    assert list(payload) == ["USDCAD"]
    assert payload["USDCAD"]["params"] == {"risk_per_trade_pct": 0.5}


def test_load_results_rejects_missing_file(tmp_path) -> None:
    with pytest.raises(FileNotFoundError):
        robust_filter.load_results(tmp_path / "missing.json")
