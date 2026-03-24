# Phase 4: Dashboard Redesign - Context

**Gathered:** 2026-03-24
**Status:** Ready for planning

<domain>
## Phase Boundary

Transform the main dashboard (`/`) into a premium command center. Restyle existing components to use the design system — hero KPI cards with glow treatment, animated signal feed with side-colored accents, WebSocket status in TopBar, and responsive stacking on mobile. No new data sources or backend changes — visual redesign only.

</domain>

<decisions>
## Implementation Decisions

### Hero Metrics Section
- 6 KPI cards: PnL, Win Rate, Active Positions, Daily Trades, Drawdown, Best Setup
- Card treatment: `glass-panel` + colored top-border accent (green for PnL/win rate, red for drawdown, amber for neutral)
- Desktop layout: 3+3 equal bento grid (6 columns, 2 rows) — `grid-cols-3 md:grid-cols-6`
- Live PnL uses `AnimatedNumber` component (already in `ui/AnimatedNumber.tsx`)

### Signal Feed & Live Data
- New signal entry animation: slide-in-right (from `globals.css`)
- Signal card: side-colored left border — LONG=`--to-long` (green), SHORT=`--to-short` (red)
- Timestamp: live relative time ("2m ago", "just now") updating in real-time; absolute on hover tooltip
- WebSocket status: small dot + label in TopBar next to existing content — leverages `useConnectionHealth()` hook

### Dashboard Layout & Mobile
- Section order: Hero KPIs → Signal Feed (right) + Active Trades (left) → Risk Bar → Live Log
- Desktop: 2-column below hero — Active Trades (60%) | Signal Feed (40%)
- Mobile: single column stacked — KPIs → Signal Feed → Active Trades → Risk Bar
- Mobile padding accounts for MobileNav (Phase 3 `pb-20`) — inherits from AppShell

### Claude's Discretion
- Exact glow color token per KPI card (green vs amber vs neutral assignment)
- Tooltip implementation for relative timestamps
- TopBar layout adjustment to fit WebSocket status pill without breaking existing content

</decisions>

<code_context>
## Existing Code Insights

### Reusable Assets
- `StatCard.tsx` — existing KPI card component (to be restyled with glass-panel + glow)
- `SignalTable.tsx` / `RecentSignalsPanel.tsx` — existing signal display (to be animated)
- `LivePnlTicker.tsx` — live PnL feed (uses AnimatedNumber)
- `AnimatedNumber.tsx` (`ui/AnimatedNumber.tsx`) — smooth number transitions, ready to use
- `ActiveTradesPanel.tsx` — active positions section
- `RiskBar` (`components/risk/RiskBar.tsx`) — risk indicator bar
- `LiveLog.tsx` — live activity log
- `SessionRing.tsx` — market session indicator
- `MarketSessionBanner.tsx` — session banner
- `useConnectionHealth()` — returns `{ status: 'healthy' | 'degraded' | 'offline' }`
- `ConnectionPill` in Sidebar — existing pattern for WS status display
- `SideBadge` — left-border colored badge using `--to-long`/`--to-short`
- `glass-panel`, `glow-green`, `glow-red`, `glow-amber` — all available in globals.css
- `slide-in-right`, `animate-fade-in-up` — animation utilities in globals.css

### Established Patterns
- Token naming: `--to-*` prefix
- `glass-panel` for elevated card surfaces (Phase 2 decision)
- Side badge left-border pattern: `border-l-[3px] border-l-[var(--to-long)]` / `--to-short`
- `cn()` for conditional class merging
- `useConnectionHealth()` already used in Sidebar and AppShell
- `key={signal.id}` + CSS animation for staggered list entries
- `formatCurrency`, `formatPercent`, `formatNumber` from `@/lib/formatters`

### Integration Points
- `frontend/src/app/page.tsx` — main dashboard page (primary file to update)
- `frontend/src/components/dashboard/StatCard.tsx` — restyle KPI cards
- `frontend/src/components/layout/TopBar.tsx` — add WebSocket status pill
- `frontend/src/components/dashboard/RecentSignalsPanel.tsx` or `SignalTable.tsx` — add entry animation + left border
- `frontend/src/app/globals.css` — add `slide-in-right` keyframe if not present

</code_context>

<specifics>
## Specific Ideas

- AnimatedNumber already used in LivePnlTicker — reuse same pattern in StatCard for PnL metric
- WebSocket status pill should visually match the `ConnectionPill` in Sidebar for consistency
- Signal entry animation should trigger when new signals are prepended to the list (use CSS `@keyframes` + class on mount)

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope.

</deferred>
