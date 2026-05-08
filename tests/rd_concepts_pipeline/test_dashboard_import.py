import importlib
import json
from pathlib import Path

import pandas as pd


def test_dashboard_import_exposes_loader() -> None:
    module = importlib.import_module("scripts.rd_concepts_pipeline.dashboard")

    assert hasattr(module, "load_processed_data")


def test_load_processed_data_returns_empty_defaults_for_missing_files(
    tmp_path: Path,
) -> None:
    module = importlib.import_module("scripts.rd_concepts_pipeline.dashboard")

    signals, rules, knowledge_base, image_index = module.load_processed_data(tmp_path)

    assert isinstance(signals, pd.DataFrame)
    assert signals.empty
    assert rules == []
    assert knowledge_base == {}
    assert isinstance(image_index, pd.DataFrame)
    assert image_index.empty


def test_load_processed_data_ignores_malformed_artifacts(tmp_path: Path) -> None:
    module = importlib.import_module("scripts.rd_concepts_pipeline.dashboard")
    processed_dir = tmp_path / "processed"
    processed_dir.mkdir()
    (processed_dir / "signals.csv").write_bytes(b"\xff\xfe\x00bad csv")
    (processed_dir / "image_index.csv").write_bytes(b"\xff\xfe\x00bad csv")
    (processed_dir / "rules.jsonl").write_text(
        '{"rule": "valid"}\n{bad json}\n',
        encoding="utf-8",
    )
    (processed_dir / "knowledge_base.json").write_text(
        json.dumps(["not", "a", "dict"]),
        encoding="utf-8",
    )

    signals, rules, knowledge_base, image_index = module.load_processed_data(tmp_path)

    assert signals.empty
    assert rules == []
    assert knowledge_base == {}
    assert image_index.empty


def test_safe_image_path_rejects_unsafe_paths_and_accepts_data_dir_image(
    tmp_path: Path,
) -> None:
    module = importlib.import_module("scripts.rd_concepts_pipeline.dashboard")
    valid_image = tmp_path / "raw" / "images" / "chart.png"
    valid_image.parent.mkdir(parents=True)
    valid_image.write_bytes(b"image")

    assert module._safe_image_path(valid_image, tmp_path) == valid_image.resolve()
    assert (
        module._safe_image_path("raw/images/chart.png", tmp_path)
        == valid_image.resolve()
    )
    assert module._safe_image_path(tmp_path / "../outside.png", tmp_path) is None
    assert module._safe_image_path("/tmp/outside.png", tmp_path) is None
    assert module._safe_image_path("raw/images/chart.txt", tmp_path) is None
