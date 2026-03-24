# Milestone v1.1 Requirements

## Automated Error-to-Ticket Pipeline
- [x] **JIR-05**: Global exception handler in Python worker catches critical runtime execution faults (e.g., Live Order Failures, MetaAPI drops).
- [x] **JIR-06**: System automatically formats the exception trace and environment context into a Jira Bug Ticket payload.
- [x] **JIR-07**: System automatically creates a "High Priority" Bug traversing the Jira REST API directly from the Python backend.

## Two-Way GitHub / Jira Sync
- [x] **JIR-08**: `autonomous-jira-cli.js` supports a new `sync-pr` command that takes a branch name and a PR URL.
- [x] **JIR-09**: The script automatically posts the GitHub PR link as a comment exactly on the corresponding Jira issue.
- [x] **JIR-10**: The script transitions the corresponding Jira ticket status from "In Progress" to "In Review" or "Done" based on PR state.

## Future Requirements
- Epic & Sub-task Architecture (AI automatically breaking down large tasks into 3+ linked tickets).
- Webhook endpoints to receive Jira updates and auto-checkout branches locally.

## Traceability
| Req ID | Phase | Plan | Status |
|---|---|---|---|
| JIR-05 | Phase 4 | 4-01 | Active |
| JIR-06 | Phase 4 | 4-01 | Active |
| JIR-07 | Phase 4 | 4-01 | Active |
| JIR-08 | Phase 5 | 5-01 | Active |
| JIR-09 | Phase 5 | 5-01 | Active |
| JIR-10 | Phase 5 | 5-01 | Active |
