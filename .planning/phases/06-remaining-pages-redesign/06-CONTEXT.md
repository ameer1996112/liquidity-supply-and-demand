# Phase 6: Remaining Pages Redesign - Context

**Gathered:** 2026-03-24
**Status:** Ready for planning

<decisions>
## Implementation Decisions

### Page Header Consistency
- `page-title` + `page-subtitle` headings on all pages missing them
- Small `glass-panel` icon chip (h-7 w-7) left of title on each page
- `PanelEmptyState` on Positions (no positions), Scanner (no results), Alerts (no alerts)
- Scope: **Positions, Scanner, Alerts** pages (others already styled)

### Card & Data Table Styling
- `DataTable` + `glow-card` wrapper wrapping data sections
- Scanner: `glass-panel` card per result with symbol, trigger, side badge, score
- Alerts: left border color — amber (warning), red (critical) on each alert row
- Positions: keep existing `PositionCard`, add consistent `page-title` header only

### Claude's Discretion
- Exact `page-subtitle` copy per page
- Icon selection per page (e.g. ScanLine for scanner, Bell for alerts, Crosshair for positions)
</decisions>

<code_context>
## Existing Patterns

- `page-title`, `page-subtitle` CSS classes in globals.css (used in risk page)
- `PanelEmptyState` component: `@/components/shared/PanelEmptyState`
- `glass-panel` class for card elevation
- `glow-card` class for section wrappers
- `--to-warning`, `--to-short` for amber/red alert colors
- `border-l-[3px]` pattern for left accent borders (established in Phase 3)
- `animate-fade-in-up` for page entry animation (already in AppShell)

### Integration Points
- `frontend/src/app/positions/page.tsx`
- `frontend/src/app/scanner/page.tsx`
- `frontend/src/app/alerts/page.tsx`
</code_context>
