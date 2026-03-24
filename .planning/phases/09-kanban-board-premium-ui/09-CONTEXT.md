# Phase 09: Kanban Board + Premium UI — Context

**Gathered:** 2026-03-24

<decisions>
## Decisions

### Board Layout & DnD
- **Library:** `@dnd-kit/core` + `@dnd-kit/sortable`
- **Mobile:** `overflow-x-auto snap-x` — 3 columns horizontal scroll on mobile, 3-col grid on desktop
- **Card grouping:** By priority within column (Critical → High → Medium → Low)
- **Status update:** Optimistic — card moves immediately, API fires async, revert on error with toast

### Card Design
- **Density:** Compact — type icon + ID (DEV-XX) + title (1-line truncated) + priority badge + bot icon
- **Priority colors:** critical=`--to-short` red, high=`--to-warning` amber, medium=blue-400, low=dim
- **Column header:** Name + count bubble (e.g. "Todo · 4"), `glass-panel` bg
- **Create:** "+ Add" button in Todo column → Sheet modal with existing create form

## Requirements Mapped
BOARD-01, BOARD-02, BOARD-03, BOARD-04, UI-01, UI-02, UI-03, UI-04

## Implementation Plan
1. Install `@dnd-kit/core @dnd-kit/sortable @dnd-kit/utilities` if not present
2. Create `frontend/src/components/tickets/TicketCard.tsx`
3. Create `frontend/src/components/tickets/KanbanBoard.tsx`
4. Rewrite `frontend/src/app/tickets/page.tsx` using board layout

## Design Tokens Used
- `glass-panel`, `glow-card`, `page-title`, `page-subtitle`
- `animate-fade-in-up`, `stagger-children`
- `--to-short` (red/critical), `--to-warning` (amber/high), `--to-long` (green)
- `PanelEmptyState` with animate-bounce icon
</decisions>
