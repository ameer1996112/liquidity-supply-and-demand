---
phase: "02"
name: "GSD ↔ Jira Full Automation"
status: complete
requirements-completed:
  - PM-01
  - PM-02
  - PM-03
  - PM-04
---

# Phase 02: GSD ↔ Jira Full Automation — Summary

**Completed:** 2026-03-23
**Status:** Complete ✅

## What Was Built

### Endpoints Added to `src/api_tickets.py`

**`POST /api/tickets/gsd-sync`** — Unified GSD lifecycle event handler:
- `phase_start` → Creates Jira ticket (or finds existing idempotently), transitions to In Progress
- `plan_execute` → Posts a comment noting plan execution is in progress
- `phase_complete` → Transitions to Done with structured summary comment
- `phase_skip` → Transitions to Done with skip note

**`POST /api/tickets/gsd-sync-epics`** — Batch endpoint for syncing ROADMAP.md phases as Jira tickets with `gsd` + `epic` labels on project initialization.

### `.agent/get-shit-done/bin/gsd-jira-hook.sh`
Shell script that wraps Jira sync calls from within GSD commands:
- `gsd-jira-hook.sh phase_start <num> <name> [goal]`
- `gsd-jira-hook.sh plan_execute <num> <name> <ticket_id> [summary]`
- `gsd-jira-hook.sh phase_complete <num> <name> <ticket_id> [summary]`
- `gsd-jira-hook.sh phase_skip <num> <name> <ticket_id>`
- `gsd-jira-hook.sh sync_epics [roadmap_file]`

Fails silently if API unavailable — never blocks GSD execution. Called by `gsd-autonomous` (which already inlined the curl calls) and can be invoked from any GSD skill.

### Note on `gsd-autonomous` Integration
The `gsd-autonomous` workflow already contains inline Jira curl calls at phase start/end. The new `gsd-jira-hook.sh` + endpoints provide the infrastructure for **`gsd-plan-phase`**, **`gsd-discuss-phase`**, and other commands that currently have no Jira integration.

## Files Modified/Created
- `src/api_tickets.py` — added GsdSyncRequest model + 2 new endpoints
- `.agent/get-shit-done/bin/gsd-jira-hook.sh` — new shell hook script

## Verification
✅ Python AST validation passed for `api_tickets.py`
