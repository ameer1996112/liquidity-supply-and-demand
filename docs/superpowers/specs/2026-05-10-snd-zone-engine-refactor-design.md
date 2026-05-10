# SND Zone Engine Refactor Design

Ticket: DEV-380

## Goal

Clean and correct the zone, liquidity, and drawing engine in `scripts/pinescript/strategies/SND_Strategy.pine` while preserving the working trade execution system.

The script should identify and draw Liquidity Supply/Demand zones according to the 2026 LSD rule set from the provided transcripts, with clear debug visibility for why each zone is waiting, valid, accuracy, mitigated, or invalid.

## Scope

This refactor is limited to the detection and visualization layer:

- source candle selection
- normal zone boundary calculation
- forex accuracy zone boundary calculation
- waiting BOS state
- liquidity swing selection
- liquidity "breaks its own high/low" validation
- pre-BOS and pre-sweep invalidation
- zone box, label, and liquidity line drawing
- debug reason strings and inspector fields related to zones

## Non-Goals

The first implementation pass must not change:

- entry execution rules
- exit rules
- risk sizing
- webhook payload shape
- backend decision flow
- daily drawdown logic
- news/session filters
- strategy result table
- AI/backend filtering behavior

## Current State

The current script already has most of the pieces, but they are tangled across several areas:

- `createZone(...)` handles source candle checks, historical de-duplication, consolidation/base expansion, accuracy checks, zone boundaries, drawing, scoring, and DB insertion.
- `f_scan_demand_liquidity(...)` and `f_scan_supply_liquidity(...)` search pivots, assign inducement/liquidity prices, infer target sweep levels, count liquidity candles, and set validity.
- `f_check_demand_sweeps(...)` and `f_check_supply_sweeps(...)` mark both liquidity sweeps and structure/target sweeps.
- The live zone loops later update `leftZone`, pre-sweep touches, mitigation, and liquidity visuals.
- Separate removal loops can delete zones after close-inside, age, or wick invalidation.

Because several blocks mutate the same fields, small fixes can create visual or behavioral regressions.

## Master Rule Contract

### Source Candle

Demand source:

- Use the final bearish candle before a strong bullish displacement.
- The bullish displacement may be one or more bullish candles, but the source is the last bearish candle immediately before that move.

Supply source:

- Use the final bullish candle before a strong bearish displacement.
- The bearish displacement may be one or more bearish candles, but the source is the last bullish candle immediately before that move.

### Normal Zone Boundaries

Demand normal zone:

- Top = high of the bearish source candle.
- Bottom = lower of the bearish source candle low and the first bullish displacement candle low.

Supply normal zone:

- Bottom = low of the bullish source candle.
- Top = higher of the bullish source candle high and the first bearish displacement candle high.

The displacement candle wick extension must only inspect the first displacement candle next to the source, not broad future candles.

### Forex Accuracy Zone Boundaries

Accuracy zones apply only when enabled and only for forex-style instruments where the strategy uses the improved marking.

Demand accuracy:

- Trigger when the bearish source candle high is higher than the first bullish displacement candle high.
- Remove the bad upper price area.
- Draw from the source candle body top down to the lower wick boundary.
- The lower wick boundary is the lower of the source low and first bullish displacement low.

Supply accuracy:

- Trigger when the bullish source candle low is lower than the first bearish displacement candle low.
- Remove the bad lower price area.
- Draw from the upper wick boundary down to the source candle body bottom.
- The upper wick boundary is the higher of the source high and first bearish displacement high.

Accuracy zones are not body-only boxes. They keep the important wick side and remove only the worse-price side.

### Untapped Rule

Before the entry tap:

- Demand is invalid if an opposing bearish candle touches the zone after the departure sequence.
- Supply is invalid if an opposing bullish candle touches the zone after the departure sequence.
- The same-color candles leaving the source area are allowed to wick through the zone during the departure move.
- Liquidity must not touch the zone. If the liquidity swing taps the zone, the setup is invalid.

### Liquidity Rule

Demand liquidity:

- Liquidity sits below a visible swing low in front of the demand zone.
- Preferred minimum is two opposite-color candles forming the retracement.
- One-candle liquidity should remain optional and lower-confidence, only valid when explicitly enabled.

Supply liquidity:

- Liquidity sits above a visible swing high in front of the supply zone.
- Preferred minimum is two opposite-color candles forming the retracement.
- One-candle liquidity follows the same optional lower-confidence rule.

Liquidity should be close enough to the zone to matter. It should be swept as part of the move into the zone, not far away long before price reaches the zone.

### Break Its Own High/Low

Demand:

- Once the swing low liquidity forms, price must break the high that created that swing low.
- A generic higher high is not enough if it is not the structure point that formed the liquidity.

Supply:

- Once the swing high liquidity forms, price must break the low that created that swing high.
- A generic lower low is not enough if it is not the structure point that formed the liquidity.

### Waiting BOS State

A new zone can exist as a candidate before structure confirmation:

- Candidate state: waiting BOS.
- Valid state: liquidity exists and its own high/low has been broken.
- Tradeable state: valid zone later gets a clean entry tap without closing inside.

Waiting BOS should be visually distinct but should not be treated as fully valid.

### Entry-Tap Invalidation

When price returns to the zone for entry:

- Wick into the zone is allowed.
- Close inside the zone invalidates the entry.
- For demand, stop logic uses the deepest wick into the zone.
- For supply, stop logic uses the deepest wick into the zone.

The drawing refactor should preserve the current entry execution behavior unless the entry code is explicitly addressed in a later pass.

## Proposed Architecture

Keep the script as a single Pine file for now, but split the zone engine into clearer local functions:

1. `f_detect_source_candidate(...)`
   - Finds the source candle and displacement context.
   - Returns source index, first displacement index, side, and displacement candle count.

2. `f_calculate_zone_bounds(...)`
   - Applies normal and accuracy boundary rules.
   - Does no drawing and does not mutate arrays.

3. `f_create_zone_record(...)`
   - Creates `Core.Zone`, assigns IDs, score/grade, and DB fields.
   - Does not scan liquidity.

4. `f_update_zone_state(...)`
   - Moves zones through waiting BOS, valid, touched, mitigated, and inactive states.
   - Centralizes invalidation reason strings.

5. `f_find_liquidity_for_zone(...)`
   - Finds the closest valid swing liquidity for the zone.
   - Enforces minimum candle count and distance rules.

6. `f_validate_liquidity_structure_break(...)`
   - Confirms the liquidity broke its own high/low.
   - Sets waiting/valid status.

7. `f_draw_zone_visuals(...)`
   - Owns boxes, labels, liquidity lines, and color state.
   - Keeps drawing separate from validity decisions.

This keeps Pine constraints in mind while still making the logic readable.

## Migration Plan

1. Add a compact `ZoneRuleContext` style tuple or equivalent local variables inside zone creation to make boundary calculation explicit.
2. Replace boundary calculation inside `createZone(...)` with the normal/accuracy contract.
3. Keep existing zone arrays and `Core.Zone` fields intact.
4. Normalize state transitions before removing old logic:
   - `WAITING_BOS`
   - `VALID`
   - `TOUCHED_PRE_SWEEP`
   - `MITIGATED`
   - `INVALID`
5. Move duplicated demand/supply concepts into mirrored helper functions only where Pine readability improves.
6. Remove unused legacy cluster/body-wick comments and logic only after proving they are not feeding scoring or backend features.

## Debugging and Visual Requirements

The chart should make debugging easier without looking messy:

- Keep zone labels visible.
- Use clear label prefixes: `D-`, `S-`, `D-ACC-`, `S-ACC-`.
- Add optional debug reason labels/table fields:
  - `WAITING_BOS`
  - `VALID_LIQ`
  - `LIQ_TOUCH_ZONE`
  - `TOUCHED_PRE_BOS`
  - `CLOSE_INSIDE`
  - `OPPOSING_TAP`
  - `BROKE_OWN_HIGH`
  - `BROKE_OWN_LOW`
- Liquidity lines should stop at mitigation/sweep, not continue past the event that resolved them.
- Waiting BOS candidates should be visually distinct from confirmed zones.

## Testing and Verification

Because Pine scripts are difficult to unit test locally, verification will use controlled chart replay:

1. Compile in TradingView after each implementation pass.
2. Compare against known screenshots/examples:
   - normal demand with first bullish wick extension
   - demand accuracy with bad upper area removed
   - normal supply with first bearish wick extension
   - supply accuracy with bad lower area removed
   - liquidity touching zone invalidates setup
   - zone returns before BOS invalidates setup
   - liquidity breaks own high/low before valid state
3. Use the zone inspector to confirm stored top/bottom, liquidity price, structure break level, and inactive reason.
4. Confirm existing strategy entries still fire from the same trade path after a zone becomes valid.

## Risks

- Zone cleanup can change historical trade counts because better invalidation may remove zones that previously traded.
- Some existing scoring fields may depend on legacy base/cluster variables.
- Pine line/box object limits may be hit if invalidated/debug zones are displayed too aggressively.
- Myrtille source code is not available, so exact matching is inferred from screenshots and transcripts, not copied from implementation.

## Approval Gate

Implementation should start only after this design is reviewed and approved. The first implementation pass should be narrow: correct boundary rules and state labels before deeper liquidity cleanup.
