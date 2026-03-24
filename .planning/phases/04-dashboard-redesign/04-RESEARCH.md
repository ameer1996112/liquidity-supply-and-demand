# Phase 4: Dashboard Redesign — Research

**Researched:** 2026-03-24
**Status:** Complete

## Executive Summary

StatCard is already premium — it has `AnimatedNumber`, `FlashValue`, `VARIANT_CONFIG` (profit/loss/warning with green/red/amber gradients, icon chips, hover glow), `hero` prop with amber border glow, shimmer scan line, sparkline, and bottom accent bar. Phase 4 work is **layout restructuring** in `page.tsx`, a **WebSocket status pill** in `TopBar.tsx`, and adding the **slide-in-right animation** for new signal entries in `RecentSignalsPanel.tsx`.

## Existing Code Analysis

### StatCard.tsx
- Already has: `glass-panel`-compatible gradient bg, `AnimatedNumber`, `FlashValue`, `hero` prop, variant-based glow/gradient, hover translate, shimmer scan line, bottom accent bar
- **No changes needed** to StatCard itself — wire up `hero`, `numericValue`, `numericFormat`, `sparklineData` props correctly in `page.tsx`

### page.tsx (dashboard root)
- Imports: `StatCard`, `SignalTable`, `LiveLog`, `ActiveTradesPanel`, `RiskBar`, `ConnectionPill`, `SessionRing`, `LivePnlTicker`, `BestSetupCard`
- Existing stat metrics: PnL, Win Rate, Active positions, Daily trades, Drawdown, Best Score
- Layout issues: stats are likely in a flat row or simple grid — needs bento upgrade + responsive stacking
- `ConnectionPill` already imported — this is a separate component from the sidebar one; needs to be moved to `TopBar`

### RecentSignalsPanel.tsx
- Uses `date-fns` `formatDistanceToNowStrict` for relative timestamps — already does live relative time via `ClientDate`
- Has Sheet for signal details, filter tabs, ScrollArea
- Missing: **slide-in-right** entry animation for new signals — needs CSS class + `key` on signal rows

### TopBar.tsx
- Has a "Metrics block" with Net Liq + Today PnL already
- Has "Action Pills" section (mode switcher, kill switch, copilot button)
- `useConnectionHealth()` is NOT yet imported/used in TopBar directly
- **Add**: small WS status dot + label between Net Liq metrics and Action Pills

### globals.css animations
- `animate-fade-in-up` ✓ exists
- `slide-in-right` — need to verify if it exists

## Implementation Plan

### Plan A: Dashboard page.tsx layout upgrade (primary work)
- Wire `hero` prop on the first KPI card (Net PnL)
- Add `numericValue`/`numericFormat` props to PnL, Win Rate cards
- Change grid from current flat layout → `grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3` for hero KPI row
- Below hero: `grid grid-cols-1 lg:grid-cols-5 gap-3` → ActiveTradesPanel (col-span-3) | RecentSignalsPanel (col-span-2)
- Remove `ConnectionPill` from page.tsx (move to TopBar)

### Plan B: WebSocket status in TopBar
- Import `useConnectionHealth` in TopBar
- Add a `<ConnectionStatusPill />` inline sub-component inside TopBar between metrics block and action pills
- Style: `h-2 w-2 rounded-full` dot + label (`text-[10px] font-mono`) — matches sidebar ConnectionPill pattern

### Plan C: Signal entry animation
- Add `@keyframes slide-in-right` to globals.css if missing
- Add CSS class `animate-slide-in-right` 
- Apply as `className` on the signal row container with `key={signal.id}` to trigger on mount

## Files to Modify

| File | Change | Scope |
|------|--------|-------|
| `frontend/src/app/page.tsx` | Bento grid layout, hero KPI wiring, remove ConnectionPill | Medium |
| `frontend/src/components/layout/TopBar.tsx` | Add inline WS status pill | Small |
| `frontend/src/app/globals.css` | Add `slide-in-right` keyframe + utility class (if missing) | Small |
| `frontend/src/components/dashboard/RecentSignalsPanel.tsx` | Add `animate-slide-in-right` to signal rows | Small |

## Validation Architecture

### DASH-01: Hero section with KPI glow cards
- `grep "hero" frontend/src/app/page.tsx` → StatCard with hero prop
- `grep "grid-cols" frontend/src/app/page.tsx` → responsive grid present

### DASH-02: Signal feed with animated entry + side colors
- `grep "slide-in-right\|animate-slide" frontend/src/components/dashboard/RecentSignalsPanel.tsx` → present
- `grep "border-l.*to-long\|border-l.*to-short" frontend/src/components/dashboard/RecentSignalsPanel.tsx` → side color

### DASH-03: WebSocket status in TopBar
- `grep "useConnectionHealth\|ConnectionStatus" frontend/src/components/layout/TopBar.tsx` → present

### DASH-04: Responsive layout
- `grep "grid-cols-1\|md:grid-cols\|lg:grid-cols" frontend/src/app/page.tsx` → responsive grid

## RESEARCH COMPLETE
