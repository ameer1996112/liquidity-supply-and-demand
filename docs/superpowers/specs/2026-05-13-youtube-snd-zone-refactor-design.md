# YouTube Liquidity S&D Zone Refactor Design

Date: 2026-05-13
Ticket: DEV-420

## Goal

Refactor the Pine strategy zone engine so supply and demand zones follow the extracted RD Forex / ArgerFX / Mangoe liquidity supply-and-demand rules instead of the current patchwork of marking, mitigation, invalidation, and display logic.

The refactor must make every zone explainable. A zone should have one current lifecycle state and one clear reason when it is skipped, invalidated, mitigated, used, or expired.

## Source Material

The strategy rules are based on transcripts from these YouTube videos:

- RD Forex: `FULL course for LIQUIDITY supply and demand best NEW trading strategy 2026`
  `https://www.youtube.com/watch?v=kxh_3__oAqg`
- ArgerFX: `The Only Supply & Demand Blueprint You Need (Mechanical Rules)`
  `https://www.youtube.com/watch?v=mRheKDk5EFI`
- ArgerFX: `copy this 4 step Liquidity S&D trading strategy (Proven Profitable)`
  `https://www.youtube.com/watch?v=12MN4AZ9Xsg`
- Mangoe: `The Supply & Demand Strategy That Changed My Life (2026 FULL COURSE)`
  `https://www.youtube.com/watch?v=rO5els-o3Oo`
- Mangoe: `How I Enter All My Trades (Supply & Demand)`
  `https://www.youtube.com/watch?v=kqa8YM5whpQ`

Rule priority:

1. RD Forex rules are primary because the user explicitly named RD Forex first.
2. ArgerFX rules are used to make ambiguous mechanics more deterministic.
3. Mangoe rules are used when they agree with RD/ArgerFX or clarify entries and invalidation.
4. User-approved script additions remain allowed only when they do not conflict with the YouTube rules. The 24-hour zone expiry remains configurable.

## Core Definitions

Demand zone:

- The last bearish candle before a strong bullish displacement.
- Normal bounds use the full origin candle wick range.
- Accuracy bounds may narrow the zone when the displacement candle creates a better extreme, following the YouTube accuracy-zone rule.

Supply zone:

- The last bullish candle before a strong bearish displacement.
- Normal bounds use the full origin candle wick range.
- Accuracy bounds may narrow the zone when the displacement candle creates a better extreme, following the YouTube accuracy-zone rule.

Liquidity:

- A visible swing in front of the zone.
- Demand liquidity is sell-side liquidity below the pullback.
- Supply liquidity is buy-side liquidity above the pullback.
- One-candle liquidity is not valid by default.
- RD minimum: at least two opposite-direction candles must form the liquidity leg.

Break of structure:

- Demand confirmation requires price to break the relevant high after the liquidity pullback.
- Supply confirmation requires price to break the relevant low after the liquidity pullback.
- The broken level is the structure level created by the same liquidity swing, not an unrelated far level.

Untapped/fresh:

- A zone is fresh only if no later candle touches the zone before the valid entry return.
- Departure candles of the same direction as the displacement do not count as taps.
- Opposite-color candles touching or wicking into the zone before the setup is armed invalidate the zone.

## Zone State Machine

Every zone moves through this lifecycle:

```text
Candidate -> Fresh -> LiquidityFormed -> Confirmed -> Armed -> Used
                                             |
                                             -> Mitigated

Candidate/Fresh/LiquidityFormed/Confirmed/Armed -> Invalid
Fresh/Confirmed/Armed -> Expired
```

State meanings:

- `Candidate`: possible origin candle found, but not enough proof yet.
- `Fresh`: origin candle and displacement are valid, and the zone has not been tapped.
- `LiquidityFormed`: valid visual liquidity exists in front of the zone and does not touch the zone.
- `Confirmed`: price broke structure in the intended direction after forming liquidity.
- `Armed`: price has swept/engaged liquidity and is allowed to return to the zone for entry.
- `Mitigated`: price returned to a confirmed/armed zone and rejected it, but no trade was opened.
- `Used`: a trade was opened from the zone.
- `Invalid`: one of the rule-breaking events happened.
- `Expired`: the zone exceeded configured age and has no open trade.

## Formation Rules

Demand formation:

1. Find the last bearish candle before a bullish displacement.
2. Displacement must be clear enough to imply institutional demand. The initial implementation should require at least one strong bullish close away from the origin, with an input for strict `bearish -> bullish -> bullish`.
3. Draw normal demand from origin high to origin low.
4. If accuracy-zone conditions apply, draw the narrowed YouTube accuracy version.

Supply formation:

1. Find the last bullish candle before a bearish displacement.
2. Displacement must be clear enough to imply institutional supply. The initial implementation should require at least one strong bearish close away from the origin, with an input for strict `bullish -> bearish -> bearish`.
3. Draw normal supply from origin high to origin low.
4. If accuracy-zone conditions apply, draw the narrowed YouTube accuracy version.

Accuracy-zone rule:

- Follow the YouTube rule even on XAUUSD, NAS100, futures, and indices.
- If this does not visually match the user's desired chart behavior, it can later be changed by settings.
- Normal and accuracy zones must be labelled distinctly in debug mode, but clean mode should stay visually premium and minimal.

## Liquidity Rules

A zone cannot become tradable until liquidity is formed and confirmed.

Valid liquidity must:

- Be in front of the zone, not inside the zone.
- Not touch the zone.
- Be a visual swing, not a single-candle pullback.
- Be formed by at least two opposite-color candles by default.
- Later take out its own high for demand, or its own low for supply.

Liquidity distance:

- Liquidity too far from the zone should reject the setup or downgrade it.
- The first implementation should expose this as an input measured as a percent of the zone-to-structure leg, with a conservative default.

## Confirmation Rules

After valid liquidity forms:

- Demand must break the relevant high in the bullish direction.
- Supply must break the relevant low in the bearish direction.
- If price returns to the zone before this confirmation, the zone is invalid.
- Confirmation should be close-based by default, with an input to allow wick-based confirmation for replay experimentation.

## Invalidation Rules

Invalidate and remove/hide the zone when:

- Price touches the zone before liquidity and BOS confirmation.
- Liquidity touches the zone.
- A candle closes inside the zone before valid entry.
- Price breaks through the distal edge.
- Opposite-color candle touches the zone during departure.
- The zone exceeds its configured lifetime and has no open trade.
- The zone is too large for the configured maximum.

Do not mark a premature return as mitigation. It is invalidation.

Do not let historical or display-pruned zones silently remain tradable.

## Entry Rules

The default entry model is directional close:

- Demand: candle taps/wicks the armed zone, rejects, does not close inside, then closes bullish.
- Supply: candle taps/wicks the armed zone, rejects, does not close inside, then closes bearish.

Optional entry model:

- Break-of-candle entry may be added as an advanced mode.
- Demand: enter when price breaks the previous candle high after zone tap.
- Supply: enter when price breaks the previous candle low after zone tap.

Stop-loss:

- Default standard entry stop goes beyond the deepest wick involved in the zone/tap, plus buffer.
- Flip/advanced entries may use candle-based stops later, but are not part of the first refactor slice.

Targets:

- Keep the existing strategy target logic initially unless it conflicts with entry validity.
- The rule engine should expose enough state to later support RD-specific TP behavior.

## Expiry Rule

The user-requested expiry rule stays:

- Default zone validity is 24 hours.
- The value is configurable.
- If no trade has opened from the zone and the zone is older than the configured lifetime, mark it `Expired`.
- If a trade is open from the zone, keep the zone alive until the trade finishes.

## Architecture

The refactor should separate the current monolithic behavior into focused Pine functions:

- `detect_origin_zone()`: finds candidate demand/supply origin candles.
- `apply_zone_bounds()`: normal vs accuracy bounds.
- `validate_departure()`: confirms same-direction displacement and departure tap exceptions.
- `update_liquidity_state()`: finds and validates liquidity swings.
- `update_confirmation_state()`: detects BOS / structure break.
- `update_zone_lifecycle()`: invalidation, expiry, armed, mitigated, used.
- `draw_zone()`: visual rendering only.
- `evaluate_entry()`: trade eligibility only.

The functions should mutate the existing `Core.Zone` structure only through clear state transitions.

## Data Model Additions

Add or repurpose fields so the strategy can explain each zone:

- `state`: candidate/fresh/liquidity/confirmed/armed/mitigated/used/invalid/expired.
- `stateReason`: short reason for the current state.
- `originBarIndex`: source candle for the zone.
- `departureEndBarIndex`: last candle used to confirm displacement.
- `firstInvalidBarIndex`: first bar that invalidated the zone.
- `liquiditySwingBarIndex`: swing used as inducement/liquidity.
- `structureBreakBarIndex`: BOS confirmation bar.
- `entryEligibleBarIndex`: first bar where the zone became armed.

If token budget is tight, encode `state` as an integer and keep only one reason string.

## Display Rules

Clean mode:

- Show only valid, confirmed, armed, mitigated, or used zones according to display settings.
- Do not show invalid candidate zones.
- Labels stay small and premium.

Debug mode:

- Show state/reason labels.
- Show why a zone was skipped or invalidated.
- Show normal vs accuracy boundary decision.
- Show liquidity and BOS anchors.

## Testing and Verification

Because Pine cannot be unit-tested like Python, verification should use three layers:

1. Static checks:
   - No negative-step Pine loops.
   - No forbidden future references for zone/liquidity discovery.
   - Parameter contract script still passes.

2. Deterministic replay checks:
   - XAUUSD 5m examples from the user's screenshots.
   - A supply setup where premature return closes inside the zone must invalidate.
   - A demand setup where same-direction departure wicks do not count as taps.
   - A liquidity swing made from only one opposite candle must not arm the zone.

3. TradingView visual QA:
   - Compare clean mode and debug mode.
   - Confirm no runtime timeout.
   - Confirm max object limits are respected.

## Implementation Slices

1. Add lifecycle state constants and helper functions without changing visuals.
2. Replace zone formation with origin/accuracy/direction rules.
3. Replace liquidity and BOS validation.
4. Replace invalidation/mitigation logic with state transitions.
5. Wire entry eligibility to `Armed` zones only.
6. Rebuild clean/debug drawing around zone state.
7. Optimize loops and object management for TradingView limits.

## Non-Goals

- No change to webhook payloads unless required by renamed fields.
- No change to broker execution logic.
- No new indicators outside the Pine strategy/libraries.
- No attempt to exactly clone proprietary TradingView indicators.

## Approval Gate

Implementation should not begin until the user approves this spec. Once approved, create a step-by-step implementation plan before editing `SND_Strategy.pine`.
