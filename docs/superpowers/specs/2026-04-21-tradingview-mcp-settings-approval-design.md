# DEV-188 TradingView MCP Settings Approval Design

## Summary

Move TradingView MCP version approval out of environment variables and into the app’s settings flow. The backend should store the approved TradingView Desktop versions, the local chart provider should continue to detect the actual local machine state, and the settings page should join both sources so operators can verify and approve the current local version with a simple UI flow.

## Goals

- Remove the need to manage approved TradingView versions through `.env`.
- Store approved TradingView Desktop versions in app-managed settings.
- Keep TradingView version detection local to the machine running TradingView Desktop and the local MCP provider.
- Reuse the existing local provider compatibility endpoint as the source of local truth.
- Let operators approve the current local TradingView version from the settings page after a passing local compatibility check.
- Preserve the existing compatibility guardrail behavior so unsupported or broken local setups still degrade safely.

## Non-Goals

- No redesign of screenshot capture or setup-evidence UX in this change.
- No change to live trading logic, worker execution, or trade gating.
- No attempt to make the main backend infer desktop state for local TradingView installations.
- No browser-local-only approval storage.
- No multi-machine synchronization beyond the backend’s normal settings store.

## Existing Context

The current compatibility guardrail already provides:

1. local TradingView Desktop version detection on the machine running the local provider
2. MCP `status` probe validation
3. a local compatibility endpoint at `GET /health/compatibility`
4. fail-closed version approval driven by `TRADINGVIEW_ALLOWED_VERSIONS` from settings/env

This is operationally safe but user-hostile. Operators still need to edit `.env` to bless a new TradingView version, even though this is exactly the kind of state that belongs in a settings workflow.

The project also already has:

- `src/api_config.py` for operator-controlled system settings
- a backend settings page that consumes those config endpoints
- a local chart provider process on `127.0.0.1:8765`

That makes this a settings-integration problem rather than a new compatibility-engine problem.

## Problem Statement

TradingView MCP compatibility is local-machine-specific, but the approval mechanism is still environment-config-driven. That creates three practical issues:

- approving a new version requires editing `.env`
- the settings page cannot show or manage the approved versions cleanly
- approval state and local machine reality are split across tools instead of one operator workflow

We want approval to happen from the settings page while keeping the source of truth honest:

- backend stores approval policy
- local provider reports actual local machine state

## Recommended Approach

Use `backend-stored approvals + local provider verification`.

That means:

- backend stores the approved version list in the existing system config store
- local chart provider continues to own version detection and local MCP probing
- settings page fetches both and combines them into one operator workflow

This is preferred over a backend-proxy design because the backend may not be on the same machine as TradingView Desktop, and it is preferred over frontend-only storage because approvals should survive browsers and belong to operator settings rather than local UI state.

## Proposed System Shape

Split the responsibility into three focused units:

### 1. Backend approval policy

The main backend stores the approved TradingView versions in `system_config`.

Suggested key:

- `local_chart_tradingview_allowed_versions`

Suggested persisted format:

- JSON array of strings

Example stored value:

```json
["2.9.0", "2.9.1"]
```

Why JSON array:

- explicit and unambiguous
- easier to validate than comma-separated strings
- frontend can consume it naturally

### 2. Local provider machine truth

The local chart provider keeps exposing:

- installed TradingView Desktop version
- local compatibility status
- local MCP probe result
- chart-context enabled/disabled

This remains the source of truth for the current machine’s reality.

### 3. Settings-page orchestration

The settings page should:

- fetch approved versions from the backend config API
- fetch local provider compatibility from `http://127.0.0.1:8765/health/compatibility`
- compare the detected local version against the approved list
- offer an `Approve current version` action only when the local provider can see a valid current version

This keeps the user workflow simple without collapsing backend policy and local runtime state into one misleading source.

## Backend API Design

Add one TradingView MCP compatibility config section to `src/api_config.py`.

Recommended endpoints:

- `GET /api/v1/config/tradingview-mcp`
- `PATCH /api/v1/config/tradingview-mcp`

Recommended response shape:

```json
{
  "approved_versions": ["2.9.0", "2.9.1"]
}
```

Recommended patch request shape:

```json
{
  "approved_versions": ["2.9.0", "2.9.1"]
}
```

Behavior:

- backend validates each version as a non-empty string
- backend normalizes whitespace and removes duplicates
- backend stores the final JSON array under the system config key

This should follow the same operator-controlled update pattern used by other config endpoints in `src/api_config.py`.

## Local Provider Approval Source

The local provider should stop relying on `TRADINGVIEW_ALLOWED_VERSIONS` for approval policy in the steady state.

Instead, it should fetch approved versions from the main backend config API and cache them briefly.

Recommended first rollout:

- local provider fetches approved versions from the backend config endpoint
- local provider caches the list with a short TTL
- if the backend config cannot be fetched, the provider degrades safely with a clear reason

This keeps the approval source centralized in the app’s settings system while preserving the local provider’s role as the compatibility checker.

## Settings Page UI

Add a TradingView MCP compatibility section to the settings page.

Recommended contents:

- `Current local TradingView version`
- `Current local MCP status`
- `Approved versions`
- `Chart context enabled` badge or status line
- `Approve current version` button

Recommended button behavior:

- enabled only when a current local TradingView version is present
- optionally disabled when the local provider is unavailable
- hidden or disabled when the current version is already approved

Recommended explanatory copy:

- approval is local-machine verification plus backend-stored policy
- approving the version does not bypass a broken local probe

## Approval Flow

The operator flow should be:

1. open settings
2. settings page fetches approved versions from backend
3. settings page fetches local compatibility from `127.0.0.1:8765`
4. UI shows whether the detected local version is already approved
5. if not approved, operator clicks `Approve current version`
6. frontend appends that exact version to the backend-approved list
7. backend persists the updated list
8. local provider becomes `supported` on the next approval-policy refresh if the local probe also passes

This keeps approval deliberate while removing manual `.env` editing.

## Failure Handling

### Backend config unavailable

- settings page still tries to show local provider status
- approved versions section shows load failure
- approve action is disabled
- local provider degrades chart context if it cannot refresh approvals from backend

### Local provider unavailable

- settings page can still show backend-approved versions
- local compatibility section shows unavailable
- approve action is disabled because local reality is unknown

### Local probe failing

- settings page shows the detected version and failed status
- approve action remains available when a concrete local TradingView version is detected, even if the current probe is failing

Recommended first rollout:

- allow approval when a version is detected, even if probe status is not `supported`
- clearly label that approval updates policy but does not override a failing local MCP probe

This avoids a dead-end where operators cannot bless a newly updated version after a successful UI-level investigation, while still preserving runtime safety because the provider still requires the local probe to pass.

### Current version already approved

- UI should show `Approved`
- approve button is hidden or disabled

## Data Flow

### Page load

1. frontend requests backend TradingView MCP config
2. frontend requests local provider compatibility
3. frontend combines both into a view model

### Approval action

1. frontend reads current local TradingView version from local provider response
2. frontend merges it into the backend-approved version list
3. frontend sends the updated list to the backend config API
4. backend stores the normalized list
5. frontend refreshes both backend config and local provider status

### Local provider runtime

1. provider refreshes approval policy from backend config on a short TTL
2. provider compares detected local version against that approved list
3. provider still runs the local MCP probe
4. provider enables chart context only when both approval and local probe are good

## Caching

Two caches remain useful:

### Local provider compatibility cache

- existing short TTL for version detection and probe status

### Local provider approval-policy cache

- new short TTL for backend-approved versions

Recommended first value:

- 60 seconds

This means the settings page approval should take effect quickly without forcing every chart-context request to hit the main backend.

## Security And Trust Boundaries

- backend config endpoints remain operator-controlled
- local provider compatibility remains local-machine-only
- backend should not fabricate desktop state
- frontend should not be the system of record for approvals

This division keeps the architecture honest and reduces confusion when backend and local machine are not the same host.

## Testing

### Backend tests

- config API returns approved versions
- config API stores normalized unique versions
- empty update clears the approved list cleanly

### Local provider tests

- provider fetches approved versions from backend config
- provider degrades cleanly when backend config is unavailable
- provider uses backend-approved versions instead of env-provided allowlist

### Frontend tests

- settings page renders backend-approved versions
- settings page renders local compatibility status
- approve button appears when current local version is not approved
- approve button updates backend config payload correctly

### Manual test

1. install or update TradingView Desktop locally
2. open settings page
3. confirm local version appears
4. approve the current version
5. confirm backend-approved list updates
6. confirm `/health/compatibility` becomes `supported` after the next local provider refresh when the probe passes

## Rollout Plan

Phase 1:

- add backend config endpoints for approved versions
- add frontend settings section
- keep env-based config as temporary fallback if desired

Phase 2:

- local provider reads approved versions from backend config
- remove or deprecate env-based version approval for normal use

This phased rollout reduces risk because the UI and backend settings can land before removing the old approval source.

## Risks And Trade-Offs

- the settings page depends on both backend reachability and local provider reachability for the best UX
- local provider now depends on backend config availability for approval policy refresh
- a phased rollout temporarily supports two policy sources unless we cut directly to backend-only

These are acceptable because the gain in operator usability and correctness is substantial.

## Recommendation

Implement backend-stored approved versions, keep local compatibility detection where it belongs, and let the settings page orchestrate approval. This gives the safest and least annoying operator workflow without weakening the runtime guardrail.
