# Institutional Liquidity Trading System + PM Command Center

## What This Is

An institutional-grade algorithmic trading system that receives TradingView webhook signals, validates them through a multi-layer AI/ML guardrail pipeline, and executes trades on MetaTrader 5 via MetaAPI. The system runs three services: a FastAPI backend (port 8000), a Redis-driven worker, and a Next.js dashboard (port 3000). A standalone Jira-like project management app (`jira/`) is being evolved into a full AI-powered PM Command Center.

## Core Value

**Every significant event in the trading system — signal, bug, phase, test failure — is tracked as actionable work without any manual intervention.**

## Requirements

### Validated

- ✓ TradingView webhook ingestion (`POST /webhook`) with optional secret auth — existing
- ✓ Redis queue signal transport (BLPOP worker loop) — existing
- ✓ Multi-layer AI/ML guardrail pipeline (AI Guardian, ML Guardian, Trinity Engine, Pine Guardian) — existing
- ✓ MetaAPI broker execution (DRY_RUN / PAPER / LIVE modes) — existing
- ✓ Supabase PostgreSQL persistence + realtime frontend updates — existing
- ✓ Discord + Telegram trade notifications — existing
- ✓ FastAPI REST API with 25+ modular router modules — existing
- ✓ Next.js trading dashboard with positions, analytics, risk, backtest pages — existing
- ✓ Standalone `jira/` app with Supabase-backed ticket board (Linear dark theme) — existing
- ✓ Jira REST API proxy (`api_tickets.py`) forwarding to real Jira — existing
- ✓ GSD workflow system (gsd-autonomous, gsd-plan-phase, gsd-execute-phase) — existing
- ✓ `update-ticket` skill for manual ticket syncing — existing
- ✓ Prop firm evaluation tracking (FTMO phase 1/2/funded) — existing
- ✓ Multi-account routing via `BROKER_PROFILES_JSON` — existing
- ✓ TCA (Transaction Cost Analysis) engine — existing
- ✓ Breakeven + trailing stop managers — existing

### Active

**Milestone: AI-Powered PM Command Center**

#### GSD ↔ Jira Full Automation (Layer 1)
- [ ] Every GSD phase start automatically creates a Jira ticket (no manual `update-ticket` calls)
- [ ] Every GSD plan execution updates the corresponding Jira ticket status in real-time
- [ ] Phase completion auto-closes Jira tickets with summary notes
- [ ] GSD roadmap phases are reflected as Jira epics automatically

#### Trading System Events → Tickets (Layer 2)
- [ ] Worker pipeline errors auto-create P1/P2 Jira tickets
- [ ] Test failures in CI auto-generate bug tickets with stack traces
- [ ] ML Guardian confidence degradation triggers a "model drift" ticket
- [ ] Late fills / watchdog alerts auto-create operational tickets

#### Full PM Dashboard UI in `jira/` app (Layer 3 — UI)
- [ ] Smart Kanban board — tickets auto-populate from GSD phases + trading events, drag-and-drop
- [ ] AI Command Center panel — natural language ticket creation ("fix the MetaAPI rate limiting issue")
- [ ] Sprint board with velocity charts and burndown
- [ ] Roadmap timeline view (phases from GSD ROADMAP.md visualized as timeline)
- [ ] AI-driven backlog grooming (suggests priority based on system health + PnL)
- [ ] Real-time activity feed — shows all automation events as they happen
- [ ] Trading system health widget embedded in PM dashboard
- [ ] Rich text editor for ticket descriptions + comments
- [ ] Labels, epics, assignees, story points

### Out of Scope

- Replacing the main `frontend/` dashboard — PM command center lives in `jira/` standalone app only
- Building a new broker integration — MetaAPI is the only broker adapter
- Public multi-tenant SaaS — single-user / single-team only
- Mobile app — desktop-first

## Context

- **Existing Jira app**: `jira/` is a Next.js 14 standalone app with Tailwind CSS, Supabase direct connection, and a `project_tickets` table. It has a Linear-inspired dark theme.
- **Jira REST API proxy**: `src/api_tickets.py` (22KB) proxies to real Jira via REST v3. Config: `JIRA_BASE_URL`, `JIRA_API_TOKEN`, `JIRA_USER_EMAIL`, `JIRA_PROJECT_KEY`.
- **`update-ticket` skill** is manually invoked — the gap is zero-friction automatic invocation from every GSD workflow event.
- **GSD system**: `.agent/get-shit-done/` contains all workflow orchestration logic in `.cjs` tools + markdown skill files.
- **Key codebase concerns** (from CONCERNS.md): god files in `worker.py` (85KB), no CI, `@lru_cache` settings gotcha, Redis fail-fast without graceful degradation.

## Constraints

- **Tech stack**: `jira/` uses Next.js 14 + Tailwind CSS + Supabase. Must stay on this stack.
- **Database**: Supabase (`project_tickets` table + migrations). No new database.
- **Jira API**: Real Jira REST v3 is the source of truth. Local Supabase is the mirror/cache.
- **GSD compatibility**: Automation hooks must not break existing GSD workflow commands.
- **No breaking changes**: Existing trading system services must continue to work unchanged.

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Upgrade `jira/` app (not `frontend/`) | Already has standalone Next.js 14, Supabase connection, dark theme board | — Pending |
| All 3 layers in one milestone | User wants maximum automation + UI in one coherent upgrade | — Pending |
| GSD hooks via skill middleware | `update-ticket` skill wraps GSD commands — least invasive integration point | — Pending |
| Supabase as event store for trading→ticket bridge | Worker already writes to Supabase; DB triggers can fire ticket creation | — Pending |

---
*Last updated: 2026-03-23 after project initialization (brownfield, existing codebase mapped)*
