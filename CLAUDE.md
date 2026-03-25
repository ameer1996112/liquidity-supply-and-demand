# Project Instructions

## Jira Automation Rules (MANDATORY)

Every piece of work — feature, bug fix, investigation, or refactor — MUST be tracked in Jira at `https://ameer1996112.atlassian.net`.

### Methodology: Scrum
- **Epics** = Milestones (v1.0, v1.1, v1.2)
- **Stories** = Features / GSD Phases
- **Tasks** = Dev work items, sub-tasks
- **Bugs** = Auto-created from exceptions (via `src/adapters/jira.py`)
- **Sprints** = 2-week cycles aligned to milestones

---

### Starting any work (feature / bug / task)

**Step 1 — Create ticket + branch:**
```bash
node scripts/jira-sync.js "<description>"           # Task
node scripts/jira-sync.js --bug "<description>"     # Bug
```

Or for full workflow (create + branch + sprint assign):
```bash
node scripts/autonomous-jira-cli.js start-feature "<title>" "<desc>" "Task"
```

**Step 2 — Track progress during work:**
```bash
node scripts/jira-agent.js add-progress <DEV-XX> "<what you just did>"
```

**Step 3 — Finish work:**
```bash
node scripts/autonomous-jira-cli.js finish-feature "<DEV-XX>" "<summary>"
```
This creates the PR, adds a Jira Smart Commit, and transitions the ticket to Done.

---

### During multi-step implementation

After each significant step (file created, bug isolated, test passing), add a progress comment:
```bash
node scripts/jira-agent.js add-progress <DEV-XX> "<step completed>"
```

Transition the ticket status as work evolves:
```bash
node scripts/jira-agent.js set-status <DEV-XX> "In Progress"
node scripts/jira-agent.js set-status <DEV-XX> "In Review"
node scripts/jira-agent.js set-status <DEV-XX> "Done"
```

---

### Auto-detection

The hooks in `.claude/settings.json` automatically:
- **On every prompt (`UserPromptSubmit`)**: Detect ticket from current git branch → set In Progress → add user's request as comment
- **On Claude stop (`Stop`)**: Add Claude's response summary as a completion comment

This means Jira stays updated on every single interaction automatically when on a `feature/DEV-XX-*` branch.

---

### Ticket key from current branch

```bash
node scripts/jira-agent.js branch-ticket
# outputs: DEV-38
```

---

### Creating a ticket mid-work (if needed)

```bash
node scripts/jira-agent.js smart-create "<description>" [Task|Bug|Story]
```

---

### Sprint management

```bash
# Start new sprint
.agent/get-shit-done/bin/gsd-jira-hook.sh sprint_start "Sprint 5" "Build trading improvements" "2026-04-06"

# End current sprint
.agent/get-shit-done/bin/gsd-jira-hook.sh sprint_end

# Check active sprint
.agent/get-shit-done/bin/gsd-jira-hook.sh sprint_status

# Sync GSD phases to Jira Epics
.agent/get-shit-done/bin/gsd-jira-hook.sh sync_epics
```

---

### Smart Commit format (git commit messages)

```
feat: [DEV-42] Add 5-minute liquidity check #time 2h
fix: [DEV-38] Resolve MetaAPI disconnect retry backoff #time 1h
```

Jira's Smart Commit integration automatically:
- Links the commit to the ticket
- Logs the time
- Can transition the ticket (`#transition Done`)

---

## Non-negotiable enforcement

- Never start coding without a Jira ticket.
- The ticket number must appear in every git commit message.
- Add a progress comment at every meaningful step.
- Mark tickets Done when the PR is merged.
