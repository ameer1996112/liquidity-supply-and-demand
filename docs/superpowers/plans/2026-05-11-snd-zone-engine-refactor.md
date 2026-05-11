# SND Zone Engine Refactor Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make `SND_Strategy.pine` draw Liquidity Supply/Demand zones according to the approved transcript rule contract while preserving existing trade execution behavior.

**Architecture:** Keep the script as a single Pine file, but carve the zone engine into explicit helper functions inside `scripts/pinescript/strategies/SND_Strategy.pine`. The first pass corrects source/zone boundary math, the second pass corrects liquidity and own-high/own-low BOS validation, and the final pass removes legacy drawing/invalidation conflicts.

**Tech Stack:** TradingView Pine Script v5, existing `Core.Zone` records, existing `demandZones` and `supplyZones` arrays, existing TradingView drawing objects.

---

## File Structure

- Modify: `scripts/pinescript/strategies/SND_Strategy.pine`
  - Add small local helper functions above `createZone(...)`.
  - Replace only zone boundary calculation, liquidity linking, BOS status, invalidation reason, and visual state code.
  - Do not change entry execution, exit execution, alert payloads, risk sizing, news/session filters, or backend payload fields.
- Reference: `docs/superpowers/specs/2026-05-10-snd-zone-engine-refactor-design.md`
  - Use as the source of truth for the rule contract.
- Create: `docs/superpowers/verification/2026-05-11-snd-zone-engine-refactor-checklist.md`
  - Manual TradingView replay checklist because Pine scripts are verified by chart compilation and replay, not repository unit tests.

## Task 1: Add Explicit Zone Boundary Helpers

**Files:**
- Modify: `scripts/pinescript/strategies/SND_Strategy.pine`

- [ ] **Step 1: Insert boundary helper functions above `createZone(...)`**

Add this block after `trimZoneArrays(bool isDemand) =>` and before `createZone(...)`:

```pinescript
f_body_top(float candleOpen, float candleClose) =>
    math.max(candleOpen, candleClose)

f_body_bottom(float candleOpen, float candleClose) =>
    math.min(candleOpen, candleClose)

f_is_accuracy_zone(bool isDemand, int sourceIdx, int displacementIdx) =>
    bool result = false
    if should_use_accuracy_zones and displacementIdx >= 0
        if isDemand
            result := high[sourceIdx] > high[displacementIdx]
        else
            result := low[sourceIdx] < low[displacementIdx]
    result

f_zone_bounds(bool isDemand, int sourceIdx, int displacementIdx, bool isAccuracy) =>
    float sourceHigh = high[sourceIdx]
    float sourceLow = low[sourceIdx]
    float sourceOpen = open[sourceIdx]
    float sourceClose = close[sourceIdx]
    float displacementHigh = displacementIdx >= 0 ? high[displacementIdx] : na
    float displacementLow = displacementIdx >= 0 ? low[displacementIdx] : na

    float top = na
    float bottom = na

    if isDemand
        float lowerWickBoundary = na(displacementLow) ? sourceLow : math.min(sourceLow, displacementLow)
        top := isAccuracy ? f_body_top(sourceOpen, sourceClose) : sourceHigh
        bottom := lowerWickBoundary
    else
        float upperWickBoundary = na(displacementHigh) ? sourceHigh : math.max(sourceHigh, displacementHigh)
        top := upperWickBoundary
        bottom := isAccuracy ? f_body_bottom(sourceOpen, sourceClose) : sourceLow

    [top, bottom]
```

- [ ] **Step 2: Replace `createZone(...)` accuracy and boundary calculation**

Inside `createZone(...)`, keep the existing `proceed_creation` logic, then replace the current `isAccuracy`, `zTop`, and `zBottom` assignment block with:

```pinescript
        bool isAccuracy = false
        int reactionIdx = baseIdx - 1

        if proceed_creation
            isAccuracy := f_is_accuracy_zone(isDemand, baseIdx, reactionIdx)

        float zTop = na
        float zBottom = na

        if proceed_creation
            [zTop, zBottom] = f_zone_bounds(isDemand, baseIdx, reactionIdx, isAccuracy)

            float max_zone_size = 50.0 * pip_size
            if (zTop - zBottom) > max_zone_size
                true
```

Delete the old confirmed-sweep extension logic:

```pinescript
demandReactionConfirms
demandReactionSweeps
supplyReactionConfirms
supplyReactionSweeps
```

Expected behavior after this task:
- Normal demand includes the first bullish displacement candle wick if that wick goes below the bearish source wick.
- Demand accuracy removes the source candle upper area when the bearish source high is above the first bullish displacement high.
- Normal supply includes the first bearish displacement candle wick if that wick goes above the bullish source wick.
- Supply accuracy removes the source candle lower area when the bullish source low is below the first bearish displacement low.

- [ ] **Step 3: Compile in TradingView**

Copy the script to TradingView and save it.

Expected:
- No Pine compile errors.
- Labels still show `D-`, `S-`, `D-ACC-`, and `S-ACC-`.
- No alerts, entry rules, or exit rules changed by this task.

- [ ] **Step 4: Commit**

```bash
git add scripts/pinescript/strategies/SND_Strategy.pine
git commit -m "DEV-380: correct SND zone boundary rules"
```

## Task 2: Make Source Detection Mechanical and Less Duplicated

**Files:**
- Modify: `scripts/pinescript/strategies/SND_Strategy.pine`

- [ ] **Step 1: Add source candidate helpers near the new boundary helpers**

```pinescript
f_is_demand_source(int sourceIdx, int displacementCount) =>
    bool valid = Utils.is_bearish(close[sourceIdx], open[sourceIdx])
    if valid
        for step = 1 to displacementCount
            int displacementIdx = sourceIdx - step
            if displacementIdx < 0 or not Utils.is_bullish(close[displacementIdx], open[displacementIdx])
                valid := false
    valid

f_is_supply_source(int sourceIdx, int displacementCount) =>
    bool valid = Utils.is_bullish(close[sourceIdx], open[sourceIdx])
    if valid
        for step = 1 to displacementCount
            int displacementIdx = sourceIdx - step
            if displacementIdx < 0 or not Utils.is_bearish(close[displacementIdx], open[displacementIdx])
                valid := false
    valid
```

- [ ] **Step 2: Replace live demand creation chain**

Replace the three live demand `if/else if` branches around the `createZone(3/2/1, true, ...)` calls with:

```pinescript
if barstate.isconfirmed and bar_index > 10
    for displacementCount = 3 to 1
        int sourceIdx = displacementCount
        int sourceBarIdx = bar_index - sourceIdx
        if f_is_demand_source(sourceIdx, displacementCount) and not is_base_bar_used(sourceBarIdx, used_demand_base_times)
            global_zone_id_counter := global_zone_id_counter + 1
            createZone(sourceIdx, true, false, 1, displacementCount, global_zone_id_counter)
            break
```

- [ ] **Step 3: Replace live supply creation chain**

Replace the three live supply `if/else if` branches around the `createZone(3/2/1, false, ...)` calls with:

```pinescript
if barstate.isconfirmed and bar_index > 10
    for displacementCount = 3 to 1
        int sourceIdx = displacementCount
        int sourceBarIdx = bar_index - sourceIdx
        if f_is_supply_source(sourceIdx, displacementCount) and not is_base_bar_used(sourceBarIdx, used_supply_base_times)
            global_zone_id_counter := global_zone_id_counter + 1
            createZone(sourceIdx, false, false, 1, displacementCount, global_zone_id_counter)
            break
```

- [ ] **Step 4: Replace historical scan creation checks**

Inside the `initial_scan_done` block, replace the demand `if/else if` source tests with:

```pinescript
        baseBarIdxDemand = bar_index - i
        for displacementCount = 3 to 1
            if i >= displacementCount and f_is_demand_source(i, displacementCount)
                if not is_base_bar_used(baseBarIdxDemand, used_demand_base_times)
                    global_zone_id_counter := global_zone_id_counter + 1
                    createZone(i, true, true, 1, displacementCount, global_zone_id_counter)
                break
```

Replace the supply `if/else if` source tests with:

```pinescript
        baseBarIdxSupply = bar_index - i
        for displacementCount = 3 to 1
            if i >= displacementCount and f_is_supply_source(i, displacementCount)
                if not is_base_bar_used(baseBarIdxSupply, used_supply_base_times)
                    global_zone_id_counter := global_zone_id_counter + 1
                    createZone(i, false, true, 1, displacementCount, global_zone_id_counter)
                break
```

- [ ] **Step 5: Compile in TradingView**

Expected:
- The same number or fewer duplicate zones.
- The source candle is always the final opposite-color candle immediately before the displacement.
- Compile succeeds with no `break` or loop-scope errors.

- [ ] **Step 6: Commit**

```bash
git add scripts/pinescript/strategies/SND_Strategy.pine
git commit -m "DEV-380: normalize SND source detection"
```

## Task 3: Correct Liquidity Location and Own-High/Own-Low BOS State

**Files:**
- Modify: `scripts/pinescript/strategies/SND_Strategy.pine`

- [ ] **Step 1: Add liquidity touch and BOS helper functions**

Place below the source helpers:

```pinescript
f_liquidity_touches_zone(bool isDemand, float liqPrice, float zoneTop, float zoneBottom, float sideTol) =>
    bool touches = false
    if not na(liqPrice)
        touches := liqPrice <= zoneTop + sideTol and liqPrice >= zoneBottom - sideTol
    touches

f_demand_liq_is_in_front(float liqPrice, float zoneTop, float sideTol) =>
    not na(liqPrice) and liqPrice > zoneTop + sideTol

f_supply_liq_is_in_front(float liqPrice, float zoneBottom, float sideTol) =>
    not na(liqPrice) and liqPrice < zoneBottom - sideTol

f_has_broken_own_level(bool isDemand, float ownLevel) =>
    bool broken = false
    if not na(ownLevel)
        broken := isDemand ? high >= ownLevel : low <= ownLevel
    broken
```

- [ ] **Step 2: Change demand liquidity location checks**

In `f_scan_demand_liquidity(...)`, replace the `use_inducement_linking` location branch with:

```pinescript
                            float sideTol = syminfo.mintick * liq_side_tol_ticks
                            bool touchesZone = f_liquidity_touches_zone(true, pLow, z.top, z.bottom, sideTol)
                            bool isValidLocation = f_demand_liq_is_in_front(pLow, z.top, sideTol) and not touchesZone
                            float distFromZone = pLow - z.top
```

Expected:
- Demand liquidity must be above the demand zone.
- Demand liquidity touching the zone is rejected with a reason in the next step.

- [ ] **Step 3: Change supply liquidity location checks**

In `f_scan_supply_liquidity(...)`, replace the `use_inducement_linking` location branch with:

```pinescript
                            float sideTol = syminfo.mintick * liq_side_tol_ticks
                            bool touchesZone = f_liquidity_touches_zone(false, pHigh, z.top, z.bottom, sideTol)
                            bool isValidLocation = f_supply_liq_is_in_front(pHigh, z.bottom, sideTol) and not touchesZone
                            float distFromZone = z.bottom - pHigh
```

Expected:
- Supply liquidity must be below the supply zone.
- Supply liquidity touching the zone is rejected with a reason in the next step.

- [ ] **Step 4: Set waiting/valid state from own high/low**

In `f_scan_demand_liquidity(...)`, after `z.structureSweepLevel := z.liqHighPrice`, replace the current validity assignment with:

```pinescript
            int minLegCandles = useOneCandleLiquidity ? 1 : 2
            bool hasStrongLeg = demandLegCount >= minLegCandles
            bool ownHighBroken = hasStrongLeg and f_has_broken_own_level(true, z.liqHighPrice)
            z.liquidityValid := ownHighBroken
            z.inactiveReason := ownHighBroken ? na : (hasStrongLeg ? "WAITING_BOS" : "WAITING_STRONG_LIQUIDITY")
```

In `f_scan_supply_liquidity(...)`, after `z.structureSweepLevel := z.liqLowPrice`, replace the current validity assignment with:

```pinescript
            int minLegCandles = useOneCandleLiquidity ? 1 : 2
            bool hasStrongLeg = supplyLegCount >= minLegCandles
            bool ownLowBroken = hasStrongLeg and f_has_broken_own_level(false, z.liqLowPrice)
            z.liquidityValid := ownLowBroken
            z.inactiveReason := ownLowBroken ? na : (hasStrongLeg ? "WAITING_BOS" : "WAITING_STRONG_LIQUIDITY")
```

- [ ] **Step 5: Preserve waiting zones visually**

In the live loops, keep calling `f_scan_demand_liquidity(i)` and `f_scan_supply_liquidity(i)` when zones are waiting. Do not remove waiting zones just because `z.inactiveReason == "WAITING_BOS"`.

Expected:
- Candidate zones can draw as waiting BOS.
- They become valid only after their own high/low is broken.

- [ ] **Step 6: Compile and replay**

Expected:
- Demand example: liquidity swing low forms above demand, then the high that created that swing low is broken before the zone becomes valid.
- Supply example: liquidity swing high forms below supply, then the low that created that swing high is broken before the zone becomes valid.
- A generic later high/low does not mark BOS unless it is the stored `z.liqHighPrice` or `z.liqLowPrice`.

- [ ] **Step 7: Commit**

```bash
git add scripts/pinescript/strategies/SND_Strategy.pine
git commit -m "DEV-380: enforce liquidity own-level BOS"
```

## Task 4: Correct Untapped and Close-Inside Invalidation

**Files:**
- Modify: `scripts/pinescript/strategies/SND_Strategy.pine`

- [ ] **Step 1: Add invalidation helper functions**

Place below liquidity helpers:

```pinescript
f_close_inside_zone(float candleClose, float zoneTop, float zoneBottom) =>
    candleClose <= zoneTop and candleClose >= zoneBottom

f_wick_touches_zone(bool isDemand, float candleHigh, float candleLow, float zoneTop, float zoneBottom) =>
    isDemand ? (candleLow <= zoneTop and candleHigh >= zoneBottom) : (candleHigh >= zoneBottom and candleLow <= zoneTop)

f_is_opposing_tap(bool isDemand, float candleOpen, float candleClose, float candleHigh, float candleLow, float zoneTop, float zoneBottom) =>
    bool opposing = isDemand ? candleClose < candleOpen : candleClose > candleOpen
    opposing and f_wick_touches_zone(isDemand, candleHigh, candleLow, zoneTop, zoneBottom)
```

- [ ] **Step 2: Keep same-color departure wicks valid**

In the demand live loop, only mark `touchedPreSweep` for a bearish opposing tap after `z.leftZone` is true:

```pinescript
                bool opposing_tap = f_is_opposing_tap(true, open, close, high, low, z.top, z.bottom)
                bool closes_inside = f_close_inside_zone(close, z.top, z.bottom)
                bool current_bar_sweeping = not na(z.structureSweepLevel) and high >= z.structureSweepLevel

                if is_future_bar and z.leftZone and not z.liquiditySwept and (opposing_tap or closes_inside)
                    z.lastTouchBar := bar_index
                    z.wasTouched := true
                    z.touchedPreSweep := true
                    z.inactiveReason := closes_inside ? "CLOSE_INSIDE" : "OPPOSING_TAP"

                if is_future_bar and z.leftZone and not z.liquiditySwept and (opposing_tap or closes_inside) and not current_bar_sweeping
                    z.mitigated := true
```

In the supply live loop, mirror the same code:

```pinescript
                bool opposing_tap = f_is_opposing_tap(false, open, close, high, low, z.top, z.bottom)
                bool closes_inside = f_close_inside_zone(close, z.top, z.bottom)
                bool current_bar_sweeping = not na(z.structureSweepLevel) and low <= z.structureSweepLevel

                if is_future_bar and z.leftZone and not z.liquiditySwept and (opposing_tap or closes_inside)
                    z.lastTouchBar := bar_index
                    z.wasTouched := true
                    z.touchedPreSweep := true
                    z.inactiveReason := closes_inside ? "CLOSE_INSIDE" : "OPPOSING_TAP"

                if is_future_bar and z.leftZone and not z.liquiditySwept and (opposing_tap or closes_inside) and not current_bar_sweeping
                    z.mitigated := true
```

- [ ] **Step 3: Stop removal loops from deleting valid waiting zones too early**

In the later demand removal loop, replace:

```pinescript
                bool bearish_close_inside = current_close <= z.top and current_close >= z.bottom
                bool close_below_zone     = current_close < z.bottom
                bool wick_below_zone = current_low < z.bottom

                if bearish_close_inside or close_below_zone or isTooOld or (invalidate_on_wick and wick_below_zone)
                    remove_zone_all_arrays(true, i)
```

with:

```pinescript
                bool close_inside = f_close_inside_zone(current_close, z.top, z.bottom)
                bool close_below_zone = current_close < z.bottom
                bool wick_below_zone = current_low < z.bottom
                bool can_remove_for_entry_failure = z.leftZone and (close_inside or close_below_zone or (invalidate_on_wick and wick_below_zone))

                if can_remove_for_entry_failure or isTooOld
                    remove_zone_all_arrays(true, i)
```

In the supply removal loop, replace:

```pinescript
            bool bullish_close_inside = current_close >= z.bottom and current_close <= z.top
            bool close_above_zone     = current_close > z.top
            bool wick_above_zone = current_high > z.top

            if bullish_close_inside or close_above_zone or isTooOld or (invalidate_on_wick and wick_above_zone)
                remove_zone_all_arrays(false, i)
```

with:

```pinescript
            bool close_inside = f_close_inside_zone(current_close, z.top, z.bottom)
            bool close_above_zone = current_close > z.top
            bool wick_above_zone = current_high > z.top
            bool can_remove_for_entry_failure = z.leftZone and (close_inside or close_above_zone or (invalidate_on_wick and wick_above_zone))

            if can_remove_for_entry_failure or isTooOld
                remove_zone_all_arrays(false, i)
```

- [ ] **Step 4: Compile and replay**

Expected:
- Same-color departure candles can wick into their own source zone and the zone remains alive.
- Opposing candle tap before entry marks invalid.
- Close inside zone marks invalid.
- Zones are not deleted before they have properly left the zone.

- [ ] **Step 5: Commit**

```bash
git add scripts/pinescript/strategies/SND_Strategy.pine
git commit -m "DEV-380: correct SND untapped invalidation"
```

## Task 5: Clean Visual State and Debug Reasons

**Files:**
- Modify: `scripts/pinescript/strategies/SND_Strategy.pine`

- [ ] **Step 1: Add zone visual state helper**

Place near the visual helper functions:

```pinescript
f_zone_state_text(Core.Zone z) =>
    string stateText = "VALID"
    if not z.active
        stateText := "INVALID"
    else if z.mitigated
        stateText := "MITIGATED"
    else if not na(z.inactiveReason) and str.length(z.inactiveReason) > 0
        stateText := z.inactiveReason
    else if z.liquidityValid
        stateText := "VALID_LIQ"
    stateText

f_zone_border_color(bool isDemand, bool isAccuracy, string stateText) =>
    color c = isDemand ? col_demand_border : col_supply_border
    if str.contains(stateText, "WAITING")
        c := col_waiting_bos_border
    else if isAccuracy
        c := isDemand ? col_acc_demand_border : col_acc_supply_border
    c

f_zone_bg_color(bool isDemand, bool isAccuracy, string stateText) =>
    color c = isDemand ? col_demand_bg : col_supply_bg
    if str.contains(stateText, "WAITING")
        c := col_waiting_bos_bg
    else if isAccuracy
        c := isDemand ? col_acc_demand_bg : col_acc_supply_bg
    c
```

- [ ] **Step 2: Use the helper where boxes are updated**

Where demand and supply boxes are extended or recolored after creation, set:

```pinescript
string stateText = f_zone_state_text(z)
box.set_bgcolor(z.boxId, f_zone_bg_color(true, z.isAccuracy, stateText))
box.set_border_color(z.boxId, f_zone_border_color(true, z.isAccuracy, stateText))
```

For supply, use:

```pinescript
string stateText = f_zone_state_text(z)
box.set_bgcolor(z.boxId, f_zone_bg_color(false, z.isAccuracy, stateText))
box.set_border_color(z.boxId, f_zone_border_color(false, z.isAccuracy, stateText))
```

- [ ] **Step 3: Add optional debug reason to labels**

When `show_debug_labels` is true and `z.inactiveReason` is set, append the reason to the zone label:

```pinescript
if show_debug_labels and not na(z.inactiveReason) and str.length(z.inactiveReason) > 0 and not na(z.idLabel)
    label.set_text(z.idLabel, label.get_text(z.idLabel) + " " + z.inactiveReason)
```

Do this only in the existing label update path, not inside every bar loop, so the text does not grow repeatedly.

- [ ] **Step 4: Compile and inspect chart**

Expected:
- Waiting BOS boxes use waiting colors.
- Accuracy zones keep accuracy labels and borders once valid.
- Invalid reasons are readable when debug labels are enabled.
- Liquidity lines still update and stop through existing `clearDemandLiquidityVisual`, `clearSupplyLiquidityVisual`, `updateDemandLiquidityVisual`, and `updateSupplyLiquidityVisual`.

- [ ] **Step 5: Commit**

```bash
git add scripts/pinescript/strategies/SND_Strategy.pine
git commit -m "DEV-380: clean SND zone visual states"
```

## Task 6: Remove Dead Legacy Boundary Logic Safely

**Files:**
- Modify: `scripts/pinescript/strategies/SND_Strategy.pine`

- [ ] **Step 1: Search only the Pine file for legacy variables**

Run:

```bash
rg -n "clusterBodyHigh|clusterBodyLow|clusterWickHigh|clusterWickLow|demandReactionConfirms|demandReactionSweeps|supplyReactionConfirms|supplyReactionSweeps|v3\\.2|Mangoe" scripts/pinescript/strategies/SND_Strategy.pine
```

Expected:
- `demandReactionConfirms`, `demandReactionSweeps`, `supplyReactionConfirms`, and `supplyReactionSweeps` should have no matches.
- `clusterBodyHigh`, `clusterBodyLow`, `clusterWickHigh`, and `clusterWickLow` should only remain if they still feed scoring or base quality.

- [ ] **Step 2: Remove unused cluster-only variables if they are not referenced**

If `clusterBodyHigh`, `clusterBodyLow`, `clusterWickHigh`, or `clusterWickLow` are only assigned and never used after Task 1, remove their assignments from `createZone(...)`. Keep `clusterHigh`, `clusterLow`, `actualCandlesInBase`, and `base_width` because they feed base quality and scoring.

Expected retained block:

```pinescript
        float clusterHigh = baseHigh
        float clusterLow  = baseLow
        int   actualCandlesInBase = 1
        int   max_base_lookback = 15
```

Expected retained expansion:

```pinescript
            if scan_high > clusterHigh
                clusterHigh := scan_high
            if scan_low < clusterLow
                clusterLow := scan_low
            actualCandlesInBase += 1
```

- [ ] **Step 3: Compile in TradingView**

Expected:
- No compile errors.
- Zone scoring still works.
- No label or table fields disappear.

- [ ] **Step 4: Commit**

```bash
git add scripts/pinescript/strategies/SND_Strategy.pine
git commit -m "DEV-380: remove legacy SND boundary code"
```

## Task 7: Manual Verification Checklist

**Files:**
- Create: `docs/superpowers/verification/2026-05-11-snd-zone-engine-refactor-checklist.md`

- [ ] **Step 1: Create the checklist file**

```markdown
# SND Zone Engine Refactor Verification Checklist

Ticket: DEV-380

## Compile

- [ ] `SND_Strategy.pine` saves in TradingView without Pine compiler errors.
- [ ] Existing alerts still compile.
- [ ] Existing strategy entries and exits still appear.

## Zone Boundary Examples

- [ ] Normal demand top is bearish source high.
- [ ] Normal demand bottom is the lower of bearish source low and first bullish displacement low.
- [ ] Demand accuracy triggers when bearish source high is higher than first bullish displacement high.
- [ ] Demand accuracy top is source body top, not full source high.
- [ ] Demand accuracy bottom still includes the lower wick boundary.
- [ ] Normal supply bottom is bullish source low.
- [ ] Normal supply top is the higher of bullish source high and first bearish displacement high.
- [ ] Supply accuracy triggers when bullish source low is lower than first bearish displacement low.
- [ ] Supply accuracy bottom is source body bottom, not full source low.
- [ ] Supply accuracy top still includes the upper wick boundary.

## Liquidity And BOS

- [ ] Demand liquidity is a swing low in front of and above the demand zone.
- [ ] Supply liquidity is a swing high in front of and below the supply zone.
- [ ] Liquidity touching the zone is rejected.
- [ ] Demand zone waits until the high that created the swing low is broken.
- [ ] Supply zone waits until the low that created the swing high is broken.
- [ ] Waiting BOS zones use waiting colors and are not tradeable as fully valid.

## Untapped And Entry Tap

- [ ] Same-color departure wicks do not invalidate the zone.
- [ ] Opposing candle tap before valid entry invalidates the zone.
- [ ] Close inside the zone invalidates the entry.
- [ ] Wick into the zone without close-inside can still give a valid reaction.

## Regression

- [ ] Webhook payload shape is unchanged.
- [ ] Risk sizing is unchanged.
- [ ] TP/SL logic is unchanged.
- [ ] News/session filters are unchanged.
- [ ] Backend AI filtering fields are unchanged.
```

- [ ] **Step 2: Fill the checklist during TradingView replay**

Use GBPJPY 5m and at least one supply example from the user screenshots. Mark every item that passes.

- [ ] **Step 3: Commit**

```bash
git add docs/superpowers/verification/2026-05-11-snd-zone-engine-refactor-checklist.md
git commit -m "DEV-380: add SND zone verification checklist"
```

## Task 8: Final Review and Ticket Update

**Files:**
- Modify only if needed after review: `scripts/pinescript/strategies/SND_Strategy.pine`

- [ ] **Step 1: Review git diff**

Run:

```bash
git diff --stat HEAD~7..HEAD
git diff HEAD~7..HEAD -- scripts/pinescript/strategies/SND_Strategy.pine
```

Expected:
- Changes are confined to zone detection, liquidity, invalidation, and visuals.
- No alert payload, risk sizing, TP/SL, backend, or execution code was changed.

- [ ] **Step 2: Run targeted text checks**

Run:

```bash
rg -n "strategy\\.entry|strategy\\.exit|alert\\(|webhook|risk|tp|sl|take_profit|stop_loss" scripts/pinescript/strategies/SND_Strategy.pine
```

Expected:
- Existing lines may appear.
- No new edits in those sections unless explicitly reviewed and documented.

- [ ] **Step 3: Close Jira ticket after implementation is complete**

Run:

```bash
curl -s -X POST "http://localhost:8000/api/tickets/DEV-380/ai-update" \
  -H "Content-Type: application/json" \
  -d '{"new_status":"done","summary_of_work":"Refactored SND zone boundary, liquidity, BOS, invalidation, and visual state logic to match the approved Liquidity Supply/Demand rule contract while preserving entry and execution behavior.","agent":"codex"}'
```

Expected:
- Local ticket proxy accepts the update.

## Self-Review

Spec coverage:
- Source candle selection is covered by Task 2.
- Normal and accuracy boundaries are covered by Task 1.
- Untapped and close-inside rules are covered by Task 4.
- Liquidity swing location and one/two-candle strength are covered by Task 3.
- Own-high/own-low BOS is covered by Task 3.
- Waiting BOS visual state and debug reasons are covered by Task 5.
- Manual TradingView verification is covered by Task 7.
- Trade execution non-goals are protected by Task 8.

Placeholder scan:
- No banned placeholder markers remain.

Type consistency:
- Helper names are consistent across tasks.
- Existing field names match observed script fields: `z.top`, `z.bottom`, `z.active`, `z.mitigated`, `z.leftZone`, `z.liquidityValid`, `z.liquiditySwept`, `z.inactiveReason`, `z.liqHighPrice`, `z.liqLowPrice`, `z.structureSweepLevel`, `z.idLabel`, and `z.isAccuracy`.
