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


def build_payload() -> Dict[str, Any]:
    """Build a representative TradingView-style payload."""
    return {
        "action": "buy",
        "symbol": "XAUUSD",
        "price": 2350.00,
        "sl": 2340.00,
        "tp": 2380.00,
        "atr": 2.5,
        "F:score": 85,
        "F:signal_encoded": 95,
    }


def main() -> None:
    base_url = os.getenv("API_BASE_URL", "http://localhost:8000")
    url = f"{base_url.rstrip('/')}/webhook"

    payload = build_payload()
    headers = {"Content-Type": "application/json"}

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

