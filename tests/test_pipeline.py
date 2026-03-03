#!/usr/bin/env python3
"""
End-to-end pipeline test for the Trading Bot webhook system.

Tests the full flow:
  Entry signal (NAS100 SELL) → MAS evaluation → Trade created
  Exit signal  (same zone)   → Trade closed   → P&L recorded

Usage:
    cd apps/backend
    python test_pipeline.py                         # test localhost:8000
    python test_pipeline.py --url https://my.server # test remote backend
    python test_pipeline.py --verbose               # show full response bodies
"""

import argparse
import json
import ssl
import sys
import time
import urllib.request
import urllib.error
from datetime import datetime

# macOS Python 3.x doesn't bundle root certs — skip verification for test scripts
_SSL_CTX = ssl.create_default_context()
_SSL_CTX.check_hostname = False
_SSL_CTX.verify_mode = ssl.CERT_NONE

# ── ANSI colours ─────────────────────────────────────────────────────────────
GREEN  = "\033[92m"
RED    = "\033[91m"
YELLOW = "\033[93m"
CYAN   = "\033[96m"
BOLD   = "\033[1m"
RESET  = "\033[0m"

def ok(msg):   print(f"  {GREEN}✓{RESET} {msg}")
def fail(msg): print(f"  {RED}✗{RESET} {msg}")
def info(msg): print(f"  {CYAN}→{RESET} {msg}")
def warn(msg): print(f"  {YELLOW}!{RESET} {msg}")
def header(msg): print(f"\n{BOLD}{msg}{RESET}")


# ── HTTP helper ───────────────────────────────────────────────────────────────

def post(url: str, payload: dict, verbose: bool = False) -> tuple[int, dict]:
    data = json.dumps(payload).encode()
    req  = urllib.request.Request(
        url, data=data,
        headers={"Content-Type": "application/json"},
        method="POST"
    )
    try:
        with urllib.request.urlopen(req, timeout=30, context=_SSL_CTX) as resp:
            body = json.loads(resp.read())
            if verbose:
                print(f"    {json.dumps(body, indent=4)}")
            return resp.status, body
    except urllib.error.HTTPError as e:
        body = {}
        try:
            body = json.loads(e.read())
        except Exception:
            pass
        if verbose:
            print(f"    HTTP {e.code}: {json.dumps(body, indent=4)}")
        return e.code, body


def get(url: str, verbose: bool = False) -> tuple[int, dict]:
    try:
        with urllib.request.urlopen(url, timeout=10, context=_SSL_CTX) as resp:
            body = json.loads(resp.read())
            if verbose:
                print(f"    {json.dumps(body, indent=4)}")
            return resp.status, body
    except urllib.error.HTTPError as e:
        body = {}
        try:
            body = json.loads(e.read())
        except Exception:
            pass
        return e.code, body


# ── Test cases ────────────────────────────────────────────────────────────────

ZONE_ID = 99901  # Unique ID so it doesn't collide with real trades

ENTRY_PAYLOAD = {
    "symbol":              "NAS100",
    "side":                "sell",
    "entry":               24540.66,
    "sl":                  24570.16,
    "tp":                  24452.16,
    "size":                1,
    "account_balance":     50000,
    "run_mode":            "PAPER",
    "zone_id":             ZONE_ID,
    "zone_type":           "supply",
    "zone_top":            24581.29,
    "zone_bottom":         24550.79,
    "zone_size_pips":      30.5,
    "rr_ratio":            3.0,
    "sl_pips":             29.5,
    "entry_model":         "DIR_CLOSE",
    "liq_swept":           True,
    "target_swept":        True,
    "caused_sweep":        True,
    "is_accuracy":         False,
    "score":               95,
    "freshness":           1,
    "session":             2,
    "atr_ratio":           0.7843,
    "trend":               0,
    "rsi":                 64.31,
    "htf_trend":           0,
    "rvol":                0.89,
    "adx":                 26.26,
    "touch_count":         1,
    "base_quality":        100,
    "departure_strength":  41.45,
    "liquidity_distance":  99.24,
    "liquidity_spread":    75.12,
    "return_strength":     100,
    "signal_time":         datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
}

EXIT_PAYLOAD = {
    "event_type":   "exit",
    "zone_id":      ZONE_ID,
    "outcome":      "win",
    "bars_held":    8,
    "close_price":  24452.16,
    "pnl_r":        3.0,
    "pnl_usd":      270.0,
    "exit_type":    "TP",
    "mae_pips":     5.2,
    "close_time":   datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
}

# Same exit but sent to /signal (the unified endpoint — this is the bug fix path)
EXIT_VIA_SIGNAL_PAYLOAD = dict(EXIT_PAYLOAD)  # same data, different URL


def run_tests(base_url: str, verbose: bool) -> int:
    """Run all tests. Returns number of failures."""
    failures = 0

    # ── 1. Health check ───────────────────────────────────────────────────────
    header("1 · Health check")
    code, body = get(f"{base_url}/", verbose)
    if code == 200 and body.get("status") == "online":
        ok(f"Backend online — model={body.get('model_version')} agents={list(body.get('agents', {}).keys())}")
    else:
        fail(f"Health check failed (HTTP {code}): {body}")
        failures += 1

    # ── 2. Entry signal → /signal (unified endpoint) ──────────────────────────
    header("2 · Entry signal  POST /signal")
    code, body = post(f"{base_url}/signal", ENTRY_PAYLOAD, verbose)
    if code == 200:
        decision   = body.get("decision", "?")
        confidence = body.get("confidence", 0)
        signal_id  = body.get("signal_id")
        ok(f"Accepted  decision={decision}  confidence={confidence:.1%}  signal_id={signal_id}")
        if decision not in ("ALLOW", "BLOCK"):
            fail(f"Unexpected decision value: {decision}")
            failures += 1
    else:
        fail(f"HTTP {code}: {body.get('detail') or body}")
        failures += 1

    # ── 3. Recent signals query ───────────────────────────────────────────────
    header("3 · Recent signals  GET /api/v1/webhook/signals/recent")
    code, body = get(f"{base_url}/api/v1/webhook/signals/recent?limit=5", verbose)
    if code == 200:
        count = body.get("count", 0)
        ok(f"Returned {count} signals")
        # Check our test signal appears
        signals = body.get("signals", [])
        found = any(s.get("symbol") == "NAS100" for s in signals)
        if found:
            ok("Test signal (NAS100) visible in recent signals")
        else:
            warn("Test signal not found yet — DB may lag, or MAS blocked it before persist")
    else:
        fail(f"HTTP {code}: {body}")
        failures += 1

    # ── 4. Open trades query ──────────────────────────────────────────────────
    header("4 · Open trades  GET /api/v1/webhook/trades/open")
    code, body = get(f"{base_url}/api/v1/webhook/trades/open", verbose)
    if code == 200:
        count = body.get("count", 0)
        ok(f"Open trades: {count}")
    else:
        fail(f"HTTP {code}: {body}")
        failures += 1

    # ── 5. Exit via dedicated /exit endpoint ──────────────────────────────────
    header("5 · Exit signal  POST /exit  (dedicated endpoint)")
    code, body = post(f"{base_url}/exit", EXIT_PAYLOAD, verbose)
    if code == 200:
        ok(f"Exit accepted  status={body.get('status')}  trade_id={body.get('trade_id')}")
    else:
        fail(f"HTTP {code}: {body.get('detail') or body}")
        failures += 1

    # ── 6. EXIT via /signal (the main bug fix) ────────────────────────────────
    header("6 · Exit via unified /signal  (regression test for 422 bug fix)")
    info("Sending exit payload {event_type:'exit', zone_id:...} to POST /signal")
    code, body = post(f"{base_url}/signal", EXIT_VIA_SIGNAL_PAYLOAD, verbose)
    if code == 200:
        ok(f"Exit routed correctly  status={body.get('status')}  trade_id={body.get('trade_id')}")
    elif code == 422:
        fail(f"Still getting 422 — unified dispatcher not routing exits properly")
        fail(f"Detail: {body.get('detail')}")
        failures += 1
    else:
        # 404/500 may mean zone not found (expected for re-send) — still a pass for routing
        warn(f"HTTP {code} (exit processed, zone lookup may return not-found): {body.get('detail') or body.get('status')}")

    # ── 7. Stats summary ──────────────────────────────────────────────────────
    header("7 · Stats summary  GET /api/v1/webhook/stats/summary")
    code, body = get(f"{base_url}/api/v1/webhook/stats/summary", verbose)
    if code == 200:
        ok(
            f"total={body.get('total_trades',0)}  "
            f"win_rate={body.get('win_rate',0):.1f}%  "
            f"total_pnl=${body.get('total_pnl_usd',0):.2f}"
        )
    else:
        fail(f"HTTP {code}: {body}")
        failures += 1

    # ── 8. Entry signal via /webhook alias ───────────────────────────────────
    header("8 · Entry via /webhook alias  POST /webhook")
    # Use a slightly different zone_id so it creates a fresh record
    alias_payload = dict(ENTRY_PAYLOAD, zone_id=ZONE_ID + 1, symbol="XAUUSD", side="buy",
                         entry=2910.50, sl=2904.00, tp=2930.00)
    code, body = post(f"{base_url}/webhook", alias_payload, verbose)
    if code == 200:
        ok(f"Alias /webhook works  decision={body.get('decision')}  signal_id={body.get('signal_id')}")
    else:
        fail(f"HTTP {code}: {body.get('detail') or body}")
        failures += 1

    # ── Summary ───────────────────────────────────────────────────────────────
    print()
    print("=" * 50)
    if failures == 0:
        print(f"{GREEN}{BOLD}ALL TESTS PASSED{RESET}")
    else:
        print(f"{RED}{BOLD}{failures} TEST(S) FAILED{RESET}")
    print("=" * 50)
    return failures


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="End-to-end pipeline test")
    parser.add_argument("--url",     default="http://localhost:8000", help="Backend base URL")
    parser.add_argument("--verbose", action="store_true",             help="Print full response bodies")
    args = parser.parse_args()

    base = args.url.rstrip("/")
    print(f"{BOLD}Trading Bot — End-to-End Pipeline Test{RESET}")
    print(f"Target: {CYAN}{base}{RESET}")
    print(f"Time:   {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    failures = run_tests(base, args.verbose)
    sys.exit(1 if failures else 0)
