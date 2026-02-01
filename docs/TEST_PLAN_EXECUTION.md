# Test Plan: Signal Ingest → Execution (DRY_RUN & Idempotency)

## Prerequisites

- **Environment:** `REDIS_URL`, `SUPABASE_URL`, `SUPABASE_ANON_KEY` (or `SUPABASE_SERVICE_ROLE_KEY` for worker) set in `.env`.
- **Schema:** Table `trading_signals` must have a `trade_key` column for idempotency. If missing, run in Supabase SQL Editor:
  ```sql
  ALTER TABLE public.trading_signals ADD COLUMN IF NOT EXISTS trade_key TEXT;
  ALTER TABLE public.trading_signals ADD COLUMN IF NOT EXISTS run_mode TEXT DEFAULT 'LIVE';
  ALTER TABLE public.trading_signals ADD COLUMN IF NOT EXISTS run_id TEXT DEFAULT 'live-default';
  ALTER TABLE public.trading_signals ADD COLUMN IF NOT EXISTS entry_time TIMESTAMPTZ;
  CREATE INDEX IF NOT EXISTS idx_trading_signals_trade_key ON public.trading_signals(trade_key);
  ```
- **DRY_RUN default:** Leave `LIVE_TRADING` unset or `false` so no real/paper orders are placed; only DB + Discord/Telegram.

---

## 1. Local Replay of Sample Webhooks

### 1.1 Start API + Redis + Worker

```bash
# From project root (e.g. galilsoftware/sources/trading)
export PYTHONPATH="$PWD:$PYTHONPATH"

# Start Redis (if not already running)
docker run -d -p 6379:6379 redis:7-alpine   # or use docker-compose up redis -d

# Start API
python3 -m uvicorn backend.main:app --host 0.0.0.0 --port 8000 &

# Start Worker (same shell or new terminal)
python3 -m backend.worker
```

Or use `./start.sh` if it starts both API and worker.

### 1.2 Send Sample Webhook (Simulator)

```bash
# From project root
python scripts/simulate_tv_event.py
# Or with custom symbol
python scripts/simulate_tv_event.py --symbol XAUUSD_TEST
```

**Expected:**

- HTTP 200, body `{"status": "queued"}`.
- Worker logs: `⚡ Processing: ...`, then Risk/Correlation/ML checks, then `✅ ML APPROVED` (or `❌ ML REJECTED`), then `DRY_RUN: Alert #N saved, no order placed (LIVE_TRADING=false)` and `🏁 logic.process_trade completed`.

### 1.3 Replay Same Payload (Idempotency)

Send the **same** payload again (same `trade_key`), e.g. run the simulator twice with the same symbol and within the same second, or use a fixed `trade_key` in a one-off curl:

```bash
curl -s -X POST http://localhost:8000/webhook \
  -H "Content-Type: application/json" \
  -d '{"symbol":"XAUUSD","side":"buy","entry":2650,"sl":2645,"tp":2660,"size":0.01,"trade_key":"XAUUSD_1738400000","zone_id":1738400000}'
```

Run twice. **Expected:**

- First request: queued → worker processes → one row in `trading_signals` (status `active` or as per logic).
- Second request: queued → worker logs `⏭️ Idempotency: signal_id/trade_key already exists, skipping` → **no** second row for that `trade_key`.

---

## 2. Expected Logs (Worker)

| Scenario | Expected log lines (order) |
|----------|----------------------------|
| Normal pass (DRY_RUN) | `⚡ Processing: SYMBOL \| SIDE \| Size` → `Risk Check: PASSED` → `Correlation Check: X/3 active` → `ML APPROVED` → `DRY_RUN: LIVE_TRADING=false` → `logic.process_trade completed` |
| Kill-switch ON | `⚡ Processing` → `❌ KILL-SWITCH: execution blocked` → `Saved: kill_switch_blocked` |
| Duplicate trade_key | `⚡ Processing` → `⏭️ Idempotency: signal_id/trade_key already exists, skipping` |
| Risk reject | `Risk Check: size X vs limit` → `❌ RISK REJECTED` → `Saved: risk_rejected` |
| ML reject | `ML Check: confidence` → `❌ ML REJECTED` → `Saved: ml_rejected` |

---

## 3. Expected State Changes (Supabase)

- **DRY_RUN (LIVE_TRADING=false):**
  - One row per **approved** signal: `status = 'active'`, `mode = 'paper'` or `'manual'`, `trade_key` set; **no** paper position opened when dry_run=True (only when LIVE_TRADING=true and paper_trading_enabled).
- **Idempotency:** No second row with the same `trade_key`; second webhook with same `trade_key` is skipped in worker.
- **Rejections:** Rows with `status` in `risk_rejected`, `correlation_rejected`, `ml_rejected`, `kill_switch_blocked`, `execution_failed` as applicable; `trade_key` stored when provided.

---

## 4. Enabling Order Placement (Paper)

1. Set in `.env`: `LIVE_TRADING=true`, `PAPER_TRADING_ENABLED=true`, `PAPER_AUTO_EXECUTE=true`.
2. Restart worker. Logs should show `LIVE_TRADING: true (orders allowed)`.
3. Send webhook again. **Expected:** Same as above plus `Paper position #N opened` and in-memory paper positions (no broker order).

---

## 5. Quick Checklist

- [ ] API returns 200 and `{"status": "queued"}` for valid webhook.
- [ ] Worker consumes from Redis and logs Processing → guards → APPROVED or REJECTED.
- [ ] On APPROVED + DRY_RUN: one row in `trading_signals`, log "DRY_RUN: ... no order placed", no paper position.
- [ ] Duplicate `trade_key`: second request does not create a second row; worker logs idempotency skip.
- [ ] Kill-switch ON: worker logs kill-switch block and saves `kill_switch_blocked`.
- [ ] LIVE_TRADING=true + paper enabled: approved signal creates row and paper position, log "Paper position #N opened".
