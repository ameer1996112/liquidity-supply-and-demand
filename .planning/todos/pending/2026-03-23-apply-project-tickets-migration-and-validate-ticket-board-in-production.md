---
created: 2026-03-23T12:48:53.398Z
title: Apply project_tickets migration and validate ticket board in production
area: tooling
files:
  - migrations/057_project_tickets.sql
---

## Problem

The ticket tracking system (Jira-style board) was fully implemented and committed in `feat: Jira-style ticket tracking system`, but the `project_tickets` table has not yet been created in the Supabase production database. Until the migration is run, the `/api/tickets` endpoints will return 503 (table missing) and the frontend Kanban board at `/tickets` will be empty with no ability to create tickets.

Additionally, the frontend build on Railway was fixed (Lucide `title` prop removed), but needs a successful deploy to confirm the board renders correctly in production.

## Solution

1. Open Supabase dashboard → SQL Editor
2. Paste contents of `migrations/057_project_tickets.sql` and run
3. Verify table created: `SELECT count(*) FROM project_tickets;` → should return 0
4. Confirm Railway frontend deploy succeeds after the `fix: remove invalid title prop` commit
5. Open `https://<frontend-url>/tickets` and create a test ticket to validate end-to-end
6. Optionally: plug `tool-schema.json` from `.agent/skills/update-ticket/` into agent config to activate AI auto-update skill
