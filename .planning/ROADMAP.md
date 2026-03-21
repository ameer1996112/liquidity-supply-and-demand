# Roadmap: Trinity Trading System

## Milestones

- ✅ **v1.0 Premium Dark Trading Terminal** — Phases 1-8 (shipped 2026-03-20)
- 🚀 **v1.1 Position Management & Risk Intelligence** — Phases 9-11 (in progress)

## Phases

<details>
<summary>✅ v1.0 Premium Dark Trading Terminal (Phases 1-8) — SHIPPED 2026-03-20</summary>

- [x] Phase 1: Design System Foundation (2/2 plans) — complete
- [x] Phase 2: Core Component Library (3/3 plans) — complete
- [x] Phase 3: Navigation Redesign (1/1 plan) — complete
- [x] Phase 4: Dashboard Redesign (2/2 plans) — complete
- [x] Phase 5: Risk & Prop Firm Redesign (2/2 plans) — complete
- [x] Phase 6: Remaining Pages Redesign (1/1 plan) — complete
- [x] Phase 7: Responsive Polish (1/1 plan) — complete
- [x] Phase 8: Micro-Interactions & Final Polish (1/1 plan) — complete

See `.planning/milestones/v1.0-ROADMAP.md` for full phase details.

</details>

---

## v1.1: Position Management & Risk Intelligence

**Goal:** Optimize the full position lifecycle and surface risk/execution health so every trade is managed smarter and every problem is caught before it costs money.

**Phases:** 3 | **Requirements:** 11 | **Started:** 2026-03-21

---

### Phase 9: Position Management Overhaul

**Goal:** Chain breakeven and trailing stop into a unified position lifecycle — BE fires with buffer, trailing stop activates automatically, winners run to TP instead of clipping at entry.

**Requirements:** POS-01, POS-02, POS-03, POS-04, POS-05

**Key changes:**
- `breakeven_manager.py` — shift `be_sl_price` by `+BREAKEVEN_BUFFER_PIPS` when firing (default 3 pips)
- After BE marks triggered, call `TrailingStopManager.add_trailing_stop()` for same position
- Per-symbol trail distance config: forex uses pips, indices use points (via `.env` or `symbol_risk_rules` DB table)
- Trail activation threshold: configurable minimum distance from entry before trailing starts
- All lifecycle events (BE trigger, trail start, trail update, exit) logged to `trade_events` table

**Success criteria:**
1. Trades that hit BE no longer close at negative PnL due to spread (must close ≥ 0)
2. After BE fires on any live position, a trailing stop is automatically active within one worker loop
3. Trail distance is different for GBPUSD (pips) vs NAS100 (points) without code changes
4. `trade_events` table shows full lifecycle: entry → be_triggered → trail_started → trail_moved → closed
5. All configurable via `.env` — no redeploy needed to tune values

**Plans estimate:** 2

---

### Phase 10: Risk Visibility

**Goal:** Expose the risk multiplier and per-trade USD risk in the dashboard so the trader always knows their actual exposure — not just the base 0.5%.

**Requirements:** RISK-01, RISK-02, RISK-03

**Key changes:**
- Dashboard Risk Status card — add "Multiplier" field showing current `step_up` multiplier value
- Signal table — add "Risk $" column showing calculated USD risk for each executed trade
- Dashboard stat card — "Effective Risk %" = base % × current multiplier

**Success criteria:**
1. Risk Status card shows live multiplier value (e.g. "0.7×") updated on each dashboard poll
2. Every closed/open signal row in the table shows its actual USD risk at entry
3. Effective Risk % stat card updates when multiplier changes (not static 0.5%)

**Plans estimate:** 1

---

### Phase 11: Execution Monitoring

**Goal:** Track the webhook→MetaTrader pipeline latency and alert when fills are late or signals fire while markets are closed.

**Requirements:** EXEC-01, EXEC-02, EXEC-03

**Key changes:**
- Store `webhook_received_at` and `fill_confirmed_at` timestamps per signal → compute latency column
- Worker watchdog: if `fill_confirmed_at` is null 30s after `webhook_received_at` → log alert + optional Telegram
- Market hours check on signal receipt: if symbol is outside trading hours → mark `staleness_rejected` with reason

**Success criteria:**
1. Every executed signal has `webhook_received_at`, `fill_confirmed_at`, and `fill_latency_ms` in the DB
2. A signal without fill within 30s triggers a visible alert in the Live Log on the dashboard
3. Signals arriving outside market hours are marked `STALENESS_REJECTED` with `"reason": "outside_market_hours"`

**Plans estimate:** 1

---

## Progress

| Phase | Milestone | Plans | Status | Completed |
|---|---|---|---|---|
| 1. Design System Foundation | v1.0 | 2/2 | Complete | 2026-03-19 |
| 2. Core Component Library | v1.0 | 3/3 | Complete | 2026-03-19 |
| 3. Navigation Redesign | v1.0 | 1/1 | Complete | 2026-03-19 |
| 4. Dashboard Redesign | v1.0 | 2/2 | Complete | 2026-03-20 |
| 5. Risk & Prop Firm Redesign | v1.0 | 2/2 | Complete | 2026-03-20 |
| 6. Remaining Pages Redesign | v1.0 | 1/1 | Complete | 2026-03-20 |
| 7. Responsive Polish | v1.0 | 1/1 | Complete | 2026-03-20 |
| 8. Micro-Interactions & Final Polish | v1.0 | 1/1 | Complete | 2026-03-20 |
| 9. Position Management Overhaul | v1.1 | 0/2 | Pending | — |
| 10. Risk Visibility | v1.1 | 0/1 | Pending | — |
| 11. Execution Monitoring | v1.1 | 0/1 | Pending | — |

---
*Archive: `.planning/milestones/v1.0-ROADMAP.md`*
*Last updated: 2026-03-21 — v1.1 milestone started*
