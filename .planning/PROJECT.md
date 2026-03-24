# Algorithmic Trading System & Autonomous Management

## What This Is

An algorithmic trading system executing on a 5-minute timeframe using Liquidity, Supply, and Demand concepts, currently being extended with an autonomous AI-driven project management layer. The AI layer acts as an Autonomous Project Manager and Lead Developer, heavily integrated with Jira and GitHub for ticket creation, branching, smart commits, and PRs.

## Core Value

End-to-end automation of both trading execution (Flip/Directional Close mechanics) and the development lifecycle (autonomous Jira issue creation, branch management, coding, and smart commits).

## Requirements

### Validated

- ✓ Fast API backend
- ✓ Next.js frontend
- ✓ Docker and Next.js integrations
- ✓ Basic Python worker structure

### Active

- [ ] Jira/GitHub Integration Utility (Phase 1): Local Node.js or Python script connecting to Jira REST API and GitHub CLI.
- [ ] Autonomous Workflow Pipeline (Phase 2): Automatic translation of feature prompts into Jira tickets, branch creation, execution, and smart-commit driven PR generation.
- [ ] 5-minute timeframe trading logic refinement using Supply/Demand architecture.

### Out of Scope

- [N/A at this stage]

## Context

- **Domain**: Algorithmic trading system.
- **Jira Workspace**: https://ameer1996112.atlassian.net/
- **Primary User/Assignee**: Ameer
- **Workflow**: Extremely strict adherence to Jira -> Ticket -> Branch -> Code -> Smart Commit -> PR flow.

## Constraints

- **Process**: Must strictly follow the defined workflow (Sprint -> Ticket -> Branch -> Execute -> PR) for every task.
- **Environment**: Requires `.env` configuration with `JIRA_API_TOKEN`, `JIRA_EMAIL`, `JIRA_DOMAIN`, and `GITHUB_TOKEN`.

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Implement custom local Jira script | Enhance autonomous agent capabilities to manage sprints/epics/tasks. | — Pending |

---
*Last updated: 2026-03-24 after initialization*
