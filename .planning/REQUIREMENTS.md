# Milestone v1.1 Requirements

## Frontend Jira Kanban Dashboard
- [ ] **JIR-01**: User can view a dedicated Jira dashboard page in the Next.js frontend.
- [ ] **JIR-02**: System automatically fetches active Sprints and Tasks directly from the Hosted Atlassian Jira API (no local Supabase ticket storage).
- [ ] **JIR-03**: User can view tasks organized in a Kanban board layout (To Do, In Progress, Done).
- [ ] **JIR-04**: User can drag and drop tickets on the Kanban board to instantly update their status in the Atlassian Jira cloud.

## Future Requirements
- Advanced Epic planning and tracking
- Bi-directional webhook updates (Hosted Jira updating the UI without refresh)

## Out of Scope
- Local Supabase database tables for Jira Tickets (Relying purely on Hosted Jira API as the source of truth).

## Traceability
| Req ID | Phase | Plan | Status |
|---|---|---|---|
| JIR-01 | Phase 4 | 4-01 | Active |
| JIR-02 | Phase 4 | 4-01 | Active |
| JIR-03 | Phase 5 | 5-01 | Active |
| JIR-04 | Phase 5 | 5-01 | Active |
