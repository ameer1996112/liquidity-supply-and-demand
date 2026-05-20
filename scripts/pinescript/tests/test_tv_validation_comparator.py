from scripts.pinescript.validation.comparator import compare_zones
from scripts.pinescript.validation.models import Scenario, Zone


def _scenario() -> Scenario:
    return Scenario(
        name="GBPJPY invalid zones",
        symbol="GBPJPY",
        timeframe="5",
        comparison_mode="manual",
        expected_scripts=["S&D Pro"],
        price_tolerance=0.001,
        time_tolerance_bars=1,
    )


def main() -> None:
    expected = [
        Zone("manual", "supply", 213.130, 213.080, None, None, "S-11134"),
        Zone("manual", "demand", 212.900, 212.880, None, None, "D-13856"),
    ]
    actual = [
        Zone("S&D Pro", "supply", 213.130, 213.080, None, None, "S-11134"),
        Zone("S&D Pro", "demand", 212.900, 212.870, None, None, "D-13856"),
        Zone("S&D Pro", "demand", 212.820, 212.740, None, None, "D-invalid"),
    ]

    result = compare_zones(_scenario(), expected_zones=expected, actual_zones=actual)
    kinds = [mismatch.kind for mismatch in result.mismatches]
    assert "wrong_zone_low" in kinds
    assert "extra_unexpected_zone" in kinds
    assert not result.passed

    clean = compare_zones(_scenario(), expected_zones=expected, actual_zones=expected)
    assert clean.passed
    assert clean.mismatches == []

    print("TradingView validation comparator contract passed")


if __name__ == "__main__":
    main()
