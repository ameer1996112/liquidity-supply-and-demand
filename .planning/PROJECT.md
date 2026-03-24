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

## Current Milestone: v1.1 Autonomous System Jira Upgrades
**Goal:** Upgrade the core Autonomous Workflow to support automatic Error-to-Bug Jira ticket creation from the Python worker and bi-directional PR transitions between GitHub and Atlassian.
**Target features:**
- Python global exception hooking into the Atlassian API.
- Native `autonomous-jira-cli.js` PR tagging.
- Jira automatic ticket transition execution.

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

- [ ] JIR-05: Global exception handler in Python worker catches critical runtime execution faults.
- [ ] JIR-06: Automatically format the exception trace/env into a Jira Bug payload.
- [ ] JIR-07: Create a High Priority Jira Bug via REST directly from Python.
- [ ] JIR-08: `autonomous-jira-cli.js` command for `sync-pr` (branch + PR URL).
- [ ] JIR-09: Post the GitHub PR link as a comment perfectly onto the Jira issue.
- [ ] JIR-10: Automatically handle ticket status transitions.

### Out of Scope

- Epic and Sub-task generation (Deferred to v1.2)
- Bi-directional webhook checkouts from Atlassian -> Github.

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
*Last updated: 2026-03-24 after v1.1 Autonomous Upgrades initialization*
