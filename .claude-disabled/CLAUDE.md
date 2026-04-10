# Project Operating Rules

You are working on a production-grade trading system.

## Non-negotiable rules

- Preserve frontend/backend contract integrity.
- Never change API payload shape without updating:
  - backend schema
  - frontend types
  - tests
  - docs
- Never change risk or execution logic without:
  - identifying affected modules
  - adding or updating tests
  - writing a short note in docs/decisions.md
- Prefer minimal safe patches over rewrites.
- For any bug:
  1. reproduce
  2. isolate first failure point
  3. patch minimally
  4. add regression protection
- For any feature:
  1. inspect impacted frontend
  2. inspect impacted backend
  3. inspect state management
  4. inspect error/loading/empty states
  5. update worklog

## Tracking rules

- After meaningful work, update:
  - docs/worklog.md
  - docs/bugs.md if a bug was fixed or discovered
  - docs/decisions.md if architecture changed

## Board rules (Kanban auto-update)

The board lives at `/board` in the frontend. Agents interact via two API endpoints:

**Create a ticket** (new bug found or task opened):

```bash
curl -s -X POST http://https://frontend-production-a7cf.up.railway.app/api/board/create-ticket \
  -H "Content-Type: application/json" \
  -d '{"type":"bug","title":"<title>","component":"<component>","priority":"<priority>","description":"<desc>","agent_name":"Claude Agent"}'
```

- component: "Pine Script" | "Python Backend" | "Supabase / DB" | "Frontend (React)" | "MT5 / Broker" | "AI / ML Pipeline" | "Infrastructure"
- priority: critical | high | medium | low

**Update a ticket** (status change or progress note):

```bash
curl -s -X POST http://localhost:3000/api/board/agent-update \
  -H "Content-Type: application/json" \
  -d '{"ticket_id":"BUG-012","new_status":"in_progress","message":"<progress note>","agent_name":"Claude Agent"}'
```

- new_status: backlog | todo | in_progress | done

**When to call these automatically:**

1. When you discover a new bug → create a BUG ticket (priority = critical if it affects money/risk, high if functional, medium otherwise)
2. When you start fixing a bug → move it to `in_progress` with a message describing the approach
3. When a fix is applied and tested → move it to `done`
4. When the frontend is not running (curl fails), skip silently — do not error out

**Board vs TodoWrite:**

- Use the board for bugs, features, and tasks the user can see and track across sessions.
- Use TodoWrite only for ephemeral step-by-step internal sub-tasks within a single session.
- Never create a TodoWrite item for something that should be a board ticket (e.g. "fix X bug", "implement Y feature").

**Slash commands available:**

- `/board-bug <description>` — open a bug ticket from natural language
- `/board-update <TICKET-ID> <status> [message]` — move a ticket to a new column

## Frontend standard

- Professional UI only.
- Consistent spacing, typography, loading, empty, and error states.
- No duplicate windows, stale statuses, or ambiguous labels.
- Prefer reusable components over one-off patches.

## Backend standard

- Strong validation and typed contracts.
- Clear logging at decision points.
- Idempotent handlers where relevant.
- No silent failures.
