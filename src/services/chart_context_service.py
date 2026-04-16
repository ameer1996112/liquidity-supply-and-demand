from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional


_REQUIRED_STRUCTURED_KEYS = {
    "provider_timestamp",
    "pine_labels",
    "zones",
    "indicator_values",
}


@dataclass(frozen=True)
class ChartContextProviderResult:
    ok: bool
    symbol: str
    timeframe: str
    structured: Optional[Dict[str, Any]]
    screenshot_url: Optional[str]
    reason: str


def _has_required_structured_fields(structured: Dict[str, Any]) -> bool:
    return _REQUIRED_STRUCTURED_KEYS.issubset(structured.keys())


def normalize_chart_context(provider_result: ChartContextProviderResult) -> Dict[str, Any]:
    structured = provider_result.structured or {}
    if not provider_result.ok:
        return {
            "status": "degraded",
            "symbol": provider_result.symbol,
            "timeframe": provider_result.timeframe,
            "reason": provider_result.reason,
            "structured": {},
            "screenshot_url": provider_result.screenshot_url,
        }
    if not _has_required_structured_fields(structured):
        return {
            "status": "degraded",
            "symbol": provider_result.symbol,
            "timeframe": provider_result.timeframe,
            "reason": "provider returned incomplete structured state",
            "structured": {},
            "screenshot_url": provider_result.screenshot_url,
        }

    return {
        "status": "ok",
        "symbol": provider_result.symbol,
        "timeframe": provider_result.timeframe,
        "reason": "",
        "structured": structured,
        "screenshot_url": provider_result.screenshot_url,
    }
