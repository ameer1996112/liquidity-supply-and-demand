# Pine Hybrid Zone Invalidation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Change S&D zone invalidation so post-departure wick touches mark a zone mitigated, while only a confirmed close through the far side removes the zone.

**Architecture:** Keep the existing zone detection, drawing, priority, and liquidity scan paths intact. Modify only the active zone maintenance/removal logic in `SND_Strategy.pine`, using the existing `Core.Zone` fields `leftZone`, `mitigated`, `active`, `lastTouchBar`, `wasTouched`, `touchedPreSweep`, `peakPrice`, and `peakBarIndex`.

**Tech Stack:** Pine Script v6 strategy, existing `SND_Core` zone model, local TradingView MCP CLI for Pine analysis/compile/update.

---

## File Structure

- Modify: `scripts/pinescript/strategies/SND_Strategy.pine`
  - Remove the obsolete `invalidate_on_wick` setting because hybrid invalidation no longer removes zones on wick touch.
  - Update demand maintenance around the `cached_demand_size` loop so mitigation uses post-left range overlap and cannot trigger on the departure candle.
  - Update supply maintenance around the `cached_supply_size` loop using the same post-left overlap model.
  - Update active zone removal passes so demand removes only on a post-left close below `z.bottom`, and supply removes only on a post-left close above `z.top`.
- Do not modify: `scripts/pinescript/libraries/SND_Core.pine`
  - The existing zone fields are sufficient.
- Do not modify: `scripts/pinescript/libraries/SND_Utils.pine`
  - No helper changes are required.

## Task 1: Remove Obsolete Wick-Removal Setting

**Files:**
- Modify: `scripts/pinescript/strategies/SND_Strategy.pine:169`

- [ ] **Step 1: Confirm the setting is only used by removal logic**

Run:

```bash
rg -n "invalidate_on_wick" scripts/pinescript/strategies/SND_Strategy.pine
```

Expected output before the change:

```text
169:invalidate_on_wick   = input.bool(true, "Invalidate on Wick Touch", group = "📐 Zone Detection")
3079:                if close_inside_zone or close_below_zone or (invalidate_on_wick and wick_below_zone)
3097:            if close_inside_zone or close_above_zone or (invalidate_on_wick and wick_above_zone)
```

- [ ] **Step 2: Delete the setting line**

Remove this exact line:

```pine
invalidate_on_wick   = input.bool(true, "Invalidate on Wick Touch", group = "📐 Zone Detection")
```

- [ ] **Step 3: Verify the setting name only remains in the old removal conditions**

Run:

```bash
rg -n "invalidate_on_wick" scripts/pinescript/strategies/SND_Strategy.pine
```

Expected output after Step 2 and before Task 4:

```text
3078:                if close_inside_zone or close_below_zone or (invalidate_on_wick and wick_below_zone)
3096:            if close_inside_zone or close_above_zone or (invalidate_on_wick and wick_above_zone)
```

The line numbers may move by one after deleting the input; the only remaining matches must be inside the active demand/supply removal passes.

## Task 2: Convert Demand Mitigation To Post-Left Range Overlap

**Files:**
- Modify: `scripts/pinescript/strategies/SND_Strategy.pine:2917-2966`

- [ ] **Step 1: Locate the current demand maintenance block**

Run:

```bash
sed -n '2910,2970p' scripts/pinescript/strategies/SND_Strategy.pine
```

Expected: the block starts with `if current_close > z.top and not z.leftZone` and contains `closes_inside`, `breaches_zone`, and `wicks_into_zone`.

- [ ] **Step 2: Replace the demand departure and mitigation block**

Replace the block from:

```pine
            if current_close > z.top and not z.leftZone
```

through:

```pine
                    z.mitigated := true
```

with:

```pine
            bool wasLeftZone = z.leftZone
            if current_close > z.top and not z.leftZone
                z.leftZone := true
                z.leftWithBearish := current_close < current_open

            if not z.mitigated
                bool is_future_bar = not na(z.createdBarIndex) and bar_index > z.createdBarIndex

                bool overlaps_zone = low <= z.top and high >= z.bottom

                bool current_bar_sweeping = not na(z.structureSweepLevel) and high > z.structureSweepLevel

                if is_future_bar and wasLeftZone and not z.liquiditySwept and overlaps_zone
                    int touchBarNow = bar_index
                    z.lastTouchBar := touchBarNow
                    z.wasTouched := true

                    // Incremental peak update: just check current bar vs stored peak (O(1) instead of O(N))
                    if na(z.peakPrice) or high > z.peakPrice
                        z.peakPrice := high
                        z.peakBarIndex := bar_index
                        array.set(demandZones, i, z)
                        db_updateZoneLiquidity(z)

                    bool is_liq_bar = false
                    if not na(z.liquidityBarIndex) and touchBarNow == z.liquidityBarIndex
                        is_liq_bar := true
                    else if not na(z.liqLowBar) and touchBarNow == z.liqLowBar
                        is_liq_bar := true
                    else if not na(z.liqHighBar) and touchBarNow == z.liqHighBar
                        is_liq_bar := true

                    int liq_anchor_bar = na
                    if not na(z.liquidityBarIndex)
                        liq_anchor_bar := z.liquidityBarIndex
                    else if not na(z.liqLowBar)
                        liq_anchor_bar := z.liqLowBar
                    else if not na(z.liqHighBar)
                        liq_anchor_bar := z.liqHighBar

                    bool delayed_retouch = not na(liq_anchor_bar) and (touchBarNow - liq_anchor_bar >= 4)

                    if is_liq_bar or delayed_retouch
                        z.touchedPreSweep := true

                if is_future_bar and wasLeftZone and not z.liquiditySwept and overlaps_zone and not current_bar_sweeping
                    z.mitigated := true
```

- [ ] **Step 3: Check the demand block has no inside-close removal language**

Run:

```bash
sed -n '2910,2970p' scripts/pinescript/strategies/SND_Strategy.pine
```

Expected: the block contains `wasLeftZone` and `overlaps_zone`; it no longer contains `closes_inside`, `breaches_zone`, or `wicks_into_zone`.

## Task 3: Convert Supply Mitigation To Post-Left Range Overlap

**Files:**
- Modify: `scripts/pinescript/strategies/SND_Strategy.pine:3027-3054`

- [ ] **Step 1: Locate the current supply maintenance block**

Run:

```bash
sed -n '3020,3060p' scripts/pinescript/strategies/SND_Strategy.pine
```

Expected: the block starts with `if current_close < z.bottom and not z.leftZone` and contains `closes_inside`, `breaches_zone`, and `wicks_into_zone`.

- [ ] **Step 2: Replace the supply departure and mitigation block**

Replace the block from:

```pine
            if current_close < z.bottom and not z.leftZone
```

through:

```pine
                    z.mitigated := true
```

with:

```pine
            bool wasLeftZone = z.leftZone
            if current_close < z.bottom and not z.leftZone
                z.leftZone := true

            if not z.mitigated
                bool is_future_bar = not na(z.createdBarIndex) and bar_index > z.createdBarIndex

                bool overlaps_zone = high >= z.bottom and low <= z.top

                bool current_bar_sweeping = not na(z.structureSweepLevel) and low < z.structureSweepLevel

                if is_future_bar and wasLeftZone and not z.liquiditySwept and overlaps_zone
                    z.lastTouchBar := bar_index
                    z.wasTouched := true
                    z.touchedPreSweep := true

                    // Incremental peak update: just check current bar vs stored peak (O(1) instead of O(N))
                    if na(z.peakPrice) or low < z.peakPrice
                        z.peakPrice := low
                        z.peakBarIndex := bar_index
                        array.set(supplyZones, i, z)
                        db_updateZoneLiquidity(z)

                if is_future_bar and wasLeftZone and not z.liquiditySwept and overlaps_zone and not current_bar_sweeping
                    z.mitigated := true
```

- [ ] **Step 3: Check the supply block has no inside-close removal language**

Run:

```bash
sed -n '3020,3060p' scripts/pinescript/strategies/SND_Strategy.pine
```

Expected: the block contains `wasLeftZone` and `overlaps_zone`; it no longer contains `closes_inside`, `breaches_zone`, or `wicks_into_zone`.

## Task 4: Convert Active Zone Removal To Close-Through Only

**Files:**
- Modify: `scripts/pinescript/strategies/SND_Strategy.pine:3061-3098`

- [ ] **Step 1: Replace the active demand removal condition**

Replace the demand removal body:

```pine
                if current_close > z.top and not z.leftZone
                    z.leftZone := true
                    z.leftWithBearish := current_close < current_open

                bool close_inside_zone   = z.leftZone and current_close <= z.top and current_close >= z.bottom
                bool close_below_zone     = current_close < z.bottom
                bool wick_below_zone = current_low < z.bottom

                // After price leaves a zone, a later close back inside means the zone is consumed/invalidated.
                if close_inside_zone or close_below_zone or (invalidate_on_wick and wick_below_zone)
                    remove_zone_all_arrays(true, i)
```

with:

```pine
                bool wasLeftZone = z.leftZone
                if current_close > z.top and not z.leftZone
                    z.leftZone := true
                    z.leftWithBearish := current_close < current_open

                bool close_below_zone = wasLeftZone and current_close < z.bottom

                // Hybrid invalidation: retouches mitigate; only a confirmed close through the far side removes.
                if close_below_zone
                    remove_zone_all_arrays(true, i)
```

- [ ] **Step 2: Replace the active supply removal condition**

Replace the supply removal body:

```pine
            bool close_inside_zone   = z.leftZone and current_close >= z.bottom and current_close <= z.top
            bool close_above_zone     = current_close > z.top
            bool wick_above_zone = current_high > z.top

            // After price leaves a zone, a later close back inside means the zone is consumed/invalidated.
            if close_inside_zone or close_above_zone or (invalidate_on_wick and wick_above_zone)
                remove_zone_all_arrays(false, i)
```

with:

```pine
            bool wasLeftZone = z.leftZone
            if current_close < z.bottom and not z.leftZone
                z.leftZone := true

            bool close_above_zone = wasLeftZone and current_close > z.top

            // Hybrid invalidation: retouches mitigate; only a confirmed close through the far side removes.
            if close_above_zone
                remove_zone_all_arrays(false, i)
```

- [ ] **Step 3: Confirm obsolete variables are gone**

Run:

```bash
rg -n "invalidate_on_wick|close_inside_zone|wick_below_zone|wick_above_zone|breaches_zone|wicks_into_zone|closes_inside" scripts/pinescript/strategies/SND_Strategy.pine
```

Expected output:

```text
```

No matches should remain.

## Task 5: Local Pine Verification

**Files:**
- Verify: `scripts/pinescript/strategies/SND_Strategy.pine`

- [ ] **Step 1: Run whitespace/diff validation**

Run:

```bash
git diff --check -- scripts/pinescript/strategies/SND_Strategy.pine
```

Expected: no output and exit code `0`.

- [ ] **Step 2: Run offline Pine analysis**

Run:

```bash
node mcp/tradingview-mcp/src/cli/index.js pine analyze --file scripts/pinescript/strategies/SND_Strategy.pine
```

Expected: analysis completes without syntax errors. Existing warning-level findings may remain if they were already present before this invalidation change.

- [ ] **Step 3: Run server-side Pine compile check**

Run:

```bash
node mcp/tradingview-mcp/src/cli/index.js pine check --file scripts/pinescript/strategies/SND_Strategy.pine
```

Expected: compile check completes without errors.

- [ ] **Step 4: Review the Pine diff for scope**

Run:

```bash
git diff -- scripts/pinescript/strategies/SND_Strategy.pine
```

Expected: the diff only removes `invalidate_on_wick` and changes the demand/supply mitigation/removal blocks described in Tasks 2-4.

## Task 6: TradingView Update And Replay Verification

**Files:**
- Update in editor: `scripts/pinescript/strategies/SND_Strategy.pine`

- [ ] **Step 1: Confirm TradingView MCP is connected**

Run:

```bash
node mcp/tradingview-mcp/src/cli/index.js status
```

Expected: TradingView CDP connection is available.

- [ ] **Step 2: Push the local Pine file into the TradingView editor**

Run:

```bash
node mcp/tradingview-mcp/src/cli/index.js pine set --file scripts/pinescript/strategies/SND_Strategy.pine
```

Expected: the editor source is replaced with the local `SND_Strategy.pine` contents.

- [ ] **Step 3: Compile in TradingView**

Run:

```bash
node mcp/tradingview-mcp/src/cli/index.js pine compile
```

Expected: compile finishes within the TradingView time limit and returns no compile errors.

- [ ] **Step 4: Save the TradingView script**

Run:

```bash
node mcp/tradingview-mcp/src/cli/index.js pine save
```

Expected: the Pine editor saves the updated strategy.

- [ ] **Step 5: Inspect active boxes from TradingView**

Run:

```bash
node mcp/tradingview-mcp/src/cli/index.js data boxes
```

Expected: supply and demand boxes are still present. The count should not collapse to the low-count state seen after the rejected historical invalidation experiment.

- [ ] **Step 6: Replay-check the known behavior manually on XAUUSD 5m**

Use the chart replay state that previously showed `S-7949`, `S-7948`, and `D-7875`.

Expected:

- A supply wick retouch after price left below the zone can mark the zone mitigated.
- A supply zone remains drawn when price only closes back inside it.
- A supply zone is removed after a later confirmed close above `z.top`.
- A demand wick retouch after price left above the zone can mark the zone mitigated.
- A demand zone remains drawn when price only closes back inside it.
- A demand zone is removed after a later confirmed close below `z.bottom`.

## Task 7: Commit

**Files:**
- Commit: `scripts/pinescript/strategies/SND_Strategy.pine`
- Do not stage: `.metaapi/*`
- Do not stage: `mcp/tradingview-mcp` submodule state unless it changed because of an intentional MCP update outside this plan.

- [ ] **Step 1: Review unstaged files**

Run:

```bash
git status --short
```

Expected: `scripts/pinescript/strategies/SND_Strategy.pine` is modified. Pre-existing `.metaapi/*` and `mcp/tradingview-mcp` changes may also appear and must stay unstaged.

- [ ] **Step 2: Stage only the Pine strategy**

Run:

```bash
git add scripts/pinescript/strategies/SND_Strategy.pine
```

Expected: only the Pine strategy file is staged.

- [ ] **Step 3: Commit the invalidation change**

Run:

```bash
git commit -m "DEV-410: implement Pine hybrid zone invalidation"
```

Expected: commit succeeds.

## Self-Review Notes

- Spec coverage: Tasks 2 and 3 implement post-left overlap mitigation for demand and supply. Task 4 implements close-through-only removal. Task 6 covers TradingView replay verification. The plan does not change detection, visuals, zone priority, entry model, or library APIs.
- Placeholder scan: This plan contains concrete file paths, commands, replacement snippets, and expected results for every code and verification step.
- Type consistency: The plan only uses existing Pine identifiers already present in `SND_Strategy.pine`: `Core.Zone`, `z.leftZone`, `z.mitigated`, `z.liquiditySwept`, `z.structureSweepLevel`, `z.top`, `z.bottom`, `z.createdBarIndex`, `demandZones`, `supplyZones`, and `remove_zone_all_arrays`.
