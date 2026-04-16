# DEV-123 Local Chart Stack Launcher Design

## Summary

Design a small pair of local runtime scripts that manage the chart-aware AI sidecar stack from one command. The launcher should start TradingView with CDP, the local MCP-backed provider, and the Cloudflare tunnel, while writing logs and PIDs into a single runtime directory. A matching stop script should stop the local provider and tunnel cleanly without shutting down TradingView by default.

## Goals

- Reduce the current multi-terminal setup into one organized command.
- Reuse the already-working local components:
  - TradingView Desktop with CDP
  - `src.local_chart_provider_app`
  - `cloudflared`
- Keep all runtime state in one predictable local folder.
- Make the tunnel URL easy to discover and copy into the app UI.
- Keep the first version foreground-oriented and easy to debug.

## Non-Goals

- No `launchd` or background macOS service management in v1.
- No Railway deployment changes.
- No automatic writing back into app settings or environment variables.
- No support for Windows or Linux in v1.
- No auto-install of `cloudflared` or TradingView Desktop.

## Existing Context

The local chart stack already works, but only through manual orchestration:

1. launch TradingView in debug mode
2. start the local provider with `uvicorn`
3. start `cloudflared`
4. manually copy the tunnel URL into the dashboard

This works functionally, but it is noisy, repetitive, and easy to misconfigure.

## Proposed System Shape

Add two scripts under `scripts/`:

- `run_local_chart_stack.sh`
- `stop_local_chart_stack.sh`

These scripts should manage only the local chart sidecar stack, not the main backend, worker, or frontend.

## Runtime Folder

Create one runtime directory:

- `.runtime/chart-stack/`

Store:

- `provider.pid`
- `cloudflared.pid`
- `provider.log`
- `cloudflared.log`
- `state.env` or equivalent small metadata file

This keeps the feature isolated and avoids cluttering `/tmp` or user home directories.

## Launcher Responsibilities

### `run_local_chart_stack.sh`

The launcher should:

1. ensure it is running from the project root
2. create `.runtime/chart-stack/`
3. verify local prerequisites
4. start or verify TradingView CDP
5. start or verify the local provider on `127.0.0.1:8765`
6. start or verify `cloudflared` against `http://127.0.0.1:8765`
7. extract and print the public tunnel URL
8. print a concise summary of:
   - CDP status
   - local provider URL
   - public tunnel URL
   - log file locations

### CDP behavior

- if `http://127.0.0.1:9222/json/version` already responds, do not relaunch TradingView
- otherwise, call the existing macOS launcher:
  - `mcp/tradingview-mcp/scripts/launch_tv_debug_mac.sh`

### Provider behavior

- if `http://127.0.0.1:8765/chart-context?...` already responds, do not start a duplicate provider
- otherwise, launch:

```bash
PYTHONPATH=. python3 -m uvicorn src.local_chart_provider_app:app --host 127.0.0.1 --port 8765
```

### Tunnel behavior

- if an existing `cloudflared` process started by this launcher is alive, reuse it
- otherwise, launch:

```bash
cloudflared tunnel --url http://127.0.0.1:8765
```

- parse the `trycloudflare.com` URL from `cloudflared.log`

## Stop Script Responsibilities

### `stop_local_chart_stack.sh`

The stop script should:

- read PID files from `.runtime/chart-stack/`
- stop `cloudflared` if running
- stop the provider if running
- remove stale PID files
- leave TradingView Desktop running by default

This behavior matches the likely operator workflow: restarting the sidecar stack should not force the chart app itself to close.

## Error Handling

The launcher should fail clearly when:

- `cloudflared` is not installed
- TradingView cannot be launched and CDP is still unavailable
- the provider fails to bind `127.0.0.1:8765`
- the tunnel never produces a public URL

When failing, it should print:

- which stage failed
- which log file to inspect
- the relevant local URL or port

## Logging

Logs should be split by process:

- `provider.log`
- `cloudflared.log`

The launcher itself can print human-readable status lines to stdout.

## Output Format

The launcher’s terminal summary should be short and copy-friendly. Recommended output:

```text
[chart-stack] CDP:        http://127.0.0.1:9222
[chart-stack] Provider:   http://127.0.0.1:8765
[chart-stack] Tunnel:     https://example.trycloudflare.com
[chart-stack] Logs:       .runtime/chart-stack/
```

## Safety Rules

- use `127.0.0.1`, not `localhost`, to avoid IPv6 loopback issues
- never kill unrelated global `cloudflared` or provider processes that were not started by this launcher
- do not stop TradingView in v1 unless a later explicit flag is added
- do not modify main app config automatically

## First Implementation Slice

Build:

- one launcher script
- one stop script
- runtime folder + PID/log management
- TradingView CDP verification/reuse
- provider verification/reuse
- tunnel verification/reuse
- tunnel URL extraction and printed summary

Do not build yet:

- `launchd` integration
- automatic tunnel URL injection into the app
- persistent named Cloudflare tunnels
- cross-platform behavior

## Recommendation

Start with a small shell-based foreground launcher. It matches the repo’s current operational style, reduces manual terminal management immediately, and keeps the runtime transparent while the chart-aware AI workflow is still being validated.
