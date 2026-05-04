import json
import asyncio

from src import api_dashboard
from scripts.optimizer.production_pair_pipeline import run_pipeline


NO_TRADE_REASONS = [
    "no_research_approved_candidates",
    "strategy_fidelity_not_proven",
    "result_truth_not_available",
    "trade_level_stress_not_available",
    "prop_survival_not_available",
]


def test_pipeline_dry_run_writes_status_files(tmp_path) -> None:
    result = run_pipeline(
        pairs=["USDJPY"],
        broker="vantage",
        brokers=["vantage"],
        prop_profile="alpha_50k_safe",
        timeframe="5m",
        results_dir=tmp_path,
        dry_run=True,
        run_daily_permissions=True,
    )

    assert result["status"] == "completed"
    assert (tmp_path / "pipeline_status.json").exists()
    assert (tmp_path / "pipeline_summary.json").exists()
    assert (tmp_path / "daily_trade_permissions.json").exists()
    assert json.loads((tmp_path / "daily_trade_permissions.json").read_text())["global_decision"] == "NO_TRADE"


def test_pipeline_writes_empty_approved_candidates_on_no_trade(tmp_path) -> None:
    run_pipeline(
        pairs=["USDJPY"],
        broker="vantage",
        brokers=["vantage"],
        prop_profile="alpha_50k_safe",
        timeframe="5m",
        results_dir=tmp_path,
        dry_run=True,
        write_approved_candidates_flag=True,
        run_daily_permissions=True,
    )

    approved = json.loads((tmp_path / "approved_candidates.json").read_text())

    assert approved["schema_version"] == 1
    assert approved["human_review_required"] is True
    assert approved["global_status"] == "NO_RESEARCH_APPROVED_CANDIDATES"
    assert approved["candidates"] == {}
    assert approved["rejected"] == {}
    assert approved["warnings"] == [
        "No candidates approved because this was a dry run or required proof artifacts were missing."
    ]


def test_pipeline_summary_contains_no_trade_reasons(tmp_path) -> None:
    run_pipeline(
        pairs=["USDJPY"],
        broker="vantage",
        brokers=["vantage"],
        prop_profile="alpha_50k_safe",
        timeframe="5m",
        results_dir=tmp_path,
        dry_run=True,
        write_approved_candidates_flag=True,
        run_daily_permissions=True,
    )

    summary = json.loads((tmp_path / "pipeline_summary.json").read_text())
    daily = json.loads((tmp_path / "daily_trade_permissions.json").read_text())

    assert summary["global_decision"] == "NO_TRADE"
    assert summary["no_trade_reasons"] == NO_TRADE_REASONS
    assert daily["reasons"] == NO_TRADE_REASONS


def test_dashboard_handles_empty_approved_candidates(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(api_dashboard, "OPTIMIZATION_RESULTS_DIR", tmp_path)
    (tmp_path / "approved_candidates.json").write_text(
        json.dumps(
            {
                "schema_version": 1,
                "generated_at": "2026-05-05T06:00:00Z",
                "human_review_required": True,
                "global_status": "NO_RESEARCH_APPROVED_CANDIDATES",
                "candidates": {},
                "rejected": {},
                "warnings": [
                    "No candidates approved because this was a dry run or required proof artifacts were missing."
                ],
            }
        )
    )
    (tmp_path / "daily_trade_permissions.json").write_text(
        json.dumps(
            {
                "schema_version": 1,
                "generated_at": "2026-05-05T06:00:00Z",
                "account_profile": "alpha_50k_safe",
                "global_decision": "NO_TRADE",
                "permissions": {},
                "blocked": {},
                "watch_only": {},
                "reasons": NO_TRADE_REASONS,
            }
        )
    )

    payload = asyncio.run(api_dashboard.get_trade_permissions_dashboard())

    assert payload["global_decision"] == "NO_TRADE"
    assert payload["allowed_today"] == {}
    assert payload["research_approved_candidates"] == {}
    assert payload["no_trade_reasons"] == NO_TRADE_REASONS
