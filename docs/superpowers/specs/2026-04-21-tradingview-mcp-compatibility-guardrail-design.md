# DEV-185 TradingView MCP Compatibility Guardrail Design

## Summary

Design a compatibility guardrail around the local TradingView Desktop MCP integration so chart-dependent bot features only run when the installed TradingView version is known-good and the MCP commands we rely on still work. When compatibility is unknown or broken, the bot should degrade chart context safely instead of failing unpredictably.

## Goals

- Detect the local TradingView Desktop version before using the MCP bridge.
- Maintain a small allowlist of approved TradingView Desktop versions.
- Run a lightweight MCP smoke test using the commands the backend depends on.
- Cache compatibility results so chart-context requests do not repeatedly probe the desktop app.
- Disable only chart-context enrichment when compatibility fails.
- Preserve the existing graceful degradation path for the AI operating layer and any consumers of `/chart-context`.

## Non-Goals

- No redesign of screenshot capture or setup-evidence cropping in this change.
- No change to live trading logic, trade execution, or worker routing.
- No automatic upgrading or downgrading of TradingView Desktop.
- No attempt to make the MCP work across every future TradingView release without verification.
- No replacement of the current local TradingView Desktop MCP provider.

## Existing Context

The current chart-context path is:

1. `src/local_chart_provider_service.py` shells into the vendored `mcp/tradingview-mcp` CLI.
2. The provider wrapper runs MCP commands such as `status`, `values`, `data lines`, `data labels`, `data boxes`, and `screenshot`.
3. `src/local_chart_provider_app.py` exposes the normalized result over `/chart-context`.
4. `src/adapters/tradingview_chart_provider.py` fetches that payload over HTTP.
5. `src/services/ai_operating_layer.py` normalizes the response and already tolerates degraded chart context.

This means MCP failure is currently survivable, but it is reactive. A TradingView Desktop update can still silently turn a previously working setup into a degraded or partially broken one until runtime discovers it.

## Problem Statement

The project depends on a local MCP bridge that reads TradingView Desktop state through CDP and TradingView-specific UI behavior. When TradingView Desktop updates, that bridge can break even if the core bot remains healthy. Today there is no explicit compatibility policy, no approved-version gate, and no single health status that says whether chart-context enrichment is safe to use.

## Recommended Approach

Use `allowlist + smoke test`.

The compatibility layer should require both:

- the local TradingView Desktop version is on a known-good allowlist
- a lightweight MCP smoke test succeeds

If either check fails, chart-context enrichment is disabled and the provider returns an explicit degraded response. The bot keeps running, but chart-aware features do not pretend to be healthy.

This is preferred over `smoke test only` because version drift becomes explicit, and it is preferred over `allowlist only` because an approved version can still fail due to environment or MCP regressions.

## Proposed System Shape

Add one small compatibility service in front of the current MCP command runner.

Suggested unit:

- `TradingViewMcpCompatibilityService`

Suggested responsibilities:

- detect the installed TradingView Desktop version
- compare it against a configured allowlist
- execute a minimal MCP probe
- cache the result for a short TTL
- expose a structured status to the local provider service

The local provider service should consult this compatibility status before running the full chart-context command sequence.

## Compatibility Status Model

The compatibility layer should return a structured payload with a small finite set of states:

- `supported`
- `unsupported_version`
- `probe_failed`
- `tradingview_not_found`
- `mcp_unavailable`

Recommended fields:

```json
{
  "status": "supported",
  "chart_context_enabled": true,
  "tradingview_version": "2.9.0",
  "checked_at": "2026-04-21T10:12:00Z",
  "reason": "",
  "probe": {
    "command": "status",
    "ok": true
  }
}
```

Notes:

- `chart_context_enabled` is the single boolean consumers can reason about quickly.
- `reason` should be human-readable and safe to surface in logs and the UI.
- `checked_at` is useful for troubleshooting stale health state.

## Version Detection

The service should detect the installed TradingView Desktop version from the local machine, not infer it from MCP behavior.

On macOS, the preferred source is the TradingView app bundle metadata. The implementation should isolate version lookup in one function so it can be swapped later if deployment changes.

If TradingView Desktop cannot be found:

- return `tradingview_not_found`
- disable chart context
- do not run the full MCP sequence

## Version Policy

Store approved TradingView Desktop versions in configuration rather than hard-coding them deep in provider logic.

Recommended configuration shape:

- `TRADINGVIEW_ALLOWED_VERSIONS`
- comma-separated exact versions

Example:

```env
TRADINGVIEW_ALLOWED_VERSIONS=2.9.0,2.9.1
```

Behavior:

- exact match only for the first rollout
- unknown version returns `unsupported_version`
- operators bless a new version only after running the smoke test manually and confirming MCP behavior

Exact matching is intentionally conservative. It keeps operations simple and avoids false confidence from loose semver ranges.

## Smoke Test Design

The probe should be lightweight and aligned with the real dependency surface.

Recommended first rollout:

1. run MCP `status`
2. require valid JSON and `success: true`
3. require `chart_symbol` and `chart_resolution` to be present

Why this scope:

- it is the cheapest command we already rely on
- it fails early if TradingView, CDP, or the MCP bridge is broken
- it is sufficient for a first compatibility gate without adding more desktop load

Later, the probe can expand to include one additional read such as `values` if needed, but the first rollout should stay minimal.

## Request Flow

For each chart-context request:

1. local provider receives `/chart-context`
2. provider asks the compatibility service for current status
3. compatibility service returns cached status when still fresh
4. when stale, compatibility service:
   - detects TradingView Desktop version
   - checks allowlist
   - runs the MCP smoke test
   - stores the result with a TTL
5. if compatibility is `supported`, the provider runs the normal MCP command sequence
6. if compatibility is not supported, the provider skips the full sequence and returns a degraded payload immediately

This makes upgrade breakage cheap to detect and cheap to avoid.

## Failure Handling

### `unsupported_version`

- cause: TradingView Desktop updated to a version not yet blessed
- behavior: disable chart context and return degraded payload
- operator action: verify the new version with the smoke test, then add it to the allowlist

### `probe_failed`

- cause: TradingView Desktop, CDP, or MCP behavior changed enough that `status` no longer works
- behavior: disable chart context and log the probe error
- operator action: inspect MCP logs, verify TradingView version, patch MCP or revert TradingView version

### `tradingview_not_found`

- cause: TradingView Desktop is not installed or app path changed
- behavior: disable chart context immediately

### `mcp_unavailable`

- cause: vendored MCP repo or runtime command path is missing or broken
- behavior: disable chart context immediately

In all failure cases, the provider should continue returning HTTP `200` with degraded payloads so existing consumers keep working with clear reasons.

## Integration Points

Primary change points:

- `src/local_chart_provider_service.py`
  - add compatibility check ahead of the full MCP command sequence
  - reuse existing degraded payload behavior
- `config/settings.py`
  - add allowed-version and cache TTL configuration
- new compatibility service module
  - own version lookup, allowlist check, probe execution, and status caching

No changes should be made to live execution paths such as `src/logic.py` or `src/worker.py`.

## Caching

Compatibility checks should be cached for a short TTL to avoid probing on every request.

Recommended first value:

- 60 seconds

Behavior:

- within TTL: reuse the last status
- after TTL: refresh on the next request
- do not background-refresh in the first rollout

This keeps implementation simple and operationally predictable.

## Logging And Observability

Each refresh of compatibility status should log:

- detected TradingView version
- resulting status
- chart-context enabled/disabled
- failure reason, when present

This should be enough for operators to understand whether they are on a known-good desktop version and why chart context is degraded.

## Testing

### Unit tests

- version policy accepts exact known-good versions
- unknown version returns `unsupported_version`
- failed probe returns `probe_failed`
- missing TradingView path returns `tradingview_not_found`
- cached status is reused within TTL
- degraded provider payload includes the compatibility reason

### Manual smoke test

Add or document one operator command that verifies:

- installed TradingView Desktop version
- MCP `status` success
- final compatibility verdict

This command becomes the approval step before a new TradingView version is added to the allowlist.

## Operational Workflow

When TradingView Desktop updates:

1. chart-context requests begin returning `unsupported_version`
2. core bot behavior remains intact
3. operator runs the manual compatibility check
4. if probe succeeds and behavior looks correct, the new version is added to the allowlist
5. chart context resumes on the next compatibility refresh

This turns upgrades into a controlled operational decision instead of a surprise runtime event.

## Rollout Plan

Phase 1:

- add compatibility service
- add config values
- gate the existing local provider flow
- add unit tests

Phase 2:

- add a simple operator-facing health command or endpoint
- document the bless-new-version workflow

## Risks And Trade-Offs

- Exact allowlists create some operator overhead when TradingView updates.
- A minimal smoke test can miss deeper issues in commands beyond `status`.
- Returning degraded payloads keeps the system stable, but it can hide severity unless logs are watched.

These are acceptable for the first rollout because the primary goal is safe containment, not perfect predictive validation.

## Success Criteria

- TradingView Desktop updates no longer silently affect chart-context behavior.
- Unknown desktop versions are detected before the full MCP flow runs.
- Broken MCP behavior disables only chart-context enrichment, not the core bot.
- Operators have a clear path to bless and re-enable a new TradingView version.
