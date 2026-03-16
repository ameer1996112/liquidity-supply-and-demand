# Worklog

## 2026-03-16 (session 2)

### Fix: Status case mismatch — risk/guard/evaluation queries returned empty results

**Problem:** All queries for closed trades in `api_risk.py`, `api_risk_monitor.py`, `api_evaluation.py`, `api_webhook_read.py`, `worker.py`, `services/alert_engine.py`, `services/graduation_service.py`, `services/backtest_engine.py`, `services/broker_reconciliation.py`, and `agents/risk_agent.py` used `.eq("status", "closed")` (lowercase). The database stores `"CLOSED"` (uppercase, written by `logic.py`). Result: every query returned 0 rows — risk monitoring was blind to all closed trades, circuit breakers never fired, evaluation page was always empty.

**Fix:** Replaced all `.eq("status", "closed")` with `.in_("status", ["CLOSED", "closed"])` across 11 files / 15 query sites. (`api_positions.py` was already fixed in a prior session.)

### Fix: `submitted` execution status silently dropped `broker_order_id`

**Problem:** When MetaAPI returned `status="submitted"` (async/pending fill), `logic.py:629` called `update_alert_status(alert_id, "OPEN")` — which only persists the status string, not `broker_order_id`. The exit webhook later read `broker_order_id=None` and returned early without closing the broker position. These positions were stuck OPEN with no automated way to close them.

**Fix:** Replaced the `update_alert_status` call with a full DB update that persists `broker_order_id`, `status=OPEN`, and `entry_time` together in one write, matching the pattern used for the `filled` path.

### Fix: `zone_id` KeyError in broker PnL update path

**Problem:** `logic.py:298` used `data["zone_id"]` (hard bracket) when both `trade_key` was falsy and `zone_id` was absent from the webhook payload, causing a `KeyError` and silently skipping the PnL DB update.

**Fix:** Changed to `data.get("zone_id")` with an explicit guard: if neither identifier is present, log a warning and skip.

### Fix: Idempotency guard on duplicate exit webhooks

**Problem:** `update_alert_exit()` in `supabase.py` would blindly overwrite any record, including already-`CLOSED` ones. If TradingView retried an exit webhook (network timeout, etc.) after broker PnL had already been written, the second call would overwrite the correct broker PnL with TradingView's simulated PnL.

**Fix:** Added a pre-check in `update_alert_exit()`: if the signal is already `CLOSED`, log and return `True` without writing. Fails-open (proceeds with update) if the pre-check query itself fails.

### Fix: Backwards log ternary in exit deal logging

**Problem:** `logic.py:283` used `"DEAL_ENTRY_OUT" if exit_deals[0].get("entryType") else ...` — this always logged the hardcoded string `"DEAL_ENTRY_OUT"` whenever `entryType` was any truthy value, masking the actual value in logs.

**Fix:** Simplified to `exit_deals[0].get("entryType", "UNKNOWN")`.

## 2026-03-16

### Fix: Rejected-entry exit signals no longer corrupt PnL

**Problem:** When the staleness guard (or other guard rails) rejected an entry signal, TradingView would still fire an exit webhook for that trade later. The system was processing that exit and writing TradingView's simulated PnL to the database, marking the record as `CLOSED` with fake profit/loss values. The dashboard showed incorrect PnL for trades that never actually executed on MetaTrader.

**Root cause:** In `src/logic.py`, the exit handler checked for a missing `broker_order_id` but still called `update_alert_exit()` (with a comment "Still record exit telemetry"). This unconditionally set `status = CLOSED` and `pnl_usd = <TradingView value>` regardless of whether the entry was ever executed.

**Fix (backend — `src/logic.py`):**
- Added a status guard before the `broker_order_id` check.
- If the alert status is one of `staleness_rejected`, `filtered`, `ai_rejected`, `execution_failed`, `rejected`, or `guard_rejected`, the handler now:
  1. Skips all PnL and status updates.
  2. Writes a human-readable note to the `notes` field: `"Exit received from TradingView (close=X) but entry was <status> — PnL not recorded."`
  3. Returns early.
- The `broker_order_id` missing case also now returns without updating the DB (previously it still called `update_alert_exit`).

**Fix (frontend — `frontend/src/components/SignalCard.tsx`):**
- For any signal whose status is in the rejected set, `displayPnl` is forced to `null`.
- `PnLDisplay` receives `null` and renders `--` instead of a stale/fake number.
- The rejection note written by the backend appears automatically in the card's reasoning section via the existing `getDisplayReason()` → `notes` field path.

**Files changed:**
- `src/logic.py` — lines ~146–180
- `frontend/src/components/SignalCard.tsx` — lines ~214–315
