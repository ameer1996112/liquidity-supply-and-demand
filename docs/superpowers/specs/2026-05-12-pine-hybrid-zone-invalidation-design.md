# Pine Hybrid Zone Invalidation Design

## Context

The S&D Pine strategy currently creates visually acceptable supply and demand zones, but invalidation has been unstable across recent experiments. Aggressive historical invalidation scans removed too many zones and broke the chart marking. The next change should keep zone detection and marking intact while tightening how zones transition from active to mitigated to removed.

## Goal

Implement hybrid invalidation:

- A wick or retouch after price leaves a zone marks the zone as mitigated.
- A zone is removed only when a confirmed candle closes through the far side of the zone.
- Zone creation, historical marking, visual priority, and full-wick zone boundaries remain unchanged.

## Behavioral Rules

Demand zones:

- A demand zone is considered left after a confirmed close above `z.top`.
- After it has been left, any candle whose range overlaps the zone can mark it mitigated.
- The zone is removed only when a confirmed candle closes below `z.bottom`.
- Wicks below `z.bottom` do not remove the zone.

Supply zones:

- A supply zone is considered left after a confirmed close below `z.bottom`.
- After it has been left, any candle whose range overlaps the zone can mark it mitigated.
- The zone is removed only when a confirmed candle closes above `z.top`.
- Wicks above `z.top` do not remove the zone.

## State Model

Use the existing zone fields:

- `z.leftZone`: true after price has fully left the zone in the expected direction.
- `z.mitigated`: true after a post-left retouch before liquidity is swept.
- `z.active`: remains true until close-through invalidation or trade entry deactivates it.

The departure candle must not mitigate the zone on the same bar it sets `leftZone`. The code should capture `wasLeftZone = z.leftZone` before updating `leftZone`, then only allow mitigation/removal using `wasLeftZone`.

## Implementation Shape

Keep the change local to the existing demand and supply maintenance loops in `SND_Strategy.pine`.

Do not reintroduce historical invalidation replay helpers. Historical zones should be drawn using the existing creation logic and then managed forward from the current replay state.

Replace the current removal conditions:

- Demand removal should only use `current_close < z.bottom`.
- Supply removal should only use `current_close > z.top`.

Mitigation should use overlap checks:

- Demand overlap: `current_low <= z.top and current_high >= z.bottom`.
- Supply overlap: `current_high >= z.bottom and current_low <= z.top`.

The overlap formula is intentionally symmetric because a candle range intersects a price zone the same way in both directions.

## Testing And Verification

Verification should include:

- `git diff --check -- scripts/pinescript/strategies/SND_Strategy.pine`
- `node mcp/tradingview-mcp/src/cli/index.js pine analyze --file scripts/pinescript/strategies/SND_Strategy.pine`
- `node mcp/tradingview-mcp/src/cli/index.js pine check --file scripts/pinescript/strategies/SND_Strategy.pine`
- Push to TradingView via MCP, save, compile, and confirm only existing severity-4 warnings remain.
- Inspect active boxes on XAUUSD 5m replay to confirm zone marking count does not collapse like the rejected historical invalidation experiment.

## Out Of Scope

- No changes to zone detection.
- No changes to visual styling.
- No changes to max visible zone priority.
- No historical replay invalidation scan.
- No strategy entry model changes beyond respecting the existing `z.mitigated` gate.
