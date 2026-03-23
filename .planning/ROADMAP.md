# ROADMAP.md — AI-Powered PM Command Center

**Milestone:** AI-Powered PM Command Center
**Granularity:** Coarse
**Total phases:** 4
**Requirements covered:** PM-01–PM-04, EV-01–EV-04, UI-01–UI-10 (14/14)

---

## Phase 1: Smart Kanban Board Foundation

**Goal:** Upgrade the `jira/` app into a polished, real-time Kanban board with rich ticket metadata and inline editing — the visual foundation everything else builds on.

**Requirements:** UI-01, UI-02, UI-03, UI-04

**Plans:**
1. Real-time Kanban board with Supabase subscriptions — auto-refreshing columns (To Do / In Progress / Done), card drag-and-drop syncing status back to Supabase + Jira
2. Rich ticket card UI — labels, epic badge, priority indicator, story points, source tag (GSD/event/manual), assignee avatar
3. Rich text editor for ticket descriptions and comments (integrated into ticket detail modal)

**Success criteria:**
1. Opening the board shows all tickets organized by status with no manual refresh
2. Dragging a ticket card to "Done" updates status in Supabase and Jira within 2 seconds
3. Clicking a ticket opens a detail panel with rich text description, comments, and metadata fields
4. Tickets created from any source (manual, GSD, events) appear on the board automatically

---

## Phase 2: GSD ↔ Jira Full Automation

**Goal:** Every GSD workflow command automatically creates, updates, or closes the corresponding Jira ticket — zero manual `update-ticket` invocations required.

**Requirements:** PM-01, PM-02, PM-03, PM-04

**Plans:**
1. GSD lifecycle hooks — modify `update-ticket` skill and GSD command wrappers to fire on phase-start, plan-execute, and phase-complete events automatically
2. Jira Epic auto-creation from ROADMAP.md — on project init or roadmap change, sync phases as Jira epics with descriptions and story counts
3. Status sync engine — bidirectional state machine ensuring GSD phase state always mirrors Jira ticket state

**Success criteria:**
1. Running `/gsd-discuss-phase N` creates a Jira ticket for Phase N with no manual action
2. Running `/gsd-execute-phase N` moves the ticket to "In Progress" automatically
3. Phase completion closes the ticket and adds a summary comment in Jira
4. GSD roadmap phases appear as Jira epics after `/gsd-new-project` or `/gsd-plan-phase`

---

## Phase 3: Trading System Events → Auto Tickets

**Goal:** Trading system health events (errors, test failures, ML drift, late fills) automatically generate actionable Jira tickets without any human involvement.

**Requirements:** EV-01, EV-02, EV-03, EV-04

**Plans:**
1. Worker error bridge — wrap worker pipeline exception handlers to POST to a new `/api/incidents` endpoint; incident service creates Jira P1/P2 ticket with stack trace and signal context
2. Test failure webhook — add pytest plugin/hook that POSTs failures to the API; backend creates bug tickets with test name and failure message
3. ML drift + watchdog alerts → tickets — ML Guardian confidence drop and TradeWatchdog late-fill events write to a `system_events` Supabase table; DB trigger or background job creates Jira tickets for unacknowledged events

**Success criteria:**
1. Throwing an unhandled exception in the worker creates a Jira P1 ticket within 10 seconds
2. A pytest test failing creates a bug ticket with the test name and failure message
3. ML Guardian dropping below `ml_min_confidence` for 3+ consecutive signals creates a "model drift" ticket
4. A late-fill watchdog alert creates an operational ticket visible on the Kanban board

---

## Phase 4: AI Command Center + Sprint Planning

**Goal:** Add the AI Command Center panel, real-time activity feed, sprint board, roadmap timeline, and AI-driven backlog grooming — completing the full PM Command Center vision.

**Requirements:** UI-05, UI-06, UI-07, UI-08, UI-09, UI-10

**Plans:**
1. AI Command Center panel — natural language input that calls the backend LLM to parse intent and create a structured Jira ticket (title, description, labels, priority, epic mapping)
2. Real-time activity feed — websocket/polling feed showing all automation events (GSD sync, incident tickets, ML drift, manual creates) as a live log
3. Sprint board + velocity charts — sprint assignment UI, burndown chart, velocity trend (tickets closed per sprint), sprint start/close actions
4. Roadmap timeline view — parse `.planning/ROADMAP.md` and render phases as a Gantt-style timeline with status indicators
5. AI backlog grooming + trading health widget — AI endpoint ranks open tickets by urgency (pulls trading PnL, error rate, open positions count), renders health widget in sidebar

**Success criteria:**
1. Typing "Fix the MetaAPI rate limit issue" in the command panel creates a complete Jira ticket with description and labels
2. The activity feed shows GSD phase events and incident tickets in real-time as they happen
3. Sprint board shows assigned tickets, burndown chart updates as tickets close
4. Roadmap timeline correctly renders all ROADMAP.md phases with their current completion status
5. "Groom backlog" AI action returns a prioritized ticket ranking with reasoning

---

## Requirement Coverage

| REQ-ID | Description | Phase |
|--------|-------------|-------|
| UI-01 | Real-time Kanban auto-populate | 1 |
| UI-02 | Drag-and-drop status sync | 1 |
| UI-03 | Rich ticket metadata | 1 |
| UI-04 | Rich text editor | 1 |
| PM-01 | GSD phase start → Jira ticket | 2 |
| PM-02 | GSD plan execution → ticket update | 2 |
| PM-03 | Phase complete → ticket close | 2 |
| PM-04 | Roadmap phases → Jira epics | 2 |
| EV-01 | Worker errors → P1/P2 tickets | 3 |
| EV-02 | Test failures → bug tickets | 3 |
| EV-03 | ML drift → drift ticket | 3 |
| EV-04 | Watchdog alerts → operational tickets | 3 |
| UI-05 | AI natural language ticket creation | 4 |
| UI-06 | Real-time activity feed | 4 |
| UI-07 | Sprint board + velocity | 4 |
| UI-08 | Roadmap timeline | 4 |
| UI-09 | AI backlog grooming | 4 |
| UI-10 | Trading health widget | 4 |
