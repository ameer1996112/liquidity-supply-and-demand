# RD Zone Lifecycle Gate Design

## Context

The current SND Pine strategy can judge zone invalidation too early. In the 01:05-style demand case, the expected RD lifecycle is that origin and departure candles are part of forming the setup, not future mitigation or invalidation. A zone should not be removed by close-inside, close-break, wick-break, or return-before-sweep checks until the zone has confirmed departure and invalidation judging has started.

This design applies to `scripts/pinescript/strategies/SND_Strategy.pine`. It keeps zone detection and liquidity detection mostly unchanged. The patch should only add a lifecycle gate around invalidation plus limited debug visibility.

## Goal

Implement Approach 1: lifecycle-gate invalidation before any behavior rewrite.

Done means:

- A demand zone like the 01:05 origin zone, high `214.989` and low `214.866`, is not removed by formation or departure candles.
- Pre-confirmation candles never invalidate a zone.
- Pre-sweep returns invalidate only after confirmation and runtime departure.
- Post-sweep returns become mitigation, not invalidation.
- Existing zone entry behavior remains otherwise unchanged.
- Debug can show why a zone is allowed or blocked from invalidation judging.

## Non-Goals

- Do not rewrite liquidity detection.
- Do not introduce the full explicit RD state machine yet.
- Do not change entry model selection, risk, alerts, webhook payload shape, or backend execution logic.
- Do not change unrelated Pine indicators.

## Design

### Lifecycle Gate

Add or derive these lifecycle values for each zone:

- `confirmationBar`: the bar where the zone is considered confirmed after valid departure/displacement.
- `invalidationStartBar`: the first bar where invalidation checks are allowed.
- `departedAfterConfirmation`: true only after price departs the zone after `confirmationBar`.
- `canJudgeInvalidation`: true only when the zone has confirmed and has runtime departure after confirmation.

Do not rely on `z.leftZone` alone for invalidation. The strategy currently initializes `z.leftZone` from formation history, which is useful for drawing and compatibility but unsafe as a future-lifecycle signal. The implementation should either reset invalidation-specific departure tracking after confirmation or add a separate runtime boolean such as `runtimeLeftZoneAfterConfirmation`.

### Demand Rules

For demand zones:

- Departure after confirmation is price closing or trading above `z.top`, using the reference behavior chosen in the existing code path.
- Close invalidation is `close < z.bottom`, only after `invalidationStartBar`.
- Wick invalidation is `low < z.bottom`, only after `invalidationStartBar` and only if wick invalidation is enabled.
- Return-before-sweep invalidation is overlap or close back into the zone after `invalidationStartBar`, before valid liquidity sweep.
- After liquidity is swept, a valid return into the demand zone is mitigation, not invalidation.

### Supply Rules

For supply zones:

- Departure after confirmation is price closing or trading below `z.bottom`, using the reference behavior chosen in the existing code path.
- Close invalidation is `close > z.top`, only after `invalidationStartBar`.
- Wick invalidation is `high > z.top`, only after `invalidationStartBar` and only if wick invalidation is enabled.
- Return-before-sweep invalidation is overlap or close back into the zone after `invalidationStartBar`, before valid liquidity sweep.
- After liquidity is swept, a valid return into the supply zone is mitigation, not invalidation.

### Invalidation Shape

The invalidation decision should be structured like:

```pine
canJudgeInvalidation = afterConfirmation and departedAfterConfirmation

invalidateNow =
     expiredByAge or
     (
         canJudgeInvalidation and
         not validSweepOrProof and
         (
             returnedBeforeSweep or
             closeInsideZoneInvalidates or
             closeBreakInvalidates or
             wickBreakInvalidates
         )
     )
```

Age expiration can remain outside the lifecycle gate. Every price-action invalidation branch must be inside the lifecycle gate.

### Debug

Add limited debug output only where it helps inspect this lifecycle:

- Zone id.
- Origin bar or time.
- `confirmationBar`.
- `invalidationStartBar`.
- Runtime departed state.
- `canJudgeInvalidation`.
- Removal reason.

Debug should be controlled by existing debug settings and should not increase normal chart noise.

## Data Flow

1. Zone is created from the existing detection flow.
2. Strategy records or derives confirmation after valid departure.
3. Runtime departure tracking starts from confirmation, separate from historical `leftZone`.
4. Invalidation logic evaluates only if `canJudgeInvalidation` is true.
5. Before valid liquidity sweep, a gated return can invalidate.
6. After valid liquidity sweep, return into the zone is mitigation.
7. Zone DB/debug records the removal or mitigation reason.

## Risks

- If confirmation is derived too late, zones may survive longer than the reference indicator.
- If confirmation is derived too early, the 01:05-style bug can remain.
- Pine token pressure is already a concern, so the patch should prefer compact derived booleans over a large explicit state machine.
- Existing `inactiveReason` has dual UI and validity meaning. New debug reasons should not accidentally block live-entry checks unless intended.

## Validation

Use focused validation:

- Static check that every price-action invalidation condition is gated by `canJudgeInvalidation`.
- Pine compile check with `node mcp/tradingview-mcp/src/cli/index.js pine check --file scripts/pinescript/strategies/SND_Strategy.pine` if the local TradingView MCP is available.
- Manual TradingView replay or screenshot comparison for the 01:05 demand zone case.
- Confirm post-sweep returns still mitigate and do not remain active as fresh zones.

## Implementation Plan Handoff

The next step is to write an implementation plan for the smallest safe patch:

1. Locate demand and supply invalidation branches in `processZone` or the current equivalent invalidation loops.
2. Add compact lifecycle booleans.
3. Wrap all price-action invalidation branches in the lifecycle gate.
4. Add limited debug fields.
5. Run Pine validation and update any mobile-copy artifact if one exists.
