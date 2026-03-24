# Phase 5: Risk & Prop Firm Redesign - Context

**Gathered:** 2026-03-24
**Status:** Ready for planning

<domain>
## Phase Boundary

Redesign the risk monitor (`/risk`) and prop firm challenge tracker (`/prop-firm`) with clear metric hierarchy and visual gauges. Uses existing components (CircularGauge, StatCard, PanelEmptyState). No new data sources.

</domain>

<decisions>
## Implementation Decisions

### Risk Monitor Layout & Hierarchy
- Critical metrics (Daily Loss, Drawdown) as large hero cards with CircularGauge at top row
- Traffic light color coding: green (`--to-long`) < 50%, amber (`--to-warning`) 50–80%, red (`--to-short`) > 80%
- Guard rails as status list: name + enabled/disabled + severity badge in glass-panel list
- Kill switch: prominent red-bordered glass panel, `animate-pulse` red border when active

### Prop Firm Challenge Tracker
- Progress bars + percentage for each limit (max drawdown, daily loss, profit target)
- Border pulse animation when metric > 80% of limit (amber warning threshold)
- Multiple accounts: tabs or accordion if multiple prop accounts
- Pass/fail: large badge ("PASSING" / "FAILING" / "AT RISK") below account name

### Mobile Layout & Shared Patterns
- Risk mobile stacking: critical metrics first (severity descending)
- Reuse `StatCard` with `variant` prop (profit/loss/warning) — no new component
- Prop firm mobile: single column stacked, full-width bars
- Empty state: `PanelEmptyState` with shield icon + "No challenge configured"

### Claude's Discretion
- Exact threshold percentages for color transitions
- Tab vs accordion choice based on actual data structure
- Progress bar height and animation easing

</decisions>

<code_context>
## Existing Code Insights

### Reusable Assets
- `CircularGauge` (`ui/CircularGauge.tsx`) — already used in risk page for drawdown visualization
- `StatCard` — `variant` prop (profit/loss/warning) maps to green/red/amber
- `PanelEmptyState` — shield icon + message for empty state
- `RiskBar` (`components/risk/RiskBar.tsx`) — horizontal progress bar already exists
- `useRiskMonitor()` — returns daily_risk, drawdown, position_limits, guard_rails
- `GuardRailToggle.tsx` — existing toggle UI for guard rails
- `glass-panel`, `glow-red`, `animate-pulse` — available in globals.css
- `cn()` utility, `--to-long`/`--to-short`/`--to-warning` tokens

### Integration Points
- `frontend/src/app/risk/page.tsx` — primary risk page to redesign
- `frontend/src/app/prop-firm/page.tsx` — prop firm page to redesign
- `frontend/src/components/risk/RiskBar.tsx` — reusable for prop firm progress bars

</code_context>

<specifics>
## Specific Ideas

- Risk page already uses `CircularGauge` — keep and enhance with traffic-light color prop
- RiskBar already exists — reuse for prop firm progress bars
- Kill switch card should visually match existing kill switch in TopBar (red glow pattern)

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope.

</deferred>
