---
name: system-tracker
description: Open, move, and update Kanban board tickets for bugs, tasks, and features. Use this to track any meaningful work on the board instead of internal to-dos.
argument-hint: [action] [ticket details]  e.g. "open bug NZDJPY position sizing wrong" or "close BUG-012 fix applied"
allowed-tools: Bash(curl *)
---

# System Tracker — Board Integration

Action: $ARGUMENTS

## Board API reference

**Base URL (local):** `http://localhost:3000`

### Create a ticket
```bash
curl -s -X POST http://localhost:3000/api/board/create-ticket \
  -H "Content-Type: application/json" \
  -d '{
    "type": "<bug|task|feature|research>",
    "title": "<title>",
    "component": "<component>",
    "priority": "<critical|high|medium|low>",
    "description": "<description>",
    "status": "<backlog|todo|in_progress|done>",
    "agent_name": "Claude Agent"
  }'
```

### Update / move a ticket
```bash
curl -s -X POST http://localhost:3000/api/board/agent-update \
  -H "Content-Type: application/json" \
  -d '{
    "ticket_id": "<BUG-012>",
    "new_status": "<backlog|todo|in_progress|done>",
    "message": "<progress note>",
    "agent_name": "Claude Agent"
  }'
```

**Valid components:** `Pine Script` | `Python Backend` | `Supabase / DB` | `Frontend (React)` | `MT5 / Broker` | `AI / ML Pipeline` | `Infrastructure`

## Workflow based on $ARGUMENTS

**If "open" or "create":** create ticket, return ticket_id.
**If "start" or "in_progress":** move ticket to `in_progress` with approach note.
**If "done" or "close" or "fix applied":** move ticket to `done` with summary.
**If "update":** post a progress message without changing status.

## Rules

- Prefer board tickets over internal todo lists for anything visible to the user.
- If the frontend is not running (curl times out), log to docs/bugs.md instead — never fail silently without a record.
- Always return the ticket_id so the user can navigate to it.
