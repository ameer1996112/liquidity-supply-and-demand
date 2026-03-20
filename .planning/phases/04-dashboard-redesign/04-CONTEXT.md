# Phase 4: Dashboard Redesign - Context

**Gathered:** 2026-03-20
**Status:** Ready for planning

<domain>
## Phase Boundary

Transform the existing functional dashboard into an eye-catching command center. Upgrade hero KPI layout to a bento-style grid with a prominent "Today PnL" hero card, add a persistent WebSocket connection pill in the header, apply slide-in animated entries and side-colored accents to the signal feed, and ensure proper mobile stacking order. No new data sources or features — pure visual enhancement and layout upgrade of existing components.

</domain>

<decisions>
## Implementation Decisions

### Hero Layout & KPI Card Presentation
- Bento-style grid: large "Today PnL" hero card spanning 2 cols + 5 smaller uniform stat cards — creates visual hierarchy over current uniform 7-card grid
- Today PnL hero card: large amber glow border (`--to-accent-amber` glow) + larger value text (2rem) — visually distinct from other stat cards
- WebSocket connection indicator: persistent pill in header row (right of page title) — always-visible `● LIVE` / `● PAPER` / `⚠ RECONNECTING` with semantic color
- Waiting banner (noData state): keep existing `WaitingBanner` but style as glass panel with amber border + icon-row status checklist

### Signal Feed Visual Treatment
- Animated entry for new signals: slide-in from right + fade (`animate-fade-in-up` variant) on new row — reuses existing animation system
- Side-colored accents: left 3px border in `--to-long` (green) or `--to-short` (red) per signal side — mirrors nav active bar pattern from Phase 3
- Live timestamp: relative time ("2m ago") with tooltip showing absolute time — updates every 30s
- Signal count badge: mono font pill on panel header (current pattern is correct — verify and preserve)

### Layout Density & Mobile Stack Order
- Mobile section stacking order: Hero KPIs → WebSocket pill → Active trades → Signal feed → Risk bar → Live log
- Active Trades panel: keep at bottom (current) — below main bento content area
- Live log on mobile: hidden by default, accessible via toggle — saves screen real estate
- Panel section headers: keep existing `to-panel-header` style — already premium with label + timestamp right-aligned

### Claude's Discretion
- Exact bento grid column spans and breakpoints for the 2-col + 5-card layout
- Animation duration and easing for slide-in signal rows
- Exact pill styling dimensions for WebSocket indicator
- Toggle implementation detail for live log on mobile (button vs tab vs sheet)

</decisions>

<code_context>
## Existing Code Insights

### Reusable Assets
- `StatCard.tsx` — fully built with sparklines, animated numbers, trend indicators, hover shimmer scan line
- `SignalTable.tsx` — existing signal feed with filter tabs (All/Active/Wins/Losses/Rejects)
- `LiveLog.tsx` — live log panel
- `ActiveTradesPanel.tsx` — open positions snapshot
- `RiskBar.tsx` — risk status component
- `BestSetupCard.tsx` — highest AI score signal card
- `MarketSessionBanner.tsx`, `PageStatusBanner.tsx` — existing status banners
- `LivePnlTicker.tsx` — live PnL ticker for open positions
- `SessionRing.tsx` — win/loss ring indicator
- `useConnectionHealth()` — provides `status`, `isConnected`
- `glass-panel`, `glow-card` CSS classes, `--to-long`, `--to-short`, `--to-warning` tokens
- `animate-fade-in-up`, `stagger-children` — existing animation utilities

### Established Patterns
- Token prefix: `--to-*`
- `glass-panel` for elevated/frosted surfaces
- Static glow preferred over pulse in trading UI
- `cn()` for conditional class merging
- Section divider format: `/* ── Label ─────────────────────────── */`
- Left 3px border accent for active/highlighted items (Phase 3 pattern)
- `animate-fade-in-up` with `stagger-children` for list entries

### Integration Points
- `frontend/src/app/page.tsx` — main dashboard page (633 lines) — primary file to update
- `frontend/src/components/dashboard/SignalTable.tsx` — add slide-in animation + left border accent
- `frontend/src/components/dashboard/StatCard.tsx` — hero card variant (larger, glow border)
- `frontend/src/app/globals.css` — any new animation utilities if needed

</code_context>

<specifics>
## Specific Ideas

- Today PnL hero card uses `col-span-2` in `grid-cols-7` layout — 2 wide + 5 normal = 7 total columns
- WebSocket pill: `● LIVE` green / `● PAPER` amber / `⚠ RECONNECTING` red — positioned right of page title in header
- Signal row slide-in: CSS animation on new row insertion, left border color driven by signal `side` field
- Live log toggle on mobile could be a simple `<button>` that reveals/hides the log section below the risk bar

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope.

</deferred>
