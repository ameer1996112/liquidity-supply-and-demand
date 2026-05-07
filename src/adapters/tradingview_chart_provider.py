from __future__ import annotations

from typing import Any, Dict

import requests


def fetch_chart_context(
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
    last_error = "unknown provider error"
    for _attempt in range(retry_count + 1):
        try:
            params: Dict[str, Any] = {"symbol": symbol, "timeframe": timeframe}
            if zone_id not in (None, ""):
                params["zone_id"] = zone_id
            if setup_time not in (None, ""):
                params["setup_time"] = setup_time
            if zone_top not in (None, ""):
                params["zone_top"] = zone_top
            if zone_bottom not in (None, ""):
                params["zone_bottom"] = zone_bottom
            if zone_type not in (None, ""):
                params["zone_type"] = zone_type
            response = requests.get(
                f"{base_url.rstrip('/')}/chart-context",
                params=params,
                timeout=timeout_seconds,
            )
            response.raise_for_status()
            payload = response.json()
            return {"ok": True, **payload}
        except Exception as exc:  # noqa: BLE001
            last_error = str(exc)

    return {
        "ok": False,
        "symbol": symbol,
        "timeframe": timeframe,
        "reason": last_error,
    }
