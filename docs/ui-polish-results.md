# UI Polish Results (Targeted Pass)

Date: 2026-02-19  
Scope: Dashboard polish/perf/correctness pass without backend contract changes.

---

## 1) Before → After Summary

## Performance

- **Before:** Top bar subscribed to full signal stream and recalculated KPIs from every list update.
- **After:** Top bar uses lightweight stats query for KPI values and no longer depends on full signal list churn.

- **Before:** Realtime batch flush could still invalidate stats even on effectively unchanged row values.
- **After:** Realtime updates now skip no-op replacements (`hasSignalMeaningfulChanges`) and only invalidate stats when list actually mutates.

- **Before:** UI used animated glow-heavy shadows for status pulses.
- **After:** Pulse is opacity-based; status dots use lightweight ring shadow tokens (reduced paint overhead).

- **Before:** Signal selection callbacks recreated on parent rerenders.
- **After:** Selection handlers stabilized (`useCallback`, direct callback pass-through to row components).

## Correctness

- **Fixed:** Signed-zero noise (`-$0.00`) via `normalizeSignedZero` + `formatSignedCurrency`.
- **Fixed:** Neutral zero values no longer styled as directional trend in top KPI strip.
- **Fixed:** Win-rate display source and trend handling improved to avoid contradictory states when trade count is empty/neutral.

## UX / Polish

- Standardized panel empty states via new shared component: `PanelEmptyState`.
- Improved top KPI strip legibility (larger numeric text + spacing).
- Improved right signals panel actionability with explicit row-level **Inspect** button.
- Cleaner empty copy in active positions and recent signals panels.

---

## 2) Files Changed

- `frontend/src/components/layout/TopBar.tsx`
- `frontend/src/hooks/useTradingSignals.ts`
- `frontend/src/lib/format.ts`
- `frontend/src/components/shared/PnLDisplay.tsx`
- `frontend/src/components/shared/PanelEmptyState.tsx` (new)
- `frontend/src/components/dashboard/RecentSignalsPanel.tsx`
- `frontend/src/components/dashboard/ActiveTradesPanel.tsx`
- `frontend/src/components/dashboard/ActiveTradeRow.tsx`
- `frontend/src/app/page.tsx`
- `frontend/src/app/globals.css`
- `docs/ui-polish-plan.md`

---

## 3) Validation

## Tests

- `npm --prefix /Users/ameeramer/dev/projects/galilsoftware/sources/trading/frontend test` ✅
  - 1 test file passed, 5/5 tests passed.

## Build

- `npm --prefix /Users/ameeramer/dev/projects/galilsoftware/sources/trading/frontend run build` ✅
  - Next.js build completed successfully.
  - Static/dynamic route generation succeeded.

---

## 4) Metrics Notes

Because interactive browser profiling exports are not generated directly in this CLI context, attach local captures below after running Chrome DevTools + React Profiler:

- **Chrome Performance (before):** _attach trace/screenshot_
- **Chrome Performance (after):** _attach trace/screenshot_
- **React Profiler (before):** _attach screenshot of commit count/flamegraph_
- **React Profiler (after):** _attach screenshot of commit count/flamegraph_

Recommended comparison targets:

1. Commit count and render duration for `TopBar`, `RecentSignalsPanel`, `ActiveTradesPanel`
2. Main-thread scripting/rendering time during 30–60s live update window
3. Long task count and FPS stability under signal update bursts

---

## 5) Screenshot Placeholders

Add screenshots to `/docs/screenshots/ui-polish/` and link here:

- `before-dashboard-overview.png` — _pending_
- `after-dashboard-overview.png` — _pending_
- `before-signals-panel-empty.png` — _pending_
- `after-signals-panel-empty.png` — _pending_
- `after-signals-panel-inspect-action.png` — _pending_
- `after-topbar-kpis.png` — _pending_
