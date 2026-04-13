# Optimizer Local Agent — Design Spec

## Summary

Add a polling-based local agent that runs on the operator's Mac, watches for queued optimizer runs in the database, auto-launches Chrome with CDP, executes the optimizer, and reports progress back via the existing API. Add an agent heartbeat so the UI shows whether the local agent and Chrome are ready.

## Goals
- Bridge the gap between Railway-hosted UI/backend and locally-running Chrome + TradingView
- Auto-launch Chrome CDP when a queued run is picked up
- Report live progress (events, per-symbol results) back to the backend
- Show agent + Chrome status in the optimizer UI
- Support cancellation from the UI

## Non-Goals
- Running the optimizer on Railway
- Tunnel/WebSocket-based communication
- Multi-user or multi-agent support
- launchd/systemd auto-start (can add later)

## Architecture

```
┌─────────────────────────────────────────────────┐
│  Railway                                         │
│  ┌──────────┐    ┌──────────────────────────┐   │
│  │ Frontend  │───▶│ Backend (FastAPI)         │   │
│  │ /optimizer│    │ /api/optimizer/runs       │   │
│  │           │◀───│ /api/optimizer/agent/status│  │
│  └──────────┘    └──────────────────────────┘   │
└─────────────────────────┬───────────────────────┘
                          │ HTTPS (polling)
┌─────────────────────────┴───────────────────────┐
│  Local Mac                                       │
│  ┌──────────────────────────────────────────┐   │
│  │ local_agent.py                            │   │
│  │  - polls for queued runs every 10s        │   │
│  │  - heartbeat every 30s                    │   │
│  │  - launches Chrome via start-chrome.sh    │   │
│  │  - spawns parallel_runner.py              │   │
│  │  - pushes events/results via API          │   │
│  └──────────────┬───────────────────────────┘   │
│                 │                                 │
│  ┌──────────────▼───────────────────────────┐   │
│  │ Chrome (CDP :9222) + TradingView tabs     │   │
│  └──────────────────────────────────────────┘   │
└─────────────────────────────────────────────────┘
```

## Local Agent (`scripts/optimizer/local_agent.py`)

### Core Loop
```
1. Load ADMIN_API_KEY and API_URL from .env
2. Start heartbeat thread (every 30s)
3. Poll loop (every 10s):
   a. GET /api/optimizer/runs?status=queued
   b. If no queued runs → continue
   c. Check Chrome CDP on :9222
   d. If not alive → run start-chrome.sh, wait up to 15s
   e. If still not alive → mark run "failed" with error
   f. Update run status → "running"
   g. Spawn parallel_runner.py with run config
   h. Monitor subprocess, stream progress to API
   i. On exit → update status to "completed" or "failed"
   j. Resume polling
```

### Chrome Management
- Check: `GET http://127.0.0.1:9222/json/version`
- Launch: `subprocess.Popen(["bash", "scripts/optimizer/start-chrome.sh"])`
- Wait: poll `/json/version` every 1s for up to 15s
- Report: include `chrome_ready: true/false` in heartbeat

### Cancellation Handling
- During optimizer execution, poll `GET /api/optimizer/runs/{id}` every 5s
- If status is `cancelled` → send SIGTERM to subprocess → wait 10s → SIGKILL if needed
- Report final status back to API

### Progress Reporting
The agent reads structured output from `parallel_runner.py` (which already writes JSON status files and JSONL worker logs) and pushes:
- `POST /api/optimizer/runs/{id}/events` — timeline events (pair_started, pair_completed, pair_failed, log)
- `PATCH /api/optimizer/runs/{id}/results/{symbol}` — per-symbol metrics as they complete
- `PATCH /api/optimizer/runs/{id}` — summary updates (completed_pairs, failed_pairs, best_score, etc.)

## Backend Changes

### Modified: `optimizer_run_service.py`
- `start_run()` → creates run with status `queued` only. No subprocess spawn. Returns the run immediately.
- Remove subprocess management code (not needed on Railway)

### New Endpoints (added to `api_optimizer_runs.py`)

#### `POST /api/optimizer/agent/heartbeat`
```json
{ "chrome_ready": true, "agent_version": "1.0" }
```
Stores in-memory (not DB). Returns 200.

#### `GET /api/optimizer/agent/status`
```json
{ "agent_online": true, "chrome_ready": true, "last_heartbeat": "2026-04-13T15:00:00Z" }
```
Agent is "online" if last heartbeat < 60s ago.

#### `PATCH /api/optimizer/runs/{id}`
Update run status and summary. Used by local agent.
```json
{ "status": "running", "summary": { "completed_pairs": 5 } }
```

#### `POST /api/optimizer/runs/{id}/events`
Push a timeline event. Used by local agent.
```json
{ "event_type": "pair_completed", "symbol": "EURUSD", "worker_id": 0, "payload": {} }
```

#### `PATCH /api/optimizer/runs/{id}/results/{symbol}`
Update per-symbol result. Used by local agent.
```json
{ "status": "completed", "metrics": { "score": 85.2, "net_profit": 1200 } }
```

All new endpoints protected by `_require_admin_key`.

## Frontend Changes

### Agent Status Badge (in Run Launcher card)
- Green dot + "Agent Ready" — agent online, Chrome ready
- Yellow dot + "Chrome Offline" — agent online, Chrome not ready (will auto-launch on run)
- Red dot + "Agent Offline" — no heartbeat in 60s

### New Hook: `useAgentStatus`
```ts
GET /api/optimizer/agent/status — poll every 15s
```

### No other UI changes
The existing Run Launcher, Active Run card, Results, Timeline, and History tabs all work as-is. The only addition is the status badge.

## Decision Log

| # | Decision | Alternatives | Reason |
|---|----------|-------------|--------|
| 1 | Local agent on Mac, not Railway | Railway headless Chrome | TradingView needs logged-in session + paid indicator |
| 2 | Polling (10s) not WebSocket/tunnel | ngrok, Cloudflare Tunnel, WebSocket | Simplest — no infra, no connection mgmt |
| 3 | Auto-launch Chrome from agent | "Start Chrome" UI button | Simpler — agent handles lifecycle |
| 4 | Agent heartbeat for status | No indicator; direct health check | User needs to know agent+Chrome ready |
| 5 | Run created as "queued" only | Backend spawns subprocess | Backend on Railway can't run Chrome |
| 6 | Push updates via API | Direct DB writes; file watching | Clean separation, existing API |

## Risks
- Agent must be running on Mac for runs to execute
- Chrome profile corruption could require manual re-login to TradingView
- Network issues between Mac and Railway could delay progress updates (but won't lose data — agent retries)

## Testing
- Agent: unit test poll loop with mocked API responses
- Backend: test new endpoints (heartbeat, agent status, PATCH run/results)
- Frontend: test status badge rendering for all 3 states
- Integration: dry-run end-to-end (agent picks up dry_run=true, reports completion)
