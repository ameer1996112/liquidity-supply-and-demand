# DEV-124 Setup Evidence Bundle Design

## Summary

Design a Setup Evidence Bundle that automatically captures the most relevant visual and structured chart evidence for a Pine-driven setup. The bundle should be created at signal-time shadow analysis and post-trade review, centered on the primary active setup zone, stored with the journal/AI run, and reused across trade detail UI, manual requests, and later Discord/Telegram delivery.

## Goals

- Automatically capture visual evidence for the actual setup, not just numeric payloads.
- Reuse the existing chart provider flow instead of creating a separate screenshot system.
- Make the focused setup zone screenshot the primary image artifact.
- Store the bundle in the journal / AI run as the source of truth.
- Reuse the same stored bundle for:
  - trade detail UI
  - manual request/share flows
  - later Discord/Telegram delivery
- Keep the first version execution-independent and failure-tolerant.

## Non-Goals

- No live-trade gating based on screenshots.
- No full multi-zone or multi-pane image stitching in v1.
- No autonomous notification fan-out in v1.
- No full-chart-only screenshot strategy in v1.
- No image annotation or drawing overlays in v1.

## Existing Context

Three building blocks already exist or are in flight:

1. The AI Operating Layer already supports chart-aware analysis and structured AI runs.
2. The local MCP-backed provider already returns:
   - zones
   - Pine labels
   - indicator values
3. The product direction is to make the current AI and debate agents understand the actual setup instead of only numeric traces.

The missing piece is a single evidence bundle that captures both:

- what the setup structurally was
- what the setup visually looked like

at the time the AI analysis ran.

## Proposed System Shape

Add one new concept to the AI Operating Layer:

- `Setup Evidence Bundle`

The bundle is produced by the chart context path and attached to AI/journal artifacts.

Data path:

1. Pre-trade shadow or post-trade review opens an AI analysis run.
2. The chart provider captures structured chart artifacts plus focused setup imagery.
3. The evidence bundle is normalized and attached to the AI run / journal record.
4. Consumers reuse the stored bundle:
   - trade detail UI
   - manual operator request/share
   - later Discord/Telegram delivery

This keeps evidence generation centralized and avoids drift between storage, UI, and notification payloads.

## Recommended Bundle Shape

The v1 bundle should contain:

- `symbol`
- `timeframe`
- `provider_timestamp`
- `zones`
- `pine_labels`
- `indicator_values`
- `setup_focus_image`
- `metadata`

Optional later:

- `full_chart_image`
- `notification_preview`
- `derived_zone_summary`

## Primary Image Strategy

### Recommended v1 image

Use a `focused setup zone` screenshot as the primary image.

This image should:

- center on the primary active setup zone
- include nearby Pine labels
- include enough surrounding candles for context
- avoid pulling in unnecessary full-chart noise

Why:

- more useful for journal and notifications
- easier for operators to scan
- better aligned with the actual decision area
- more meaningful for later AI explanation and post-trade review

### Full chart handling

Treat the full chart as optional later evidence, not the primary v1 image.

## Zone Selection Rules

The first version should focus on the `top active zone only`.

Why:

- simplest and clearest crop target
- easier to reason about and test
- avoids image clutter when multiple overlapping zones are present

Future versions can expand to:

- multiple nearby zones
- ranked zone candidates
- combined focus windows

## Capture Timing

Automatically capture the bundle at:

- `pre-trade shadow analysis`
- `post-trade review`

This gives the system:

- what the setup looked like at signal time
- what the chart context looked like at review time

That creates a much stronger learning loop than on-demand-only capture.

## Provider Responsibilities

The chart provider should expand from structured-only output into evidence-capable output.

### Existing responsibilities

- symbol/timeframe
- zones
- Pine labels
- indicator values

### New responsibilities

- determine the primary active setup zone
- capture a focused setup screenshot from the same provider session
- return a stable reference to that screenshot

The screenshot capture must come from the same provider layer as the structured data so that:

- the screenshot and zones come from the same moment
- the AI is not reasoning over mismatched evidence

## Evidence Bundle Normalization

The normalized bundle should preserve:

- the actual active symbol/timeframe
- the primary zone used for image focus
- the visual artifact reference
- the structured chart artifacts used by the AI

Suggested v1 shape:

```json
{
  "symbol": "VANTAGE:AUDUSD",
  "timeframe": "5m",
  "provider_timestamp": "2026-04-17T00:20:00Z",
  "zones": [],
  "pine_labels": [],
  "indicator_values": {},
  "setup_focus_image": {
    "storage": "local_provider",
    "path_or_url": "http://provider/screenshots/setup-123.png",
    "focus_zone_label": "Institutional Liquidity Protocol [Pro]",
    "focus_zone_price": 0.72
  },
  "metadata": {
    "capture_phase": "pretrade_shadow"
  }
}
```

## Storage Strategy

### Source of truth

Store the bundle with the journal / AI run first.

Why:

- one durable source of truth
- easier replay and auditability
- easier comparison between signal-time and review-time evidence
- downstream consumers can reuse instead of recapturing

### First storage model

The image may remain on the provider machine in v1 if necessary, as long as the journal stores a stable reference.

Longer term:

- move image storage to durable shared storage if needed

## Consumer Strategy

### Trade detail UI

Show the full evidence bundle here first:

- focused setup image
- zones
- Pine labels
- indicator values
- linked AI verdict

This should be the first main surface because it is best for validation and debugging.

### Manual request/share

Allow a future manual action to package the stored bundle for operator requests without recapturing.

### Discord/Telegram

Later notification delivery should reuse the same stored bundle and send a compact representation:

- focused setup image
- summary verdict
- key zone / label context

## Failure and Degradation Rules

- evidence capture failure must never break the core trading flow
- evidence capture failure must never block AI run persistence
- structured chart context may still succeed even if screenshot capture fails
- if screenshot capture fails:
  - keep the rest of the bundle
  - mark image status as degraded
  - surface a short reason

This means the evidence system should degrade in layers:

1. full evidence bundle
2. structured-only bundle
3. legacy non-chart fallback

## Testing Strategy

The first implementation should be validated against:

- one clear Pine setup with active zone + labels
- signal-time shadow capture
- post-trade review capture
- journal persistence of the bundle
- UI rendering of the stored bundle

The most important acceptance check is:

- does the stored bundle clearly show the same setup area the trader would point to on the chart?

## Rollout Plan

### Phase 1

- provider support for focused setup screenshot capture
- normalized evidence bundle
- journal / AI run persistence
- trade detail UI rendering

### Phase 2

- manual request/share flow
- compact notification formatting for Discord/Telegram

### Phase 3

- optional full chart image
- multi-zone evidence
- durable shared storage improvements

## Recommendation

Build the Setup Evidence Bundle as a journal-first, provider-driven extension of the current chart-aware AI architecture. The primary image should be a focused setup zone screenshot derived from the same provider session as the structured zones and Pine labels. That gives the AI, the journal, and future notifications one consistent source of truth for what the setup actually was.
