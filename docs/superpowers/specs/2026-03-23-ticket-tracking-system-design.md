# Ticket Tracking System Design
*Created: 2026-03-23*

## Summary

A Jira-style task and bug tracking system embedded in the existing trading dashboard. Tickets are stored in Supabase, managed via a new FastAPI router (`api_tickets.py`), displayed in a full Kanban board in the Next.js frontend, and updatable programmatically by the AI agent via a tool-calling schema (`update_jira_ticket`).

**Key design choices:**
- Tickets can optionally link to a `trading_signals` row (hybrid: dev tool + trading context)
- AI actions are append-only to a `ai_changelog` JSONB field — no separate audit table needed
- Follows the exact existing router pattern (like `api_alerts.py`, `api_rules.py`)
- No Supabase Realtime needed — frontend polls like the rest of the dashboard

---

## 1. Data Model

### Table: `project_tickets`

```sql
CREATE TABLE project_tickets (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    title       TEXT NOT NULL,
    description TEXT,
    type        TEXT NOT NULL CHECK (type IN ('bug', 'feature', 'task')),
    status      TEXT NOT NULL DEFAULT 'todo'
                     CHECK (status IN ('todo', 'in_progress', 'done', 'archived')),
    priority    TEXT NOT NULL DEFAULT 'medium'
                     CHECK (priority IN ('low', 'medium', 'high', 'critical')),
    assignee    TEXT,
    signal_id   INTEGER REFERENCES trading_signals(id) ON DELETE SET NULL,
    ai_changelog JSONB NOT NULL DEFAULT '[]'::jsonb,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Auto-update updated_at on any row change
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER project_tickets_updated_at
    BEFORE UPDATE ON project_tickets
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- Indexes
CREATE INDEX idx_project_tickets_status   ON project_tickets(status);
CREATE INDEX idx_project_tickets_type     ON project_tickets(type);
CREATE INDEX idx_project_tickets_priority ON project_tickets(priority);
CREATE INDEX idx_project_tickets_signal   ON project_tickets(signal_id);
```

### `ai_changelog` entry shape (JSONB array element)
```json
{
  "timestamp": "2026-03-23T14:30:00Z",
  "agent": "antigravity",
  "old_status": "todo",
  "new_status": "in_progress",
  "summary": "Fixed departure_strength in SND_Core.pine lines 387-455. Replaced single-candle scoring with multi-candle accumulation and rolling-range normalization."
}
```

---

## 2. API Endpoints

**File:** `src/api_tickets.py`  
**Router prefix:** `/api/tickets`  
**Registered in:** `src/api.py`

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/tickets` | List tickets; supports `?status=`, `?type=`, `?priority=` query params |
| `POST` | `/api/tickets` | Create a new ticket |
| `GET` | `/api/tickets/{id}` | Fetch single ticket (full `ai_changelog`) |
| `PATCH` | `/api/tickets/{id}` | Human update: status, priority, assignee, description |
| `POST` | `/api/tickets/{id}/ai-update` | AI skill endpoint: update status + append changelog entry |
| `DELETE` | `/api/tickets/{id}` | Soft-delete: sets status to `archived` |

### AI update endpoint payload
```json
{
  "new_status": "in_progress",
  "summary_of_work": "Fixed departure_strength...",
  "agent": "antigravity"
}
```

---

## 3. AI Tool Schema (`update_jira_ticket`)

Anthropic-compatible tool definition (drop-in for Claude / OpenAI function calling):

```json
{
  "name": "update_jira_ticket",
  "description": "Update a project ticket's status and append a structured AI changelog entry. Call this after completing work on a task or bug that has a registered ticket. Be specific in summary_of_work — include file names and line numbers.",
  "input_schema": {
    "type": "object",
    "properties": {
      "ticket_id": {
        "type": "string",
        "description": "UUID of the ticket to update"
      },
      "new_status": {
        "type": "string",
        "enum": ["todo", "in_progress", "done"],
        "description": "The new status to set on the ticket"
      },
      "summary_of_work": {
        "type": "string",
        "description": "1-3 sentence summary of what was done. Include file names and line numbers where relevant."
      }
    },
    "required": ["ticket_id", "new_status", "summary_of_work"]
  }
}
```

### GSD Skill: `update-ticket`
File: `.agent/skills/update-ticket/SKILL.md`  
Instructs the AI to call `POST /api/tickets/{ticket_id}/ai-update` when:
- Completing a GSD phase that references a `ticket_id` in its PLAN.md
- Fixing a bug that was previously reported as a ticket
- Closing out a task after verification passes

---

## 4. Frontend — Kanban Board

**Route:** `/tickets` (new sidebar nav entry)  
**File:** `frontend/src/app/tickets/page.tsx` + `frontend/src/components/tickets/`

### Components
- `TicketsPage` — fetches all non-archived tickets, renders 3 columns
- `KanbanColumn` — renders a status column with card list + drop zone
- `TicketCard` — compact card with type icon, priority badge, title, signal link
- `TicketDrawer` — slide-in panel on card click; shows full details + AI changelog
- `NewTicketModal` — form to create a ticket (title, type, priority, optional signal link)

### UX behaviour
- Drag a card between columns → `PATCH /api/tickets/{id}` with `new_status`
- Click card → `TicketDrawer` opens; AI changelog rendered as a timeline
- Signal link in card/drawer → links to the signal in the existing dashboard
- `+ New Ticket` button top-right → `NewTicketModal`

---

## 5. Verification Plan

### Automated
```bash
# Backend tests
PYTHONPATH=/workspace pytest tests/ -v -k "ticket"
```
A new test file `tests/test_api_tickets.py` will be written covering:
- `POST /api/tickets` creates a row in Supabase
- `PATCH /api/tickets/{id}` updates status
- `POST /api/tickets/{id}/ai-update` appends to `ai_changelog`
- Invalid enum values return 422

### Manual
1. Run `./start.sh fullstack`
2. Navigate to `http://localhost:3000/tickets`
3. Click `+ New Ticket` → fill form → confirm card appears in TODO column
4. Drag card to IN PROGRESS → confirm status change persists on refresh
5. Call `POST http://localhost:8000/api/tickets/{id}/ai-update` via curl → confirm changelog entry appears in drawer
6. Create a ticket with `signal_id` → confirm signal link is clickable
