# Clean SND Detector Prototype Design

Jira: DEV-328

## Goal

Create a new PineScript prototype that detects supply and demand zones and liquidity with a cleaner, Myrtille-style visual model, without touching the current live strategy.

The first milestone is visual and diagnostic only. The prototype should make zone and liquidity detection easier to trust by showing fewer, higher-quality zones, one meaningful liquidity level per setup, and clear state transitions.

## Current Context

`scripts/pinescript/strategies/SND_Strategy.pine` is the current live strategy. It already handles zone detection, liquidity detection, sweep state, entry validation, alerts, debug plots, webhook fields, and some backend feature context.

That concentration of responsibilities makes the script noisy and difficult to reason about. The new work should not modify this file.

The referenced TradingView indicator, `Zones Liq S/D - Myrtille`, is published as a protected/closed-source script. Public release notes mention accuracy zones, one-candle liquidity detection, alerts, multi-timeframe compatibility, and more accurate zone detection. We can use the visible behavior as inspiration, but we cannot depend on or copy its implementation.

## Proposed Files

Add a new visual prototype:

```text
scripts/pinescript/indicators/SND_Clean_Zones_Prototype.pine
```

Later, after the detector is visually proven, add a separate candidate emitter:

```text
scripts/pinescript/strategies/SND_Candidate_Emitter.pine
```

Do not change:

```text
scripts/pinescript/strategies/SND_Strategy.pine
scripts/pinescript/libraries/SND_Core.pine
scripts/pinescript/libraries/SND_Utils.pine
```

unless a later implementation plan explicitly approves a small shared-library extraction.

## Detector Model

The prototype should model each zone as a simple state machine:

```text
candidate_base -> waiting_bos -> valid -> tested -> invalid
```

`candidate_base` means price formed a possible supply or demand base.

`waiting_bos` means the zone exists visually but has not yet proven displacement or structure break.

`valid` means the zone caused a break of structure and has not been mitigated.

`tested` means price has returned to the zone after validation.

`invalid` means the zone was broken, expired, overlapped by a better zone, or mitigated before the required liquidity event.

## Zone Detection

The prototype should prefer sparse zones over complete coverage.

Detect a base only when:

- The base is one to several consolidation candles.
- Candle bodies are relatively small compared with total range.
- The base is followed by displacement in the correct direction.
- The displacement causes a break of structure.

Demand zones should come from a base followed by bullish displacement. Supply zones should come from a base followed by bearish displacement.

Zone bounds should be simple and explainable:

- Demand proximal line: body high or base open, depending on accuracy mode.
- Demand distal line: base wick low.
- Supply proximal line: body low or base open, depending on accuracy mode.
- Supply distal line: base wick high.

The detector should merge, suppress, or age out overlapping zones so the chart stays clean.

## Liquidity Detection

Liquidity should be a first-class object attached to a zone, not a scatter of markers.

For each valid zone, select one best inducement level and one optional target level:

- Demand inducement: sell-side liquidity above the demand zone but below the later push high.
- Demand target: buy-side high between zone creation and inducement.
- Supply inducement: buy-side liquidity below the supply zone but above the later push low.
- Supply target: sell-side low between zone creation and inducement.

The prototype should support two liquidity modes:

- Internal liquidity: closer, smaller structure.
- External liquidity: larger structure, farther from the zone.

Inputs should expose separate distance limits for these modes, similar to the Myrtille settings:

```text
enable_one_candle_liquidity
max_internal_liquidity_distance
max_external_liquidity_distance
external_structure_max_percent_of_move
strict_bos_close_beyond_level
```

The default should allow one-candle liquidity only in the prototype, not in the current live strategy.

## Visual Design

The chart should be quiet by default.

Show:

- Valid demand and supply zones.
- Tested zones in a different color.
- One inducement liquidity line per zone.
- Optional target liquidity line.

Hide by default:

- Fractal markers.
- Per-bar debug labels.
- Large inspector tables.
- Hidden webhook plots.

Add a debug mode that can show rejected bases, rejected liquidity, BOS levels, and state labels.

## Alert And Backend Contract

The first prototype does not need alerts.

After visual validation, the candidate emitter should send setup candidates to the backend. Pine should not make the final trade decision.

Candidate fields should include:

- `strategy_id`
- `strategy_version`
- `symbol`
- `timeframe`
- `side`
- `zone_id`
- `zone_state`
- `zone_top`
- `zone_bottom`
- `zone_created_time`
- `is_accuracy_zone`
- `bos_level`
- `bos_strength`
- `liquidity_mode`
- `inducement_price`
- `inducement_swept`
- `target_price`
- `target_swept`
- `liquidity_distance_pips`
- `zone_age_bars`
- `touch_count`
- `session_context`
- optional `nearest_news_context`

The backend remains responsible for news, risk, account constraints, AI/ML decisions, and execution.

## News Integration

The toodegrees economic calendar script can remain a separate chart indicator for visibility.

Do not make Pine execution safety depend on that script. If news context is later added to alerts, it should be context only. The backend news guard should remain authoritative.

## Non-Goals

- Do not modify the current live strategy.
- Do not execute trades from the prototype.
- Do not emit production alerts from the prototype.
- Do not copy or reverse-engineer protected TradingView source.
- Do not move backend risk or news decisions into Pine.
- Do not add new top-level directories.

## Implementation Milestones

1. Add `SND_Clean_Zones_Prototype.pine` as a visual-only indicator.
2. Implement the zone state machine and sparse zone rendering.
3. Implement internal and external liquidity selection.
4. Add debug mode for rejected zones and liquidity.
5. Compare visually against the current strategy and Myrtille on the same charts.
6. Tune defaults for 5-minute forex pairs, especially GBPJPY.
7. Design the candidate emitter only after the prototype is clean enough.

## Testing

Use source-level checks first:

- The current live strategy file is unchanged.
- The new prototype compiles as Pine v6.
- The prototype contains no `strategy.entry`, `strategy.order`, or webhook production alert path.
- The prototype has bounded loops and object counts.

Manual TradingView validation:

- Add the prototype beside the current strategy and Myrtille.
- Check GBPJPY 5m first, then other JPY pairs.
- Confirm fewer zones than the current strategy.
- Confirm one meaningful liquidity line per zone.
- Confirm zones move through `waiting_bos`, `valid`, `tested`, and `invalid` states as expected.

## Acceptance Criteria

- A new Pine indicator file exists and does not affect live trading.
- The current live strategy remains unchanged.
- The prototype shows sparse, readable zones and liquidity lines.
- One-candle liquidity is configurable in the prototype.
- Internal and external liquidity distance settings are separate.
- Pine remains a detector and messenger, while backend decisions remain backend-owned.
