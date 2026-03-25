# AGENTS.md

## 🎫 Jira Auto-Ticket (MANDATORY — applies to EVERY agent, EVERY task)

**This rule fires automatically. No CLI. No user prompting needed.**

For any non-trivial task (bug fix, feature, refactor, investigation, phase execution):

### 1. Before touching any code — Create ticket

```bash
curl -s -X POST http://localhost:8000/api/tickets \
  -H "Content-Type: application/json" \
  -d '{
    "title": "<[Type] Concise, professional title>",
    "problem": "<Deep technical overview of the root issue or feature requirement>",
    "solution": "<Proposed architectural or code-level changes needed to resolve it>",
    "acceptance_criteria": [
      "<Explicit testing bound 1>",
      "<Explicit testing bound 2>"
    ],
    "assignee": "5e77682c79f5ad0c34f09c9c",
    "type": "bug|feature|task",
    "priority": "low|medium|high|critical"
  }'
```

Save the returned `id` (e.g. `DEV-42`) as `TICKET_ID`. The API auto-assigns to the active sprint.

### 1.5. Sync Jira Branch (MANDATORY)

We use the Jira integrated "Create Branch" button in the Development panel.
Immediately after getting the `TICKET_ID` (or reading it from the task):
1. Ask the user: "Please click the 'Create branch' button in Jira for ticket `$TICKET_ID` and let me know the branch name when it's ready."
2. **STOP** and wait for the user to click the button and provide the branch name.
3. Once the user provides the branch name, fetch and checkout that exact branch from the remote:
```bash
git fetch origin
git checkout <exact-branch-name-from-jira>
```
**If backend is offline**, call Jira directly:
```bash
curl -s -u "$JIRA_EMAIL:$JIRA_API_TOKEN" \
  -X POST "https://ameer1996112.atlassian.net/rest/api/3/issue" \
  -H "Content-Type: application/json" \
  -d '{"fields":{"project":{"key":"DEV"},"summary":"<title>","issuetype":{"id":"10003"},"description":{"type":"doc","version":1,"content":[{"type":"paragraph","content":[{"type":"text","text":"<description>"}]}]}}}'
```

### 2. After completing work — Close ticket

```bash
curl -s -X POST "http://localhost:8000/api/tickets/$TICKET_ID/ai-update" \
  -H "Content-Type: application/json" \
  -d '{
    "new_status": "done",
    "summary_of_work": "<what was built/fixed, which files changed, how to verify>",
    "agent": "antigravity"
  }'
```

### Type mapping

| Situation | type |
|-----------|------|
| Bug fix / error / unexpected behavior | `bug` |
| New feature / UI / API endpoint | `feature` |
| Refactor / config / docs / cleanup | `task` |

### Skip ticket when
- Answering a question with no code changes
- Single-line typo fix
- User explicitly says "no ticket"

---

## Cursor Cloud specific instructions

### Architecture overview
This is an institutional liquidity-based algorithmic trading system with three main services:
- **Backend API** (FastAPI, port 8000): Receives TradingView webhook signals, validates them, pushes to Redis queue
- **Worker** (Python): Consumes signals from Redis, runs AI/ML guardrails, executes trades
- **Frontend** (Next.js, port 3000): Real-time trading dashboard with signal feed, risk monitoring, analytics

### Required infrastructure
- **Redis** must be running on `localhost:6379` before the backend API starts (it fail-fast checks Redis on startup). Start with `redis-server --daemonize yes`.

### Environment
- Python venv is at `/workspace/.venv` — activate with `source /workspace/.venv/bin/activate`
- Backend `.env` is at project root (`/workspace/.env`). Required vars: `SUPABASE_URL`, `REDIS_URL`. See `.env.example` for all options.
- Frontend uses `npm` (lockfile: `package-lock.json`). Node >=20.9 required.
- `PYTHONPATH=/workspace` must be set when running backend commands outside `start.sh`.

### Running services
- **Backend API**: `source .venv/bin/activate && PYTHONPATH=/workspace python3 -m uvicorn src.api:app --host 0.0.0.0 --port 8000`
- **Worker**: `source .venv/bin/activate && PYTHONPATH=/workspace python3 -m src.worker`
- **Frontend dev**: `cd frontend && npm run dev`
- **Full stack**: `./start.sh fullstack` (starts API + Worker + Frontend)

### Lint / Test / Build
- **Backend lint**: `ruff check src/ config/ tests/` (98 pre-existing warnings)
- **Backend tests**: `PYTHONPATH=/workspace pytest tests/ -v` (11 tests, all pass)
- **Frontend lint**: `cd frontend && npx eslint` (pre-existing warnings/errors)
- **Frontend tests**: `cd frontend && npx vitest run` (1 pre-existing failure in `tradingMetrics.test.ts`)
- **Frontend build**: `cd frontend && npm run build`

### Gotchas
- The `config/settings.py` uses `@lru_cache` for `get_settings()`. If you change `.env` values, the backend process must be restarted for changes to take effect.
- The Makefile references `docker-compose.test.yml` which does not exist in the repo. Use a local Redis server directly instead.
- AI/ML guardrails (`AI_FILTER_ENABLED`, `ML_GUARDIAN_ENABLED`, `TRINITY_ENABLED`) can be disabled in `.env` for local dev to avoid needing external API keys.
- The webhook endpoint at `POST /webhook` accepts JSON with fields: `symbol`, `side`, `entry`, `sl`, `tp`, `size`. A `WEBHOOK_SECRET` is only checked if set in `.env`.
