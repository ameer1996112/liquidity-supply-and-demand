from __future__ import annotations

from scripts.pinescript.validation.models import Mismatch, Scenario, ValidationResult, Zone


def _price_close(left: float, right: float, tolerance: float) -> bool:
    return abs(left - right) <= tolerance


def _zone_candidate(expected: Zone, actual: Zone, tolerance: float) -> bool:
    if expected.label and actual.label and expected.label == actual.label:
        return True

    top_near = _price_close(expected.top, actual.top, tolerance * 4)
    bottom_near = _price_close(expected.bottom, actual.bottom, tolerance * 4)
    return top_near or bottom_near


def _edge_distance(expected: Zone, actual: Zone) -> float:
    return abs(expected.top - actual.top) + abs(expected.bottom - actual.bottom)


def _candidate_score(
    expected: Zone,
    actual: Zone,
    tolerance: float,
) -> tuple[int, int, float] | None:
    side_rank = 0 if expected.side == actual.side else 1
    if expected.label and actual.label and expected.label == actual.label:
        return side_rank, 0, _edge_distance(expected, actual)

    top_near = _price_close(expected.top, actual.top, tolerance * 4)
    bottom_near = _price_close(expected.bottom, actual.bottom, tolerance * 4)
    if top_near and bottom_near:
        return side_rank, 1, _edge_distance(expected, actual)
    if top_near or bottom_near:
        return side_rank, 2, _edge_distance(expected, actual)
    return None


def _find_match(
    expected: Zone,
    actual_zones: list[Zone],
    used_actual: set[int],
    tolerance: float,
) -> tuple[int, Zone] | None:
    best_match: tuple[tuple[int, int, float], int, Zone] | None = None
    for idx, actual in enumerate(actual_zones):
        if idx in used_actual:
            continue
        score = _candidate_score(expected, actual, tolerance)
        if score is None:
            continue
        if best_match is None or score < best_match[0]:
            best_match = (score, idx, actual)

    if best_match is None:
        return None
    _, idx, actual = best_match
    return idx, actual


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
        if expected.side != actual.side:
            mismatches.append(
                Mismatch(
                    kind="wrong_side",
                    message=(
                        f"{expected.label} side expected {expected.side}, "
                        f"got {actual.side}"
                    ),
                    expected=expected,
                    actual=actual,
                )
            )
            continue

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
