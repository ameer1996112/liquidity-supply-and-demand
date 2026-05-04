"""Static regression checks for PineScript TP multiplier wiring."""

from pathlib import Path


STRATEGY_PATH = (
    Path(__file__).resolve().parents[1]
    / "scripts"
    / "pinescript"
    / "strategies"
    / "SND_Strategy.pine"
)


def test_double_tp_multiplier_is_applied_once() -> None:
    source = STRATEGY_PATH.read_text()

    assert source.count("base_ratio := base_ratio * 2.0") == 1
    assert "tp_r := tp_r * 2.0" not in source
