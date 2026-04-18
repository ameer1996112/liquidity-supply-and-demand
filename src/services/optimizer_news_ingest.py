from __future__ import annotations

from datetime import datetime, timezone
from typing import Any


def _normalize_event_time(raw_value: Any) -> str:
    timestamp = str(raw_value).strip()
    if timestamp.endswith("Z"):
        timestamp = f"{timestamp[:-1]}+00:00"

    parsed = datetime.fromisoformat(timestamp)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)

    return parsed.astimezone(timezone.utc).isoformat()


def normalize_trading_economics_event(event: dict[str, Any]) -> dict[str, Any]:
    return {
        "source": "tradingeconomics",
        "external_id": str(event["CalendarId"]),
        "event_time": _normalize_event_time(event["Date"]),
        "currency": event["Currency"],
        "country": event.get("Country"),
        "importance": int(event.get("Importance", 0)),
        "title": event["Event"],
        "payload": event,
    }
