# Phase 8: Discord Alerts Hub — Context

**Gathered:** 2026-03-25
**Status:** Ready for planning

<domain>
## Phase Boundary
Attach Discord notification calls to two key agent lifecycle events: when the Python worker creates a Jira bug ticket (error-to-ticket pipeline), and when the Node.js CLI syncs a GitHub PR to Jira (finish-feature / sync-pr command).
</domain>

<decisions>
## Implementation Decisions

### Discord Notification Points
- NOTIF-01: Post embed to DISCORD_WEBHOOK_URL on successful Jira bug creation in jira.py — fires asynchronously via send_bug_alert_async()
- NOTIF-02: Post embed in sync-pr and finish-feature CLI commands via notifyDiscord() utility

### Claude's Discretion
All implementation details delegated to Claude — infrastructure phase using existing discord adapter.
</decisions>

<code_context>
## Existing Code Insights

### Reusable Assets
- `src/adapters/discord.py`: `send_bug_alert_async(title, description, jira_key)` — background Discord embed
- `scripts/autonomous-jira-cli.js`: `notifyDiscord(title, color, description)` — inline webhook POST

### Integration Points
- `src/adapters/jira.py` `create_bug_ticket()` → calls `send_bug_alert_async()` after Jira API success
- `scripts/autonomous-jira-cli.js` `sync-pr` → calls `notifyDiscord()` with PR + ticket URL
</code_context>

<specifics>
## Specific Ideas
No additional requirements — infrastructure phase wiring existing capabilities.
</specifics>

<deferred>
## Deferred Ideas
None — discussion stayed within phase scope
</deferred>
