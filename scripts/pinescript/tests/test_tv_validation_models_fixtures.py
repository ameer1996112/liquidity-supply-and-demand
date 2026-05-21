from pathlib import Path
from tempfile import TemporaryDirectory

from scripts.pinescript.validation.fixtures import load_fixture, save_fixture
from scripts.pinescript.validation.models import Scenario, Zone


def main() -> None:
    scenario = Scenario(
        name="GBPJPY invalid zones",
        symbol="GBPJPY",
        timeframe="5",
        comparison_mode="manual",
        expected_scripts=["S&D Pro"],
        price_tolerance=0.001,
        time_tolerance_bars=1,
    )
    zones = [
        Zone(
            source="S&D Pro",
            side="demand",
            top=212.900,
            bottom=212.880,
            left_time="2026-05-20T12:30:00+03:00",
            right_time="2026-05-20T13:00:00+03:00",
            label="D-13856",
        )
    ]
    with TemporaryDirectory() as tmp:
        path = Path(tmp) / "fixture.json"
        save_fixture(path, scenario=scenario, zones=zones)
        loaded = load_fixture(path)
        assert loaded.scenario.name == scenario.name
        assert loaded.scenario.symbol == "GBPJPY"
        assert loaded.zones[0].label == "D-13856"
        assert loaded.zones[0].bottom == 212.880

    print("TradingView validation models/fixtures contract passed")


if __name__ == "__main__":
    main()
