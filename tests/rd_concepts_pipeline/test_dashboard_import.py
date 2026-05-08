import importlib


def test_dashboard_import_exposes_loader() -> None:
    module = importlib.import_module("scripts.rd_concepts_pipeline.dashboard")

    assert hasattr(module, "load_processed_data")
