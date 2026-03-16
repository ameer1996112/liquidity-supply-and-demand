# Worklog

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
