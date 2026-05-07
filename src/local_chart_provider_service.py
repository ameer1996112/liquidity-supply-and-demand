from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import subprocess
import time
from typing import Any, Dict, List, Optional, Sequence

from src.services.tradingview_mcp_compatibility import get_tradingview_mcp_compatibility_service


MCP_REPO_PATH = Path(__file__).resolve().parents[1] / "mcp" / "tradingview-mcp"


def _normalize_timeframe(raw_resolution: str) -> str:
    return f"{raw_resolution}m" if raw_resolution.isdigit() else raw_resolution


def _mcp_timeframe(requested_timeframe: str) -> str:
    raw = str(requested_timeframe or "").strip()
    if raw.lower().endswith("m") and raw[:-1].isdigit():
        return raw[:-1]
    return raw


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


def _normalize_setup_time(value: Optional[str]) -> Optional[str]:
    if not value:
        return None
    raw = str(value).strip()
    if not raw:
        return None
    try:
        if raw.isdigit():
            dt = datetime.fromtimestamp(int(raw), tz=timezone.utc)
        else:
            cleaned = raw.replace("Z", "+00:00")
            if "T" not in cleaned and " " in cleaned:
                cleaned = cleaned.replace(" ", "T")
            dt = datetime.fromisoformat(cleaned)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            else:
                dt = dt.astimezone(timezone.utc)
        return dt.replace(microsecond=0).isoformat().replace("+00:00", "Z")
    except (TypeError, ValueError):
        return raw


def _setup_date(value: str) -> str:
    normalized = _normalize_setup_time(value) or value
    return normalized[:10]


def _should_use_replay(setup_time: Optional[str], now_iso: Optional[str] = None) -> bool:
    normalized = _normalize_setup_time(setup_time)
    if not normalized:
        return False
    now_normalized = _normalize_setup_time(now_iso or _now_iso()) or _now_iso()
    return _setup_date(normalized) < _setup_date(now_normalized)


def _replay_start_date(setup_time: str) -> str:
    normalized = _normalize_setup_time(setup_time) or setup_time
    try:
        dt = datetime.fromisoformat(normalized.replace("Z", "+00:00"))
    except ValueError:
        return _setup_date(normalized)
    return (dt - timedelta(days=1)).date().isoformat()


def _safe_name_token(value: Any) -> str:
    token = str(value or "").strip()
    return "".join(ch if ch.isalnum() or ch in ("-", "_") else "-" for ch in token).strip("-")


def _to_float(value: Any) -> Optional[float]:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _symbol_matches(actual: Any, requested: str) -> bool:
    actual_text = str(actual or "").upper()
    requested_text = requested.upper()
    if not actual_text or not requested_text:
        return False
    return actual_text == requested_text or actual_text.endswith(f":{requested_text}")


def _requested_focus_zone(
    requested_zone_id: Optional[int],
    zone_top: Optional[float],
    zone_bottom: Optional[float],
    zone_type: Optional[str],
) -> Optional[Dict[str, Any]]:
    if requested_zone_id is None or zone_top is None or zone_bottom is None:
        return None
    high = max(zone_top, zone_bottom)
    low = min(zone_top, zone_bottom)
    return {
        "type": zone_type or "price_zone",
        "source": "signal",
        "id": requested_zone_id,
        "label": f"{(zone_type or 'zone').upper()}-{requested_zone_id}",
        "high": high,
        "low": low,
    }


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
        return None
    for zone in zones:
        if zone.get("type") == "price_zone":
            return zone
    return None


def _zone_matches_requested_focus(
    zone: Optional[Dict[str, Any]],
    requested_focus_zone: Optional[Dict[str, Any]],
) -> bool:
    if not zone or not requested_focus_zone:
        return True
    requested_high = _to_float(requested_focus_zone.get("high"))
    requested_low = _to_float(requested_focus_zone.get("low"))
    actual_high = _to_float(zone.get("high"))
    actual_low = _to_float(zone.get("low"))
    if requested_high is None or requested_low is None:
        return True
    if actual_high is None or actual_low is None:
        return False
    return abs(actual_high - requested_high) <= 0.00001 and abs(actual_low - requested_low) <= 0.00001


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


def _screenshot_has_chart_content(screenshot_payload: Optional[Dict[str, Any]]) -> bool:
    path = (screenshot_payload or {}).get("file_path")
    if not path or not Path(str(path)).exists():
        return True
    try:
        from PIL import Image, ImageStat

        image = Image.open(str(path)).convert("L")
        stat = ImageStat.Stat(image)
        mean = float(stat.mean[0])
        stddev = float(stat.stddev[0])
        image.close()
        return mean > 30 and stddev > 8
    except Exception:
        return True


def _build_setup_evidence(
    focus_zone: Optional[Dict[str, Any]],
    screenshot_payload: Optional[Dict[str, Any]],
    requested_zone_id: Optional[int] = None,
) -> Dict[str, Any]:
    if screenshot_payload and screenshot_payload.get("success"):
        missing_requested_zone = requested_zone_id is not None and not focus_zone
        return {
            "status": "degraded" if missing_requested_zone else "ok" if focus_zone else "degraded",
            "focus_zone": focus_zone,
            "focus_image": {
                "path": screenshot_payload.get("file_path", ""),
                "region": screenshot_payload.get("region", "chart"),
            },
            "requested_zone_id": requested_zone_id,
            "reason": (
                ""
                if focus_zone
                else f"requested zone {requested_zone_id} not detected; screenshot captured"
                if requested_zone_id is not None
                else "zone not detected; full chart screenshot captured"
            ),
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
    requested_focus_zone: Optional[Dict[str, Any]] = None,
    boxes_payload: Optional[Dict[str, Any]] = None,
    screenshot_payload: Optional[Dict[str, Any]] = None,
    setup_time: Optional[str] = None,
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
    normalized_labels = _normalize_labels(labels_payload if labels_payload and labels_payload.get("success") else None)
    focus_zone_candidates = [*normalized_box_zones, *normalized_labels, *normalized_line_zones]
    focus_zone = (
        _pick_primary_zone(focus_zone_candidates, requested_zone_id)
        or requested_focus_zone
        or (normalized_line_zones[0] if requested_zone_id is None and normalized_line_zones else None)
    )
    if requested_focus_zone and not _zone_matches_requested_focus(focus_zone, requested_focus_zone):
        focus_zone = requested_focus_zone
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
        "pine_labels": normalized_labels,
        "zones": [*normalized_box_zones, *normalized_line_zones],
        "indicator_values": _normalize_indicator_values(values_payload if values_payload and values_payload.get("success") else None),
        "setup_evidence": _build_setup_evidence(focus_zone, screenshot_payload, requested_zone_id),
        "reason": "",
        "metadata": {
            "requested_symbol": requested_symbol,
            "requested_timeframe": requested_timeframe,
            "requested_zone_id": requested_zone_id,
            "setup_time": _normalize_setup_time(setup_time),
            "partial_failures": partial_failures,
        },
    }


def run_mcp_command(command: Sequence[str]) -> Dict[str, Any]:
    try:
        completed = subprocess.run(
            command,
            cwd=MCP_REPO_PATH,
            capture_output=True,
            text=True,
            timeout=25,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        return {
            "success": False,
            "error": f"MCP command timed out after {exc.timeout} seconds: {' '.join(command)}",
        }
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
    setup_time: Optional[str] = None,
    zone_top: Optional[float] = None,
    zone_bottom: Optional[float] = None,
    zone_type: Optional[str] = None,
) -> Dict[str, Any]:
    requested_focus_zone = _requested_focus_zone(zone_id, zone_top, zone_bottom, zone_type)
    compatibility_status = get_chart_provider_compatibility_status()
    if not compatibility_status.get("chart_context_enabled"):
        payload = build_chart_context_payload(
            requested_symbol=requested_symbol,
            requested_timeframe=requested_timeframe,
            requested_zone_id=zone_id,
            requested_focus_zone=requested_focus_zone,
            setup_time=setup_time,
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
            requested_focus_zone=requested_focus_zone,
            setup_time=setup_time,
            status_payload=status_payload,
            values_payload=None,
            lines_payload=None,
            labels_payload=None,
            boxes_payload=None,
            screenshot_payload=None,
        )

    normalized_setup_time = _normalize_setup_time(setup_time)
    screenshot_time = normalized_setup_time or _now_iso()
    screenshot_parts = ["setup", requested_symbol, requested_timeframe]
    if zone_id is not None:
        screenshot_parts.append(str(zone_id))
    screenshot_parts.append(screenshot_time)
    screenshot_name = "_".join(_safe_name_token(part) for part in screenshot_parts if part)
    replay_stop_payload: Optional[Dict[str, Any]] = None
    if normalized_setup_time:
        replay_stop_payload = run_mcp_command(["node", "src/cli/index.js", "replay", "stop"])
    symbol_payload = run_mcp_command(["node", "src/cli/index.js", "symbol", requested_symbol])
    timeframe_payload = run_mcp_command(["node", "src/cli/index.js", "timeframe", _mcp_timeframe(requested_timeframe)])
    replay_payload: Optional[Dict[str, Any]] = None
    scroll_payload: Optional[Dict[str, Any]] = None
    if normalized_setup_time and _should_use_replay(normalized_setup_time):
        replay_payload = run_mcp_command(
            ["node", "src/cli/index.js", "replay", "start", "--date", _replay_start_date(normalized_setup_time)]
        )
    if normalized_setup_time:
        scroll_payload = run_mcp_command(["node", "src/cli/index.js", "scroll", normalized_setup_time])
    final_status_payload = run_mcp_command(["node", "src/cli/index.js", "status"])
    values_payload = run_mcp_command(["node", "src/cli/index.js", "values"])
    lines_payload = run_mcp_command(["node", "src/cli/index.js", "data", "lines"])
    labels_payload = run_mcp_command(["node", "src/cli/index.js", "data", "labels"])
    boxes_payload = run_mcp_command(["node", "src/cli/index.js", "data", "boxes", "--verbose"])
    visual_ready = symbol_payload.get("chart_ready") is not False and timeframe_payload.get("chart_ready") is not False
    if visual_ready:
        screenshot_payload = run_mcp_command(
            ["node", "src/cli/index.js", "screenshot", "--region", "chart", "--output", screenshot_name]
        )
        if screenshot_payload.get("success") and not _screenshot_has_chart_content(screenshot_payload):
            time.sleep(2)
            screenshot_payload = run_mcp_command(
                ["node", "src/cli/index.js", "screenshot", "--region", "chart", "--output", screenshot_name]
            )
        if screenshot_payload.get("success") and not _screenshot_has_chart_content(screenshot_payload):
            screenshot_payload = {
                "success": False,
                "error": "visual chart screenshot was blank or still loading",
            }
    else:
        screenshot_payload = {
            "success": False,
            "error": "visual chart did not confirm requested symbol/timeframe; screenshot skipped",
        }

    payload = build_chart_context_payload(
        requested_symbol=requested_symbol,
        requested_timeframe=requested_timeframe,
        requested_zone_id=zone_id,
        requested_focus_zone=requested_focus_zone,
        status_payload={
            **status_payload,
            **{k: v for k, v in symbol_payload.items() if k.startswith("chart_")},
            **{k: v for k, v in timeframe_payload.items() if k.startswith("chart_")},
            **{k: v for k, v in final_status_payload.items() if k.startswith("chart_")},
        },
        values_payload=values_payload,
        lines_payload=lines_payload,
        labels_payload=labels_payload,
        boxes_payload=boxes_payload,
        screenshot_payload=screenshot_payload,
        setup_time=normalized_setup_time,
    )
    partial_failures = payload["metadata"].setdefault("partial_failures", [])
    if not symbol_payload.get("success"):
        partial_failures.append(symbol_payload.get("error", "symbol switch failed"))
    elif symbol_payload.get("chart_ready") is False:
        partial_failures.append("visual chart did not confirm requested symbol after switch")
    if not timeframe_payload.get("success"):
        partial_failures.append(timeframe_payload.get("error", "timeframe switch failed"))
    elif timeframe_payload.get("chart_ready") is False:
        partial_failures.append("visual chart did not confirm requested timeframe after switch")
    if not final_status_payload.get("success"):
        partial_failures.append(final_status_payload.get("error", "post-navigation status failed"))
    elif not _symbol_matches(final_status_payload.get("chart_symbol"), requested_symbol):
        partial_failures.append(
            f"requested symbol {requested_symbol} not active; active chart is {final_status_payload.get('chart_symbol')}"
        )
    if replay_payload is not None and not replay_payload.get("success"):
        partial_failures.append(replay_payload.get("error", "replay start failed"))
    if replay_stop_payload is not None and not replay_stop_payload.get("success"):
        partial_failures.append(replay_stop_payload.get("error", "replay stop failed"))
    if scroll_payload is not None and not scroll_payload.get("success"):
        partial_failures.append(scroll_payload.get("error", "setup time scroll failed"))
    return payload
