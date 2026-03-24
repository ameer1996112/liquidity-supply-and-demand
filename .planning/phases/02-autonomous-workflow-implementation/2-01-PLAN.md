---
wave: 1
depends_on: []
files_modified:
  - CLAUDE.md
autonomous: true
---

# Plan 1: Enforce Autonomous Workflow

## Objective
Finalize the integration of the autonomous Jira workflow by creating or updating `CLAUDE.md` to instruct all executing AI agents to use the workflow.

## Tasks

<task>
<id>2-01-01</id>
<title>Update Agent Prompt Instructions</title>
<read_first>
- .planning/PROJECT.md
</read_first>
<action>
Create or append to `CLAUDE.md` at the root of the project.
Add a mandatory instruction block titled `# Autonomous Workflow Enforcement`.
In this block, instruct the agent: "Whenever executing a new feature, bug report, or raw idea, before writing any code you MUST strictly execute `node scripts/autonomous-jira-cli.js start-feature \"<title>\" \"<desc>\" \"<type>\"` to spin up a ticket and branch implicitly. Upon completion, you MUST execute `node scripts/autonomous-jira-cli.js finish-feature \"<issue-key>\" \"<summary>\"` to create the PR and Jira Smart Commits."
</action>
<acceptance_criteria>
- `CLAUDE.md` exists.
- `CLAUDE.md` contains the exact string `scripts/autonomous-jira-cli.js start-feature`
- `CLAUDE.md` contains the exact string `scripts/autonomous-jira-cli.js finish-feature`
</acceptance_criteria>
</task>

## Verification
- Run `cat CLAUDE.md | grep "scripts/autonomous-jira-cli.js"` to ensure the workflow instructions are present.

## Must Haves
- Instructions must clearly mandate the use of the CLI script for all feature executions natively within the agent's context.
