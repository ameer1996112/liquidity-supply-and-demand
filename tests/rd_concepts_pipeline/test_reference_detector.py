from decimal import Decimal
import json
from pathlib import Path

from scripts.rd_concepts_pipeline.reference_detector import (
    Bar,
    Direction,
    Geometry,
    ZoneState,
    detect_zones,
)


FIXTURE = Path(
    "tests/rd_concepts_pipeline/fixtures/reference_detector_cases.json"
)


def load_cases() -> list[dict]:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


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
