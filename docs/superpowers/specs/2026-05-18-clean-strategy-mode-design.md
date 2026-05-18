# Clean Strategy Display Mode Design

## Goal

Make `SND_Strategy.pine` look and behave closer to the clean `Zones Liq S/D v22 - Myrtille` indicator while keeping the strategy execution logic intact.

The strategy should load faster, expose fewer visual settings, and avoid showing rejected or candidate zones during normal use. Trade, risk, SL/TP, webhook, and order execution behavior must not change.

## Scope

This design only covers display and debug simplification in:

- `scripts/pinescript/strategies/SND_Strategy.pine`
- the existing static Pine guard test

It does not change:

- zone detection patterns
- zone boundaries
- liquidity selection
- liquidity sweep or BOS logic
- entry models
- risk, SL/TP, alerts, webhooks, or orders

## Current Problem

The strategy currently mixes trading behavior with several visual/debug modes:

- `zone_lab_mode`
- `show_invalid_zones`
- `show_mitigated_zones`
- `show_candidate_zones`
- `show_rejection_reason_labels`
- `show_entry_used_zones`

These settings make the chart confusing and add more branches to the display path. The user wants the strategy to look clean by default, like the reference indicator, without needing display-mode tuning.

## Proposed Behavior

The strategy will have one default clean display behavior:

- Show live active zones normally.
- Show zones that fired entries as muted grey archive zones.
- Show liquidity lines when the script has liquidity data.
- Show entry labels, SL, TP, and trade plots as they work today.
- Hide rejected, invalid, and candidate zones from normal chart display.

Used-entry archive zones must remain queryable in the inspector and must not trade again.

## Debug Behavior

The zone inspector remains available, but only through `debug_level`:

- `debug_level = None`: no inspector table and no debug-only zone clutter.
- `debug_level = Basic` or `Full`: inspector/debug information can render.

This keeps the debugging tool available without making normal replay/load visually or computationally heavy.

## Inputs To Remove

Remove these display inputs from the strategy settings:

- `zone_lab_mode`
- `show_invalid_zones`
- `show_mitigated_zones`
- `show_candidate_zones`
- `show_rejection_reason_labels`
- `show_entry_used_zones`

Keep `show_relevant_zones_only`, because it reduces clutter and can reduce object update work.

## Display Classification

The display path should classify zones with simple deterministic booleans:

- `activeDisplayZone`: active, not mitigated, not invalid/rejected, and relevant.
- `entryUsedArchive`: `lastEntryBar` exists and the zone is not structurally invalid.
- `visible`: active display zone or entry-used archive.

Rejected/candidate/invalid zones should not be drawn in normal display. Inspector data can still expose their state when debug is enabled and the zone remains in live arrays or ZoneDB.

## Performance Notes

The implementation should avoid adding new loops or arrays.

Entry-used archive behavior should reuse the existing zone arrays and ZoneDB fields:

- `lastEntryBar`
- `active`
- `mitigated`
- `inactiveReason`

Display simplification should reduce branches in `zone_should_show_visual()` and avoid maintaining separate mode flags.

## Tests

Update the static Pine guard test to check that:

- removed display inputs are absent
- entry-used zones are persisted into demand/supply arrays
- entry-used zones use `MITIGATED:USED_FOR_ENTRY`
- the display path no longer depends on the removed mode inputs

Manual TradingView verification:

1. Script compiles.
2. Normal chart shows active zones cleanly.
3. A zone that fires an entry remains visible as grey archive.
4. Used-entry archive zones do not fire another trade.
5. `debug_level = None` hides the inspector.
6. `debug_level = Basic` or `Full` shows the inspector.
7. Risk, SL/TP, webhooks, and orders behave unchanged.
