---
wave: 1
depends_on: []
files_modified:
  - scripts/autonomous-jira-cli.js
autonomous: true
---

# Plan 1: Implement Jira and GitHub Integrations

## Objective
Finalize the `autonomous-jira-cli.js` script to seamlessly handle Sprints, feature branches, and Pull Requests via GitHub CLI and Jira API.

## Tasks

<task>
<id>1-01-01</id>
<title>Expand Jira API Utility Functions</title>
<read_first>
- scripts/autonomous-jira-cli.js
- .planning/PROJECT.md
</read_first>
<action>
Modify `scripts/autonomous-jira-cli.js`:
Add async methods for `getActiveSprint()`, `createSprint()`, `assignIssueToSprint(issueKey, sprintId)`, and `transitionIssue(issueKey, statusId)`.
Implement GitHub CLI wrapping via `child_process.execSync` to create branches (`git checkout -b feature/[ISSUE-KEY]-desc`) and Pull Requests (`gh pr create --title "[ISSUE-KEY] feat: ..." --body "Automated PR"`).
Update the CLI routing to accept commands: `start-feature <title> <desc> <type>`, `finish-feature <issue-key> <summary>`.
</action>
<acceptance_criteria>
- `scripts/autonomous-jira-cli.js` contains `function getActiveSprint`
- `scripts/autonomous-jira-cli.js` contains `execSync('git checkout -b`
- `scripts/autonomous-jira-cli.js` contains `execSync('gh pr create`
- Running `node scripts/autonomous-jira-cli.js` outputs usage instructions including the new commands.
</acceptance_criteria>
</task>

## Verification
- Run `node scripts/autonomous-jira-cli.js` and verify it exits 0 without syntax errors.

## Must Haves
- The script must support automated branch creation and Jira Sprint assignment.
