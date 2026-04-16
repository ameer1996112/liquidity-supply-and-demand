from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional


@dataclass(frozen=True)
class ChartContextProviderResult:
    ok: bool
    symbol: str
    timeframe: str
    structured: Optional[Dict[str, Any]]
    screenshot_url: Optional[str]
    reason: str


def normalize_chart_context(provider_result: ChartContextProviderResult) -> Dict[str, Any]:
    if not provider_result.ok:
        return {
            "status": "degraded",
            "symbol": provider_result.symbol,
            "timeframe": provider_result.timeframe,
            "reason": provider_result.reason,
            "structured": {},
            "screenshot_url": provider_result.screenshot_url,
        }

    return {
        "status": "ok",
        "symbol": provider_result.symbol,
        "timeframe": provider_result.timeframe,
        "reason": "",
        "structured": provider_result.structured or {},
        "screenshot_url": provider_result.screenshot_url,
    }
