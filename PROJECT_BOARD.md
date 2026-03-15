# 🚀 Algo-Trading System: Project Board

## 🛑 Active Bugs (The Bug Board)
| ID | Component | Description | Status | Priority |
|---|---|---|---|---|
| B-01 | Frontend/DB | "Council" column showing empty `-` on dashboard | 🟡 Investigating | High |

---

## 🏗️ Active Tasks (Current Sprint)
- [ ] **Task 1:** Audit Pine Script webhook payload for `council` JSON key.
- [ ] **Task 2:** Audit Python backend for extraction and Supabase insertion of Council data.

---

## ✅ Completed & Implemented (Changelog)

### Session: 2026-03-15
* **Python/MT5:** Implemented Position Summation Loop in `broker_reconciliation`. Backend now calculates True Net PnL (Gross - Commission - Swap) perfectly matching MT5.
* **Python/MT5:** Fixed background sync loop so trades closed via broker SL/TP are correctly marked as `CLOSED` in Supabase.
* **Pine Script:** Replaced real-time peak tracking with Retroactive Historical Loop tied directly to the Touch Block, permanently fixing the `N/A` memory leak.
* **Python/Backend:** Fixed race condition in async AI Council processing — council data now reliably written to Supabase before signal is finalized.
* **Python/Backend:** Ran retroactive backfill script (`retroactive_council.py`) to populate council data for all historical signals missing it.
* **Frontend:** Fixed aggressive Next.js App Router caching on Supabase API calls — dashboard now always shows up-to-date data.
* **Pine Script:** Replaced "Return Strength" scoring system with explicit bar-count filters (`max_sweep_to_touch_bars`, `max_peak_to_touch_bars`) and added `peakBarIndex` tracking for structural extremes.

---

## 📋 Update Rule (Standard Operating Procedure)
> Whenever a bug is fixed or a feature is implemented, move it from Active Bugs/Tasks → Completed & Implemented.
> When the user says **"Update the board."**, summarize everything done that session, add it to the Changelog with today's date, and update the Bug Board to reflect current state.
