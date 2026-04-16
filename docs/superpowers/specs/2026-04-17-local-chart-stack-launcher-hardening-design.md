# DEV-125 Local Chart Stack Launcher Hardening Design

## Summary

Harden the local chart stack launcher so it no longer silently reuses arbitrary processes on `127.0.0.1:8765`. The launcher should only trust tracked provider and tunnel processes, validate the provider against the current chart-context contract including `setup_evidence`, expose a clean `--fresh` restart path, and fail clearly when unmanaged conflicts are present.

## Goals

- Keep the same one-command operator workflow:
  - `./scripts/run_local_chart_stack.sh`
  - `./scripts/stop_local_chart_stack.sh`
- Make provider reuse safe instead of optimistic.
- Detect stale provider versions that still answer on `8765` but do not return `setup_evidence`.
- Distinguish tracked, healthy processes from unmanaged listeners.
- Add a clean restart path with `--fresh`.
- Improve operator-facing status and error messages.

## Non-Goals

- No `launchd` or background service migration in this slice.
- No automatic killing of unrelated unmanaged processes.
- No Railway deployment changes.
- No automatic dashboard config mutation.
- No TradingView shutdown behavior changes.

## Existing Context

The current scripts already:

1. verify TradingView CDP on `127.0.0.1:9222`
2. start the local provider on `127.0.0.1:8765`
3. start `cloudflared`
4. write tunnel metadata to `.runtime/chart-stack/state.env`

The weak point is the trust model:

- if anything responds on `127.0.0.1:8765`, the launcher reuses it
- that can mean:
  - an older provider process
  - a manually-started debug process
  - a stale process the launcher does not own

This causes confusing behavior where the stack looks healthy, but the provider response does not match the current UI/backend contract.

## Proposed System Shape

Keep the two-script structure:

- `scripts/run_local_chart_stack.sh`
- `scripts/stop_local_chart_stack.sh`

But harden `run_local_chart_stack.sh` with:

- tracked-process reuse only
- provider contract validation
- explicit conflict detection
- `--fresh` restart mode

The stop script remains intentionally conservative:

- stop only tracked provider/tunnel PIDs
- leave TradingView running

## Trust Model

### Provider reuse

The launcher may reuse a provider only if all of the following are true:

1. `provider.pid` exists
2. the PID is still alive
3. the provider health check succeeds
4. the provider response contains the expected current contract, including:
   - `provider_timestamp`
   - `zones`
   - `pine_labels`
   - `indicator_values`
   - `setup_evidence`

If any of those checks fail, the provider must not be considered safely reusable.

### Tunnel reuse

The launcher may reuse a tunnel only if:

1. `cloudflared.pid` exists
2. the PID is still alive
3. a `trycloudflare.com` URL can still be extracted from the tracked log

### Unmanaged processes

If something is listening on `127.0.0.1:8765` but the launcher does not own it through `provider.pid`, that listener is a conflict, not reusable state.

The launcher should fail with a clear message instead of silently continuing.

## Provider Health States

The launcher should classify provider state into four cases.

### `healthy`

- tracked provider PID exists
- PID is alive
- health check passes
- response includes the full expected contract including `setup_evidence`

Behavior:

- reuse the provider

### `stale`

- tracked provider PID exists
- PID is alive
- provider responds
- response is missing `setup_evidence` or otherwise does not satisfy the current contract

Behavior:

- fail with a message telling the operator to rerun with `--fresh`

### `conflict`

- port `8765` is occupied
- but there is no live tracked provider PID for that listener

Behavior:

- fail with a message showing that an unmanaged process is occupying the port

### `down`

- no provider is listening
- or tracked PID is gone and port is unused

Behavior:

- start a fresh provider

## `--fresh` Mode

Add explicit support for:

```bash
./scripts/run_local_chart_stack.sh --fresh
```

Behavior:

1. stop tracked `cloudflared`
2. stop tracked provider
3. remove stale PID/state files
4. leave TradingView running
5. start provider cleanly
6. start tunnel cleanly

It should not:

- kill unrelated unmanaged processes
- stop TradingView
- change dashboard config

This gives operators a reliable clean-restart path without making default launcher behavior destructive.

## Runtime State

Keep using:

- `.runtime/chart-stack/provider.pid`
- `.runtime/chart-stack/cloudflared.pid`
- `.runtime/chart-stack/provider.log`
- `.runtime/chart-stack/cloudflared.log`
- `.runtime/chart-stack/state.env`

No new runtime directory structure is needed in this slice.

## Health Check Contract

The provider health check should go beyond “port is open”.

Recommended probe:

- `GET /chart-context?symbol=VANTAGE:AUDUSD&timeframe=5m`

The response should be considered current only if it contains:

- `provider_timestamp`
- `zones`
- `pine_labels`
- `indicator_values`
- `setup_evidence`

For the new evidence workflow, `setup_evidence` is the differentiator between:

- current provider
- old but still reachable provider

The launcher does not need to require `setup_evidence.status == "ok"` for reuse. It only needs to require that:

- `setup_evidence` exists as an object
- the provider speaks the current contract

This allows degraded screenshot capture while still recognizing the provider as current.

## Operator Messaging

The launcher should print clearer status lines such as:

- `provider healthy, reusing tracked process`
- `provider stale: missing setup_evidence; rerun with --fresh`
- `provider conflict on 8765: unmanaged PID 12345`
- `provider down, starting tracked process`
- `tunnel healthy, reusing tracked process`
- `--fresh requested, restarting tracked provider and tunnel`

The goal is to make failures self-explanatory without forcing the operator to inspect logs first.

## Error Handling

The launcher should fail clearly when:

- `cloudflared` is missing
- project venv Python is missing
- TradingView CDP is unavailable and cannot be started
- unmanaged process conflict exists on `8765`
- tracked provider is stale
- tracked tunnel exists but no URL can be recovered

Failure output should include:

- which subsystem failed
- whether it was `healthy`, `stale`, `conflict`, or `down`
- the relevant PID or port when available
- the log path when that helps

## First Implementation Slice

Build:

- tracked-provider-only reuse
- tracked-tunnel-only reuse
- contract-aware provider health check including `setup_evidence`
- unmanaged conflict detection on `8765`
- `--fresh` handling
- clearer operator messages

Do not build yet:

- `--status`
- `launchd`
- automatic config injection into the app
- unmanaged process auto-kill behavior

## Recommendation

Keep the existing script-based workflow, but harden the launcher’s trust model. Only reuse processes the launcher owns, validate the provider against the current evidence-aware contract, and add `--fresh` as the explicit clean-restart path. This gives you a more reliable day-to-day workflow without making the script overly magical or destructive.
