# Phase 4: Dashboard Redesign — Research

**Phase:** 04 — Dashboard Redesign
**Date:** 2026-03-20
**Status:** RESEARCH COMPLETE

## Executive Summary

- Dashboard already has StatCards, SignalTable, RiskBar, LiveLog, BestSetupCard, ActiveTradesPanel — all functional, all wired to live data
- Phase 4 is **visual enhancement only**: upgrade layout to bento-grid hero, add WebSocket pill, animate signal rows, add side-colored borders on rows
- The StatCard is already sophisticated (sparklines, animated numbers, hover shimmer, trend indicators) — needs a `hero` variant (larger, stronger glow)
- `useConnectionHealth()` returns `{ status, isConnected }` — status values map to display states
- `animate-fade-in-up` and `stagger-children` already defined in globals.css — slide-in for signals needs a new keyframe
- `--to-long` and `--to-short` tokens already defined — use directly for side-colored borders
- `formatDistanceToNowStrict` from `date-fns` already imported in `RecentSignalsPanel.tsx` — reusable pattern for relative timestamps

## Current Dashboard Analysis

### What Exists (to preserve)
- `StatCard` — 7 cards in `grid-cols-2 md:grid-cols-4 xl:grid-cols-7` grid; has sparklines, animated numbers, hover shimmer scan line, trend indicator
- `SignalTable` — filterable signal table (All/Active/Wins/Losses/Rejects), signal count badge, signal row with `StatusBadge`, `PnLDisplay`
- `LiveLog` — live log panel (flex-1, scrollable)
- `ActiveTradesPanel` — open positions snapshot at the bottom
- `RiskBar` — inside glow-card panel in side rail
- `BestSetupCard` — conditional best setup card in side rail
- `MarketSessionBanner`, `PageStatusBanner` — status banners below header
- `LivePnlTicker` — PnL ticker for open positions
- `SessionRing` — win/loss ring
- `WaitingBanner` — shown when `noData`
- Page transitions: `animate-fade-in-up` with `key={pathname}` already in AppShell

### What Needs Changing
- KPI grid: make 7-column bento with `Today PnL` as hero card (`col-span-2` + hero styling)
- Header: add WebSocket connection pill right of page title
- SignalTable rows: add left border (3px, color by side), slide-in animation on new rows
- WaitingBanner: glass panel treatment with amber border
- Mobile: properly ordered stacking (KPIs → WebSocket → Active trades → Signal feed → Risk → Live log)
- Live log mobile: hidden by default with toggle

## Token & Animation Inventory

### Design Tokens (confirmed from globals.css + STATE.md)
- `--to-long`: green long color (`#0ecb81` area)
- `--to-short`: red short color (`#f6465d` area)
- `--to-warning`: amber warning (`#f0b90b` area)
- `--to-accent-amber`: primary amber accent
- `--to-surface`: base surface
- `--to-surface-raised`: elevated surface
- `--to-border`: default border
- `--to-border-glow`: glow border color
- `--to-text-dim`: dim text
- `--to-text-secondary`: secondary text
- `--font-mono`: JetBrains Mono

### Animation Classes (confirmed in globals.css)
- `animate-fade-in-up` — existing fade-up keyframe ✅
- `stagger-children` — staggered animation for grid children ✅
- `skeleton-shimmer` — shimmer animation ✅
- `glow-card` — glass background + amber glow shadow ✅
- `glass-panel` — frosted glass treatment ✅

### New animation needed:
- `animate-slide-in-right` — for signal row entry (slide from right + fade)

## StatCard Hero Variant

Add optional `hero?: boolean` prop to `StatCard`:

**Hero styling changes:**
- Add `col-span-2` via `className` prop (caller sets this) — no prop needed in component
- Add `variant='hero'` prop that applies:
  - Value: `text-[2rem]` instead of `text-[1.15rem]`
  - Border glow: `border-[var(--to-accent-amber)]/40 hover:border-[var(--to-accent-amber)]/70`
  - Extra ambient glow: `shadow-[0_0_20px_rgba(240,185,11,0.12)] hover:shadow-[0_0_30px_rgba(240,185,11,0.25)]`
  - Padding: `px-5 py-4` instead of `px-4 py-3.5`
- All other StatCard features preserved (sparkline, animated number, trend, shimmer scan line)

**Approach:** Add `hero` to `VARIANT_CONFIG` or add a conditional `heroClass` in the component. Prefer the latter to minimize diff.

## Signal Row Animation Pattern

### New keyframe for globals.css:
```css
@keyframes slide-in-right {
  from { transform: translateX(8px); opacity: 0; }
  to   { transform: translateX(0);   opacity: 1; }
}
.animate-slide-in-right {
  animation: slide-in-right 200ms ease-out both;
}
```

### Left border on signal rows in SignalTable.tsx:
- Add `border-l-[3px]` to each row `<tr>` or row wrapper
- Color: `border-l-[var(--to-long)]` when `side === 'LONG'` or `side === 'BUY'`
- Color: `border-l-[var(--to-short)]` when `side === 'SHORT'` or `side === 'SELL'`
- Default: `border-l-transparent` for unknown side
- Apply via `cn()` conditional class merging

### Relative timestamp:
- `formatDistanceToNowStrict` already imported in `RecentSignalsPanel.tsx` — import same in SignalTable if not present
- Tooltip: use existing `Tooltip` / `TooltipContent` from `@/components/ui/tooltip` (shadcn) with absolute time

## WebSocket Pill Implementation

### Hook: `useConnectionHealth()`
Returns `{ status, isConnected }` where status likely has values like `'connected'`, `'reconnecting'`, `'disconnected'`, `'paper'` (or similar).

### New component: `ConnectionPill.tsx` (or inline in page.tsx)
Location: `frontend/src/components/dashboard/ConnectionPill.tsx`

```tsx
// ConnectionPill.tsx
import { useConnectionHealth } from '@/hooks/useConnectionHealth';

export function ConnectionPill() {
  const { status, isConnected } = useConnectionHealth();

  const config = {
    connected:     { label: 'LIVE',         icon: '●', color: 'text-[var(--to-long)]',    bg: 'bg-[var(--to-long)]/10    border-[var(--to-long)]/30' },
    paper:         { label: 'PAPER',         icon: '●', color: 'text-[var(--to-warning)]', bg: 'bg-[var(--to-warning)]/10 border-[var(--to-warning)]/30' },
    reconnecting:  { label: 'RECONNECTING', icon: '⚠', color: 'text-[var(--to-short)]',   bg: 'bg-[var(--to-short)]/10   border-[var(--to-short)]/30', pulse: true },
    disconnected:  { label: 'OFFLINE',       icon: '●', color: 'text-[var(--to-short)]',   bg: 'bg-[var(--to-short)]/10   border-[var(--to-short)]/30' },
  };
  // ... render pill
}
```

**Placement in page.tsx header:** After `<ModeBadge>`, before the end of the header right-side `<div>`.

## Mobile Stack Strategy

### Approach: CSS `order` utility via Tailwind

The current layout uses `flex flex-col` — which naturally stacks. The bento KPI section goes first, then a `flex xl:flex-row` for the main content. For mobile ordering:

1. KPI hero section → naturally first (no order needed)
2. WebSocket pill → in header (always visible)
3. Active trades → move `<section>` for ActiveTradesPanel to be rendered directly after the bento KPIs on mobile (use `order-first xl:order-last` pattern, or just restructure the render order)
4. Signal feed → the `<section className="flex-1">` main content
5. Risk bar → in side rail, which on mobile becomes full-width below signals
6. Live log toggle → button + collapsible `<section>` on `<md`

### Live log mobile toggle:
- Wrap `<LiveLog>` in a `<section>` with `hidden md:block` by default on the section itself
- Add `<button>` that toggles `showLog` state → `{showLog && <LiveLog ... />}`
- Button text: "Show Live Log" / "Hide Live Log"
- Only render button on mobile (`md:hidden`)

## Implementation Notes & Gotchas

1. **`col-span-2` on mobile:** In `grid-cols-1 md:grid-cols-4 xl:grid-cols-7`, `col-span-2` on mobile makes the hero card span 2 of 1 col — just use `col-span-1 xl:col-span-2` for the hero card
2. **SignalTable rows:** The existing `SignalTable` renders `<tr>` elements — adding `border-l-[3px]` requires also setting `border-l-color` and removing default `border` on the row (if any)
3. **Animation on new rows:** CSS `animate-slide-in-right` on `<tr>` may have limited browser support — use a wrapper `<div>` or apply on `<td>` first child instead
4. **`useConnectionHealth` status values:** Read the hook source to confirm exact string values before coding the pill
5. **WaitingBanner glass treatment:** Add `glass-panel` class + `border-[var(--to-warning)]/30` to the outer section

## Validation Architecture

| Success Criterion | Verification Command |
|---|---|
| Hero card col-span-2 in the grid | `grep "xl:col-span-2" frontend/src/app/page.tsx` |
| StatCard hero variant applied to Today PnL | `grep "hero" frontend/src/app/page.tsx` |
| animate-slide-in-right keyframe defined | `grep "slide-in-right" frontend/src/app/globals.css` |
| Signal rows have left border by side | `grep "to-long\|to-short" frontend/src/components/dashboard/SignalTable.tsx` |
| ConnectionPill component exists | `test -f frontend/src/components/dashboard/ConnectionPill.tsx` |
| ConnectionPill rendered in header | `grep "ConnectionPill" frontend/src/app/page.tsx` |
| WaitingBanner has glass-panel class | `grep "glass-panel" frontend/src/app/page.tsx` |
| Live log toggle button on mobile | `grep "showLog\|Show Live Log" frontend/src/app/page.tsx` |
| TypeScript compiles cleanly | `cd frontend && npx tsc --noEmit 2>&1 | tail -5` |
