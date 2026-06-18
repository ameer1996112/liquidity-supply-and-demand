# Zone Lifecycle and Invalidation Optimization

## Purpose
To optimize the zone lifecycle in `SND_Raw_RD_Forex.pine` so that zones are not prematurely invalidated by arbitrary rules, while ensuring strict structural invalidation when the zone boundaries are breached.

## Current Issues
1. **Premature Invalidation (Return Before Sweep):** The script currently invalidates zones if price touches them before sweeping the opposing liquidity target. This kills perfectly valid setups where price returns to mitigate the origin after grabbing internal inducement.
2. **Infinite Lifespan on Chop:** Zones currently never die from being chopped through or touched repeatedly; they only die on a break or the "return before sweep" rule.

## Optimized Zone Lifecycle Rules

### 1. Multi-Touch Mitigation (Chop is Allowed)
- A zone does **not** die simply because it was touched, nor is there a limit to how many times it can be touched. 
- Price is allowed to chop inside the zone, bounce off it, or consolidate within it.
- **Action:** The `returnedBeforeSweep` invalidation logic will be completely removed. Zones will no longer die for returning before hitting a liquidity target.

### 2. Strict Boundary Invalidation (Wick Break = Dead)
- The zone's absolute boundaries (the high/low) are the ultimate line of defense.
- **Demand Zone:** If price wicks below the bottom boundary (or closes below it), the zone is instantly invalidated.
- **Supply Zone:** If price wicks above the top boundary (or closes above it), the zone is instantly invalidated.
- **Action:** The invalidation logic will strictly evaluate `wickBreak` and `closeBreak`. If either occurs at any point after the zone is created, the zone dies.

## Code Changes Required
- In `processZone()`, delete the `returnedBeforeSweep` boolean and all related logic.
- Ensure `invalidateNow := closeBreak or wickBreak`.
- Ensure `wickBreak` accurately checks if `low < z.bottom` (for demand) or `high > z.top` (for supply).

## Verification
- Zones that are chopped through (but not broken) will remain active.
- Zones that are pierced by a single tick (wick break) will be correctly removed from the chart or marked inactive immediately.
