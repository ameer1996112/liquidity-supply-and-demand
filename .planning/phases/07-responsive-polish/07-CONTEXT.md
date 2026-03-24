# Phase 7: Responsive Polish - Context

**Gathered:** 2026-03-24
**Status:** Ready for planning

<decisions>
## Implementation Decisions

### Mobile Layout
- Dashboard KPI: `grid-cols-2` on mobile (pre-existing per research) — verify
- Table overflow: `overflow-x-auto` on containers of signal/trade tables where missing
- Sidebar/MobileNav: Phase 3 already handled — skip

### Ultra-Wide & Typography
- Max-width cap: already in AppShell (`max-w-[1800px] 2xl:max-w-[2000px]`) — verify
- Hero StatCard font: `text-[1.6rem] md:text-[2rem]` (responsive size to prevent overflow on small screens)
- Touch targets: `min-h-[40px]` enforcement on filter tabs, nav buttons where missing
- `overflow-x-auto` on signal table containers where missing

### Claude's Discretion
- Which specific tables lack overflow-x-auto
- Exact breakpoint for hero text size reduction
</decisions>

<code_context>
## Key Files
- `frontend/src/components/dashboard/StatCard.tsx` — hero text size
- `frontend/src/components/dashboard/RecentSignalsPanel.tsx` — signal table overflow
- `frontend/src/components/layout/AppShell.tsx` — max-width already applied
- `frontend/src/app/page.tsx` — KPI grid cols
</code_context>
