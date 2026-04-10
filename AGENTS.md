# AGENTS.md — Agent Entry Point

## 🚦 Before You Touch Code

1. **Read the module map:** `.planning/codebase/MODULE_MAP.md`
2. **Read conventions:** `.planning/codebase/CONVENTIONS.md`
3. **Check concerns:** `.planning/codebase/CONCERNS.md`
4. **Never scan the full repo.** Use MODULE_MAP to find the right files.
5. **Plan first.** Write your change plan before editing any source code.

---

## 🎫 Jira Auto-Ticket (MANDATORY)

For any non-trivial task (bug fix, feature, refactor):

### Before touching code — Create ticket
```bash
curl -s -u "$JIRA_EMAIL:$JIRA_API_TOKEN" \
  -X POST "https://ameer1996112.atlassian.net/rest/api/3/issue" \
  -H "Content-Type: application/json" \
  -d '{"fields":{"project":{"key":"DEV"},"summary":"<title>","issuetype":{"id":"10003"},"description":{"type":"doc","version":1,"content":[{"type":"paragraph","content":[{"type":"text","text":"<description>"}]}]}}}'
```

### After completing work — Close ticket
```bash
curl -s -X POST "http://localhost:8000/api/tickets/$TICKET_ID/ai-update" \
  -H "Content-Type: application/json" \
  -d '{"new_status":"done","summary_of_work":"<what changed>","agent":"antigravity"}'
```

### Type mapping
| Situation | type |
|-----------|------|
| Bug / error | `bug` |
| New feature / endpoint | `feature` |
| Refactor / docs / cleanup | `task` |

### Skip ticket when
- Answering a question with no code changes
- Single-line typo fix
- User says "no ticket"

---

## 🏗️ Codebase Reference

Read these documents **before** making changes. They are the single source of truth.

| Document | Purpose |
|----------|---------|
| `.planning/codebase/MODULE_MAP.md` | **Start here.** Which files belong to which module |
| `.planning/codebase/ARCHITECTURE.md` | System architecture, data flows, layer responsibilities |
| `.planning/codebase/STRUCTURE.md` | Directory layout, naming conventions, where to add code |
| `.planning/codebase/CONVENTIONS.md` | Coding rules (Python, TypeScript, Git, API contracts) |
| `.planning/codebase/CONCERNS.md` | Known bugs, TODOs, tech debt, security issues |
| `.planning/codebase/INTEGRATIONS.md` | External services, env vars, API keys |
| `.planning/codebase/STACK.md` | Dependencies, versions, runtime requirements |
| `.planning/codebase/TESTING.md` | Test patterns, fixtures, what to test |

---

## Stack (quick reference)

- **API**: FastAPI port 8000 — receives TradingView webhooks → Redis queue
- **Worker**: Python — consumes Redis, runs AI/ML guardrails, executes via MetaApi
- **Frontend**: Next.js port 3000 — Supabase realtime dashboard

---

## Environment

- Venv: `./venv` — `source ./venv/bin/activate`
- Config: `get_settings()` with `@lru_cache` — restart backend after `.env` changes
- `PYTHONPATH=.` required outside `start.sh`
- Redis must be running: `redis-server --daemonize yes`

---

## Run
```bash
# API
source ./venv/bin/activate && PYTHONPATH=. python3 -m uvicorn src.api:app --host 0.0.0.0 --port 8000
# Worker
source ./venv/bin/activate && PYTHONPATH=. python3 -m src.worker
# Frontend
cd frontend && npm run dev
# Full stack
./start.sh fullstack
```

## Lint / Test
```bash
ruff check src/ config/ tests/          # 98 pre-existing warnings — ignore
PYTHONPATH=. pytest tests/ -v           # 11 tests, all pass
cd frontend && npx vitest run           # 1 pre-existing failure in tradingMetrics.test.ts — ignore
cd frontend && npm run build
```

---

## Gotchas

- Makefile references `docker-compose.test.yml` — doesn't exist, use local Redis instead
- Disable guardrails locally: set `AI_FILTER_ENABLED=false`, `ML_GUARDIAN_ENABLED=false`, `TRINITY_ENABLED=false`
- Webhook `POST /webhook` fields: `symbol`, `side`, `entry`, `sl`, `tp`, `size`. `WEBHOOK_SECRET` only checked if set.

---

## Rules

- **Never change trading logic/strategies** unless explicitly asked — live system
- **Always async/await** for all I/O
- **Always type hints** on new functions
- **Always `get_settings()`** — never `os.environ` directly
- **Respect DDD layers** — logic in `/services`, not in `api.py`
- **Check `settings.paper_trading`** before any trade execution code
- **Branch format**: `feature/DEV-XX-description`
- **Commit format**: `DEV-XX: description`

---

## ⛔ Anti-Patterns (Do NOT Do These)

- **No blind `find .` or `grep -r` from root** — use MODULE_MAP to locate files
- **No reading >3 files before stating a plan** — plan first, read targeted
- **No changes to `src/logic.py` or `src/worker.py` trading paths** unless explicitly asked
- **No full-repo scans** — always scope to a module from MODULE_MAP
- **No creating new top-level directories** without explicit approval