from decimal import Decimal
import json
from pathlib import Path

from scripts.rd_concepts_pipeline.reference_detector import (
    Bar,
    Direction,
    EligibilityState,
    Geometry,
    RawZoneDetector,
    SetupState,
    ZoneState,
    detect_zones,
)


FIXTURE = Path(
    "tests/rd_concepts_pipeline/fixtures/reference_detector_cases.json"
)


def load_cases() -> list[dict]:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def load_case(case_id: str) -> dict:
    return next(case for case in load_cases() if case["case_id"] == case_id)


def test_reference_detector_matches_geometry_contract_cases() -> None:
    for case in load_cases():
        result = detect_zones([Bar.from_mapping(row) for row in case["bars"]])
        assert len(result.zones) == 1, case["case_id"]
        zone = result.zones[0]
        expected = case["expected"]
        assert zone.direction.value == expected["direction"], case["case_id"]
        assert zone.formation.value == expected["formation"], case["case_id"]
        assert zone.geometry.value == expected["geometry"], case["case_id"]
        assert zone.origin_index == expected["origin_index"], case["case_id"]
        assert zone.confirmation_index == expected["confirmation_index"], case["case_id"]
        assert zone.top == Decimal(expected["top"]), case["case_id"]
        assert zone.bottom == Decimal(expected["bottom"]), case["case_id"]


def test_opposite_candle_interrupts_unconfirmed_formation() -> None:
    bars = [
        Bar.from_mapping({"time": "t0", "open": 10.2, "high": 10.3, "low": 9.8, "close": 9.9}),
        Bar.from_mapping({"time": "t1", "open": 9.9, "high": 10.0, "low": 9.5, "close": 9.6}),
        Bar.from_mapping({"time": "t2", "open": 9.6, "high": 9.9, "low": 9.4, "close": 9.8}),
        Bar.from_mapping({"time": "t3", "open": 9.8, "high": 9.9, "low": 9.3, "close": 9.5}),
    ]

    result = detect_zones(bars)

    assert result.zones == ()
    assert any(
        rejection.direction is Direction.DEMAND
        and rejection.origin_index == 1
        and rejection.reason == "REJECT_FORMATION_INTERRUPTED"
        for rejection in result.rejections
    )


def test_post_confirmation_overlap_taps_without_resizing_zone() -> None:
    bars = [Bar.from_mapping(row) for row in load_cases()[0]["bars"]]
    bars.append(
        Bar.from_mapping(
            {"time": "t3", "open": 10.0, "high": 10.2, "low": 9.95, "close": 10.1}
        )
    )
    bars.append(
        Bar.from_mapping(
            {"time": "t4", "open": 10.1, "high": 10.2, "low": 9.7, "close": 9.95}
        )
    )

    result = detect_zones(bars)
    zone = result.zones[0]

    assert zone.state is ZoneState.TAPPED
    assert zone.state_index == 4
    assert zone.top == Decimal("9.9")
    assert zone.bottom == Decimal("9.4")


def test_same_direction_departure_wick_does_not_count_as_a_retest() -> None:
    case = load_case("SUPPLY-INSIDE-BASE-INTERRUPTION")
    bars = [Bar.from_mapping(row) for row in case["bars"][:5]]
    bars.extend(
        [
            Bar.from_mapping(
                {
                    "time": "departure-wick",
                    "open": "162.500",
                    "high": "162.504",
                    "low": "162.470",
                    "close": "162.480",
                }
            ),
            Bar.from_mapping(
                {
                    "time": "departure-ended",
                    "open": "162.480",
                    "high": "162.490",
                    "low": "162.470",
                    "close": "162.488",
                }
            ),
            Bar.from_mapping(
                {
                    "time": "later-retest",
                    "open": "162.488",
                    "high": "162.500",
                    "low": "162.470",
                    "close": "162.480",
                }
            ),
        ]
    )

    zone = detect_zones(bars).zones[0]

    assert zone.state is ZoneState.TAPPED
    assert zone.state_index == 7


def test_close_beyond_distal_invalidates_zone() -> None:
    bars = [Bar.from_mapping(row) for row in load_cases()[0]["bars"]]
    bars.append(
        Bar.from_mapping(
            {"time": "t3", "open": 10.0, "high": 10.1, "low": 9.2, "close": 9.3}
        )
    )

    zone = detect_zones(bars).zones[0]
    assert zone.state is ZoneState.INVALIDATED
    assert zone.reason == "INVALIDATE_CLOSE_BEYOND_DISTAL"


def test_doji_approach_fails_closed() -> None:
    bars = [
        Bar.from_mapping({"time": "t0", "open": 10, "high": 10.1, "low": 9.9, "close": 10}),
        Bar.from_mapping({"time": "t1", "open": 10, "high": 10.1, "low": 9.6, "close": 9.7}),
        Bar.from_mapping({"time": "t2", "open": 9.7, "high": 10.3, "low": 9.65, "close": 10.2}),
    ]
    result = detect_zones(bars)
    assert result.zones == ()
    assert result.rejections[-1].reason == "REJECT_UNKNOWN_APPROACH"


def test_invalid_bar_geometry_is_rejected() -> None:
    try:
        Bar.from_mapping({"time": "t0", "open": 10, "high": 9, "low": 8, "close": 9.5})
    except ValueError as exc:
        assert str(exc) == "bar high is below its body"
    else:
        raise AssertionError("invalid OHLC must fail")


def test_global_liquidity_detects_both_sides_without_parent_zones() -> None:
    bars = [
        Bar.from_mapping({"time": "t0", "open": 10, "high": 10.2, "low": 9.8, "close": 10}),
        Bar.from_mapping({"time": "t1", "open": 10, "high": 10.1, "low": 9.7, "close": 9.9}),
        Bar.from_mapping({"time": "t2", "open": 9.9, "high": 10.0, "low": 9.6, "close": 9.8}),
        Bar.from_mapping({"time": "t3", "open": 9.8, "high": 10.05, "low": 9.55, "close": 9.95}),
        Bar.from_mapping({"time": "t4", "open": 9.95, "high": 10.1, "low": 9.9, "close": 10.05}),
        Bar.from_mapping({"time": "t5", "open": 10.05, "high": 10.15, "low": 9.8, "close": 9.9}),
    ]

    result = detect_zones(bars)
    demand_liquidity = next(
        level for level in result.liquidity_levels if level.direction is Direction.DEMAND
    )
    supply_liquidity = next(
        level for level in result.liquidity_levels if level.direction is Direction.SUPPLY
    )

    assert demand_liquidity.run_start_index == 1
    assert demand_liquidity.formed_index == 2
    assert demand_liquidity.anchor == Decimal("10.2")
    assert demand_liquidity.anchor_index == 0
    assert demand_liquidity.near_extreme == Decimal("9.55")
    assert demand_liquidity.near_extreme_index == 3
    assert demand_liquidity.taken_index is None

    assert supply_liquidity.run_start_index == 3
    assert supply_liquidity.formed_index == 4
    assert supply_liquidity.anchor == Decimal("9.55")
    assert supply_liquidity.anchor_index == 3
    assert supply_liquidity.near_extreme == Decimal("10.15")
    assert supply_liquidity.near_extreme_index == 5
    assert supply_liquidity.taken_index is None


def test_global_liquidity_requires_strict_later_break_of_own_extreme() -> None:
    rows = [
        {"time": "t0", "open": 10, "high": 10.2, "low": 9.8, "close": 10},
        {"time": "t1", "open": 10, "high": 10.1, "low": 9.7, "close": 9.9},
        {"time": "t2", "open": 9.9, "high": 10.0, "low": 9.6, "close": 9.8},
        {"time": "t3", "open": 9.8, "high": 10.05, "low": 9.55, "close": 9.95},
        {"time": "t4", "open": 9.95, "high": 10.2, "low": 9.9, "close": 10.1},
        {"time": "t5", "open": 10.1, "high": 10.21, "low": 10.0, "close": 10.15},
    ]
    detector = RawZoneDetector()
    for row in rows[:5]:
        detector.update(Bar.from_mapping(row))

    demand_liquidity = next(
        level
        for level in detector.result.liquidity_levels
        if level.direction is Direction.DEMAND
    )
    assert demand_liquidity.taken_index is None

    detector.update(Bar.from_mapping(rows[5]))

    assert demand_liquidity.taken_index == 5


def test_zone_does_not_reuse_liquidity_started_before_confirmation() -> None:
    rows = [
        {"time": "t0", "open": 10, "high": 10.2, "low": 9.8, "close": 10},
        {"time": "t1", "open": 10, "high": 10.1, "low": 9.7, "close": 9.9},
        {"time": "t2", "open": 9.9, "high": 10.0, "low": 9.5, "close": 9.6},
        {"time": "t3", "open": 9.6, "high": 10.2, "low": 9.55, "close": 10.1},
        {"time": "t4", "open": 10.1, "high": 10.3, "low": 10.0, "close": 10.2},
    ]

    result = detect_zones([Bar.from_mapping(row) for row in rows])
    zone = next(zone for zone in result.zones if zone.origin_index == 2)
    level = next(
        level for level in result.liquidity_levels if level.direction is Direction.DEMAND
    )

    assert level.run_start_index == 1
    assert level.formed_index == 2
    assert zone.confirmation_index == 3
    assert zone.eligibility_state is EligibilityState.WAITING_FOR_LIQUIDITY
    assert zone.liquidity_qualified is False
    assert zone.liquidity_anchor is None


def test_demand_zone_becomes_eligible_after_two_bearish_candles_take_own_high() -> None:
    bars = [Bar.from_mapping(row) for row in load_cases()[0]["bars"]]
    bars.extend(
        Bar.from_mapping(row)
        for row in [
            {"time": "t3", "open": 10.5, "high": 10.6, "low": 10.3, "close": 10.4},
            {"time": "t4", "open": 10.4, "high": 10.45, "low": 10.15, "close": 10.2},
            {"time": "t5", "open": 10.2, "high": 10.61, "low": 10.1, "close": 10.55},
        ]
    )

    zone = detect_zones(bars).zones[0]

    assert zone.state is ZoneState.CONFIRMED_FRESH
    assert zone.eligibility_state is EligibilityState.ELIGIBLE
    assert zone.eligibility_index == 5
    assert zone.liquidity_anchor == Decimal("10.6")
    assert zone.eligibility_reason == "LIQUIDITY_OWN_EXTREME_TAKEN"
    assert zone.liquidity_qualified is True
    assert zone.setup_state is SetupState.ARMED
    assert zone.setup_reason == "ARM_SETUP_AFTER_LIQUIDITY"


def test_supply_zone_becomes_eligible_after_two_bullish_candles_take_own_low() -> None:
    bars = [
        Bar.from_mapping({"time": "t0", "open": 10.4, "high": 10.5, "low": 10.1, "close": 10.2}),
        Bar.from_mapping({"time": "t1", "open": 10.2, "high": 10.6, "low": 10.15, "close": 10.5}),
        Bar.from_mapping({"time": "t2", "open": 10.5, "high": 10.55, "low": 9.9, "close": 10.0}),
        Bar.from_mapping({"time": "t3", "open": 9.9, "high": 10.05, "low": 9.7, "close": 10.0}),
        Bar.from_mapping({"time": "t4", "open": 10.0, "high": 10.1, "low": 9.8, "close": 10.05}),
        Bar.from_mapping({"time": "t5", "open": 10.05, "high": 10.1, "low": 9.65, "close": 9.7}),
    ]

    zone = next(zone for zone in detect_zones(bars).zones if zone.origin_index == 1)

    assert zone.state is ZoneState.CONFIRMED_FRESH
    assert zone.eligibility_state is EligibilityState.ELIGIBLE
    assert zone.eligibility_index == 5
    assert zone.liquidity_anchor == Decimal("9.7")
    assert zone.setup_state is SetupState.ARMED


def test_one_candle_liquidity_fails_closed_without_hiding_raw_zone() -> None:
    bars = [Bar.from_mapping(row) for row in load_cases()[0]["bars"]]
    bars.extend(
        Bar.from_mapping(row)
        for row in [
            {"time": "t3", "open": 10.5, "high": 10.6, "low": 10.3, "close": 10.4},
            {"time": "t4", "open": 10.4, "high": 10.7, "low": 10.2, "close": 10.65},
        ]
    )

    result = detect_zones(bars)
    zone = result.zones[0]

    assert zone in result.zones
    assert zone.eligibility_state is EligibilityState.WAITING_FOR_LIQUIDITY
    assert zone.eligibility_reason == "REJECT_ONE_CANDLE_LIQUIDITY"


def test_zone_tapped_before_liquidity_confirmation_expires_eligibility() -> None:
    bars = [Bar.from_mapping(row) for row in load_cases()[0]["bars"]]
    bars.extend(
        Bar.from_mapping(row)
        for row in [
            {"time": "t3", "open": 10.5, "high": 10.6, "low": 10.3, "close": 10.4},
            {"time": "t4", "open": 10.4, "high": 10.45, "low": 10.15, "close": 10.2},
            {"time": "t5", "open": 10.2, "high": 10.3, "low": 9.8, "close": 10.0},
        ]
    )

    zone = detect_zones(bars).zones[0]

    assert zone.state is ZoneState.TAPPED
    assert zone.eligibility_state is EligibilityState.EXPIRED
    assert zone.eligibility_index == 5
    assert zone.eligibility_reason == "EXPIRE_ZONE_NOT_FRESH"
    assert zone.setup_state is SetupState.REJECTED
    assert zone.setup_reason == "REJECT_TARGET_TAP_WITHOUT_ELIGIBILITY"


def test_closer_unswept_liquidity_replaces_older_eligible_primary() -> None:
    rows = [
        *load_cases()[0]["bars"],
        {"time": "t3", "open": 10.5, "high": 10.6, "low": 10.3, "close": 10.4},
        {"time": "t4", "open": 10.4, "high": 10.45, "low": 10.15, "close": 10.2},
        {"time": "t5", "open": 10.2, "high": 10.61, "low": 10.1, "close": 10.55},
        {"time": "t6", "open": 10.55, "high": 10.58, "low": 10.2, "close": 10.3},
        {"time": "t7", "open": 10.3, "high": 10.35, "low": 10.05, "close": 10.1},
        {"time": "t8", "open": 10.1, "high": 10.4, "low": 10.0, "close": 10.3},
        {"time": "t9", "open": 10.3, "high": 10.62, "low": 10.2, "close": 10.6},
    ]
    detector = RawZoneDetector()
    for row in rows[:6]:
        detector.update(Bar.from_mapping(row))

    zone = detector.result.zones[0]
    assert zone.eligibility_state is EligibilityState.ELIGIBLE
    assert zone.liquidity_anchor == Decimal("10.6")
    assert zone.liquidity_extreme == Decimal("10.1")

    for row in rows[6:9]:
        detector.update(Bar.from_mapping(row))

    assert zone.eligibility_state is EligibilityState.WAITING_FOR_LIQUIDITY
    assert zone.eligibility_reason == "WAIT_LIQUIDITY_OWN_EXTREME"
    assert zone.liquidity_anchor == Decimal("10.61")
    assert zone.liquidity_extreme == Decimal("10.0")
    assert zone.setup_state is SetupState.WAITING_FOR_ELIGIBILITY
    assert zone.setup_reason == "WAIT_SETUP_ELIGIBILITY"

    detector.update(Bar.from_mapping(rows[9]))

    assert zone.eligibility_state is EligibilityState.ELIGIBLE
    assert zone.eligibility_index == 9
    assert zone.liquidity_anchor == Decimal("10.61")
    assert zone.setup_state is SetupState.ARMED

    detector.update(
        Bar.from_mapping(
            {"time": "t10", "open": 10.6, "high": 10.7, "low": 10.5, "close": 10.65}
        )
    )

    assert zone.eligibility_index == 9
    assert zone.eligibility_time == "t9"


def test_supply_primary_uses_highest_completed_liquidity_swing() -> None:
    rows = [
        {"time": "t0", "open": 10.4, "high": 10.5, "low": 10.1, "close": 10.2},
        {"time": "t1", "open": 10.2, "high": 10.6, "low": 10.15, "close": 10.5},
        {"time": "t2", "open": 10.5, "high": 10.55, "low": 9.9, "close": 10.0},
        {"time": "t3", "open": 9.9, "high": 10.05, "low": 9.7, "close": 10.0},
        {"time": "t4", "open": 10.0, "high": 10.1, "low": 9.8, "close": 10.05},
        {"time": "t5", "open": 10.05, "high": 10.1, "low": 9.65, "close": 9.7},
        {"time": "t6", "open": 9.7, "high": 10.05, "low": 9.68, "close": 9.95},
        {"time": "t7", "open": 9.95, "high": 10.12, "low": 9.9, "close": 10.05},
        {"time": "t8", "open": 10.05, "high": 10.13, "low": 9.8, "close": 9.9},
        {"time": "t9", "open": 9.9, "high": 10.05, "low": 9.64, "close": 9.7},
    ]
    detector = RawZoneDetector()
    for row in rows[:6]:
        detector.update(Bar.from_mapping(row))

    zone = next(zone for zone in detector.result.zones if zone.origin_index == 1)
    assert zone.eligibility_state is EligibilityState.ELIGIBLE
    assert zone.liquidity_anchor == Decimal("9.7")
    assert zone.liquidity_extreme == Decimal("10.1")

    for row in rows[6:9]:
        detector.update(Bar.from_mapping(row))

    assert zone.eligibility_state is EligibilityState.WAITING_FOR_LIQUIDITY
    assert zone.liquidity_anchor == Decimal("9.65")
    assert zone.liquidity_extreme == Decimal("10.13")

    detector.update(Bar.from_mapping(rows[9]))

    assert zone.eligibility_state is EligibilityState.ELIGIBLE
    assert zone.eligibility_index == 9


def test_demand_setup_expires_after_tapping_intervening_supply_zone() -> None:
    rows = [
        *load_cases()[0]["bars"],
        {"time": "t3", "open": 10.5, "high": 10.6, "low": 10.3, "close": 10.4},
        {"time": "t4", "open": 10.4, "high": 10.45, "low": 10.15, "close": 10.2},
        {"time": "t5", "open": 10.2, "high": 10.61, "low": 10.1, "close": 10.55},
        {"time": "t6", "open": 10.55, "high": 10.58, "low": 10.0, "close": 10.05},
        {"time": "t7", "open": 10.0, "high": 10.2, "low": 9.95, "close": 10.1},
        {"time": "t8", "open": 10.1, "high": 10.15, "low": 9.95, "close": 10.0},
    ]

    result = detect_zones([Bar.from_mapping(row) for row in rows])
    target = next(zone for zone in result.zones if zone.origin_index == 1)
    blocker = next(
        zone
        for zone in result.zones
        if zone.direction is Direction.SUPPLY and zone.confirmation_index == 6
    )

    assert target.state is ZoneState.CONFIRMED_FRESH
    assert blocker.state is ZoneState.TAPPED
    assert blocker.state_index == 7
    assert target.eligibility_state is EligibilityState.EXPIRED
    assert target.eligibility_index == 7
    assert target.eligibility_reason == "EXPIRE_OPPOSITE_ZONE_RETRACE"
    assert target.liquidity_qualified is True
    assert target.route_blocker_zone_id == blocker.zone_id
    assert target.setup_state is SetupState.REJECTED
    assert target.setup_reason == "EXPIRE_OPPOSITE_ZONE_RETRACE"


def test_supply_setup_expires_after_tapping_intervening_demand_zone() -> None:
    rows = [
        {"time": "t0", "open": 10.4, "high": 10.5, "low": 10.1, "close": 10.2},
        {"time": "t1", "open": 10.2, "high": 10.6, "low": 10.15, "close": 10.5},
        {"time": "t2", "open": 10.5, "high": 10.55, "low": 9.9, "close": 10.0},
        {"time": "t3", "open": 9.9, "high": 10.05, "low": 9.7, "close": 10.0},
        {"time": "t4", "open": 10.0, "high": 10.1, "low": 9.8, "close": 10.05},
        {"time": "t5", "open": 10.05, "high": 10.1, "low": 9.65, "close": 9.7},
        {"time": "t6", "open": 9.7, "high": 10.12, "low": 9.68, "close": 10.11},
        {"time": "t7", "open": 10.11, "high": 10.14, "low": 10.0, "close": 10.05},
    ]

    result = detect_zones([Bar.from_mapping(row) for row in rows])
    target = next(zone for zone in result.zones if zone.origin_index == 1)
    blocker = next(
        zone
        for zone in result.zones
        if zone.direction is Direction.DEMAND and zone.confirmation_index == 6
    )

    assert target.state is ZoneState.CONFIRMED_FRESH
    assert blocker.state is ZoneState.TAPPED
    assert blocker.state_index == 7
    assert target.eligibility_state is EligibilityState.EXPIRED
    assert target.eligibility_index == 7
    assert target.eligibility_reason == "EXPIRE_OPPOSITE_ZONE_RETRACE"
    assert target.route_blocker_zone_id == blocker.zone_id
    assert target.setup_state is SetupState.REJECTED


def test_invalidated_opposite_zone_does_not_block_eligible_route() -> None:
    rows = [
        *load_cases()[0]["bars"],
        {"time": "t3", "open": 10.5, "high": 10.6, "low": 10.3, "close": 10.4},
        {"time": "t4", "open": 10.4, "high": 10.45, "low": 10.15, "close": 10.2},
        {"time": "t5", "open": 10.2, "high": 10.61, "low": 10.1, "close": 10.55},
        {"time": "t6", "open": 10.55, "high": 10.58, "low": 10.0, "close": 10.05},
        {"time": "t7", "open": 10.05, "high": 10.72, "low": 9.95, "close": 10.7},
    ]

    result = detect_zones([Bar.from_mapping(row) for row in rows])
    target = next(zone for zone in result.zones if zone.origin_index == 1)
    opposite = next(
        zone
        for zone in result.zones
        if zone.direction is Direction.SUPPLY and zone.confirmation_index == 6
    )

    assert opposite.state is ZoneState.INVALIDATED
    assert target.state is ZoneState.CONFIRMED_FRESH
    assert target.eligibility_state is EligibilityState.ELIGIBLE
    assert target.eligibility_reason == "LIQUIDITY_OWN_EXTREME_TAKEN"
    assert target.route_blocker_zone_id is None
    assert target.setup_state is SetupState.ARMED


def test_demand_setup_triggers_on_first_valid_return_after_liquidity() -> None:
    rows = [
        *load_cases()[0]["bars"],
        {"time": "t3", "open": 10.5, "high": 10.6, "low": 10.3, "close": 10.4},
        {"time": "t4", "open": 10.4, "high": 10.45, "low": 10.15, "close": 10.2},
        {"time": "t5", "open": 10.2, "high": 10.61, "low": 10.1, "close": 10.55},
        {"time": "t6", "open": 10.55, "high": 10.6, "low": 9.8, "close": 9.95},
    ]

    zone = detect_zones([Bar.from_mapping(row) for row in rows]).zones[0]

    assert zone.state is ZoneState.TAPPED
    assert zone.setup_state is SetupState.TRIGGERED
    assert zone.setup_index == 6
    assert zone.setup_time == "t6"
    assert zone.setup_reason == "TRIGGER_FIRST_FRESH_TAP_AFTER_LIQUIDITY"


def test_supply_setup_triggers_on_first_valid_return_after_liquidity() -> None:
    rows = [
        {"time": "t0", "open": 10.4, "high": 10.5, "low": 10.1, "close": 10.2},
        {"time": "t1", "open": 10.2, "high": 10.6, "low": 10.15, "close": 10.5},
        {"time": "t2", "open": 10.5, "high": 10.55, "low": 9.9, "close": 10.0},
        {"time": "t3", "open": 9.9, "high": 10.05, "low": 9.7, "close": 10.0},
        {"time": "t4", "open": 10.0, "high": 10.1, "low": 9.8, "close": 10.05},
        {"time": "t5", "open": 10.05, "high": 10.1, "low": 9.65, "close": 9.7},
        {"time": "t6", "open": 9.7, "high": 10.2, "low": 9.65, "close": 10.1},
    ]

    zone = next(
        zone
        for zone in detect_zones([Bar.from_mapping(row) for row in rows]).zones
        if zone.origin_index == 1
    )

    assert zone.state is ZoneState.TAPPED
    assert zone.setup_state is SetupState.TRIGGERED
    assert zone.setup_index == 6
    assert zone.setup_reason == "TRIGGER_FIRST_FRESH_TAP_AFTER_LIQUIDITY"


def test_armed_setup_rejects_when_return_closes_beyond_target_distal() -> None:
    rows = [
        *load_cases()[0]["bars"],
        {"time": "t3", "open": 10.5, "high": 10.6, "low": 10.3, "close": 10.4},
        {"time": "t4", "open": 10.4, "high": 10.45, "low": 10.15, "close": 10.2},
        {"time": "t5", "open": 10.2, "high": 10.61, "low": 10.1, "close": 10.55},
        {"time": "t6", "open": 10.55, "high": 10.6, "low": 9.2, "close": 9.3},
    ]

    zone = detect_zones([Bar.from_mapping(row) for row in rows]).zones[0]

    assert zone.state is ZoneState.INVALIDATED
    assert zone.setup_state is SetupState.REJECTED
    assert zone.setup_index == 6
    assert zone.setup_reason == "REJECT_TARGET_INVALIDATED_ON_RETURN"


def test_same_bar_target_and_opposite_zone_taps_fail_closed() -> None:
    rows = [
        *load_cases()[0]["bars"],
        {"time": "t3", "open": 10.5, "high": 10.6, "low": 10.3, "close": 10.4},
        {"time": "t4", "open": 10.4, "high": 10.45, "low": 10.15, "close": 10.2},
        {"time": "t5", "open": 10.2, "high": 10.61, "low": 10.1, "close": 10.55},
        {"time": "t6", "open": 10.55, "high": 10.58, "low": 10.0, "close": 10.05},
        {"time": "t7", "open": 10.05, "high": 10.2, "low": 9.8, "close": 10.1},
    ]

    result = detect_zones([Bar.from_mapping(row) for row in rows])
    target = next(zone for zone in result.zones if zone.origin_index == 1)
    blocker = next(
        zone
        for zone in result.zones
        if zone.direction is Direction.SUPPLY and zone.confirmation_index == 6
    )

    assert target.state is ZoneState.TAPPED
    assert blocker.state is ZoneState.TAPPED
    assert target.eligibility_state is EligibilityState.EXPIRED
    assert target.route_blocker_zone_id == blocker.zone_id
    assert target.setup_state is SetupState.REJECTED
    assert target.setup_reason == "REJECT_AMBIGUOUS_SAME_BAR_ROUTE"
