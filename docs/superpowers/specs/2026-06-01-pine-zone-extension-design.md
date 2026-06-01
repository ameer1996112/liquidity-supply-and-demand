# Pine Zone Extension Design

Date: 2026-06-01
Jira: DEV-843

## Goal

Make PineScript demand and supply zones extend like the reference chart:

- A newly created valid zone projects forward into the future.
- The first wick touch anywhere inside the zone stops the box extension.
- The shortened zone remains visible after that first touch.
- Trading logic, liquidity logic, and visual box lifecycle stay separate.

## Problem

The current script mixes zone drawing with strategy state:

- `lastTouchBar` is used by entry and analytics logic, so it is not a stable visual stop.
- `z.mitigated` is controlled by trade and liquidity gates, so some visually touched zones never stop extending.
- Historical and live zones pass through different branches, so replay can look inconsistent.
- Recent fixes added visual stop arrays, but the stop condition is still attached to branches that do not cover every valid visual touch.

This causes zones such as `D-29164` to keep extending even after price has clearly wicked into the zone.

## Approved Behavior

Use a visual-only zone lifecycle:

```text
zone created
  -> box right = createdBar + projectionBars

zone leaves
  -> box right remains createdBar + projectionBars

first wick touch after leaving
  -> save visualStopBar once
  -> box right = visualStopBar forever

zone invalidated
  -> existing invalidation/removal rules apply
```

Default future projection: `50` bars.

The projection should be configurable with an input such as `Unmitigated Zone Projection Bars`, defaulting to `50`.

## Zone Touch Rule

A visual stop is recorded only after a zone has already left.

For a demand zone:

```pine
hadLeftZone and low <= z.top and high >= z.bottom
```

For a supply zone:

```pine
hadLeftZone and high >= z.bottom and low <= z.top
```

This is intentionally wick-based. A close inside the zone is not required.

## State Model

Do not use `z.lastTouchBar` or `z.mitigated` to decide the visual right edge.

Use separate visual state keyed by zone ID:

```pine
var int[] visual_stop_zone_ids = array.new_int()
var int[] visual_stop_bars = array.new_int()
```

Required helper behavior:

- `visual_stop_bar(zoneId)` returns the stored stop bar or `na`.
- `record_visual_stop(zoneId, barIndex)` writes once and never moves the stop later.
- `clear_visual_stop(zoneId)` removes state when the zone is removed or pruned.
- `zone_visual_right(z)` returns the stored stop bar when present, otherwise `z.createdBarIndex + zone_projection_bars`.

## Data Flow

1. Capture `hadLeftZone = z.leftZone` before updating `z.leftZone` on the current bar.
2. Update `z.leftZone` using existing leave rules.
3. Independently evaluate the visual wick-touch rule for every active zone.
4. If the rule is true, call `record_visual_stop(z.id, bar_index)`.
5. Draw the box and label using `zone_visual_right(z)`.
6. Keep existing invalidation/removal behavior unchanged.

The visual stop check must run for both live and historical zones. It must not be skipped by liquidity validation, sweep detection, entry checks, or mitigation branches.

## Non-Goals

- Do not change zone creation rules.
- Do not change liquidity detection.
- Do not change trade entry or exit rules.
- Do not force `z.mitigated := true` just because a visual stop happened.
- Do not remove a zone only because it received its first wick touch.

## Error Handling And Edge Cases

- If `z.id` is `na`, do not record visual state.
- If `z.createdBarIndex` is `na`, avoid drawing or fall back to existing drawing guards.
- If a zone is removed or pruned, clear the matching visual stop entry.
- If a later candle touches the same zone again, keep the original stop bar.
- If a zone is invalidated on the same candle as the first visual touch, existing invalidation rules decide whether the zone remains.

## Testing

Manual TradingView replay checks are required because Pine cannot be fully compiled locally here.

Minimum checks:

- USDJPY 5m around the reference sequence: zones like `D-29164` stop at the first wick touch and remain visible.
- A fresh unmitigated zone projects `50` bars into the future.
- A mitigated/touched zone does not continue moving its right edge on later candles.
- Historical reload/replay produces the same right edge as live progression.
- Supply zones follow the same behavior in reverse.

Local checks:

- Run `git diff --check` after edits.
- Review the affected Pine blocks for duplicate declarations and branch skips.
