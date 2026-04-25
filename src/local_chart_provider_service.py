from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess
from typing import Any, Dict, List, Optional, Sequence

from src.services.tradingview_mcp_compatibility import get_tradingview_mcp_compatibility_service


MCP_REPO_PATH = Path(__file__).resolve().parents[1] / "mcp" / "tradingview-mcp"


def _normalize_timeframe(raw_resolution: str) -> str:
    return f"{raw_resolution}m" if raw_resolution.isdigit() else raw_resolution


def _normalize_indicator_values(values_payload: Optional[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    studies = (values_payload or {}).get("studies") or []
    return {
        study["name"]: study.get("values", {})
        for study in studies
        if study.get("name")
    }


def _normalize_zones(lines_payload: Optional[Dict[str, Any]]) -> List[Dict[str, Any]]:
    zones: List[Dict[str, Any]] = []
    for study in ((lines_payload or {}).get("studies") or []):
        for level in study.get("horizontal_levels", []) or []:
            zones.append(
                {
                    "type": "horizontal_level",
                    "source": "pine",
                    "label": study.get("name", ""),
                    "price": level,
                    "study": study.get("name", ""),
                }
            )
    return zones


def _normalize_box_zones(boxes_payload: Optional[Dict[str, Any]]) -> List[Dict[str, Any]]:
    zones: List[Dict[str, Any]] = []
    for study in ((boxes_payload or {}).get("studies") or []):
        verbose_boxes = study.get("all_boxes") or []
        for item in study.get("boxes", []) or []:
            high = item.get("high")
            low = item.get("low")
            if high is None or low is None:
                continue
            coords = next(
                (
                    candidate
                    for candidate in verbose_boxes
                    if candidate.get("high") == high and candidate.get("low") == low
                ),
                {},
            )
            zones.append(
                {
                    "type": "price_zone",
                    "source": "pine",
                    "id": coords.get("id"),
                    "label": study.get("name", ""),
                    "high": high,
                    "low": low,
                    "study": study.get("name", ""),
                    "x1": coords.get("x1"),
                    "x2": coords.get("x2"),
                }
            )
    return zones


def _normalize_labels(labels_payload: Optional[Dict[str, Any]]) -> List[Dict[str, Any]]:
    labels: List[Dict[str, Any]] = []
    for study in ((labels_payload or {}).get("studies") or []):
        for item in study.get("labels", []) or []:
            labels.append(
                {
                    "type": "label",
                    "source": "pine",
                    "id": item.get("id"),
                    "label": item.get("text", ""),
                    "price": item.get("price"),
                    "study": study.get("name", ""),
                }
            )
    return labels


def _zone_matches_requested_id(zone: Dict[str, Any], requested_zone_id: Optional[int]) -> bool:
    if requested_zone_id is None:
        return False
    target = str(requested_zone_id)
    for key in ("id", "zone_id"):
        if zone.get(key) is not None and str(zone.get(key)).strip("#") == target:
            return True
    label = str(zone.get("label") or "")
    return target in label or f"#{target}" in label


def _pick_primary_zone(
    zones: Sequence[Dict[str, Any]],
    requested_zone_id: Optional[int] = None,
) -> Optional[Dict[str, Any]]:
    if requested_zone_id is not None:
        for zone in zones:
            if _zone_matches_requested_id(zone, requested_zone_id):
                return zone
    for zone in zones:
        if zone.get("type") == "price_zone":
            return zone
    return None


def _crop_focus_image(source_path: str, focus_zone: Optional[Dict[str, Any]]) -> Optional[str]:
    if not source_path or not focus_zone:
        return source_path

    x1 = focus_zone.get("x1")
    x2 = focus_zone.get("x2")
    if x1 is None or x2 is None:
        return source_path

    try:
        from PIL import Image

        image = Image.open(source_path)
        width, height = image.size
        left = max(0, int(float(x1) - width * 0.08))
        right = min(width, int(float(x2) + width * 0.08))
        top = max(0, int(height * 0.18))
        bottom = min(height, int(height * 0.82))
        cropped = image.crop((left, top, right, bottom))
        target = str(Path(source_path).with_name(Path(source_path).stem + "_focus.png"))
        cropped.save(target)
        image.close()
        cropped.close()
        return target
    except Exception:
        return source_path


def _build_setup_evidence(
    focus_zone: Optional[Dict[str, Any]],
    screenshot_payload: Optional[Dict[str, Any]],
    requested_zone_id: Optional[int] = None,
) -> Dict[str, Any]:
    if screenshot_payload and screenshot_payload.get("success"):
        return {
            "status": "ok" if focus_zone else "degraded",
            "focus_zone": focus_zone,
            "focus_image": {
                "path": screenshot_payload.get("file_path", ""),
                "region": screenshot_payload.get("region", "chart"),
            },
            "requested_zone_id": requested_zone_id,
            "reason": "" if focus_zone else "zone not detected; full chart screenshot captured",
        }

    return {
        "status": "degraded",
        "focus_zone": focus_zone,
        "focus_image": None,
        "requested_zone_id": requested_zone_id,
        "reason": (screenshot_payload or {}).get("error", "setup image unavailable"),
    }


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def build_chart_context_payload(
    requested_symbol: str,
    requested_timeframe: str,
    status_payload: Dict[str, Any],
    values_payload: Optional[Dict[str, Any]],
    lines_payload: Optional[Dict[str, Any]],
    labels_payload: Optional[Dict[str, Any]],
    requested_zone_id: Optional[int] = None,
    boxes_payload: Optional[Dict[str, Any]] = None,
    screenshot_payload: Optional[Dict[str, Any]] = None,
    now_iso: Optional[str] = None,
) -> Dict[str, Any]:
    timestamp = now_iso or _now_iso()
    if not status_payload.get("success"):
        return {
            "symbol": requested_symbol,
            "timeframe": requested_timeframe,
            "provider_timestamp": timestamp,
            "pine_labels": [],
            "zones": [],
            "indicator_values": {},
            "setup_evidence": {
                "status": "degraded",
                "focus_zone": None,
                "focus_image": None,
                "reason": status_payload.get("error", "status failed"),
            },
            "reason": status_payload.get("error", "status failed"),
            "metadata": {"requested_zone_id": requested_zone_id, "partial_failures": []},
        }

    partial_failures: List[str] = []
    if values_payload and not values_payload.get("success"):
        partial_failures.append(values_payload.get("error", "values failed"))
    if lines_payload and not lines_payload.get("success"):
        partial_failures.append(lines_payload.get("error", "lines failed"))
    if labels_payload and not labels_payload.get("success"):
        partial_failures.append(labels_payload.get("error", "labels failed"))
    if boxes_payload and not boxes_payload.get("success"):
        partial_failures.append(boxes_payload.get("error", "boxes failed"))

    normalized_box_zones = _normalize_box_zones(
        boxes_payload if boxes_payload and boxes_payload.get("success") else None
    )
    normalized_line_zones = _normalize_zones(
        lines_payload if lines_payload and lines_payload.get("success") else None
    )
    focus_zone = _pick_primary_zone(normalized_box_zones, requested_zone_id) or (
        normalized_line_zones[0] if normalized_line_zones else None
    )
    if focus_zone and requested_zone_id is not None:
        focus_zone = {**focus_zone, "requested_zone_id": requested_zone_id}

    if screenshot_payload and screenshot_payload.get("success"):
        screenshot_payload = {
            **screenshot_payload,
            "file_path": _crop_focus_image(
                str(screenshot_payload.get("file_path", "")),
                focus_zone,
            ),
        }

    return {
        "symbol": status_payload.get("chart_symbol", requested_symbol),
        "timeframe": _normalize_timeframe(status_payload.get("chart_resolution", requested_timeframe)),
        "provider_timestamp": timestamp,
        "pine_labels": _normalize_labels(labels_payload if labels_payload and labels_payload.get("success") else None),
        "zones": [*normalized_box_zones, *normalized_line_zones],
        "indicator_values": _normalize_indicator_values(values_payload if values_payload and values_payload.get("success") else None),
        "setup_evidence": _build_setup_evidence(focus_zone, screenshot_payload, requested_zone_id),
        "reason": "",
        "metadata": {
            "requested_symbol": requested_symbol,
            "requested_timeframe": requested_timeframe,
            "requested_zone_id": requested_zone_id,
            "partial_failures": partial_failures,
        },
    }


def run_mcp_command(command: Sequence[str]) -> Dict[str, Any]:
    completed = subprocess.run(
        command,
        cwd=MCP_REPO_PATH,
        capture_output=True,
        text=True,
        timeout=10,
        check=False,
    )
    if completed.returncode != 0:
        return {
            "success": False,
            "error": completed.stderr.strip() or completed.stdout.strip() or "command failed",
        }

    try:
        return json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        return {"success": False, "error": f"invalid JSON from MCP CLI: {exc}"}


def get_chart_provider_compatibility_status() -> Dict[str, Any]:
    return get_tradingview_mcp_compatibility_service().get_status().to_payload()


def fetch_live_chart_context(
    requested_symbol: str,
    requested_timeframe: str,
    zone_id: Optional[int] = None,
) -> Dict[str, Any]:
    compatibility_status = get_chart_provider_compatibility_status()
    if not compatibility_status.get("chart_context_enabled"):
        payload = build_chart_context_payload(
            requested_symbol=requested_symbol,
            requested_timeframe=requested_timeframe,
            requested_zone_id=zone_id,
            status_payload={
                "success": False,
                "error": compatibility_status.get("reason") or "chart context disabled",
            },
            values_payload=None,
            lines_payload=None,
            labels_payload=None,
            boxes_payload=None,
            screenshot_payload=None,
        )
        payload["metadata"]["compatibility"] = compatibility_status
        return payload

    status_payload = run_mcp_command(["node", "src/cli/index.js", "status"])
    if not status_payload.get("success"):
        return build_chart_context_payload(
            requested_symbol=requested_symbol,
            requested_timeframe=requested_timeframe,
            requested_zone_id=zone_id,
            status_payload=status_payload,
            values_payload=None,
            lines_payload=None,
            labels_payload=None,
            boxes_payload=None,
            screenshot_payload=None,
        )

    screenshot_name = f"setup_{requested_symbol}_{requested_timeframe}_{_now_iso()}".replace(":", "-")
    values_payload = run_mcp_command(["node", "src/cli/index.js", "values"])
    lines_payload = run_mcp_command(["node", "src/cli/index.js", "data", "lines"])
    labels_payload = run_mcp_command(["node", "src/cli/index.js", "data", "labels"])
    boxes_payload = run_mcp_command(["node", "src/cli/index.js", "data", "boxes", "--verbose"])
    screenshot_payload = run_mcp_command(
        ["node", "src/cli/index.js", "screenshot", "--region", "chart", "--output", screenshot_name]
    )

    return build_chart_context_payload(
        requested_symbol=requested_symbol,
        requested_timeframe=requested_timeframe,
        requested_zone_id=zone_id,
        status_payload=status_payload,
        values_payload=values_payload,
        lines_payload=lines_payload,
        labels_payload=labels_payload,
        boxes_payload=boxes_payload,
        screenshot_payload=screenshot_payload,
    )
