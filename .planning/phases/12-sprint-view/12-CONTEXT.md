# Phase 12: Sprint View — Context

**Gathered:** 2026-03-24

<decisions>
## Decisions

### Sprint Data
- Extend `GET /api/tickets` backend to include `sprint` field from Jira issue customfield
- Tickets with non-null sprint → active sprint (group by sprint name)
- Tickets with null sprint → Backlog section

### Sprint UI
- `glow-card` SprintHeader section ABOVE the Kanban board
- Sprint name + date range + thin `h-1.5` progress bar (done/total) with `--to-long` fill
- Empty: bouncing Calendar icon + "No active sprint"
- Backlog: collapsible `glow-card` below board — "▸ Backlog (N)" toggle
</decisions>
