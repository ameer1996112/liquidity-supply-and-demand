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
    if not _zone_candidate(expected, actual, tolerance):
        return None

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


def _price_mismatch_count(expected: Zone, actual: Zone, tolerance: float) -> int:
    if expected.side != actual.side:
        return 0
    return int(not _price_close(expected.top, actual.top, tolerance)) + int(
        not _price_close(expected.bottom, actual.bottom, tolerance)
    )


def _assignment_score(
    expected_zones: list[Zone],
    actual_zones: list[Zone],
    matches: list[tuple[int, Zone] | None],
    tolerance: float,
) -> tuple[int, int, int, int, int, float]:
    used_actual = {match[0] for match in matches if match is not None}
    missing_count = len(expected_zones) - len(used_actual)
    extra_count = len(actual_zones) - len(used_actual)
    wrong_side_count = 0
    quality_score = 0
    price_mismatch_count = 0
    distance_score = 0.0

    for expected, match in zip(expected_zones, matches, strict=True):
        if match is None:
            continue

        _, actual = match
        candidate_score = _candidate_score(expected, actual, tolerance)
        if candidate_score is None:
            continue

        side_rank, quality_rank, distance = candidate_score
        wrong_side_count += side_rank
        quality_score += quality_rank
        price_mismatch_count += _price_mismatch_count(expected, actual, tolerance)
        distance_score += distance

    return (
        missing_count,
        extra_count,
        wrong_side_count,
        quality_score,
        price_mismatch_count,
        distance_score,
    )


def _find_best_assignment(
    expected_zones: list[Zone],
    actual_zones: list[Zone],
    tolerance: float,
) -> list[tuple[int, Zone] | None]:
    candidates_by_expected: list[list[tuple[tuple[int, int, float], int, Zone]]] = []
    for expected in expected_zones:
        candidates: list[tuple[tuple[int, int, float], int, Zone]] = []
        for idx, actual in enumerate(actual_zones):
            score = _candidate_score(expected, actual, tolerance)
            if score is not None:
                candidates.append((score, idx, actual))
        candidates.sort(key=lambda candidate: (candidate[0], candidate[1]))
        candidates_by_expected.append(candidates)

    current_matches: list[tuple[int, Zone] | None] = [None] * len(expected_zones)
    best_matches: list[tuple[int, Zone] | None] = current_matches.copy()
    best_score: tuple[int, int, int, int, int, float] | None = None
    used_actual: set[int] = set()

    def search(expected_idx: int) -> None:
        nonlocal best_matches, best_score
        if expected_idx == len(expected_zones):
            score = _assignment_score(
                expected_zones,
                actual_zones,
                current_matches,
                tolerance,
            )
            if best_score is None or score < best_score:
                best_score = score
                best_matches = current_matches.copy()
            return

        for _, actual_idx, actual in candidates_by_expected[expected_idx]:
            if actual_idx in used_actual:
                continue
            used_actual.add(actual_idx)
            current_matches[expected_idx] = (actual_idx, actual)
            search(expected_idx + 1)
            current_matches[expected_idx] = None
            used_actual.remove(actual_idx)

        search(expected_idx + 1)

    search(0)
    return best_matches


def compare_zones(
    scenario: Scenario,
    *,
    expected_zones: list[Zone],
    actual_zones: list[Zone],
    screenshot_path: str | None = None,
) -> ValidationResult:
    mismatches: list[Mismatch] = []
    matches = _find_best_assignment(
        expected_zones,
        actual_zones,
        scenario.price_tolerance,
    )
    used_actual: set[int] = set()

    for expected, match in zip(expected_zones, matches, strict=True):
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
