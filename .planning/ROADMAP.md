# ROADMAP.md — System Reliability & Trading Intelligence

**Milestone:** System Reliability & Trading Intelligence (v1.1)
**Total phases:** 4 (phases 5–8)
**Requirements covered:** INFRA-01–04, ANALYTICS-01–03, PROP-01–03, SPRINT-01–03, HEALTH-01–03 (16/16)

---

## Phase 5: Backend Persistence

**Goal:** Make the backend API self-sustaining — it runs as a managed service, auto-restarts on crash, and never requires manual terminal intervention.

**Requirements:** INFRA-01, INFRA-02, INFRA-03, INFRA-04

**Plans:**
1. macOS launchd plist — create `com.tradeops.api.plist` + `com.tradeops.worker.plist` in `~/Library/LaunchAgents/` with `RunAtLoad: true`, `KeepAlive: true`; generate via a `install-services.sh` script
2. Redis pre-check + log persistence — add Redis liveness check before API starts; route all API + Worker logs to `~/.tradeops/logs/api.log` / `worker.log` with rotation
3. One-command full-stack start — update `start.sh fullstack` to be idempotent (check if port 8000 is already occupied, use launchctl if installed, fall back to background process)

**Success criteria:**
1. Closing the terminal does not stop the API — `curl http://localhost:8000/health` returns healthy after terminal close
2. If the API crashes, it restarts within 5 seconds automatically
3. Starting with `./start.sh fullstack` twice in a row shows "already running" instead of starting a duplicate
4. All logs are written to `~/.tradeops/logs/` with timestamps

---

## Phase 6: Signal & Prop Analytics

**Goal:** Surface trading intelligence — per-symbol win rates, risk/reward, and prop firm challenge progress — in the `jira/` analytics page.

**Requirements:** ANALYTICS-01, ANALYTICS-02, ANALYTICS-03, PROP-01, PROP-02, PROP-03

**Plans:**
1. Signal analytics backend — add `GET /api/analytics/signals` endpoint aggregating closed signals from Supabase: win rate, avg RR, slippage, grouped by symbol and side
2. Prop firm tracker backend — add `GET /api/analytics/prop-firm` reading FTMO config from `.env` (`PROP_DAILY_DD_LIMIT`, `PROP_PROFIT_TARGET`, `PROP_PHASE`) and live account data from MetaAPI cache
3. Analytics page upgrade — add signal performance table (win rate / avg RR / slippage per symbol) and prop firm progress section (phase badge, daily DD bar, profit target bar) to the existing `/analytics` page

**Success criteria:**
1. Analytics page shows a table with win %, avg RR, and slippage for each symbol with closed trades
2. Long vs short breakdown chart is visible on the analytics page
3. Prop firm section shows phase (Phase 1 / Phase 2 / Funded), today's DD remaining as a progress bar, and weekly profit target progress
4. Data updates within 60 seconds of a trade closing without page refresh

---

## Phase 7: Sprint Lifecycle Automation

**Goal:** The sprint workflow is self-managing — when all tickets close, the sprint auto-closes and a new one starts; velocity and burndown charts give real-time insight into team pace.

**Requirements:** SPRINT-01, SPRINT-02, SPRINT-03

**Plans:**
1. Sprint auto-close hook — add a background check in `api_tickets.py` (triggered on every ticket status update to "done") that counts open tickets in the active sprint; if zero remain, calls `end_sprint()` and `start_sprint()` with an auto-generated name
2. Velocity chart — add `GET /api/analytics/sprint-velocity` returning tickets closed per sprint for last 5 sprints; render as bar chart in analytics page
3. Live burndown — update the `/analytics` burndown chart to use real sprint ticket data (open vs closed over time); poll every 30s

**Success criteria:**
1. Closing the last open ticket in a sprint triggers auto-close and a new sprint is created without any manual action
2. Velocity chart shows bars for the last 5 sprints with ticket counts
3. Burndown chart shows a downward slope as tickets close during the sprint
4. Sprint auto-naming uses a sequential pattern (`Sprint N` or date-based)

---

## Phase 8: Trading Health Widget

**Goal:** Add a live trading system health widget to the `jira/` sidebar that shows open positions, unrealised P&L, account equity, and worker pipeline status at a glance.

**Requirements:** HEALTH-01, HEALTH-02, HEALTH-03

**Plans:**
1. Health API endpoint — add `GET /api/health/trading` combining: MetaAPI cached account info (equity, balance), open positions count + unrealised P&L, today's closed trades + realised P&L, and worker/Redis status
2. Health widget component — create `TradingHealthWidget.tsx` in `jira/src/components/` with live polling (30s interval): equity chip, today P&L chip (green/red), open positions count, pipeline status indicator
3. Sidebar integration — embed `TradingHealthWidget` below the nav links in `Sidebar.tsx`; collapse to icon-only on narrow viewports

**Success criteria:**
1. Sidebar shows current account equity, today's realised P&L, and open positions count without navigating away from any page
2. Values update every 30 seconds — no manual refresh needed
3. Worker pipeline status shows "running" / "waiting" / "stopped" with a colored dot
4. Widget degrades gracefully when backend is down — shows "Offline" state, not broken layout

---

## Requirement Coverage

| REQ-ID | Description | Phase |
|--------|-------------|-------|
| INFRA-01 | Backend survives terminal close | 5 |
| INFRA-02 | Redis pre-check on startup | 5 |
| INFRA-03 | Logs persist to file | 5 |
| INFRA-04 | Single command full-stack start | 5 |
| ANALYTICS-01 | Signal win rate, RR, slippage per symbol | 6 |
| ANALYTICS-02 | Slippage tracking per signal | 6 |
| ANALYTICS-03 | P&L by strategy/side chart | 6 |
| PROP-01 | FTMO phase progress display | 6 |
| PROP-02 | Daily drawdown remaining | 6 |
| PROP-03 | Weekly profit target progress | 6 |
| SPRINT-01 | Auto-close + new sprint when all tickets done | 7 |
| SPRINT-02 | Velocity chart (last 5 sprints) | 7 |
| SPRINT-03 | Live burndown chart | 7 |
| HEALTH-01 | Live open positions + unrealised P&L | 8 |
| HEALTH-02 | Today closed trades + realised P&L | 8 |
| HEALTH-03 | Worker pipeline status indicator | 8 |
