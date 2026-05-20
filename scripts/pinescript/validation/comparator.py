from __future__ import annotations

from scripts.pinescript.validation.models import Mismatch, Scenario, ValidationResult, Zone


def _price_close(left: float, right: float, tolerance: float) -> bool:
    return abs(left - right) <= tolerance


def _zone_candidate(expected: Zone, actual: Zone, tolerance: float) -> bool:
    if expected.side != actual.side:
        return False
    if expected.label and actual.label and expected.label == actual.label:
        return True

    top_near = _price_close(expected.top, actual.top, tolerance * 4)
    bottom_near = _price_close(expected.bottom, actual.bottom, tolerance * 4)
    return top_near or bottom_near


def _find_match(
    expected: Zone,
    actual_zones: list[Zone],
    used_actual: set[int],
    tolerance: float,
) -> tuple[int, Zone] | None:
    if expected.label:
        for idx, actual in enumerate(actual_zones):
            if idx in used_actual:
                continue
            if (
                expected.side == actual.side
                and actual.label
                and expected.label == actual.label
            ):
                return idx, actual

    for idx, actual in enumerate(actual_zones):
        if idx in used_actual:
            continue
        if _zone_candidate(expected, actual, tolerance):
            return idx, actual
    return None


def compare_zones(
    scenario: Scenario,
    *,
    expected_zones: list[Zone],
    actual_zones: list[Zone],
    screenshot_path: str | None = None,
) -> ValidationResult:
    mismatches: list[Mismatch] = []
    used_actual: set[int] = set()

    for expected in expected_zones:
        match = _find_match(
            expected,
            actual_zones,
            used_actual,
            scenario.price_tolerance,
        )
        if match is None:
            mismatches.append(
                Mismatch(
                    kind="missing_expected_zone",
                    message=f"Missing expected {expected.side} zone {expected.label}",
                    expected=expected,
                )
            )
            continue

        idx, actual = match
        used_actual.add(idx)
        if not _price_close(expected.top, actual.top, scenario.price_tolerance):
            mismatches.append(
                Mismatch(
                    kind="wrong_zone_high",
                    message=(
                        f"{expected.label} high expected {expected.top}, "
                        f"got {actual.top}"
                    ),
                    expected=expected,
                    actual=actual,
                )
            )
        if not _price_close(expected.bottom, actual.bottom, scenario.price_tolerance):
            mismatches.append(
                Mismatch(
                    kind="wrong_zone_low",
                    message=(
                        f"{expected.label} low expected {expected.bottom}, "
                        f"got {actual.bottom}"
                    ),
                    expected=expected,
                    actual=actual,
                )
            )

    for idx, actual in enumerate(actual_zones):
        if idx not in used_actual:
            mismatches.append(
                Mismatch(
                    kind="extra_unexpected_zone",
                    message=f"Unexpected {actual.side} zone {actual.label}",
                    actual=actual,
                )
            )

    return ValidationResult(
        scenario=scenario,
        expected_zones=expected_zones,
        actual_zones=actual_zones,
        mismatches=mismatches,
        screenshot_path=screenshot_path,
    )
