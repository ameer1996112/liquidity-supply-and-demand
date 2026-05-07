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


def capture_setup_evidence_for_signal(
    supabase_client: Any,
    signal_id: int,
    payload: Dict[str, Any],
    provider: ChartContextProvider = fetch_and_normalize_chart_context,
) -> bool:
    zone_id = _payload_zone_id(payload)
    symbol = str(payload.get("symbol") or "").strip()
    timeframe = str(payload.get("timeframe") or "5m").strip() or "5m"
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
        )
        setup_evidence = _extract_setup_evidence(chart_context)
        if not setup_evidence:
            return False

        update_payload: Dict[str, Any] = {"setup_evidence": setup_evidence}
        image_url = _focus_image_url(setup_evidence)
        if image_url:
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
