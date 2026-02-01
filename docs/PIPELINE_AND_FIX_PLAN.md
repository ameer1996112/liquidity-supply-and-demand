# Trading Pipeline Map & Execution Fix Plan

## 1. Pipeline Map (End-to-End)

```
TradingView Alert
       │
       ▼
[main.py] POST /webhook
       │ validate secret + body → parse_body → EntryWebhookPayload
       │ rpush(trading_queue, payload_json)
       ▼
Redis "trading_queue"
       │
       ▼
[worker.py] blpop → process_trade(payload)   ◄── BREAK POINT
       │
       ├─ Risk Guard (size <= MAX_LOT_SIZE)
       ├─ Correlation Guard (active count < MAX_OPEN_POSITIONS)
       ├─ ML Guard (win_prob >= ML_MIN_CONFIDENCE)
       │
       └─ On pass: save_result(payload, "active", ...)  ← ONLY logs to Supabase
          On reject: save_result(payload, status, ...)

       ❌ logic.process_trade() is NEVER called
```

**Intended flow (per Dockerfile.worker comment "blpop -> logic.execute_trade"):**

- Worker should run guards, then on pass call **logic.process_trade(payload)**.
- **logic.process_trade()** does: exit handling, **save_alert()**, R:R filter, **paper_trader.open_position()** (when paper enabled), **send_discord()**, **send_telegram()**.

**Break point:** Worker has its own inline `process_trade()` that only runs Risk/Correlation/ML and `save_result()`. It never imports or calls `logic.process_trade()`, so no orders (paper or live) are ever placed and Discord/Telegram are never sent from the worker path.

---

## 2. Fixes (Incremental)

| # | Fix | Scope |
|---|-----|--------|
| 1 | When all guards pass, call `logic.process_trade(payload)` instead of `save_result(..., "active")`. Rejections still use `save_result`. | worker.py |
| 2 | Idempotency: before processing, check if `signal_id` or `trade_key` already exists in DB; if yes, skip and log. | supabase_db.py + worker.py |
| 3 | Kill-switch + LIVE_TRADING gate: config `trading_kill_switch`, `live_trading_enabled`; worker rejects when kill-switch on; logic receives `dry_run=(not live_trading_enabled)` so DRY_RUN = no paper/live execution. | config.py, worker.py, logic.py |
| 4 | Test plan: local webhook replay, expected logs, expected state. | docs/TEST_PLAN_EXECUTION.md |

---

## 3. How to Test After Each Diff

1. **After worker + logic + config changes:** Restart worker; send one webhook via `scripts/simulate_tv_event.py`. Expect: API 200 → worker logs Processing → guards → `ML APPROVED` → `DRY_RUN: ... no order placed` → `logic.process_trade completed`. One row in `trading_signals` with `status=active`.
2. **After idempotency:** Send the same payload again (same `trade_key`). Expect: worker logs `Idempotency: signal_id/trade_key already exists, skipping`; no second row.
3. **After kill-switch:** Set `TRADING_KILL_SWITCH=true` (or `KILL_SWITCH=true`), restart worker, send webhook. Expect: `KILL-SWITCH: execution blocked`; one row with `status=kill_switch_blocked`.
4. **After LIVE_TRADING gate:** Set `LIVE_TRADING=true`, `PAPER_TRADING_ENABLED=true`, restart worker, send webhook. Expect: `Paper position #N opened` (if paper symbols allow).

Full steps: **docs/TEST_PLAN_EXECUTION.md**.

---

## 4. Safety Notes

- **DRY_RUN first:** Default `LIVE_TRADING=false` (`live_trading_enabled=false`) so first runs only log + notify, no orders.
- **Kill-switch:** `TRADING_KILL_SWITCH=true` (or `KILL_SWITCH=true`) blocks all execution regardless of guards.
- **Idempotency:** Prevents duplicate orders for the same signal (`signal_id` or `trade_key`).
