from __future__ import annotations

from functools import lru_cache

from scripts.pinescript.validation.models import Mismatch, Scenario, ValidationResult, Zone


AssignmentScore = tuple[int, int, int, int, int, float]
CandidateScore = tuple[int, int, float]
Match = tuple[int, Zone] | None


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
) -> CandidateScore | None:
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


def _add_scores(left: AssignmentScore, right: AssignmentScore) -> AssignmentScore:
    return (
        left[0] + right[0],
        left[1] + right[1],
        left[2] + right[2],
        left[3] + right[3],
        left[4] + right[4],
        left[5] + right[5],
    )


def _price_mismatch_count(expected: Zone, actual: Zone, tolerance: float) -> int:
    if expected.side != actual.side:
        return 0
    return int(not _price_close(expected.top, actual.top, tolerance)) + int(
        not _price_close(expected.bottom, actual.bottom, tolerance)
    )


def _match_assignment_score(
    expected: Zone,
    actual: Zone,
    candidate_score: CandidateScore,
    tolerance: float,
) -> AssignmentScore:
    side_rank, quality_rank, distance = candidate_score
    return (
        0,
        0,
        side_rank,
        quality_rank,
        _price_mismatch_count(expected, actual, tolerance),
        distance,
    )


def _find_best_assignment(
    expected_zones: list[Zone],
    actual_zones: list[Zone],
    tolerance: float,
) -> list[Match]:
    candidates_by_expected: list[list[tuple[CandidateScore, int, Zone]]] = []
    for expected in expected_zones:
        candidates: list[tuple[CandidateScore, int, Zone]] = []
        for idx, actual in enumerate(actual_zones):
            score = _candidate_score(expected, actual, tolerance)
            if score is not None:
                candidates.append((score, idx, actual))
        candidates.sort(key=lambda candidate: (candidate[0], candidate[1]))
        candidates_by_expected.append(candidates)

    @lru_cache(maxsize=None)
    def solve(
        expected_idx: int,
        used_actual_mask: int,
    ) -> tuple[AssignmentScore, tuple[int | None, ...]]:
        if expected_idx == len(expected_zones):
            extra_count = len(actual_zones) - used_actual_mask.bit_count()
            return (0, extra_count, 0, 0, 0, 0.0), ()

        missing_tail_score, missing_tail_matches = solve(
            expected_idx + 1,
            used_actual_mask,
        )
        best_score = _add_scores((1, 0, 0, 0, 0, 0.0), missing_tail_score)
        best_matches: tuple[int | None, ...] = (None, *missing_tail_matches)

        expected = expected_zones[expected_idx]
        for candidate_score, actual_idx, actual in candidates_by_expected[expected_idx]:
            actual_mask = 1 << actual_idx
            if used_actual_mask & actual_mask:
                continue

            tail_score, tail_matches = solve(
                expected_idx + 1,
                used_actual_mask | actual_mask,
            )
            total_score = _add_scores(
                _match_assignment_score(expected, actual, candidate_score, tolerance),
                tail_score,
            )
            if total_score < best_score:
                best_score = total_score
                best_matches = (actual_idx, *tail_matches)

        return best_score, best_matches

    _, match_indexes = solve(0, 0)
    return [
        (idx, actual_zones[idx]) if idx is not None else None for idx in match_indexes
    ]


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
