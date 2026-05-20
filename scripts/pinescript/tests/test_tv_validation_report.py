from pathlib import Path
from tempfile import TemporaryDirectory

from scripts.pinescript.validation.comparator import compare_zones
from scripts.pinescript.validation.models import Scenario, Zone
from scripts.pinescript.validation.report import write_report


def main() -> None:
    scenario = Scenario(
        name="XAUUSD normal supply",
        symbol="XAUUSD",
        timeframe="5",
        comparison_mode="manual",
        expected_scripts=["S&D Pro", "Zones Liq S/D v23 - Myrtille"],
        price_tolerance=0.25,
        time_tolerance_bars=1,
    )
    expected = [Zone("manual", "supply", 4496.0, 4492.0, None, None, "S-manual")]
    actual = [Zone("S&D Pro", "supply", 4495.0, 4492.0, None, None, "S-19396")]
    result = compare_zones(
        scenario,
        expected_zones=expected,
        actual_zones=actual,
        screenshot_path="screenshot.png",
    )

    with TemporaryDirectory() as tmp:
        report_path = write_report(Path(tmp), result)
        text = report_path.read_text(encoding="utf-8")
        assert "# TradingView Validation Report" in text
        assert "XAUUSD normal supply" in text
        assert "wrong_zone_high" in text
        assert "screenshot.png" in text

    print("TradingView validation report contract passed")


if __name__ == "__main__":
    main()
