# Milestone v1.1 Requirements — AI-Driven Jira Upgrade

## BOARD — Kanban Board View

- [ ] **BOARD-01**: User can view all tickets in a Kanban board with Todo / In Progress / Done columns
- [ ] **BOARD-02**: User can drag a ticket card between columns to update its status in Jira
- [ ] **BOARD-03**: Ticket cards show type icon, priority badge, ID, title, and AI agent indicator if AI-touched
- [ ] **BOARD-04**: Board columns use glass-panel styling with count badges per column

## TICKET — Rich Ticket Detail

- [ ] **TICKET-01**: User can click any ticket to open a full detail slide-over panel (not a new page)
- [ ] **TICKET-02**: Detail panel shows title, description, type, priority, status, created date, and labels
- [ ] **TICKET-03**: User can update ticket status directly from the detail panel
- [ ] **TICKET-04**: Detail panel shows AI changelog entries as a vertical timeline (agent, timestamp, old→new status, summary)

## SPRINT — Sprint View

- [ ] **SPRINT-01**: User can see an active sprint section at the top of the tickets page with its tickets
- [ ] **SPRINT-02**: Sprint header shows sprint name, date range, and a progress bar (completed/total tickets)
- [ ] **SPRINT-03**: Tickets not in active sprint are grouped in a Backlog section below

## AI — AI-Driven Features

- [ ] **AI-01**: Ticket creation form auto-suggests type (bug/feature/task) and priority based on title keywords
- [ ] **AI-02**: Board shows a global "AI Activity Feed" panel — last 5 AI agent updates across all tickets
- [ ] **AI-03**: Tickets touched by AI agents show a small bot indicator icon on their card

## UI — Premium Design

- [ ] **UI-01**: Tickets page uses page-title header with ClipboardList icon chip
- [ ] **UI-02**: Board columns and sprint section use glow-card / glass-panel treatment
- [ ] **UI-03**: Ticket cards have hover lift (`hover:-translate-y-[1px]`) and smooth transitions
- [ ] **UI-04**: All empty states use PanelEmptyState with animated bounce icon

---

## Future (v1.2+)

- Comment threads on tickets
- Assignee filtering
- Burndown chart
- Webhook trigger on ticket change

## Out of Scope (v1.1)

- Standalone Jira app (separate Next.js project) — stays embedded in trading frontend
- Custom sprint creation/management — read-only sprint from Jira API
- Full Jira field editing (description edit) — view-only for now

---

## Traceability

| REQ-ID | Phase | Status |
|--------|-------|--------|
| BOARD-01 | 09 | [ ] |
| BOARD-02 | 09 | [ ] |
| BOARD-03 | 09 | [ ] |
| BOARD-04 | 09 | [ ] |
| UI-01 | 09 | [ ] |
| UI-02 | 09 | [ ] |
| UI-03 | 09 | [ ] |
| UI-04 | 09 | [ ] |
| TICKET-01 | 10 | [ ] |
| TICKET-02 | 10 | [ ] |
| TICKET-03 | 10 | [ ] |
| TICKET-04 | 10 | [ ] |
| AI-01 | 11 | [ ] |
| AI-02 | 11 | [ ] |
| AI-03 | 11 | [ ] |
| SPRINT-01 | 12 | [ ] |
| SPRINT-02 | 12 | [ ] |
| SPRINT-03 | 12 | [ ] |
