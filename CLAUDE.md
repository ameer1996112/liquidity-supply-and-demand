# Project Instructions

## Autonomous Workflow Enforcement

Whenever executing a new feature, bug report, or raw idea, before writing any code you **MUST strictly execute**:

```bash
node scripts/autonomous-jira-cli.js start-feature "<title>" "<desc>" "<type>"
```

to spin up a ticket and branch implicitly. 

Upon completion of the implementation, you **MUST execute**:

```bash
node scripts/autonomous-jira-cli.js finish-feature "<issue-key>" "<summary>"
```

to create the Pull Request and generate Jira Smart Commits back.

**Strict Output Requirements:**
- All executions must enforce this process natively without manual bypass.
