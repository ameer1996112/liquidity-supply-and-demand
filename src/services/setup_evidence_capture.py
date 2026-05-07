from __future__ import annotations

import logging
import os
import threading
from typing import Any, Callable, Dict, Optional

from src.services.ai_operating_layer import fetch_and_normalize_chart_context

logger = logging.getLogger(__name__)

ChartContextProvider = Callable[..., Dict[str, Any]]


def _to_int(value: Any) -> Optional[int]:
    if value in (None, ""):
        return None
    try:
        return int(str(value).strip().strip("#"))
    except (TypeError, ValueError):
        return None


def _payload_zone_id(payload: Dict[str, Any]) -> Optional[int]:
    for key in ("zone_id", "F:zone_id", "zoneId", "zone"):
        zone_id = _to_int(payload.get(key))
        if zone_id is not None:
            return zone_id
    return None


def _payload_setup_time(payload: Dict[str, Any]) -> Optional[str]:
    for key in ("bar_time", "signal_time", "created_at", "time", "timestamp"):
        value = payload.get(key)
        if value not in (None, ""):
            return str(value)
    return None


def _payload_value(payload: Dict[str, Any], key: str) -> Any:
    return payload.get(key) if payload.get(key) is not None else payload.get(f"F:{key}")


def _extract_setup_evidence(chart_context: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    structured = chart_context.get("structured")
    if not isinstance(structured, dict):
        return None
    setup_evidence = structured.get("setup_evidence")
    if not isinstance(setup_evidence, dict):
        return None

    screenshot_url = chart_context.get("screenshot_url")
    focus_image = setup_evidence.get("focus_image")
    if isinstance(focus_image, dict) and screenshot_url and not focus_image.get("url"):
        setup_evidence = {
            **setup_evidence,
            "focus_image": {**focus_image, "url": screenshot_url},
        }

    return setup_evidence


def _focus_image_url(setup_evidence: Dict[str, Any]) -> Optional[str]:
    focus_image = setup_evidence.get("focus_image")
    if isinstance(focus_image, dict) and focus_image.get("url"):
        return str(focus_image["url"])
    return None


def _to_float(value: Any) -> Optional[float]:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _nearly_equal(left: float, right: float, tolerance: float = 0.00001) -> bool:
    return abs(left - right) <= tolerance


def setup_evidence_matches_signal(payload: Dict[str, Any], setup_evidence: Any) -> bool:
    """Return True only when evidence points at this signal's exact setup zone."""
    if not isinstance(setup_evidence, dict):
        return False
    if setup_evidence.get("status") != "ok":
        return False
    if not _focus_image_url(setup_evidence):
        return False

    zone_id = _payload_zone_id(payload)
    focus_zone = setup_evidence.get("focus_zone")
    if zone_id is None or not isinstance(focus_zone, dict):
        return False

    focus_zone_id = _to_int(focus_zone.get("id"))
    if focus_zone_id != zone_id:
        return False

    expected_top = _to_float(_payload_value(payload, "zone_top"))
    expected_bottom = _to_float(_payload_value(payload, "zone_bottom"))
    if expected_top is not None and expected_bottom is not None:
        expected_high = max(expected_top, expected_bottom)
        expected_low = min(expected_top, expected_bottom)
        actual_high = _to_float(focus_zone.get("high"))
        actual_low = _to_float(focus_zone.get("low"))
        if actual_high is None or actual_low is None:
            return False
        if not _nearly_equal(actual_high, expected_high) or not _nearly_equal(actual_low, expected_low):
            return False

    expected_type = _payload_value(payload, "zone_type")
    actual_type = focus_zone.get("type")
    if expected_type and actual_type and str(expected_type).lower() != str(actual_type).lower():
        return False

    return True


def needs_setup_evidence_backfill(row: Dict[str, Any]) -> bool:
    return _payload_zone_id(row) is not None and not setup_evidence_matches_signal(
        row,
        row.get("setup_evidence"),
    )


def capture_setup_evidence_for_signal(
    supabase_client: Any,
    signal_id: int,
    payload: Dict[str, Any],
    provider: ChartContextProvider = fetch_and_normalize_chart_context,
) -> bool:
    zone_id = _payload_zone_id(payload)
    symbol = str(payload.get("symbol") or "").strip()
    timeframe = str(payload.get("timeframe") or "5m").strip() or "5m"
    setup_time = _payload_setup_time(payload)
    if not supabase_client or not signal_id or not zone_id or not symbol:
        return False

    base_url = (
        os.environ.get("LOCAL_CHART_PROVIDER_BASE_URL")
        or os.environ.get("CHART_CONTEXT_PROVIDER_URL")
        or "http://localhost:8765"
    )
    try:
        chart_context = provider(
            base_url=base_url,
            symbol=symbol,
            timeframe=timeframe,
            timeout_seconds=25.0,
            retry_count=0,
            zone_id=zone_id,
            setup_time=setup_time,
            zone_top=_payload_value(payload, "zone_top"),
            zone_bottom=_payload_value(payload, "zone_bottom"),
            zone_type=_payload_value(payload, "zone_type"),
        )
        setup_evidence = _extract_setup_evidence(chart_context)
        if not setup_evidence:
            return False

        update_payload: Dict[str, Any] = {"setup_evidence": setup_evidence}
        image_url = _focus_image_url(setup_evidence)
        update_payload["image_url"] = image_url

        supabase_client.table("trading_signals").update(update_payload).eq("id", signal_id).execute()
        logger.info("Setup evidence captured for signal_id=%s zone_id=%s", signal_id, zone_id)
        return True
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "Setup evidence capture failed for signal_id=%s zone_id=%s: %s",
            signal_id,
            zone_id,
            exc,
        )
        return False


def schedule_setup_evidence_capture(
    supabase_client: Any,
    signal_id: int,
    payload: Dict[str, Any],
) -> None:
    if _payload_zone_id(payload) is None:
        return

    thread = threading.Thread(
        target=capture_setup_evidence_for_signal,
        args=(supabase_client, signal_id, dict(payload)),
        daemon=True,
        name=f"SetupEvidenceCapture-{signal_id}",
    )
    thread.start()
