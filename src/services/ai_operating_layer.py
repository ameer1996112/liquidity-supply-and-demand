from __future__ import annotations

from typing import Any, Dict

from src.adapters.tradingview_chart_provider import fetch_chart_context
from src.services.chart_context_service import (
    ChartContextProviderResult,
    normalize_chart_context,
)


def _base_layered_output() -> Dict[str, Any]:
    return {
        "top_level": {"verdict": "unclear", "confidence": 0},
        "scorecard": {"confluence": [], "risks": [], "evidence": []},
        "deep_layer": {"agent_opinions": [], "disagreements": []},
    }


def fetch_and_normalize_chart_context(
    base_url: str,
    symbol: str,
    timeframe: str,
    timeout_seconds: float,
    retry_count: int,
    zone_id: int | str | None = None,
    setup_time: str | None = None,
    zone_top: float | str | None = None,
    zone_bottom: float | str | None = None,
    zone_type: str | None = None,
) -> Dict[str, Any]:
    raw = fetch_chart_context(
        base_url,
        symbol,
        timeframe,
        timeout_seconds,
        retry_count,
        zone_id=zone_id,
        setup_time=setup_time,
        zone_top=zone_top,
        zone_bottom=zone_bottom,
        zone_type=zone_type,
    )
    setup_evidence = raw.get(
        "setup_evidence",
        {
            "status": "degraded",
            "focus_zone": None,
            "focus_image": None,
            "reason": raw.get("reason", "setup evidence unavailable"),
        },
    )
    screenshot_url = (
        ((setup_evidence.get("focus_image") or {}).get("url"))
        if isinstance(setup_evidence, dict)
        else None
    ) or raw.get("screenshot_url")
    return normalize_chart_context(
        ChartContextProviderResult(
            ok=raw.get("ok", False),
            symbol=raw.get("symbol", symbol),
            timeframe=raw.get("timeframe", timeframe),
            structured={
                "provider_timestamp": raw.get("provider_timestamp"),
                "pine_labels": raw.get("pine_labels", []),
                "zones": raw.get("zones", []),
                "indicator_values": raw.get("indicator_values", {}),
                "setup_evidence": setup_evidence,
            }
            if raw.get("ok")
            else {"setup_evidence": setup_evidence},
            screenshot_url=screenshot_url,
            reason=raw.get("reason", ""),
        )
    )


def build_shadow_pretrade_run(
    signal_payload: Dict[str, Any],
    chart_context: Dict[str, Any] | None,
    pine_context: Dict[str, Any],
) -> Dict[str, Any]:
    resolved_chart_context = chart_context or fetch_and_normalize_chart_context(
        base_url="http://localhost:8765",
        symbol=str(signal_payload.get("symbol", "UNKNOWN")),
        timeframe=str(signal_payload.get("timeframe", "5m")),
        timeout_seconds=1.0,
        retry_count=2,
        zone_id=signal_payload.get("zone_id"),
    )
    return {
        "analysis_mode": "shadow_pretrade",
        "signal_payload": signal_payload,
        "chart_context": resolved_chart_context,
        "pine_context": pine_context,
        "module_status": {
            "chart_context": {
                "status": resolved_chart_context.get("status", "degraded"),
                "reason": resolved_chart_context.get("reason", ""),
            }
        },
        "layered_output": _base_layered_output(),
    }


def build_posttrade_review_run(
    signal_payload: Dict[str, Any],
    trade_outcome: Dict[str, Any],
    chart_context: Dict[str, Any] | None,
    pine_context: Dict[str, Any],
) -> Dict[str, Any]:
    payload = build_shadow_pretrade_run(signal_payload, chart_context, pine_context)
    payload["analysis_mode"] = "posttrade_review"
    payload["trade_outcome"] = trade_outcome
    return payload
