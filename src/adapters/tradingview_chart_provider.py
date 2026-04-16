from __future__ import annotations

from typing import Any, Dict

import requests


def fetch_chart_context(
    base_url: str,
    symbol: str,
    timeframe: str,
    timeout_seconds: float,
    retry_count: int,
) -> Dict[str, Any]:
    last_error = "unknown provider error"
    for _attempt in range(retry_count + 1):
        try:
            response = requests.get(
                f"{base_url.rstrip('/')}/chart-context",
                params={"symbol": symbol, "timeframe": timeframe},
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
