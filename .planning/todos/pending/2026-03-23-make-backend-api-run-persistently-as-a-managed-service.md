---
created: 2026-03-23T22:37:21.513Z
title: Make backend API run persistently as a managed service
area: api
ticket_id: "DEV-11"
files:
  - src/api.py
  - start.sh
---

## Problem

The backend API (FastAPI on port 8000) dies whenever the terminal closes or a manual process is killed. During this session it needed to be restarted 3+ times to unblock the PM automation system:

- `POST /api/incidents` — creates P1/P2 Jira tickets from system events
- `POST /api/tickets/gsd-sync` — GSD phase lifecycle → Jira
- `GET /api/tickets/active-sprint` — sprint resolution for all new tickets
- `POST /api/tickets/sprints/start` — sprint management

Without the backend running, `/gsd-add-todo`, `gsd-jira-hook.sh`, and the jira/ app's AI Assist page all degrade to `api_unavailable`.

## Solution

Set up the backend as a persistent managed process using one of:

**Option A — launchd (macOS preferred):**
```bash
# Create plist at ~/Library/LaunchAgents/com.tradeops.api.plist
# Cmd: source venv/bin/activate && PYTHONPATH=/path uvicorn src.api:app --port 8000
# RunAtLoad: true, KeepAlive: true
launchctl load ~/Library/LaunchAgents/com.tradeops.api.plist
```

**Option B — pm2 (Node ecosystem):**
```bash
npm install -g pm2
pm2 start "source venv/bin/activate && PYTHONPATH=$(pwd) python3 -m uvicorn src.api:app --port 8000" --name tradeops-api
pm2 save && pm2 startup
```

**Option C — update start.sh:**
The existing `start.sh fullstack` already starts API + Worker + Frontend. Make it idempotent (check if port 8000 is already in use before spawning).

Acceptance criteria:
- Backend survives terminal close
- Auto-restarts on crash
- Redis is started first (fail-fast check)
- Logs go to `/tmp/tradeops-api.log` or similar
