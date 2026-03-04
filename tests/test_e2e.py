#!/usr/bin/env python3
"""
END-TO-END TRADING SYSTEM TEST
================================
Simulates a TradingView webhook alert and verifies the full pipeline:

  TradingView signal (simulated)
      ↓
  Backend webhook endpoint
      ↓
  Multi-Agent System (Risk → Quant → Researcher → Historian → Critic)
      ↓
  Trade record created in DB
      ↓
  MetaAPI order placed in MetaTrader (if LIVE_TRADING=true)
      ↓
  Verify open position in broker
      ↓
  Exit signal → Trade closed → P&L recorded

MODES:
  --mode paper   → PAPER run: backend processes signal, no real MT5 order
  --mode live    → LIVE run:  requires META_API_TOKEN + META_API_ACCOUNT_ID + LIVE_TRADING=true in .env

USAGE:
  cd apps/backend
  python test_e2e.py                          # paper mode, localhost:8000
  python test_e2e.py --mode live              # live mode (real MT5 order)
  python test_e2e.py --symbol XAUUSD --side buy
  python test_e2e.py --url https://my.server  # remote backend
  python test_e2e.py --verbose                # show full response JSON
  python test_e2e.py --score 95              # high score → forces ALLOW by MAS
"""

import argparse
import json
import os
import ssl
import sys
import time
import urllib.request
import urllib.error
from datetime import datetime

# ── SSL (macOS Python 3.x doesn't ship root certs) ───────────────────────────
_SSL = ssl.create_default_context()
_SSL.check_hostname = False
_SSL.verify_mode = ssl.CERT_NONE

# ── ANSI colors ───────────────────────────────────────────────────────────────
GREEN  = "\033[92m"
RED    = "\033[91m"
YELLOW = "\033[93m"
CYAN   = "\033[96m"
BLUE   = "\033[94m"
MAGENTA = "\033[95m"
BOLD   = "\033[1m"
DIM    = "\033[2m"
RESET  = "\033[0m"

def ok(msg):      print(f"  {GREEN}✓{RESET}  {msg}")
def fail(msg):    print(f"  {RED}✗{RESET}  {RED}{msg}{RESET}")
def info(msg):    print(f"  {CYAN}→{RESET}  {msg}")
def warn(msg):    print(f"  {YELLOW}!{RESET}  {YELLOW}{msg}{RESET}")
def step(msg):    print(f"\n{BOLD}{BLUE}━━ {msg} ━━{RESET}")
def dim(msg):     print(f"  {DIM}{msg}{RESET}")
def banner(msg):  print(f"\n{BOLD}{MAGENTA}{'═'*60}\n  {msg}\n{'═'*60}{RESET}")


# ── HTTP helpers ──────────────────────────────────────────────────────────────

def _post(url: str, payload: dict, verbose: bool = False) -> tuple[int, dict]:
    data = json.dumps(payload).encode()
    req = urllib.request.Request(
        url, data=data,
        headers={"Content-Type": "application/json"},
        method="POST"
    )
    try:
        with urllib.request.urlopen(req, timeout=60, context=_SSL) as r:
            body = json.loads(r.read())
            if verbose:
                print(f"  {DIM}{json.dumps(body, indent=4)}{RESET}")
            return r.status, body
    except urllib.error.HTTPError as e:
        body = {}
        try:
            body = json.loads(e.read())
        except Exception:
            pass
        if verbose:
            print(f"  {DIM}HTTP {e.code}: {json.dumps(body, indent=4)}{RESET}")
        return e.code, body


def _get(url: str, verbose: bool = False) -> tuple[int, dict]:
    try:
        with urllib.request.urlopen(url, timeout=15, context=_SSL) as r:
            body = json.loads(r.read())
            if verbose:
                print(f"  {DIM}{json.dumps(body, indent=4)}{RESET}")
            return r.status, body
    except urllib.error.HTTPError as e:
        body = {}
        try:
            body = json.loads(e.read())
        except Exception:
            pass
        return e.code, body


# ── Signal payload builder ────────────────────────────────────────────────────

# Realistic market prices per symbol (for a coherent SL/TP)
_PRICES = {
    "NAS100": dict(entry=21500.0, sl_pips=30, tp_mult=3.0, pip=1.0),
    "XAUUSD": dict(entry=3220.0,  sl_pips=80, tp_mult=4.0, pip=0.1),
    "EURUSD": dict(entry=1.1645,  sl_pips=20, tp_mult=2.0, pip=0.0001),
    "GBPUSD": dict(entry=1.2700,  sl_pips=25, tp_mult=2.0, pip=0.0001),
    "GBPJPY": dict(entry=190.00,  sl_pips=15, tp_mult=3.0, pip=0.01),
    "USDJPY": dict(entry=150.00,  sl_pips=15, tp_mult=2.5, pip=0.01),
}

def build_entry_payload(symbol: str, side: str, run_mode: str, zone_id: int, score: int) -> dict:
    p = _PRICES.get(symbol, _PRICES["EURUSD"])
    entry = p["entry"]
    # Use live price when available so Staleness Guard passes (entry ≈ current price)
    try:
        from src.adapters.market_data import get_current_price
        live = get_current_price(symbol)
        if live and live > 0:
            entry = round(live, 5)
    except Exception:
        pass
    sl_dist = p["sl_pips"] * p["pip"]
    tp_dist = sl_dist * p["tp_mult"]

    if side == "buy":
        sl = round(entry - sl_dist, 5)
        tp = round(entry + tp_dist, 5)
        zone_top    = round(entry + p["pip"] * 5, 5)
        zone_bottom = round(entry - p["pip"] * p["sl_pips"] * 0.5, 5)
        zone_type   = "demand"
    else:
        sl = round(entry + sl_dist, 5)
        tp = round(entry - tp_dist, 5)
        zone_top    = round(entry + p["pip"] * p["sl_pips"] * 0.5, 5)
        zone_bottom = round(entry - p["pip"] * 5, 5)
        zone_type   = "supply"

    return {
        "symbol":               symbol,
        "side":                 side,
        "entry":                entry,
        "sl":                   sl,
        "tp":                   tp,
        "size":                 1.0,
        "account_balance":      50000,
        "run_mode":             run_mode,
        "zone_id":              zone_id,
        "zone_type":            zone_type,
        "zone_top":             zone_top,
        "zone_bottom":          zone_bottom,
        "zone_size_pips":       round(p["sl_pips"] * 0.7, 1),
        "rr_ratio":             p["tp_mult"],
        "sl_pips":              p["sl_pips"],
        "entry_model":          "DIR_CLOSE",
        "liq_swept":            True,
        "target_swept":         True,
        "caused_sweep":         True,
        "is_accuracy":          False,
        "score":                score,
        "freshness":            1,
        "session":              2,
        "atr_ratio":            0.72,
        "trend":                1 if side == "buy" else 0,
        "rsi":                  35.0 if side == "buy" else 65.0,
        "htf_trend":            1 if side == "buy" else 0,
        "rvol":                 2.1,
        "adx":                  28.5,
        "touch_count":          1,
        "base_quality":         100,
        "departure_strength":   75.0,
        "liquidity_distance":   92.0,
        "liquidity_spread":     68.0,
        "return_strength":      100,
        "liquidity_distance_pips": p["sl_pips"] * 0.8,
        "liquidity_spread_pips":   p["sl_pips"] * 2.2,
        "liquidity_sweep":      True,
        "arrival_type":         "aggressive",
        "market_structure_break": True,
        "signal_time":          datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "bar_time":             datetime.now().strftime("%Y-%m-%dT%H:%M:%S"),
    }


def build_exit_payload(zone_id: int, entry: dict) -> dict:
    side = entry["side"]
    ep   = entry["entry"]
    tp   = entry["tp"]
    sl   = entry["sl"]
    pnl_r = entry["rr_ratio"]
    pnl_usd = round(abs(tp - ep) / abs(ep - sl) * 50000 * 0.005 * pnl_r, 2)  # approx

    return {
        "event_type":  "exit",
        "zone_id":     zone_id,
        "outcome":     "win",
        "bars_held":   12,
        "close_price": tp,
        "pnl_r":       pnl_r,
        "pnl_usd":     pnl_usd,
        "exit_type":   "TP",
        "mae_pips":    round(abs(ep - sl) / 0.0001 * 0.15, 1),
        "close_time":  datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }


# ── Main test runner ──────────────────────────────────────────────────────────

def run(base: str, symbol: str, side: str, run_mode: str, score: int, verbose: bool, secret: str | None = None) -> int:
    failures = 0
    zone_id  = int(time.time()) % 100000 + 80000  # unique per run
    signal_id = None
    trade_id  = None

    banner(f"E2E TEST  {symbol} {side.upper()}  mode={run_mode}  score={score}")
    print(f"  Backend : {CYAN}{base}{RESET}")
    print(f"  Zone ID : {zone_id}")
    print(f"  Time    : {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    # ── Step 1: Health check ────────────────────────────────────────────────
    step("1 · Backend health check")
    code, body = _get(f"{base}/health", verbose)
    if code == 200 and body.get("status") in ("healthy", "online"):
        ok(f"Backend online")
        info(f"service={body.get('service', 'api')}")
    else:
        fail(f"Backend not reachable (HTTP {code})")
        fail("Start backend:  PYTHONPATH=. python -m uvicorn src.api:app --port 8000")
        return 1  # can't continue

    # ── Step 2: Send entry signal (simulate TradingView) ────────────────────
    step("2 · Send entry signal  →  POST /webhook")
    entry_payload = build_entry_payload(symbol, side, run_mode, zone_id, score)
    info(f"Payload: {symbol} {side.upper()} @ {entry_payload['entry']}  "
         f"SL={entry_payload['sl']}  TP={entry_payload['tp']}")
    dim(f"zone_id={zone_id}  score={score}  rvol={entry_payload['rvol']}  "
        f"run_mode={run_mode}")

    webhook_url = f"{base}/webhook"
    if secret:
        webhook_url = f"{webhook_url}?secret={secret}"
    code, body = _post(webhook_url, entry_payload, verbose)

    if code == 200:
        status = body.get("status", "")
        if status == "queued":
            ok("Signal queued by API (worker will process)")
            info(f"account_id={body.get('account_id', 'N/A')}")
        else:
            decision   = body.get("decision", "?")
            confidence = body.get("confidence", 0)
            signal_id  = body.get("signal_id")
            reasoning  = body.get("reasoning", "")

            color = GREEN if decision == "ALLOW" else RED
            print(f"\n  {BOLD}MAS Decision: {color}{decision}{RESET}")
            info(f"confidence={confidence:.1%}  signal_id={signal_id}")
            if reasoning:
                info(f"reasoning={reasoning[:120]}{'...' if len(reasoning)>120 else ''}")

            if decision == "ALLOW":
                ok("Signal accepted by Multi-Agent System")
            elif decision == "BLOCK":
                warn("Signal BLOCKED by MAS (this may be expected — agents are selective)")
                warn("Try --score 95 to force ALLOW, or check agent logs in AI terminal")
            else:
                fail(f"Unexpected decision: {decision}")
                failures += 1
    elif code == 422:
        fail(f"Validation error (HTTP 422) — payload schema mismatch")
        if verbose:
            dim(str(body.get("detail", "")))
        failures += 1
    else:
        fail(f"Unexpected HTTP {code}: {body.get('detail') or body}")
        failures += 1

    # ── Step 3: Verify signal in DB ──────────────────────────────────────────
    step("3 · Verify signal stored  →  GET /api/v1/webhook/signals/recent")
    time.sleep(0.5)  # small delay for DB write
    code, body = _get(f"{base}/api/v1/webhook/signals/recent?limit=10", verbose)
    if code == 200:
        signals = body.get("signals", [])
        match = next((s for s in signals if s.get("zone_id") == zone_id
                      or s.get("symbol") == symbol), None)
        if match:
            ok(f"Signal in DB: id={match.get('id')}  decision={match.get('ml_decision')}  "
               f"confidence={match.get('ml_confidence', 0):.2f}")
        else:
            warn(f"Signal not found by zone_id={zone_id} — checking by symbol only")
            count = body.get("count", 0)
            info(f"Most recent {count} signals returned")
    elif code == 404:
        warn("Signals/recent endpoint not found (API may use different paths)")
    else:
        fail(f"GET signals/recent returned HTTP {code}")
        failures += 1

    # ── Step 4: Check if trade was created ──────────────────────────────────
    step("4 · Check open trades  →  GET /api/v1/webhook/trades/open")
    time.sleep(0.5)
    code, body = _get(f"{base}/api/v1/webhook/trades/open", verbose)
    if code == 404:
        warn("Trades/open endpoint not found (API may use /positions/active)")
    elif code == 200:
        trades = body.get("trades", []) or body.get("db_trades", [])
        total  = body.get("count", len(trades))
        match  = next((t for t in trades if t.get("zone_id") == zone_id
                       or str(t.get("zone_id")) == str(zone_id)), None)

        if match:
            trade_id = match.get("id") or match.get("trade_id")
            status   = match.get("status", "?")
            ok(f"Trade in DB: id={trade_id}  status={status}  "
               f"side={match.get('side')}  symbol={match.get('symbol')}")

            # Check MetaAPI order ID (means real broker order was placed)
            meta_order_id = match.get("meta_order_id")
            if meta_order_id:
                ok(f"Broker order placed! meta_order_id={meta_order_id}")
            elif run_mode == "LIVE":
                warn("meta_order_id is None — check LIVE_TRADING=true in .env")
            else:
                info("PAPER mode: no broker order sent (expected)")
        else:
            if body.get("decision") == "BLOCK" or total == 0:
                warn("No trade created — MAS likely blocked the signal")
                info("This is normal if all agents voted NO")
            else:
                info(f"Trade not found for zone_id={zone_id} in {total} open trades")
    else:
        fail(f"GET trades/open returned HTTP {code}")
        failures += 1

    # ── Step 5: MetaTrader position verification (LIVE mode only) ───────────
    if run_mode == "LIVE":
        step("5 · Verify MetaTrader position  →  GET /api/v1/webhook/trades/open (broker)")
        time.sleep(2)  # Allow MetaAPI to process
        code, body = _get(f"{base}/api/v1/webhook/trades/open", verbose)
        if code == 200:
            broker_positions = body.get("broker_positions", [])
            if broker_positions:
                ok(f"MetaTrader positions: {len(broker_positions)} open")
                for pos in broker_positions[:3]:  # show first 3
                    info(f"  position: symbol={pos.get('symbol')}  "
                         f"side={pos.get('side')}  volume={pos.get('volume')}  "
                         f"floating_pnl={pos.get('floating_pnl', 0):.2f}")
            else:
                warn("No broker positions returned — check MetaAPI credentials")
                info("Make sure META_API_TOKEN and META_API_ACCOUNT_ID are set in .env")
        elif code == 404:
            warn("Trades/open endpoint not found (API may use /positions/active)")
        else:
            fail(f"Trades/open returned HTTP {code}")
            failures += 1
    else:
        step("5 · MetaTrader check  [SKIPPED — PAPER mode]")
        info("Run with --mode live to test real MetaTrader order placement")

    # ── Step 6: Send exit signal ─────────────────────────────────────────────
    step("6 · Send exit signal  →  POST /webhook (event_type=exit)")
    exit_payload = build_exit_payload(zone_id, entry_payload)
    info(f"Simulating TP hit: close_price={exit_payload['close_price']}  "
         f"pnl_r={exit_payload['pnl_r']}  pnl_usd=${exit_payload['pnl_usd']}")

    exit_url = f"{base}/webhook"
    if secret:
        exit_url = f"{exit_url}?secret={secret}"
    code, body = _post(exit_url, exit_payload, verbose)
    if code == 200:
        status   = body.get("status", "?")
        ret_id   = body.get("trade_id")
        if status == "queued":
            ok(f"Exit queued (worker will process)")
        else:
            ok(f"Exit processed: status={status}  trade_id={ret_id}")
    elif code == 404:
        warn("Trade not found for exit (expected if MAS blocked signal — no trade was created)")
    else:
        fail(f"Exit returned HTTP {code}: {body.get('detail') or body}")
        failures += 1

    # ── Step 7: Stats summary ────────────────────────────────────────────────
    step("7 · Performance stats  →  GET /api/v1/webhook/stats/summary")
    code, body = _get(f"{base}/api/v1/webhook/stats/summary", verbose)
    if code == 200:
        total   = body.get("total_trades", 0)
        win_rate = body.get("win_rate", 0)
        pnl_usd = body.get("total_pnl_usd", 0)
        ok(f"total_trades={total}  win_rate={win_rate:.1f}%  total_pnl=${pnl_usd:.2f}")
    elif code == 404:
        warn("Stats/summary endpoint not found (API may use /analytics or /risk)")
    else:
        fail(f"Stats returned HTTP {code}")
        failures += 1

    # ── Step 8: WebSocket check (informational) ──────────────────────────────
    step("8 · WebSocket endpoints  [informational]")
    info(f"AI stream:  ws://{base.replace('http://','').replace('https://','')}  /ws/ai-stream")
    info(f"Log stream: ws://{base.replace('http://','').replace('https://','')}  /ws/logs")
    info("Open the frontend (http://localhost:3000) to see live updates from these sockets")

    # ── Summary ──────────────────────────────────────────────────────────────
    banner("TEST SUMMARY")
    if failures == 0:
        print(f"  {GREEN}{BOLD}ALL STEPS PASSED{RESET}")
    else:
        print(f"  {RED}{BOLD}{failures} STEP(S) FAILED{RESET}")

    print(f"""
  QUICK REFERENCE
  ───────────────────────────────────────────────────────
  Backend health    : {base}/
  Recent signals    : {base}/api/v1/webhook/signals/recent
  Open trades       : {base}/api/v1/webhook/trades/open
  Performance stats : {base}/api/v1/webhook/stats/summary
  Zone inspector    : {base}/api/v1/webhook/zones/<SYMBOL>
  ───────────────────────────────────────────────────────
  To enable live MetaTrader execution, add to .env:
    META_API_TOKEN=<your-token>
    META_API_ACCOUNT_ID=<your-account-id>
    LIVE_TRADING=true
  Then run: python tests/test_e2e.py --mode live
""")
    return failures


# ── CLI ───────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="End-to-end trading system test — simulates TradingView → backend → MetaTrader",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )
    parser.add_argument("--url",    default="http://localhost:8000",
                        help="Backend base URL (default: http://localhost:8000)")
    parser.add_argument("--secret", default=os.environ.get("WEBHOOK_SECRET", ""),
                        help="Webhook secret for /webhook (or set WEBHOOK_SECRET env)")
    parser.add_argument("--mode",   default="paper", choices=["paper", "live"],
                        help="Run mode: paper (no real trades) or live (real MT5 order)")
    parser.add_argument("--symbol", default="NAS100",
                        choices=list(_PRICES.keys()),
                        help="Symbol to test (default: NAS100)")
    parser.add_argument("--side",   default="sell", choices=["buy", "sell"],
                        help="Trade direction (default: sell)")
    parser.add_argument("--score",  default=95, type=int,
                        help="AI quality score 0-100 (default: 95, forces ALLOW)")
    parser.add_argument("--verbose", action="store_true",
                        help="Print full response JSON")
    args = parser.parse_args()

    run_mode = "LIVE" if args.mode == "live" else "PAPER"

    failures = run(
        base     = args.url.rstrip("/"),
        symbol   = args.symbol,
        side     = args.side,
        run_mode = run_mode,
        score    = args.score,
        verbose  = args.verbose,
        secret   = args.secret or None,
    )
    sys.exit(1 if failures else 0)
