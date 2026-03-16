# Bug Tracker

## Fixed

### BUG-006 — Status case mismatch: all risk/guard/evaluation queries returned empty
**Status:** Fixed (2026-03-16)
**Severity:** Critical (circuit breakers never fired — daily/weekly/monthly loss limits and consecutive loss guard silently disabled)

**Symptom:** Risk monitor showed 0 closed trades. Evaluation page always empty. Circuit breakers never triggered regardless of losses. Daily PnL in TopBar always $0.

**Root cause:** DB stores `"CLOSED"` uppercase (written by `logic.py`). Eleven files queried with `.eq("status", "closed")` lowercase — Supabase exact-match returned 0 rows.

**Fix:** Replaced all `.eq("status", "closed")` with `.in_("status", ["CLOSED", "closed"])` across 11 files.

**Files:** `api_risk.py`, `api_risk_monitor.py`, `api_evaluation.py`, `api_webhook_read.py`, `worker.py`, `services/alert_engine.py`, `services/graduation_service.py`, `services/backtest_engine.py`, `services/broker_reconciliation.py`, `agents/risk_agent.py`

---

### BUG-007 — `submitted` execution silently dropped `broker_order_id`
**Status:** Fixed (2026-03-16)
**Severity:** Critical (async/pending fills could never be closed by the bot)

**Symptom:** Trades placed as pending orders (MetaAPI returns `submitted`) were marked OPEN in DB but had no `broker_order_id`. Exit webhooks silently skipped broker close for these positions.

**Root cause:** `logic.py:629` called `update_alert_status(alert_id, "OPEN")` which only writes the status field, not `broker_order_id`.

**Fix:** Replaced with a full DB update that persists `broker_order_id + status + entry_time` atomically.

---

### BUG-008 — `zone_id` KeyError in broker PnL update
**Status:** Fixed (2026-03-16)
**Severity:** Medium (silent KeyError skipped broker PnL DB write)

**Root cause:** `logic.py:298` used `data["zone_id"]` (hard bracket) when `trade_key` was missing and `zone_id` was not in the payload.

**Fix:** Changed to `data.get("zone_id")` with an explicit guard + warning log.

---

### BUG-009 — Duplicate exit webhook overwrites broker-verified PnL
**Status:** Fixed (2026-03-16)
**Severity:** Medium (TradingView retries could replace real broker PnL with simulated value)

**Root cause:** `update_alert_exit()` had no idempotency check — always wrote unconditionally, even if the signal was already `CLOSED`.

**Fix:** Added pre-check: if signal is already `CLOSED`, return early without writing.

---

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
