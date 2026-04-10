---
name: trading-reconcile
description: Reconcile signal state, execution state, broker truth, frontend status, and persistence for trading-system bugs.
argument-hint: [trade id / signal id / symbol / time]
allowed-tools: Read, Edit, Write, Grep, Glob, Bash(pytest *), Bash(python *), Bash(git diff *), Bash(curl *)
---

# Trading Reconcile

Investigate: $ARGUMENTS

## Compare these layers

- strategy signal generated
- order request prepared
- risk checks passed/blocked
- execution request sent
- broker/meta layer accepted or rejected
- persisted DB state
- websocket/polling update
- frontend rendered state

## Board integration

If a real bug is confirmed during reconciliation, open a ticket immediately:
```bash
curl -s -X POST http://localhost:3000/api/board/create-ticket \
  -H "Content-Type: application/json" \
  -d '{"type":"bug","title":"<symbol/id>: <mismatch description>","component":"<MT5 / Broker|Python Backend|Supabase / DB>","priority":"<critical|high>","status":"in_progress","agent_name":"Claude Agent"}'
```
Close it when the fix is applied:
```bash
curl -s -X POST http://localhost:3000/api/board/agent-update \
  -H "Content-Type: application/json" \
  -d '{"ticket_id":"<BUG-id>","new_status":"done","message":"<fix summary>","agent_name":"Claude Agent"}'
```

## Return

- source of truth
- first layer that diverged
- exact state mismatch
- minimal safe fix
- logs or instrumentation to add

## Rules

- Broker/execution truth beats frontend assumptions.
- Frontend must not display active trades unless execution is confirmed.
- Distinguish:
  - signal exists
  - order requested
  - order accepted
  - order filled
  - position active
  - position closed
