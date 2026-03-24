# Milestone v1.1 Roadmap — AI-Driven Jira Upgrade

## Overview

**4 phases** · **18 requirements** · Continues from phase 08 (v1.0 ended at 08)

---

## Phase 09: Kanban Board + Premium UI

**Goal:** Replace the flat ticket list with a premium Kanban board matching the trading terminal's dark design system.

**Requirements:** BOARD-01, BOARD-02, BOARD-03, BOARD-04, UI-01, UI-02, UI-03, UI-04

**Success criteria:**
1. Tickets page shows 3 Kanban columns (Todo / In Progress / Done) with glass-panel cards
2. User can drag a card to a new column and status updates in Jira immediately
3. Page header uses page-title + ClipboardList icon chip + animate-fade-in-up
4. Ticket cards show type icon, priority badge, ID, title; hover lifts card slightly
5. Empty columns show PanelEmptyState with bouncing icon

**Key files:**
- `frontend/src/app/tickets/page.tsx` — full rewrite to board layout
- New: `frontend/src/components/tickets/KanbanBoard.tsx`
- New: `frontend/src/components/tickets/TicketCard.tsx`

---

## Phase 10: Rich Ticket Detail Panel

**Goal:** Add a slide-over detail panel that shows full ticket context and AI changelog timeline.

**Requirements:** TICKET-01, TICKET-02, TICKET-03, TICKET-04

**Success criteria:**
1. Clicking any ticket card opens a right slide-over panel without page navigation
2. Panel shows title, description, type, priority, status, created date, labels
3. User can change ticket status from the panel (calls PATCH /api/tickets/{id})
4. AI changelog renders as a vertical timeline with agent name, timestamp, status transition, and summary

**Key files:**
- New: `frontend/src/components/tickets/TicketDetailPanel.tsx`
- New: `frontend/src/components/tickets/AIChangelogTimeline.tsx`

---

## Phase 11: AI-Driven Features

**Goal:** Surface AI agent activity throughout the board — creation assist, card indicators, global feed.

**Requirements:** AI-01, AI-02, AI-03

**Success criteria:**
1. Typing in the create-ticket title auto-suggests type and priority (keyword matching)
2. A "AI Activity Feed" panel shows last 5 AI agent updates across all tickets (agent, ticket ID, summary)
3. Cards touched by AI agents show a small bot icon
4. Auto-suggestions appear within 300ms of typing with no extra API calls (client-side keyword match)

**Key files:**
- `frontend/src/components/tickets/CreateTicketForm.tsx` — AI suggestion logic
- New: `frontend/src/components/tickets/AIActivityFeed.tsx`
- `frontend/src/components/tickets/TicketCard.tsx` — bot indicator

---

## Phase 12: Sprint View

**Goal:** Add sprint context to the board — active sprint panel at the top, backlog below.

**Requirements:** SPRINT-01, SPRINT-02, SPRINT-03

**Success criteria:**
1. Active sprint section appears above the Kanban board with sprint name + date range
2. Sprint progress bar shows X of Y tickets closed (numeric + visual bar)
3. Tickets not in sprint are in a collapsible Backlog section
4. Empty sprint shows PanelEmptyState "No active sprint"

**Key files:**
- New: `frontend/src/components/tickets/SprintHeader.tsx`
- `frontend/src/app/tickets/page.tsx` — sprint data fetching + layout integration
- Backend: Extend `/api/tickets` to include sprint field from Jira API
