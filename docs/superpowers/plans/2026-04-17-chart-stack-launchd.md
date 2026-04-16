# Chart Stack LaunchAgent Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a repo-managed macOS LaunchAgent setup that keeps the local chart stack running after login with sleep prevention and simple lifecycle commands.

**Architecture:** Preserve the current chart stack bootstrap script and wrap it with a `caffeinate` runner plus a small supervision loop. Install a templated LaunchAgent into the user session with a management script that handles install, start, stop, status, and uninstall.

**Tech Stack:** Bash, macOS `launchctl`, macOS `caffeinate`, LaunchAgent plist templates

---

### Task 1: Add repo-managed background runner assets

**Files:**
- Create: `scripts/run_chart_stack_background.sh`
- Create: `scripts/manage_chart_stack_launch_agent.sh`
- Create: `support/launchd/com.ameer.trading.chart-stack.plist.template`

- [ ] Add the wrapper script that `cd`s to the repo root, runs `/usr/bin/caffeinate`, bootstraps with `--fresh`, and periodically re-runs the existing launcher to keep the process alive and self-heal provider/tunnel state.
- [ ] Add the management script that renders the plist template into `~/Library/LaunchAgents`, then supports `install`, `start`, `stop`, `restart`, `status`, and `uninstall`.
- [ ] Add the plist template with placeholders for the wrapper path and log file paths.

### Task 2: Verify the local management flow

**Files:**
- Modify: `scripts/run_chart_stack_background.sh`
- Modify: `scripts/manage_chart_stack_launch_agent.sh`

- [ ] Run `bash -n scripts/run_chart_stack_background.sh scripts/manage_chart_stack_launch_agent.sh` and fix any shell syntax issues.
- [ ] Run `./scripts/manage_chart_stack_launch_agent.sh status` to confirm the script can report state before installation.
- [ ] Run `./scripts/manage_chart_stack_launch_agent.sh install` and confirm the LaunchAgent file is created and loaded.
- [ ] Run `./scripts/manage_chart_stack_launch_agent.sh stop` and `./scripts/manage_chart_stack_launch_agent.sh start` to confirm the lifecycle commands work.

### Task 3: Close out docs and operator notes

**Files:**
- Modify: `docs/superpowers/specs/2026-04-17-chart-stack-launchd-design.md`
- Modify: `docs/superpowers/plans/2026-04-17-chart-stack-launchd.md`

- [ ] Confirm the spec and plan still match the final implementation.
- [ ] Tell the user where logs live and which command to use for install/start/stop/status.
