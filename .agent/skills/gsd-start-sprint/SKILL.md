---
name: gsd-start-sprint
description: Create and start a new Jira sprint natively so tickets don't get stuck in the backlog.
---

<objective>
Automates the creation of a new Jira sprint directly from the terminal via the AI-Driven Jira API proxy.
</objective>

<execution_context>
@.agent/get-shit-done/workflows/start-sprint.md
</execution_context>

<context>
Arguments: $ARGUMENTS (optional sprint name)
</context>

<process>
Execute the start-sprint workflow from @.agent/get-shit-done/workflows/start-sprint.md.
</process>
