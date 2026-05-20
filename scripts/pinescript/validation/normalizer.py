from __future__ import annotations

from collections.abc import Iterable

from scripts.pinescript.validation.models import Zone


def _first_value(data: dict, keys: Iterable[str]) -> object | None:
    for key in keys:
        if key in data and data[key] is not None:
            return data[key]
    return None


def _label_for_box(raw_labels: list[dict], box_id: str | None, source: str) -> str:
    for label in raw_labels:
        label_box_id = _first_value(label, ["boxId", "box_id", "parentId", "parent_id"])
        label_source = str(_first_value(label, ["study", "source", "script", "owner"]) or "")
        if box_id and label_box_id == box_id:
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
        top = float(_first_value(box, ["top", "high", "zoneHigh"]) or 0.0)
        bottom = float(_first_value(box, ["bottom", "low", "zoneLow"]) or 0.0)
        zones.append(
            Zone(
                source=source,
                side=_side_from_label(label),  # type: ignore[arg-type]
                top=max(top, bottom),
                bottom=min(top, bottom),
                left_time=_first_value(box, ["leftTime", "left_time", "startTime", "start_time"]),  # type: ignore[arg-type]
                right_time=_first_value(box, ["rightTime", "right_time", "endTime", "end_time"]),  # type: ignore[arg-type]
                label=label,
                id=box_id,
            )
        )
    return zones
