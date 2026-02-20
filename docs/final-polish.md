q# Final Polish Pass (Frontend Only)

This document summarizes the premium UI polish pass requested for the dashboard experience, while keeping backend contracts/routes unchanged.

## Task 1 — Simplify Top Bar + Move KPIs into Dashboard

### What changed

- Kept top bar focused on core controls only:
  - Connection status
  - LIVE/PAPER mode toggle
  - Kill switch
- Added a compact KPI row inside `frontend/src/app/page.tsx` (top of dashboard content) with:
  - Today PnL
  - Total PnL
  - Drawdown
  - Daily DD
  - Active Positions
  - Trades Today
- Added **Last updated** timestamp above KPI row.

### Files

- `frontend/src/app/page.tsx`

---

## Task 2 — Adaptive Empty States (Center Layout)

### What changed

- Added adaptive `noData` behavior in dashboard:
  - Collapses center technical panel height when there is no active/usable data
  - Runs `ActiveTradesPanel` in compact mode
- Added a primary card: **“Bot is waiting for…”** with:
  - Strategy name
  - Timeframe
  - Last signal time
  - Last reject reason (when available)
  - Readiness checklist (Connected / Config loaded / Risk guard / Market open)
- When data returns, layout expands back to full-size content.

### Files

- `frontend/src/app/page.tsx`
- `frontend/src/components/dashboard/ActiveTradesPanel.tsx` (compact mode use)

---

## Task 3 — Formatting Consistency + Buggy Tells

### What changed

- Standardized numeric formatting with shared formatter helpers:
  - `EMPTY_VALUE = "—"`
  - negative-zero normalization (`-0.00` → `0.00`)
  - consistent currency/percent/number formatters
- Applied formatter usage across dashboard display surfaces:
  - PnL display
  - Active trade row values
  - KPI row values
  - Mini equity total + tooltip
- Existing support for empty win-rate/profit-factor style metrics (`formatWinRateValue`, `formatOptionalMetric`) remains available in shared formatter module for 0-trade scenarios.

### Files

- `frontend/src/lib/formatters.ts`
- `frontend/src/components/shared/PnLDisplay.tsx`
- `frontend/src/components/dashboard/ActiveTradeRow.tsx`
- `frontend/src/components/dashboard/MiniEquityChart.tsx`
- `frontend/src/app/page.tsx`

---

## Task 4 — Signals Panel Readability + Actions

### What changed

- Improved recent signals scanability:
  - slightly taller rows + cleaner spacing
  - strong symbol emphasis and secondary time-ago metadata
  - direction indicator and single primary status badge
- Consolidated secondary actions into menu (`⋯`) per row:
  - View details
  - Copy symbol
  - Copy payload
  - Mark reviewed
- Added details drawer behavior for selected signal with:
  - signal metadata, trigger, status, timestamp, rationale

### Files

- `frontend/src/components/dashboard/RecentSignalsPanel.tsx`

---

## Task 5 — Performance + Smoothness

### What changed

- Real-time signal updates are batched/throttled in `useTradingSignals` (300ms window) to reduce excessive re-render churn.
- Signals panel uses memoized rows and paging to prevent heavy long-list rendering cost spikes.
- Derived dashboard values are memoized (`useMemo`) to reduce unnecessary recomputation.

### React Profiler notes

- Manual code-level profiling pass focused on render hotspots in dashboard/signal list flow.
- Main reductions were achieved through batching, memoized rows, and list pagination.
- If you want a strict numeric profiler report (commit duration deltas), run React DevTools Profiler in your target environment and capture before/after traces with live feed enabled.

---

## Screenshots

- Before/after screenshots: optional (not added in this commit).
