# Chart Stack LaunchAgent Design

**Goal:** Keep the local TradingView chart stack available after login with automatic restart and sleep prevention on macOS.

## Approach

Keep `scripts/run_local_chart_stack.sh --fresh` as the only stack bootstrapper. Add a thin wrapper script that runs it under `caffeinate`, performs the initial bootstrap, then stays alive in a small supervision loop that periodically re-runs the launcher to self-heal provider and tunnel state. Manage that wrapper with a user `launchd` LaunchAgent so it starts on login and restarts if it exits.

## Components

- `scripts/run_chart_stack_background.sh`
  Runs the existing chart stack entrypoint under `/usr/bin/caffeinate -dims`, then keeps the process alive with periodic health rechecks.
- `scripts/manage_chart_stack_launch_agent.sh`
  Installs, loads, unloads, starts, stops, and removes the LaunchAgent in `~/Library/LaunchAgents`.
- `support/launchd/com.ameer.trading.chart-stack.plist.template`
  Checked-in plist template with placeholders filled in by the management script.

## Behavior

- Start at user login.
- Restart automatically if the wrapper exits.
- Keep the Mac awake while the wrapper is active.
- Re-check the chart stack on a timer and reuse the existing launcher for recovery.
- Write stdout and stderr logs to `~/Library/Logs/trading-chart-stack/`.
- Leave the tracked provider and tunnel lifecycle to the existing stack scripts.

## Non-Goals

- Moving TradingView Desktop or CDP to the cloud.
- Changing trading logic, provider contract logic, or tunnel behavior.
- Managing a system-wide daemon outside the logged-in user session.
