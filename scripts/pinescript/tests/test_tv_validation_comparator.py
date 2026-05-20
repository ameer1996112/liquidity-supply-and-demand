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


def _contract_zones() -> tuple[list[Zone], list[Zone]]:
    expected = [
        Zone("manual", "supply", 213.130, 213.080, None, None, "S-11134"),
        Zone("manual", "demand", 212.900, 212.880, None, None, "D-13856"),
    ]
    actual = [
        Zone("S&D Pro", "supply", 213.130, 213.080, None, None, "S-11134"),
        Zone("S&D Pro", "demand", 212.900, 212.870, None, None, "D-13856"),
        Zone("S&D Pro", "demand", 212.820, 212.740, None, None, "D-invalid"),
    ]
    return expected, actual


def test_comparator_reports_wrong_low_and_extra_zone() -> None:
    expected, actual = _contract_zones()
    result = compare_zones(_scenario(), expected_zones=expected, actual_zones=actual)
    kinds = [mismatch.kind for mismatch in result.mismatches]
    assert "wrong_zone_low" in kinds
    assert "extra_unexpected_zone" in kinds
    assert not result.passed


def test_comparator_clean_compare_passes() -> None:
    expected, _ = _contract_zones()
    clean = compare_zones(_scenario(), expected_zones=expected, actual_zones=expected)
    assert clean.passed
    assert clean.mismatches == []


def test_reversed_actual_order_chooses_best_unlabeled_fallback_match() -> None:
    expected = [
        Zone("manual", "supply", 100.000, 99.990, None, None, ""),
        Zone("manual", "supply", 100.003, 99.970, None, None, ""),
    ]
    actual = [
        Zone("S&D Pro", "supply", 100.003, 99.970, None, None, "changed-b"),
        Zone("S&D Pro", "supply", 100.000, 99.990, None, None, "changed-a"),
    ]

    result = compare_zones(_scenario(), expected_zones=expected, actual_zones=actual)

    assert result.passed
    assert result.mismatches == []


def test_wrong_side_uses_matching_actual_without_missing_or_extra() -> None:
    expected = [
        Zone("manual", "demand", 212.900, 212.880, None, None, "D-13856"),
    ]
    actual = [
        Zone("S&D Pro", "supply", 212.900, 212.880, None, None, "D-13856"),
    ]

    result = compare_zones(_scenario(), expected_zones=expected, actual_zones=actual)
    kinds = [mismatch.kind for mismatch in result.mismatches]

    assert kinds == ["wrong_side"]
    assert result.mismatches[0].expected == expected[0]
    assert result.mismatches[0].actual == actual[0]
    assert "missing_expected_zone" not in kinds
    assert "extra_unexpected_zone" not in kinds
    assert not result.passed


def test_same_side_candidate_wins_over_earlier_wrong_side_candidate() -> None:
    expected = [
        Zone("manual", "demand", 212.900, 212.880, None, None, "D-13856"),
        Zone("manual", "supply", 212.900, 212.880, None, None, "S-overlap"),
    ]
    actual = [
        Zone("S&D Pro", "supply", 212.900, 212.880, None, None, "D-13856"),
        Zone("S&D Pro", "demand", 212.900, 212.880, None, None, "D-13856"),
    ]

    result = compare_zones(_scenario(), expected_zones=expected, actual_zones=actual)
    kinds = [mismatch.kind for mismatch in result.mismatches]

    assert result.passed
    assert kinds == []
    assert "wrong_side" not in kinds
    assert "extra_unexpected_zone" not in kinds


def main() -> None:
    test_comparator_reports_wrong_low_and_extra_zone()
    test_comparator_clean_compare_passes()
    test_reversed_actual_order_chooses_best_unlabeled_fallback_match()
    test_wrong_side_uses_matching_actual_without_missing_or_extra()
    test_same_side_candidate_wins_over_earlier_wrong_side_candidate()

    print("TradingView validation comparator contract passed")


if __name__ == "__main__":
    main()
