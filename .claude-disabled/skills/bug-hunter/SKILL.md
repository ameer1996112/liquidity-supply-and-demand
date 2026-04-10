---
name: bug-hunter
description: Reproduce, isolate, fix, and harden a bug with a minimal patch and regression protection.
argument-hint: [bug description]
allowed-tools: Read, Edit, Write, Grep, Glob, Bash(pytest *), Bash(python *), Bash(npm test *), Bash(pnpm test *), Bash(yarn test *), Bash(git diff *), Bash(curl *)
---

# Bug Hunter

Investigate: $ARGUMENTS

## Required workflow

1. **Open a board ticket** immediately (before touching code):
   ```bash
   curl -s -X POST http://localhost:3000/api/board/create-ticket \
     -H "Content-Type: application/json" \
     -d '{"type":"bug","title":"<short title from $ARGUMENTS>","component":"<best match>","priority":"<critical|high|medium|low>","status":"in_progress","description":"<what is known so far>","agent_name":"Claude Agent"}'
   ```
   Note the returned `ticket_id` (e.g. BUG-015) — use it in all follow-up updates.

2. Reproduce or infer the failure path.
3. Identify the first exact point of divergence.
4. Decide whether the bug is caused by:
   - logic
   - state
   - data mapping
   - timing
   - UI rendering
   - backend contract mismatch
5. Post a progress update once root cause is confirmed:
   ```bash
   curl -s -X POST http://localhost:3000/api/board/agent-update \
     -H "Content-Type: application/json" \
     -d '{"ticket_id":"<BUG-id>","message":"Root cause: <one line>. Starting fix.","agent_name":"Claude Agent"}'
   ```
6. Make the smallest safe patch.
7. Add or update regression coverage.
8. **Close the board ticket** when fix is verified:
   ```bash
   curl -s -X POST http://localhost:3000/api/board/agent-update \
     -H "Content-Type: application/json" \
     -d '{"ticket_id":"<BUG-id>","new_status":"done","message":"Fixed: <one line summary>","agent_name":"Claude Agent"}'
   ```
9. Update docs/bugs.md with:
   - summary
   - root cause
   - fix
   - regression risk

## Hard rule

Do not stop at symptoms.
Find the actual blocking condition or incorrect state transition.

## Board component map

| Area | Component value |
|---|---|
| Pine Script / TradingView | `Pine Script` |
| Python backend, worker, risk | `Python Backend` |
| Supabase, DB, migrations | `Supabase / DB` |
| React frontend | `Frontend (React)` |
| MetaAPI, MT5, broker | `MT5 / Broker` |
| ML models, AI ensemble | `AI / ML Pipeline` |
| Redis, Railway, infra | `Infrastructure` |
