import json

from scripts.optimizer.robust_pipeline import run_pipeline


def test_pipeline_writes_status_and_summary_files(tmp_path) -> None:
    result = run_pipeline(
        pairs=["USDCAD"],
        broker="vantage",
        brokers=["vantage", "oanda", "fxcm"],
        prop_profile_name="generic_cfd_safe",
        results_dir=tmp_path,
        run_selector=True,
    )

    assert result["status"] in {"completed", "completed_with_no_trade"}
    assert (tmp_path / "pipeline_status.json").exists()
    assert (tmp_path / "pipeline_summary.json").exists()
    assert (tmp_path / "pipeline_errors.json").exists()
    summary = json.loads((tmp_path / "pipeline_summary.json").read_text())
    assert summary["schema_version"] == 1
