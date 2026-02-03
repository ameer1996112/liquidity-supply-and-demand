"""
Simulate a trade EXIT webhook so the worker updates the trade status and PNL.

Use this to test that:
  1. Worker processes exit events (no longer skips them).
  2. Supabase row gets status=closed, outcome, pnl_usd, close_price.
  3. Dashboard shows Win/Loss and PNL.

Run from project root:

  # Close by zone_id (must match an existing active row in trading_signals):
  ZONE_ID=18580 API_BASE_URL=https://... WEBHOOK_SECRET=... python scripts/simulate_exit.py

  # Optional: set outcome and PNL
  ZONE_ID=18580 OUTCOME=win PNL_USD=150 python scripts/simulate_exit.py

For real flow: configure TradingView/Pine to send an exit webhook when TP or SL
is hit, with event_type="exit", zone_id (or trade_key), outcome, close_price, etc.
"""

from __future__ import annotations

import json
import os
from typing import Any, Dict

import requests


def build_exit_payload(zone_id: int, outcome: str = "win", pnl_usd: float = 100.0) -> Dict[str, Any]:
    """Build a valid ExitWebhookPayload (see src/core/signal.py ExitWebhookPayload)."""
    return {
        "event_type": "exit",
        "zone_id": zone_id,
        "outcome": outcome,
        "bars_held": 10,
        "close_price": 25920.0,
        "exit_type": "tp" if outcome == "win" else "sl",
        "mae_pips": 5.0,
        "pnl_r": 2.0,
        "pnl_usd": pnl_usd,
    }


def main() -> None:
    base_url = os.getenv("API_BASE_URL", "http://localhost:8000")
    url = f"{base_url.rstrip('/')}/webhook"
    zone_id = int(os.getenv("ZONE_ID", "0"))
    outcome = os.getenv("OUTCOME", "win").strip().lower()
    if outcome not in ("win", "loss", "breakeven"):
        outcome = "win"
    pnl_usd = float(os.getenv("PNL_USD", "100.0"))

    if zone_id <= 0:
        print("Set ZONE_ID to an existing active trade's zone_id (e.g. from Mission Control or Supabase).")
        print("Example: ZONE_ID=18580 API_BASE_URL=https://... WEBHOOK_SECRET=... python scripts/simulate_exit.py")
        return

    payload = build_exit_payload(zone_id, outcome=outcome, pnl_usd=pnl_usd)
    headers = {"Content-Type": "application/json"}
    secret = os.getenv("WEBHOOK_SECRET", "").strip().strip('"').strip("'")
    if secret:
        headers["X-Webhook-Secret"] = secret

    print(f"POST {url} (exit event for zone_id={zone_id})")
    print("Payload:", json.dumps(payload, indent=2))

    try:
        resp = requests.post(url, headers=headers, json=payload, timeout=10)
    except Exception as e:
        print(f"\n❌ Request failed: {e}")
        return

    print(f"\n✅ Response status: {resp.status_code}")
    ctype = resp.headers.get("content-type", "")
    if "application/json" in ctype.lower():
        try:
            body = resp.json()
            print("Response:", json.dumps(body, indent=2))
        except Exception:
            print(resp.text)
    else:
        print(resp.text)

    if resp.status_code == 200:
        print("\nCheck worker logs for 'Exit event for zone_id=... - processing' and 'Exit recorded'.")
        print("Check Supabase trading_signals: row with zone_id=%s should have status=closed, outcome=%s, pnl_usd=%s."
              % (zone_id, outcome, pnl_usd))
        print("Refresh Mission Control: PNL and Win/Loss should update.")


if __name__ == "__main__":
    main()
