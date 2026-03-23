# REQUIREMENTS.md — AI-Powered PM Command Center

## v1 Requirements

### PM Automation — GSD ↔ Jira Sync

- [ ] **PM-01**: GSD phase start automatically creates a Jira ticket (no manual `update-ticket` invocation required)
- [ ] **PM-02**: GSD plan execution in real-time updates the status of the corresponding Jira ticket
- [ ] **PM-03**: GSD phase completion automatically closes the Jira ticket with a summary note
- [ ] **PM-04**: GSD roadmap phases are automatically reflected as Jira epics on initialization

### EV — Trading System Events → Tickets

- [ ] **EV-01**: Worker pipeline errors (uncaught exceptions, guard rail crashes) auto-create P1/P2 Jira tickets with stack trace
- [ ] **EV-02**: Backend test failures auto-generate bug tickets with test name and failure message
- [ ] **EV-03**: ML Guardian confidence falling below threshold triggers an auto-created "model drift" ticket
- [ ] **EV-04**: TradeWatchdog late fills and operational alerts auto-create operational tickets

### UI — Smart Kanban Board

- [ ] **UI-01**: Kanban board auto-populates tickets from GSD phases and trading system events in real-time
- [ ] **UI-02**: Drag-and-drop status changes (To Do → In Progress → Done) sync back to Jira
- [ ] **UI-03**: Tickets display rich metadata: labels, epic, assignee, story points, priority, source (GSD/event/manual)
- [ ] **UI-04**: Rich text editor for ticket descriptions and inline comments

### UI — AI Command Center

- [ ] **UI-05**: Natural language ticket creation panel ("Fix the MetaAPI rate limiting issue") — AI generates title, description, labels, priority, and creates in Jira
- [ ] **UI-06**: Real-time activity feed showing all automation events (GSD sync, event triggers, AI decisions) as they happen

### UI — Sprint & Roadmap Planning

- [ ] **UI-07**: Sprint board view with velocity charts and burndown graph
- [ ] **UI-08**: Roadmap timeline view that reads `.planning/ROADMAP.md` and visualizes phases on a timeline
- [ ] **UI-09**: AI-driven backlog grooming — suggests ticket priority ranking based on trading system health, PnL, and error frequency
- [ ] **UI-10**: Trading system health widget embedded in the PM dashboard (open positions, daily PnL, error count)

---

## v2 (Deferred)

- Multi-user/team support with role-based access
- Slack integration for ticket notifications
- Mobile-responsive layout
- Custom workflow states beyond To Do / In Progress / Done
- Automated sprint retrospective reports

---

## Out of Scope

- Replacing the main `frontend/` trading dashboard — PM lives in `jira/` only
- Building a new broker integration — MetaAPI stays
- Public multi-tenant SaaS — single team only
- Native mobile app

---

## Traceability

| REQ-ID | Phase |
|--------|-------|
| PM-01–PM-04 | Phase 2 |
| EV-01–EV-04 | Phase 3 |
| UI-01–UI-04 | Phase 1 |
| UI-05–UI-06 | Phase 4 |
| UI-07–UI-10 | Phase 4 |
