import json

from scripts.optimizer.production_pair_pipeline import run_pipeline


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
