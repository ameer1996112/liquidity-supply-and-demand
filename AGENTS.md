# AGENTS.md — Agent Entry Point

## ⛔ STOP — Read This Before Any File

Before touching **any** file or tool, you MUST state out loud:

1. **Which module** from MODULE_MAP covers this task
2. **Which 1-3 files** you will read (by name)
3. **What you expect to find** in each

If you cannot answer all three → read `.planning/codebase/MODULE_MAP.md` first. Nothing else.

**Never do this:**
- `find .` or `ls` from root
- Read more than 3 files before stating a plan
- Open files "just to understand the codebase"

---

## 🔧 Mandatory Tools

| Task | Tool to use |
|------|-------------|
| Read a file | `Read` — use `limit` + `offset` for large files (never read >200 lines blind) |
| Find files by name/pattern | `Glob` — faster than Bash find |
| Search code content | `Grep` — use `output_mode: files_with_matches` first, then `content` |
| Explore unfamiliar area | `Agent` with subagent_type `Explore` |
| Library/framework docs | context7 `resolve-library-id` + `get-library-docs` |

---

## 🗺️ Where to Start

| I need to… | Read this first |
|------------|----------------|
| Find which files to touch | `.planning/codebase/MODULE_MAP.md` |
| Understand data flow | `.planning/codebase/ARCHITECTURE.md` |
| Know coding rules | `.planning/codebase/CONVENTIONS.md` |
| See known bugs / TODOs | `.planning/codebase/CONCERNS.md` |
| Find env vars / API keys | `.planning/codebase/INTEGRATIONS.md` |
| Check dependencies | `.planning/codebase/STACK.md` |
| Write tests | `.planning/codebase/TESTING.md` |

**Read these only if relevant to your task. Never read all of them upfront.**

---

## 🎫 Jira Auto-Ticket (MANDATORY)

For any non-trivial task (bug fix, feature, refactor):

### Before touching code — Create ticket (recommended)
```bash
# Reads Jira creds from the repo `.env` (no need to export JIRA_* manually)
node scripts/jira/jira-sync.js --no-branch "<title>"
```

### Alternate — Create ticket via curl (requires exported env vars)
```bash
set -a; source .env; set +a  # export JIRA_* from .env into your shell
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

### Skip ticket when
- Answering a question with no code changes
- Single-line typo fix
- User says "no ticket"

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
