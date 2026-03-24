---
status: passed
phase: 12
phase_name: Sprint View
verified: 2026-03-24
---

# Phase 12: Sprint View — Verification

## Status: passed ✅

## Checks

### Backend
- ✅ `_extract_sprint_info` returns `(sprint_id, sprint_name)` from `customfield_10020`
- ✅ `_jira_to_ticket` now includes `sprint_name` field alongside `sprint_id`
- ✅ `_extract_sprint_id` alias preserved for backward compat

### SPRINT-01: Active sprint section
- ✅ `glow-card` SprintHeader above board with Calendar icon header
- ✅ Sprint name derived from first sprint-assigned ticket's `sprint_name`
- ✅ Bouncing Calendar icon + "No active sprint" when no sprint tickets

### SPRINT-02: Progress bar
- ✅ `h-1.5` bar with `bg-[var(--to-long)]` fill
- ✅ `X of Y closed` + percentage label
- ✅ `transition-all duration-500` smooth fill animation
- ✅ `sprintDone / sprintTickets.length * 100` width calculation

### SPRINT-03: Backlog section
- ✅ Collapsible `glow-card` below board — toggle `ChevronDown`/`ChevronUp`
- ✅ `backlogTickets = tickets.filter(t => !t.sprint_name)`
- ✅ Backlog rows show type icon + ID + title + priority
- ✅ Clicking row opens `TicketDrawer`
- ✅ Bouncing Calendar empty state if no backlog items

### TypeScript
- ✅ `npx tsc --noEmit` — exit 0
- ✅ `sprint_id` and `sprint_name` added to `Ticket` interface
