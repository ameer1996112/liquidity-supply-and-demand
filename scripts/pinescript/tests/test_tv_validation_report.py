from pathlib import Path
from tempfile import TemporaryDirectory

from scripts.pinescript.validation.comparator import compare_zones
from scripts.pinescript.validation.models import Scenario, ValidationResult, Zone
from scripts.pinescript.validation.report import write_report


def _normal_supply_scenario() -> Scenario:
    return Scenario(
        name="XAUUSD normal supply",
        symbol="XAUUSD",
        timeframe="5",
        comparison_mode="manual",
        expected_scripts=["S&D Pro", "Zones Liq S/D v23 - Myrtille"],
        price_tolerance=0.25,
        time_tolerance_bars=1,
    )


def _write_report_text(result: ValidationResult) -> str:
    with TemporaryDirectory() as tmp:
        report_path = write_report(Path(tmp), result)
        return report_path.read_text(encoding="utf-8")


def test_report_includes_core_validation_details() -> None:
    scenario = _normal_supply_scenario()
    expected = [Zone("manual", "supply", 4496.0, 4492.0, None, None, "S-manual")]
    actual = [Zone("S&D Pro", "supply", 4495.0, 4492.0, None, None, "S-19396")]
    result = compare_zones(
        scenario,
        expected_zones=expected,
        actual_zones=actual,
        screenshot_path="screenshot.png",
    )

    text = _write_report_text(result)

    assert "# TradingView Validation Report" in text
    assert "XAUUSD normal supply" in text
    assert "wrong_zone_high" in text
    assert "screenshot.png" in text


def test_report_renders_none_for_empty_expected_and_actual_zones() -> None:
    result = ValidationResult(
        scenario=_normal_supply_scenario(),
        expected_zones=[],
        actual_zones=[],
        mismatches=[],
    )

    text = _write_report_text(result)

    assert (
        "## Expected Zones\n\n"
        "- None\n\n"
        "## Actual Zones\n\n"
        "- None\n\n"
        "## Mismatches"
    ) in text


def main() -> None:
    test_report_includes_core_validation_details()
    test_report_renders_none_for_empty_expected_and_actual_zones()

    print("TradingView validation report contract passed")


if __name__ == "__main__":
    main()
