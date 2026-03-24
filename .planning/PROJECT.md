# Algorithmic Trading System & Autonomous Management

## What This Is

An algorithmic trading system executing on a 5-minute timeframe using Liquidity, Supply, and Demand concepts, currently being extended with an autonomous AI-driven project management layer. The AI layer acts as an Autonomous Project Manager and Lead Developer, heavily integrated with Jira and GitHub for ticket creation, branching, smart commits, and PRs.

## Core Value

End-to-end automation of both trading execution (Flip/Directional Close mechanics) and the development lifecycle (autonomous Jira issue creation, branch management, coding, and smart commits).

## Current State (v1.0)
Shipped v1.0 MVP:
- Jira/GitHub autonomous CLI integration configured.
- Claude enforced autonomous workflow rules via CLAUDE.md.
- Python worker natively refactored to align exactly with 5-minute timeframes dynamically.

## Current Milestone: v1.1 Hosted Jira Frontend Integration
**Goal:** Build a live Kanban board inside the Next.js frontend that syncs directly with the Atlassian Jira cloud API, avoiding the need for a local ticket database.
**Target features:**
- Next.js proxy endpoints for Jira API calls to avoid CORS issues.
- Kanban UI component in the dashboard.
- Live fetching of active Sprints and Epics.
- Drag and drop status updates syncing directly back to Hosted Jira.

## Requirements

### Validated (v1.0)

- ✓ Fast API backend
- ✓ Next.js frontend
- ✓ Docker and Next.js integrations
- ✓ Basic Python worker structure
- ✓ Jira/GitHub Integration Utility (Phase 1)
- ✓ Autonomous Workflow Pipeline (Phase 2)
- ✓ 5-minute timeframe trading logic refinement (Phase 3)

### Active (v1.1)

- [ ] JIR-01: Dedicated Jira dashboard page in the Next.js frontend.
- [ ] JIR-02: Auto-fetch active Sprints and Tasks directly from Hosted Jira API.
- [ ] JIR-03: Display tasks in a Kanban board layout (To Do, In Progress, Done).
- [ ] JIR-04: Drag and drop Kanban tickets to instantly update Atlassian Jira status.

### Out of Scope

- Local Supabase database tables for Jira Tickets (Relying purely on Hosted Jira API as the source of truth).

## Context

- **Domain**: Algorithmic trading system.
- **Jira Workspace**: https://ameer1996112.atlassian.net/
- **Primary User/Assignee**: Ameer

## Constraints

- **Process**: Must strictly follow the defined workflow (Sprint -> Ticket -> Branch -> Execute -> PR) for every task.
- **Environment**: Requires `.env` configuration with `JIRA_API_TOKEN`, `JIRA_EMAIL`, `JIRA_DOMAIN`, and `GITHUB_TOKEN`.

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Implement custom local Jira script | Enhance autonomous agent capabilities to manage sprints/epics/tasks. | ✓ Good |
| Enforce rules via CLAUDE.md | Stop agents from breaking the Jira -> Code -> Commit loop. | ✓ Good |
| Use Modulo 5 logic in Worker | Dynamically enforce 5m boundaries over static evaluation arrays. | ✓ Good |

---
*Last updated: 2026-03-24 after v1.1 initialization*
