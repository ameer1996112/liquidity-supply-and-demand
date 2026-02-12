"""
Fire drill script: simulate a TradingView webhook hitting the local API.

Run from project root:

    python scripts/simulate_signal.py
    python scripts/simulate_signal.py --symbol NAS100
    python scripts/simulate_signal.py --symbol GBPJPY --side sell
    python scripts/simulate_signal.py --symbol BTCUSD
    python scripts/simulate_signal.py --all
    python scripts/simulate_signal.py --all --url https://YOUR-APP.up.railway.app

Env vars: SIMULATE_SYMBOL, ZONE_ID, API_BASE_URL, API_WEBHOOK_URL, WEBHOOK_SECRET
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict

import requests

# Load .env from project root (API_BASE_URL, API_WEBHOOK_URL, WEBHOOK_SECRET)
_project_root = Path(__file__).resolve().parent.parent
try:
    from dotenv import load_dotenv
    load_dotenv(_project_root / ".env")
except ImportError:
    pass


# Symbol-specific test payloads (entry, sl, tp, size lots, atr)
# Sized for ~0.5% risk on $50k; adjust as needed.
_SYMBOL_PRESETS: Dict[str, Dict[str, Any]] = {
    "XAUUSD": {
        "entry": 2650.50,
        "sl": 2645.00,
        "tp": 2665.00,
        "size": 0.10,
        "atr": 2.5,
    },
    "NAS100": {
        "entry": 18500.0,
        "sl": 18480.0,
        "tp": 18580.0,
        "size": 0.10,
        "atr": 25.0,
    },
    "GBPJPY": {
        "entry": 185.50,
        "sl": 185.00,
        "tp": 186.50,
        "size": 0.10,
        "atr": 0.35,
    },
    "BTCUSD": {
        "entry": 62000.0,
        "sl": 61800.0,
        "tp": 62600.0,
        "size": 0.01,
        "atr": 500.0,
    },
}


def build_payload(symbol: str = "XAUUSD", zone_id: int = 0, side: str = "buy") -> Dict[str, Any]:
    """
    Build a representative Supply & Demand test payload.

    Supports XAUUSD, NAS100, GBPJPY, BTCUSD with realistic entry/sl/tp/size.
    """
    sym = symbol.upper()


    def _get_preset(s: str) -> Dict[str, Any]:
        for key, preset in _SYMBOL_PRESETS.items():
            if key in s or s in key:
                return preset
        return _SYMBOL_PRESETS["XAUUSD"]

    preset = _get_preset(sym)
    entry = preset["entry"]
    sl = preset["sl"]
    tp = preset["tp"]
    size = preset["size"]
    atr = preset["atr"]

    # Reverse levels for sell (SL above entry, TP below)
    if side.lower() == "sell":
        risk = entry - sl
        reward = tp - entry
        sl = entry + risk
        tp = entry - reward

    payload = {
        "symbol": symbol,
        "side": side.lower(),
        "entry": entry,
        "sl": sl,
        "tp": tp,
        "size": size,
        "action": side.lower(),
        "atr": atr,
        "F:score": 85,
        "F:signal_encoded": 95,
    }
    if zone_id:
        payload["zone_id"] = zone_id
        payload["trade_key"] = f"{symbol}_{zone_id}"
    return payload


def _post_and_print(url: str, payload: Dict[str, Any]) -> None:
    """POST payload to url and print response."""
    headers = {"Content-Type": "application/json"}
    secret = os.getenv("WEBHOOK_SECRET", "").strip().strip('"').strip("'")
    if secret:
        headers["X-Webhook-Secret"] = secret

    print(json.dumps(payload, indent=2))
    try:
        resp = requests.post(url, headers=headers, json=payload, timeout=10)
    except Exception as e:
        print(f"❌ Request failed: {e}")
        return

    print(f"→ {resp.status_code}")
    if resp.status_code == 404:
        if "localhost" in url:
            print(
                "   (404: Using localhost. For Railway: add API_BASE_URL=https://YOUR-APP.up.railway.app to .env)"
            )
        else:
            print(
                "   (404: Check that the backend is deployed and the URL is correct)"
            )
    ctype = resp.headers.get("content-type", "")
    if "application/json" in ctype.lower():
        try:
            body = resp.json()
        except Exception:
            body = resp.text
    else:
        body = resp.text
    if isinstance(body, (dict, list)):
        print(json.dumps(body, indent=2))
    else:
        print(body)


def main() -> None:
    import argparse
    import sys

    parser = argparse.ArgumentParser(description="Simulate webhook POST to /webhook")
    parser.add_argument("json_file", nargs="?", help="Load payload from JSON file")
    parser.add_argument("--symbol", default=None, help="Symbol: XAUUSD, NAS100, GBPJPY, BTCUSD")
    parser.add_argument("--side", default="buy", choices=["buy", "sell"], help="Trade side")
    parser.add_argument("--all", action="store_true", help="Fire all 4 symbols (XAUUSD, NAS100, GBPJPY, BTCUSD)")
    parser.add_argument("--url", default=None, help="Backend URL (e.g. https://xxx.railway.app) overrides .env")
    args = parser.parse_args()

    # --url overrides env; else API_WEBHOOK_URL, API_BASE_URL, NEXT_PUBLIC_API_URL, API_URL
    if args.url:
        base = args.url.strip().rstrip("/")
        url = base if base.endswith("/webhook") else f"{base}/webhook"
    else:
        webhook_url = os.getenv("API_WEBHOOK_URL", "").strip()
        if webhook_url:
            url = webhook_url.rstrip("/")
        else:
            base = (
                os.getenv("API_BASE_URL")
                or os.getenv("NEXT_PUBLIC_API_URL")
                or os.getenv("API_URL")
                or "http://localhost:8000"
            )
            url = f"{base.strip().rstrip('/')}/webhook"

    # Check if a JSON file was provided as argument
    if args.json_file:
        print(f"Loading payload from: {args.json_file}")
        try:
            with open(args.json_file, "r") as f:
                payload = json.load(f)
        except Exception as e:
            print(f"❌ Failed to load JSON file: {e}")
            return
    elif args.all:
        print(f"POST {url}\n")
        symbols = ["XAUUSD", "NAS100", "GBPJPY", "BTCUSD"]
        for sym in symbols:
            print(f"\n--- {sym} ---")
            _post_and_print(url, build_payload(sym, zone_id=0, side=args.side))
        return
    else:
        symbol = (args.symbol or os.getenv("SIMULATE_SYMBOL", "XAUUSD")).strip().upper() or "XAUUSD"
        zone_id = int(os.getenv("ZONE_ID", "0"))
        payload = build_payload(symbol, zone_id=zone_id, side=args.side)

    print(f"POST {url}")
    print("Payload:")
    _post_and_print(url, payload)


if __name__ == "__main__":
    main()

