# REQUIREMENTS.md — System Reliability & Trading Intelligence (v1.1)

## v1.1 Requirements

### Infra — Backend Persistence
- [ ] **INFRA-01**: Backend API survives terminal close and auto-restarts on crash (launchd plist or pm2)
- [ ] **INFRA-02**: Redis is verified running before API starts; backend logs a clear error if Redis is down
- [ ] **INFRA-03**: Backend logs persist to a file (`/tmp/tradeops-api.log` or equivalent)
- [ ] **INFRA-04**: A single command starts the full stack (API + Worker + Frontend) persistently

### Analytics — Signal Performance
- [ ] **ANALYTICS-01**: Analytics page shows per-symbol win rate, avg risk/reward, and total closed trades
- [ ] **ANALYTICS-02**: Slippage is tracked per signal (entry price vs actual fill) and shown in analytics
- [ ] **ANALYTICS-03**: Signal P&L by strategy/side (long vs short) is visualized as a chart or table

### Analytics — Prop Firm Tracker
- [ ] **PROP-01**: Dashboard shows FTMO challenge phase (Phase 1 / Phase 2 / Funded) with progress
- [ ] **PROP-02**: Daily drawdown remaining is displayed prominently (current DD vs max allowed)
- [ ] **PROP-03**: Weekly profit target progress is shown (current vs required % for phase completion)

### Sprint — Auto-Lifecycle & Velocity
- [ ] **SPRINT-01**: When all tickets in active sprint are "done", sprint auto-closes and a new sprint is created
- [ ] **SPRINT-02**: Sprint velocity chart shows tickets closed per sprint over last 5 sprints
- [ ] **SPRINT-03**: Burndown chart in analytics updates in real-time as tickets close

### UI — Trading Health Widget
- [ ] **HEALTH-01**: Sidebar or dashboard shows live open positions count, unrealised P&L, and account equity
- [ ] **HEALTH-02**: Widget shows today's closed trades count and realised P&L
- [ ] **HEALTH-03**: Widget displays signal pipeline status (worker running / waiting / stopped)

---

## Future Requirements (deferred)

- Discord → Jira bridge (ML drift/watchdog → ticket via Discord webhook)
- AI trade review auto-generation after signal closes
- Smart alert deduplication / ML incident grouping
- Multi-account portfolio view

---

## Out of Scope

- Replacing the main `frontend/` dashboard — PM Command Center lives in `jira/` only
- New broker integrations
- Mobile app

---

## Traceability

| REQ-ID | Description | Phase |
|--------|-------------|-------|
| INFRA-01–04 | Backend persistence | TBD |
| ANALYTICS-01–03 | Signal analytics | TBD |
| PROP-01–03 | Prop firm tracker | TBD |
| SPRINT-01–03 | Sprint auto-lifecycle | TBD |
| HEALTH-01–03 | Trading health widget | TBD |
