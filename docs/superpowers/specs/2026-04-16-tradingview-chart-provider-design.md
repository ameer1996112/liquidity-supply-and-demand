# DEV-121 TradingView Chart Provider Integration Design

## Summary

Design a read-only TradingView chart provider integration that supplies structured chart context to the AI Operating Layer for pre-trade shadow analysis and post-trade review. The provider must be optional, failure-tolerant, and isolated from the live trading path.

## Goals

- Add a real chart-context provider behind the existing chart context service.
- Fetch structured TradingView chart state automatically for:
  - pre-trade shadow analysis
  - post-trade review
- Keep the provider integration read-only in v1.
- Support one global provider endpoint first.
- Preserve graceful degradation when the provider is unavailable.
- Keep the integration execution-independent.

## Non-Goals

- No chart-control actions in v1.
- No automatic TradingView UI interaction beyond read-only fetch.
- No screenshot requirement in v1.
- No provider failover chain in v1.
- No per-strategy or per-account provider routing in v1.
- No direct effect on live trading decisions or execution in v1.

## Existing Context

The AI Operating Layer v1 already includes:

- chart context normalization
- AI operating-layer orchestration primitives
- expanded AI run persistence and API response fields
- settings UI and global config API for AI Operating Layer controls

Currently, chart context is only a normalized service boundary. There is no real external provider connected yet.

## Proposed System Shape

Add one new external adapter:

- `TradingViewChartProviderAdapter`

The data path becomes:

1. AI Operating Layer decides chart context is needed.
2. Adapter calls one global chart provider endpoint.
3. Provider returns structured chart state.
4. `chart_context_service.py` validates and normalizes the result.
5. `ai_operating_layer.py` attaches normalized chart context to AI runs.

This integration must remain optional. If the provider fails, the AI run continues with degraded chart context and the core trading flow remains untouched.

## Recommended Provider Strategy

Support one provider interface from the start, but implement the `tradesdontlie/tradingview-mcp` style desktop chart bridge first.

Why:

- it best addresses the current product gap: chart awareness and Pine/chart-state visibility
- it is more differentiated than analytics-heavy alternatives
- it fits the existing AI Operating Layer design

The second provider family can be added later behind the same adapter contract.

## Runtime Placement

### Initial rollout

- provider can run locally beside TradingView Desktop

### Target operational model

- provider should later run on a dedicated always-on machine or VPS

The backend must treat the provider as an external network service, not a local-only assumption. The provider host should be configurable so the backend does not need code changes when the provider moves off the operator machine.

## Adapter Boundary

### Adapter responsibilities

- call one global provider endpoint
- apply short timeout and retry policy
- return raw provider payload or failure reason
- avoid leaking transport details upward

### Chart context service responsibilities

- validate required structured fields
- normalize provider payload into internal schema
- mark degraded status when required fields are missing

### AI operating-layer responsibilities

- decide when chart fetch is needed
- attach normalized chart context to shadow pre-trade and post-trade runs
- continue safely when chart provider is unavailable

## First Provider Contract

The first version requires structured chart state. Screenshot support is optional.

### Required top-level fields

- `symbol`
- `timeframe`
- `provider_timestamp`
- `pine_labels`
- `zones`
- `indicator_values`

### Artifact requirements

`zones` and similar chart artifacts should support both Pine-generated and manual chart objects.

Each structured artifact should include:

- `type`
- `source` (`pine` or `manual`)
- `label`
- `price` or `region`
- optional metadata

### Optional v1 fields

- `screenshot_url`
- `pine_tables`
- `layout_name`
- `pane_metadata`

## Required Internal Normalized Shape

The backend should normalize provider payloads into a stable shape similar to:

```json
{
  "status": "ok",
  "symbol": "XAUUSD",
  "timeframe": "5m",
  "reason": "",
  "structured": {
    "provider_timestamp": "2026-04-16T12:34:56Z",
    "pine_labels": [],
    "zones": [],
    "indicator_values": {}
  },
  "screenshot_url": null
}
```

If required structured state is missing, normalize to:

```json
{
  "status": "degraded",
  "symbol": "XAUUSD",
  "timeframe": "5m",
  "reason": "provider returned incomplete structured state",
  "structured": {},
  "screenshot_url": null
}
```

## Triggering Rules

The first live provider integration should fetch chart context automatically for:

- pre-trade shadow analysis
- post-trade review

It should not yet support:

- manual operator fetch workflows
- continuous polling
- live execution-time gating

## Retry and Timeout Rules

Provider unavailability should not silently disappear, but it also should not stall the AI flow too long.

Recommended policy:

- one initial request
- two quick retries
- short total timeout budget
- if still unavailable:
  - mark chart context as degraded
  - record the failure reason
  - continue the AI run

## Failure and Degradation Rules

- provider failure must never break the core trading path
- provider failure must never block AI run persistence
- missing required structured fields should be treated as degraded, not successful
- degradation reason must surface in:
  - `module_status`
  - chart context payload
  - operator UI

## Configuration Model

The first provider integration should use one global endpoint configuration.

Recommended configurable values:

- provider enabled/disabled
- provider base URL
- request timeout
- retry count

These can live initially in global config only. Per-strategy/provider routing is deferred.

## Security and Safety Rules

- provider integration is read-only only in v1
- backend must never send commands that alter TradingView state
- adapter must treat provider output as untrusted external input and validate required fields before use
- provider health must be observable in the AI Operating Layer, not hidden

## First Implementation Slice

Build:

- one read-only TradingView chart provider adapter
- one global provider endpoint config
- structured-state fetch only
- adapter integration into `chart_context_service.py`
- automatic fetch for:
  - shadow pre-trade analysis
  - post-trade review
- retry + degradation handling

Do not build yet:

- screenshot requirement
- TradingView control actions
- multiple provider backends
- per-scope provider routing
- provider-driven execution influence

## Rollout Plan

### Phase 1

- local provider validation
- automatic shadow pre-trade fetch
- automatic post-trade fetch
- degraded-state observability

### Phase 2

- move provider to a dedicated always-on host
- improve provider health reporting
- optionally add screenshot support

### Phase 3

- add alternative providers behind the same adapter contract
- consider scoped routing and richer operator workflows

## Key Design Decisions

- choose a provider interface that can support multiple backends later
- implement the desktop chart bridge first because it solves the current gap best
- keep the first provider integration structured-state-first
- keep the provider read-only
- keep it global-first
- keep it execution-independent

## Open Expansion Paths

Later iterations can add:

- screenshots as first-class evidence
- manual fetch from operator UI
- per-strategy provider selection
- provider failover
- Pine table extraction
- richer chart metadata
- real health dashboards for provider uptime and latency

These are intentionally deferred to keep the first provider integration narrow and safe.
