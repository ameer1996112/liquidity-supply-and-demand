"""
Fire drill script: simulate a TradingView webhook hitting the local API.

Run from project root:

    python scripts/simulate_signal.py

It will POST a fake signal to http://localhost:8000/webhook and print
the HTTP status code and JSON/text response.
"""

from __future__ import annotations

import json
import os
from typing import Any, Dict

import requests


def build_payload(symbol: str = "XAUUSD", zone_id: int = 0) -> Dict[str, Any]:
    """Build a representative TradingView-style payload. Use symbol=NAS100 to test index pts+pips in Discord."""
    if symbol.upper() == "NAS100":
        entry, sl, tp = 25893.16, 25886.28, 25920.68
        size = 0.1
    else:
        entry, sl, tp = 2350.00, 2340.00, 2380.00
        size = 0.1
    payload = {
        "symbol": symbol,
        "side": "buy",
        "entry": entry,
        "sl": sl,
        "tp": tp,
        "size": size,
        "action": "buy",
        "atr": 2.5,
        "F:score": 85,
        "F:signal_encoded": 95,
    }
    if zone_id:
        payload["zone_id"] = zone_id
        payload["trade_key"] = f"{symbol}_{zone_id}"
    return payload


def main() -> None:
    base_url = os.getenv("API_BASE_URL", "http://localhost:8000")
    symbol = os.getenv("SIMULATE_SYMBOL", "XAUUSD").strip().upper() or "XAUUSD"
    zone_id = int(os.getenv("ZONE_ID", "0"))
    url = f"{base_url.rstrip('/')}/webhook"

    payload = build_payload(symbol, zone_id=zone_id)
    headers = {"Content-Type": "application/json"}

    # Optional webhook secret for auth (matches API validate_webhook_secret)
    secret = os.getenv("WEBHOOK_SECRET", "").strip().strip('"').strip("'")
    if secret:
        headers["X-Webhook-Secret"] = secret

    print(f"POST {url}")
    print("Payload:")
    print(json.dumps(payload, indent=2))

    try:
        resp = requests.post(url, headers=headers, json=payload, timeout=10)
    except Exception as e:
        print(f"\n❌ Request failed: {e}")
        return

    print(f"\n✅ Response status: {resp.status_code}")
    ctype = resp.headers.get("content-type", "")
    body: Any
    if "application/json" in ctype.lower():
        try:
            body = resp.json()
        except Exception:
            body = resp.text
    else:
        body = resp.text

    print("Response body:")
    if isinstance(body, (dict, list)):
        print(json.dumps(body, indent=2))
    else:
        print(body)


if __name__ == "__main__":
    main()

