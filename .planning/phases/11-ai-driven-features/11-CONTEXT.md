# Phase 11: AI-Driven Features — Context

**Gathered:** 2026-03-24

<decisions>
## Decisions

### Auto-Suggest
- 300ms debounce on title onChange
- Keyword word-map: bug/error/crash/fix/broken → bug; feat/add/new/build/implement → feature; else → task
- Priority: crash/critical/urgent → critical; important/high → high; else → medium
- Inline chip suggestion below title: click to accept, selects remain editable

### AI Activity Feed
- Below Kanban board, collapsible glow-card: "Recent AI Activity"
- Last 5 entries aggregated from all ticket ai_changelogs at page load
- Format: [agent] updated [DEV-XX] old→new + relative time
- Empty state: bouncing Bot icon + "No AI activity yet"

### Bot Indicator
- Pre-existing on TicketCard (Bot icon when ai_changelog.length > 0) — just verify
</decisions>
