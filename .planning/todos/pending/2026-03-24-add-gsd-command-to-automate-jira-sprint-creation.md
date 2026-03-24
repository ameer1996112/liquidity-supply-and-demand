---
created: 2026-03-24T15:06:56.210Z
title: Add GSD command to automate Jira sprint creation
area: planning
ticket_id: "DEV-22"
files:
  - src/api_tickets.py
  - .agent/skills/gsd-start-sprint/SKILL.md
---

## Problem

Currently, if the Jira board has no active sprint, the GSD workflow and Jira API proxy place all new tickets directly into the **Backlog**. Because the active board view only shows tickets assigned to an active sprint, users are forced to go into the Jira UI manually to create a sprint and drag tickets in before development can continue properly.

## Solution

Build a new `gsd-start-sprint` workflow (or integrate it into `gsd-add-phase`) that:
1. Calls the `POST /api/tickets/sprints/start` endpoint exposed by the backend to natively create a sprint.
2. Prompts the user or autonomously decides to start a sprint if it detects that no sprint is active.
3. Automatically maps any new `gsd-add-todo` tasks to this new sprint so they appear on the board instantly.
