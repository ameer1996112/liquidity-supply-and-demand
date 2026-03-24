# Algorithmic Trading System & Autonomous Management

## What This Is

An algorithmic trading system executing on a 5-minute timeframe using Liquidity, Supply, and Demand concepts, currently being extended with an autonomous AI-driven project management layer. The AI layer acts as an Autonomous Project Manager and Lead Developer, heavily integrated with Jira and GitHub for ticket creation, branching, smart commits, and PRs.

## Core Value

End-to-end automation of both trading execution (Flip/Directional Close mechanics) and the development lifecycle (autonomous Jira issue creation, branch management, coding, and smart commits).

## Current State (v1.1)
Shipped v1.1 Autonomous System Jira Upgrades:
<details>
<summary>v1.0 MVP details</summary>

- Jira/GitHub autonomous CLI integration configured.
- Claude enforced autonomous workflow rules via CLAUDE.md.
- Python worker natively refactored to align exactly with 5-minute timeframes dynamically.
</details>

- Python global exception hooking into the Atlassian API successfully catches crash logs and builds tickets autonomously.
- Native `autonomous-jira-cli.js` PR tagging links Github reviews natively to the matching Jira ticket.
- Jira automatic ticket transition execution perfectly syncs Github development with Kanban board flow limits.

## Next Milestone Goals (v1.2)
- Planning next milestone...

## Requirements

### Validated

- ✓ Fast API backend — v1.0
- ✓ Next.js frontend — v1.0
- ✓ Docker and Next.js integrations — v1.0
- ✓ Basic Python worker structure — v1.0
- ✓ Jira/GitHub Integration Utility (Phase 1) — v1.0
- ✓ Autonomous Workflow Pipeline (Phase 2) — v1.0
- ✓ 5-minute timeframe trading logic refinement (Phase 3) — v1.0
- ✓ JIR-05: Global exception handler in Python worker catches critical runtime execution faults. — v1.1
- ✓ JIR-06: Automatically format the exception trace/env into a Jira Bug payload. — v1.1
- ✓ JIR-07: Create a High Priority Jira Bug via REST directly from Python. — v1.1
- ✓ JIR-08: `autonomous-jira-cli.js` command for `sync-pr` (branch + PR URL). — v1.1
- ✓ JIR-09: Post the GitHub PR link as a comment perfectly onto the Jira issue. — v1.1
- ✓ JIR-10: Automatically handle ticket status transitions. — v1.1

### Active
(Planning next milestone)

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
| Implement automated Error-to-Ticket integration | Reduce manual monitoring by converting runtime faults dynamically to dev actions | ✓ Good |
| Utilize native Javascript for Github -> Jira sync | Simplify local dev dependency load via pure REST queries and static string parsing | ✓ Good |

---
*Last updated: 2026-03-25 after v1.1 Milestone Completion*
