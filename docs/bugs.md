# Bug Tracker

## Fixed

### BUG-001 — Rejected-entry exits corrupt dashboard PnL
**Status:** Fixed (2026-03-16)
**Severity:** High (incorrect financial data shown to user)

**Symptom:** Dashboard showed closed trades with PnL values for positions that were never executed on MetaTrader (rejected by staleness guard or other guard rails).

**Root cause:** `process_trade()` in `src/logic.py` (exit path) called `update_alert_exit()` even when `broker_order_id` was null, writing TradingView's simulated PnL to the DB and setting status to `CLOSED`.

**Fix:**
- Added rejected-status guard in `src/logic.py` before the exit DB update.
- Writes a visible `notes` message instead of PnL data.
- Frontend `SignalCard.tsx` suppresses PnL display (`displayPnl = null`) for all rejected statuses.

**Affected statuses:** `staleness_rejected`, `filtered`, `ai_rejected`, `execution_failed`, `rejected`, `guard_rejected`
