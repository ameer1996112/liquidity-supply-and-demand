# UI Polish Plan (Targeted Pass — No Backend Contract Changes)

Date: 2026-02-19
Scope: Preserve current routes/features/data; improve performance, correctness, and UX polish for dashboard shell (sidebar + main grid + right signals panel).

---

## 1) Problems Found

## Performance

1. **Top bar subscribed to full signals list**

   - `TopBar` was recomputing KPI values from `useTradingSignals(mode)`.
   - Because it is mounted globally via `AppShell`, realtime signal churn could cause unnecessary rerenders outside dashboard context.

2. **Realtime cache updates could trigger avoidable invalidations**

   - `useTradingSignals` already batches events (300ms), but still invalidated stats after each batch even if effective list values were unchanged.

3. **Action handlers caused avoidable prop identity churn**

   - Signal selection callbacks were recreated per render in dashboard list panels.

4. **Paint-heavy visual hints**
   - Status dots and pulse animation relied on glow-like box-shadows and animated shadow spread.

## Correctness / Contradictory States

1. **Signed-zero display noise**

   - UI could show values like `-$0.00` from floating-point precision.

2. **Win-rate display edge cases**

   - Win-rate trend color and source could contradict trade volume / mode in top KPI strip.

3. **Neutral PnL still shown as directional trend**
   - `0` values were treated as positive trend in KPI styling.

## UX / Polish

1. **Empty states felt inconsistent and “beta”**

   - Different panels used different copy and visual patterns.

2. **Signals panel felt dense without row-level action affordance**

   - No clear inline action for inspection, forcing full-row reliance.

3. **Top strip readability**
   - Very small typography and tight metric cards reduced scannability.

---

## 2) Proposed Component Changes

- `frontend/src/components/layout/TopBar.tsx`

  - Use stats query as KPI source (no direct full signals subscription).
  - Improve metric legibility (slightly larger typography/spacing).
  - Neutral trend handling for exact zero.
  - Slower health polling interval to reduce churn.

- `frontend/src/hooks/useTradingSignals.ts`

  - Keep batched realtime pipeline.
  - Add meaningful-change guard before replacing list items.
  - Invalidate stats only when list actually mutates.

- `frontend/src/lib/format.ts`

  - Add signed-zero normalization utility.
  - Add consistent signed currency formatter.

- `frontend/src/components/shared/PnLDisplay.tsx`

  - Normalize `-0.00` to `0.00` and neutral color on flat values.

- `frontend/src/components/dashboard/RecentSignalsPanel.tsx`

  - Add explicit per-row `Inspect` action button.
  - Introduce cleaner empty-state messaging and icon semantics.

- `frontend/src/components/dashboard/ActiveTradesPanel.tsx`
- `frontend/src/components/dashboard/ActiveTradeRow.tsx`

  - Reuse shared empty-state component.
  - Normalize row PnL signed zero.
  - Stabilize row selection callback usage.

- `frontend/src/components/shared/PanelEmptyState.tsx` (new)

  - Standardized empty-state primitive for panel-level consistency.

- `frontend/src/app/globals.css`

  - Replace glow-heavy status dot shadows with lightweight ring shadows.
  - Replace shadow-pulse animation with opacity pulse.

- `frontend/src/app/page.tsx`
  - Memoize `handleSelectSignal` with `useCallback` to reduce rerender propagation.

---

## 3) Implementation Steps (Phase-Based)

## Phase 1 — Performance First (required)

1. Decouple topbar KPIs from high-churn full signal list.
2. Tighten realtime batch update logic to skip no-op cache mutations.
3. Lower expensive visual paint costs (status glow + pulse shadows).
4. Stabilize callback identities passed to list children.

## Phase 2 — Correctness & Contradiction Fixes

1. Introduce signed-zero normalization and shared currency formatting.
2. Ensure win-rate only displays meaningful trend and consistent mode source.
3. Ensure zero PnL surfaces render neutral style/state.

## Phase 3 — UX Polish

1. Improve KPI readability (font size / spacing).
2. Standardize empty states with a shared component.
3. Improve signals table action discoverability via explicit row action.

## Phase 4 — Validation & Documentation

1. Run test/build checks and capture status.
2. Record before/after notes and checklist outcomes.
3. Attach screenshot placeholders + profiling capture checklist for local DevTools run.

---

## 4) Profiling Workflow (Chrome + React Profiler)

Because this environment cannot directly capture interactive browser trace exports, use this exact local workflow:

1. Open dashboard in Chrome with live/mock feed.
2. **Chrome Performance**
   - Record 30–60s during realtime updates.
   - Capture: scripting time, rendering time, long tasks, FPS drops.
3. **React Profiler**
   - Profile `DashboardPage`, `TopBar`, `RecentSignalsPanel`, `ActiveTradesPanel`.
   - Capture: commit count, flamegraph hotspots, render durations.
4. Compare against pre-change traces from same session conditions.
