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
            "id": "box-2",
            "top": 212.900,
            "bottom": 212.880,
            "left_time": "2026-05-20T12:30:00+03:00",
            "right_time": "2026-05-20T13:00:00+03:00",
            "study": "Zones Liq S/D v23 - Myrtille",
        },
    ]
    raw_labels = [
        {"text": " S-19396 ", "boxId": "box-1", "study": "S&D Pro"},
        {"text": "D-13856", "boxId": "box-2", "study": "Zones Liq S/D v23 - Myrtille"},
    ]

    zones = normalize_zones(raw_boxes=raw_boxes, raw_labels=raw_labels)
    assert len(zones) == 2
    assert zones[0].source == "S&D Pro"
    assert zones[0].side == "supply"
    assert zones[0].label == "S-19396"
    assert zones[1].side == "demand"
    assert zones[1].left_time == "2026-05-20T12:30:00+03:00"

    print("TradingView validation normalizer contract passed")


if __name__ == "__main__":
    main()
