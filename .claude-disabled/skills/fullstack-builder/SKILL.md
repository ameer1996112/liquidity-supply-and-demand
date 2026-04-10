---
name: fullstack-builder
description: Build or upgrade a feature across frontend, backend, state, contracts, tests, and docs in a production-grade way.
argument-hint: [feature or task]
allowed-tools: Read, Edit, Write, Grep, Glob, Bash(npm *), Bash(pnpm *), Bash(yarn *), Bash(pytest *), Bash(python *), Bash(git diff *), Bash(curl *)
---

# Fullstack Builder

Implement: $ARGUMENTS

## Goal

Deliver a professional end-to-end feature, not a partial patch.

## Required workflow

1. Inspect relevant frontend, backend, shared types, data flow, and tests.
2. Write a short implementation plan before changing code.
3. Identify:
   - UI components affected
   - API routes / services affected
   - schemas / types affected
   - state/cache effects
   - loading/error/empty states
4. **Open a board TASK ticket** before writing code:
   ```bash
   curl -s -X POST http://localhost:3000/api/board/create-ticket \
     -H "Content-Type: application/json" \
     -d '{"type":"task","title":"<feature name>","component":"<component>","priority":"medium","status":"in_progress","agent_name":"Claude Agent"}'
   ```
5. Implement the smallest coherent complete solution.
6. Add or update:
   - frontend validation
   - backend validation
   - types/contracts
   - tests
   - docs/worklog.md
7. **Close the board ticket** when done:
   ```bash
   curl -s -X POST http://localhost:3000/api/board/agent-update \
     -H "Content-Type: application/json" \
     -d '{"ticket_id":"<TASK-id>","new_status":"done","message":"Feature complete: <one line>","agent_name":"Claude Agent"}'
   ```
8. End with:
   - files changed
   - contract changes
   - test status
   - known follow-ups

## Quality bar

- No half-finished UI states
- No backend/frontend mismatch
- No hidden breaking changes
- No orphan logic
