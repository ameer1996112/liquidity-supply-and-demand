---
created: 2026-03-24T14:23:08.843Z
title: Auto-assign Jira tickets and map to sprints
area: planning
ticket_id: ""
files:
  - src/api_tickets.py
---

## Problem

The user wants to upgrade the Jira ticket creation process so that tickets are automatically assigned to their email/account. Additionally, they asked for a development process that maps tasks to a single active sprint to keep work focused.

## Solution

1. Update the Jira proxy (`src/api_tickets.py`) ticket creation payload to lookup and assign the user's Jira Account ID (using the user email from `.env`).
2. Document the "Single Sprint Mapping" development process and enforce it. The process should involve creating a sprint with `POST /api/tickets/sprints/start`, and moving all development tasks to that sprint during auto-creation.
3. Update GSD ticket creation hooks (e.g. `gsd-add-todo`, `update-ticket`) as needed to adopt these workflows.
