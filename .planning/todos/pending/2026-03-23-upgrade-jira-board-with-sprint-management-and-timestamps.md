---
created: 2026-03-23T14:14:19.000Z
title: Upgrade Jira board with sprint management and timestamps
area: ui
files:
  - jira/src/app/(app)/board/page.tsx
  - jira/src/lib/supabase.ts
  - jira/src/components/IssueCard.tsx
  - jira/src/components/IssueDrawer.tsx
---

## Problem

The current Jira board is a basic kanban. The user wants it elevated to a proper sprint-based workflow with time awareness — similar to Linear or Jira's sprint board. Key missing features:
- No sprint planning view (start/end dates, sprint goal, velocity)
- Timestamps on cards are not prominent or useful enough
- No sprint switching / filtering on the board
- No "time in column" tracking or deadline indicators
- Sprints table (`jira_sprints`) exists but isn't fully wired into the board UX

## Solution

### Phase 1 — Timestamps
- Show `created_at` and `updated_at` on cards in relative format ("2h ago", "3d ago")
- Show "time in current status" on each card (requires tracking when status last changed — may need a `status_changed_at` column)
- Highlight tickets that have been stuck in a column too long (e.g. > 3 days in `in_progress`)

### Phase 2 — Sprint Management
- Sprint selector in board header (active sprint / backlog toggle)
- Sprint creation modal: name, goal, start date, end date
- Sprint progress bar (done / total tickets, days remaining)
- "Move to sprint" action on ticket cards
- Backlog view: unassigned tickets drag-into-sprint
- Sprint completion flow: auto-move incomplete tickets to next sprint or backlog
