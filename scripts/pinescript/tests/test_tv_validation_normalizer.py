from scripts.pinescript.validation.normalizer import normalize_zones


def main() -> None:
    raw_boxes = [
        {
            "id": "box-1",
            "top": 4496.0,
            "bottom": 4492.0,
            "leftTime": "2026-05-20T03:45:00+03:00",
            "rightTime": "2026-05-20T13:00:00+03:00",
            "study": "S&D Pro",
        },
        {
            "id": 2,
            "top": 212.900,
            "bottom": 212.880,
            "left_time": "2026-05-20T12:30:00+03:00",
            "right_time": "2026-05-20T13:00:00+03:00",
            "study": "Zones Liq S/D v23 - Myrtille",
        },
    ]
    raw_labels = [
        {"text": " S-19396 ", "boxId": "box-1", "study": "S&D Pro"},
        {"text": "D-13856", "boxId": 2, "study": "Zones Liq S/D v23 - Myrtille"},
    ]

    zones = normalize_zones(raw_boxes=raw_boxes, raw_labels=raw_labels)
    assert len(zones) == 2
    assert zones[0].source == "S&D Pro"
    assert zones[0].side == "supply"
    assert zones[0].label == "S-19396"
    assert zones[1].side == "demand"
    assert zones[1].label == "D-13856"
    assert zones[1].left_time == "2026-05-20T12:30:00+03:00"

    numeric_time_zones = normalize_zones(
        raw_boxes=[
            {
                "id": "numeric-time",
                "top": 11,
                "bottom": 10,
                "leftTime": 1770000000,
                "rightTime": 1770000300,
                "study": "S&D Pro",
            }
        ],
        raw_labels=[{"text": "D-1", "boxId": "numeric-time", "study": "S&D Pro"}],
    )
    assert numeric_time_zones[0].left_time == "1770000000"
    assert numeric_time_zones[0].right_time == "1770000300"

    try:
        normalize_zones(
            raw_boxes=[{"id": "missing-top", "bottom": 10, "study": "S&D Pro"}],
            raw_labels=[],
        )
    except ValueError as exc:
        assert "top" in str(exc)
    else:
        raise AssertionError("missing top coordinate should fail loudly")

    try:
        normalize_zones(
            raw_boxes=[{"id": "missing-bottom", "top": 11, "study": "S&D Pro"}],
            raw_labels=[],
        )
    except ValueError as exc:
        assert "bottom" in str(exc)
    else:
        raise AssertionError("missing bottom coordinate should fail loudly")

    print("TradingView validation normalizer contract passed")


if __name__ == "__main__":
    main()
