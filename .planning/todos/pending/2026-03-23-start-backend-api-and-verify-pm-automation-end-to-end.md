---
created: 2026-03-23T21:47:23.345Z
title: Start backend API and verify PM automation end-to-end
area: api
ticket_id: ""
files:
  - src/api.py
  - src/api_incidents.py
  - src/api_tickets.py
  - .agent/get-shit-done/bin/gsd-jira-hook.sh
---

## Problem

The backend API (FastAPI, port 8000) is not currently running locally, which means the entire PM automation system built in the AI-Powered PM Command Center milestone is untested end-to-end:

- `POST /api/incidents` — auto-creates Jira P1/P2 tickets from system events (can't test)
- `POST /api/tickets/gsd-sync` — GSD phase lifecycle → Jira (can't test)
- `GET /api/tickets/active-sprint` — sprint resolution for new todos (returns error)
- The jira/ frontend's AI Assist page calls `localhost:8000` for quick actions

Redis is also required before the API can start (fail-fast check on startup).

Additionally, a `curl` command has been running for ~2 hours in the background — should be killed.

## Solution

1. Kill the stuck background curl process
2. Start Redis: `redis-server --daemonize yes`
3. Start the backend: `PYTHONPATH=$(pwd) python3 -m uvicorn src.api:app --host 0.0.0.0 --port 8000`
4. Run smoke tests:
   - `curl http://localhost:8000/health` → `{"status":"healthy"}`
   - `curl -X POST http://localhost:8000/api/incidents -H "Content-Type: application/json" -d '{"type":"worker_error","title":"Test incident","summary":"smoke test","source":"manual","priority":"P3"}'`
   - `curl http://localhost:8000/api/tickets/active-sprint`
5. Verify ticket appears on Jira board and in the jira/ app `/incidents` page
