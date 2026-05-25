from __future__ import annotations

from collections.abc import Iterable

from scripts.pinescript.validation.models import Zone


def _first_value(data: dict, keys: Iterable[str]) -> object | None:
    for key in keys:
        if key in data and data[key] is not None:
            return data[key]
    return None


def _required_float(data: dict, keys: Iterable[str], field_name: str) -> float:
    value = _first_value(data, keys)
    if value is None:
        raise ValueError(f"raw TradingView box missing required {field_name} coordinate")
    return float(value)


def _optional_str(value: object | None) -> str | None:
    if value is None:
        return None
    return str(value)


def _label_for_box(raw_labels: list[dict], box_id: str | None, source: str) -> str:
    for label in raw_labels:
        label_box_id = _first_value(label, ["boxId", "box_id", "parentId", "parent_id"])
        label_source = str(_first_value(label, ["study", "source", "script", "owner"]) or "")
        if box_id is not None and label_box_id is not None and str(label_box_id) == str(box_id):
            return str(_first_value(label, ["text", "label", "name"]) or "").strip()
        if not box_id and label_source == source:
            text = str(_first_value(label, ["text", "label", "name"]) or "").strip()
            if text.startswith(("D-", "S-", "ACC D-", "ACC S-")):
                return text
    return ""


def _side_from_label(label: str) -> str:
    clean = label.strip().upper()
    if clean.startswith("ACC D-") or clean.startswith("D-"):
        return "demand"
    if clean.startswith("ACC S-") or clean.startswith("S-"):
        return "supply"
    return "demand"


def normalize_zones(*, raw_boxes: list[dict], raw_labels: list[dict]) -> list[Zone]:
    zones: list[Zone] = []
    for box in raw_boxes:
        box_id_value = _first_value(box, ["id", "boxId", "box_id"])
        box_id = str(box_id_value) if box_id_value is not None else None
        source = str(_first_value(box, ["study", "source", "script", "owner"]) or "unknown")
        label = _label_for_box(raw_labels, box_id, source)
        top = _required_float(box, ["top", "high", "zoneHigh"], "top")
        bottom = _required_float(box, ["bottom", "low", "zoneLow"], "bottom")
        zones.append(
            Zone(
                source=source,
                side=_side_from_label(label),  # type: ignore[arg-type]
                top=max(top, bottom),
                bottom=min(top, bottom),
                left_time=_optional_str(_first_value(box, ["leftTime", "left_time", "startTime", "start_time"])),
                right_time=_optional_str(_first_value(box, ["rightTime", "right_time", "endTime", "end_time"])),
                label=label,
                id=box_id,
            )
        )
    return zones
