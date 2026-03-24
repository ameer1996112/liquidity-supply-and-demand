# Milestone v1.2 Requirements

## Epic & Sub-Task Intelligence
- [ ] **JIR-11**: The `autonomous-jira-cli.js` script can accept a composite payload and automatically generate a parent Epic ticket.
- [ ] **JIR-12**: The CLI script can generate multiple Sub-task tickets and securely link them to the parent Epic via Atlassian's modern `parent` field architecture.

## Multi-Account Execution
- [ ] **EXEC-01**: Python `worker.py` dynamically parses a list of MetaAPI account tokens from configuration instead of routing to a single hardcoded account string.
- [ ] **EXEC-02**: Trading signals are routed almost simultaneously across all configured MetaAPI accounts without severe synchronous slippage.
- [ ] **EXEC-03**: Guardrails (Correlation, PropGuard) enforce limits securely per-account in Redis tracking spaces to avoid cross-account contamination.

## Discord Agent Alerts
- [ ] **NOTIF-01**: Python Worker pushes an embedded Discord message when it fires a Jira Bug via the Error-to-Ticket pipeline.
- [ ] **NOTIF-02**: Node.js CLI script pushes an embedded Discord message reporting when a GitHub PR is synced and a ticket transitions.

## Agentic View Dashboard
- [ ] **UI-01**: Next.js Trading Health frontend includes an "Agentic View" component tracking recent events from the Autonomous system.
- [ ] **UI-02**: Backend FastAPI exposes an `/api/agent/status` endpoint to serve the AI's current operational state (ticket creation events, PR syncs, exceptions) stored in Redis.

## Future Requirements
- Machine Learning driven take-profit variance execution.

## Out of Scope
- Telegram integration (Discord is the primary and singular destination for AI logs).
- Webhook endpoints to receive Jira updates locally.

## Traceability
| Req ID | Description | Phase | Plan | Status |
|---|---|---|---|---|
| JIR-11 | Generate Jira Epic natively | Phase 6 | 6-01 | Active |
| JIR-12 | Attach Sub-Tasks to Epic | Phase 6 | 6-02 | Active |
| EXEC-01 | Configure Multi-Account parsing | Phase 7 | 7-01 | Active |
| EXEC-02 | Execute simultaneous trade broadcasting | Phase 7 | 7-02 | Active |
| EXEC-03 | Localize Risk engines per account | Phase 7 | 7-03 | Active |
| NOTIF-01 | Discord broadcast on Python Crash | Phase 8 | 8-01 | Active |
| NOTIF-02 | Discord broadcast on PR Sync | Phase 8 | 8-02 | Active |
| UI-01 | Agentic View frontend components | Phase 9 | 9-01 | Active |
| UI-02 | FastAPI agent status endpoint | Phase 9 | 9-02 | Active |
