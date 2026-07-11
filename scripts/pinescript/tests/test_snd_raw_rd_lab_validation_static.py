import re
from pathlib import Path


LAB = Path("scripts/pinescript/indicators/SND_Raw_RD_Forex_LAB.pine")


def test_lab_object_budget_caps_stay_below_tradingview_limits() -> None:
    source = LAB.read_text()

    header = source.split("\n", 1)[1]
    for field in ("max_boxes_count", "max_lines_count", "max_labels_count"):
        match = re.search(rf"{field}\s*=\s*(\d+)", header)
        assert match is not None
        assert int(match.group(1)) <= 300

    assert "const int maxZones = 200" in source
    assert "const int referenceLiquidityMaxLines = 220" in source
    assert "while array.size(referenceLiquidityLines) > referenceLiquidityMaxLines" in source
    assert "while array.size(zones) > maxZones" in source


def test_lab_documents_liquidity_tie_break_semantics() -> None:
    source = LAB.read_text()

    assert "Liquidity tie-break semantics" in source
    assert "closest qualifying candidate by price distance" in source
    assert "earliest pivot bar on equal distance" in source
    assert "already-consumed levels are never valid" in source


def test_lab_keeps_continuation_out_of_core_validation_phase() -> None:
    source = LAB.read_text()

    assert "const bool enableContinuationZones = false" in source
    assert "effectiveModel == MODEL_CONTINUATION and enableContinuationZones" in source
    assert "effectiveModel == MODEL_ACC_CONTINUATION and accuracyBoundsAllowed() and enableContinuationZones" in source
