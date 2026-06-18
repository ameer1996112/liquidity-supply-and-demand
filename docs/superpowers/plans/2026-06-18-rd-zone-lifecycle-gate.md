# RD Zone Lifecycle Gate Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Prevent RD zones from being invalidated by formation/departure candles before the zone has confirmed and departed in runtime lifecycle.

**Architecture:** Keep the current SND strategy and liquidity flow intact. Use existing `Core.Zone` lifecycle fields: `departureEndBarIndex` as `confirmationBar`, `firstInvalidBarIndex` as `invalidationStartBar`, and `structureBreakBarIndex` as the runtime departure marker after confirmation. Gate all price-action invalidation branches behind `canJudgeInvalidation`. Add one focused static contract test for the active strategy.

**Tech Stack:** Pine Script v6, Python static tests, TradingView MCP Pine checker.

---

## File Structure

- Modify: `scripts/pinescript/strategies/SND_Strategy.pine`
  - Set zone confirmation/invalidation-start anchors at creation.
  - Prevent pre-confirmation/pre-runtime-departure return candles from marking zones mitigated before sweep.
  - Gate demand and supply invalidation loops.
  - Add compact debug fields to the zone inspector.
- Create: `scripts/pinescript/tests/test_snd_strategy_lifecycle_gate_static.py`
  - Static acceptance test for lifecycle-gated invalidation in the active strategy only.
- Do not modify: `scripts/pinescript/libraries/SND_Core.pine`
  - It already exposes `departureEndBarIndex`, `firstInvalidBarIndex`, `stateReason`, and related lifecycle fields.
- Do not modify: unrelated Pine indicators or backend trading logic.

---

### Task 1: Add Lifecycle Gate Static Contract

**Files:**
- Create: `scripts/pinescript/tests/test_snd_strategy_lifecycle_gate_static.py`

- [ ] **Step 1: Write the failing static test**

Create `scripts/pinescript/tests/test_snd_strategy_lifecycle_gate_static.py`:

```python
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
STRATEGY = ROOT / "scripts/pinescript/strategies/SND_Strategy.pine"


def _body(source: str, start_marker: str, end_marker: str) -> str:
    if start_marker not in source:
        return ""
    start = source.index(start_marker)
    if end_marker not in source[start:]:
        return source[start:]
    end = source.index(end_marker, start)
    return source[start:end]


def main() -> None:
    strategy = STRATEGY.read_text(encoding="utf-8")

    create_zone = _body(
        strategy,
        "createZone(int baseIdx, bool isDemand, bool isHistorical, int candlesInBase, int legCandles, int zoneUZID",
        "\nremove_zone_all_arrays(",
    )
    for needle in [
        "z.departureEndBarIndex := bar_index",
        "z.firstInvalidBarIndex := bar_index + 1",
        "z.structureBreakBarIndex := na",
        'z.stateReason := "CONFIRMED_WAIT_RUNTIME_DEPARTURE"',
    ]:
        if needle not in create_zone:
            raise AssertionError(f"createZone missing lifecycle anchor {needle!r}")

    demand_lifecycle = _body(
        strategy,
        "int demandSize = array.size(demandZones)",
        "int supplySize = array.size(supplyZones)",
    )
    for needle in [
        "int confirmationBar = not na(z.departureEndBarIndex) ? z.departureEndBarIndex : z.createdBarIndex",
        "int invalidationStartBar = not na(z.firstInvalidBarIndex) ? z.firstInvalidBarIndex : confirmationBar + 1",
        "bool afterConfirmation = bar_index >= invalidationStartBar",
        "bool departedAfterConfirmation = not na(z.structureBreakBarIndex) and z.structureBreakBarIndex >= invalidationStartBar",
        "bool canJudgeInvalidation = afterConfirmation and departedAfterConfirmation",
        "bool validSweepOrProof = z.liquidityValid and z.liquiditySwept",
        "bool gatedReturnedBeforeLiqSweep = canJudgeInvalidation and not validSweepOrProof and returned_before_liq_sweep",
        "bool gatedReturnedInvalidAfterLeft = canJudgeInvalidation and not validSweepOrProof and returned_invalid_after_left",
        "bool gatedCloseBelowZone = canJudgeInvalidation and not validSweepOrProof and close_below_zone",
        "bool gatedWickBelowZone = canJudgeInvalidation and not validSweepOrProof and invalidate_on_wick and wick_below_zone",
        "if gatedReturnedBeforeLiqSweep or gatedReturnedInvalidAfterLeft or gatedCloseBelowZone or gatedWickBelowZone or isTooOld",
        "bool canTrackDemandPreSweepMitigation = bar_index >= demandInvalidationStartBar and not na(z.structureBreakBarIndex) and z.structureBreakBarIndex >= demandInvalidationStartBar",
        "if is_future_bar and z.leftZone and (closes_inside or breaches_zone) and not current_bar_sweeping and not z.liquiditySwept and canTrackDemandPreSweepMitigation",
    ]:
        if needle not in demand_lifecycle:
            raise AssertionError(f"demand lifecycle gate missing {needle!r}")
    for forbidden in [
        "if returned_before_liq_sweep or returned_invalid_after_left or close_below_zone or wick_below_zone or isTooOld",
        "else if wick_below_zone",
        "if is_future_bar and z.leftZone and (closes_inside or breaches_zone) and not current_bar_sweeping and not z.liquiditySwept\n                    z.mitigated := true",
    ]:
        if forbidden in demand_lifecycle:
            raise AssertionError(f"demand lifecycle still has ungated invalidation {forbidden!r}")

    supply_lifecycle = _body(
        strategy,
        "int supplySize = array.size(supplyZones)",
        "if show_zones and show_demand_zones",
    )
    for needle in [
        "int confirmationBar = not na(z.departureEndBarIndex) ? z.departureEndBarIndex : z.createdBarIndex",
        "int invalidationStartBar = not na(z.firstInvalidBarIndex) ? z.firstInvalidBarIndex : confirmationBar + 1",
        "bool afterConfirmation = bar_index >= invalidationStartBar",
        "bool departedAfterConfirmation = not na(z.structureBreakBarIndex) and z.structureBreakBarIndex >= invalidationStartBar",
        "bool canJudgeInvalidation = afterConfirmation and departedAfterConfirmation",
        "bool validSweepOrProof = z.liquidityValid and z.liquiditySwept",
        "bool gatedReturnedBeforeLiqSweep = canJudgeInvalidation and not validSweepOrProof and returned_before_liq_sweep",
        "bool gatedReturnedInvalidAfterLeft = canJudgeInvalidation and not validSweepOrProof and returned_invalid_after_left",
        "bool gatedCloseAboveZone = canJudgeInvalidation and not validSweepOrProof and close_above_zone",
        "bool gatedWickAboveZone = canJudgeInvalidation and not validSweepOrProof and invalidate_on_wick and wick_above_zone",
        "if gatedReturnedBeforeLiqSweep or gatedReturnedInvalidAfterLeft or gatedCloseAboveZone or gatedWickAboveZone or isTooOld",
        "bool canTrackSupplyPreSweepMitigation = bar_index >= supplyInvalidationStartBar and not na(z.structureBreakBarIndex) and z.structureBreakBarIndex >= supplyInvalidationStartBar",
        "if is_future_bar and z.leftZone and (closes_inside or breaches_zone) and not current_bar_sweeping and not z.liquiditySwept and canTrackSupplyPreSweepMitigation",
    ]:
        if needle not in supply_lifecycle:
            raise AssertionError(f"supply lifecycle gate missing {needle!r}")
    for forbidden in [
        "if returned_before_liq_sweep or returned_invalid_after_left or close_above_zone or wick_above_zone or isTooOld",
        "else if wick_above_zone",
        "if is_future_bar and z.leftZone and (closes_inside or breaches_zone) and not current_bar_sweeping and not z.liquiditySwept\n                    z.mitigated := true",
    ]:
        if forbidden in supply_lifecycle:
            raise AssertionError(f"supply lifecycle still has ungated invalidation {forbidden!r}")

    inspector = _body(
        strategy,
        "var table zoneInspector = na",
        "if not showZoneInspector",
    )
    for needle in [
        "string lifecycleDebug =",
        '"Confirm"',
        '"InvStart"',
        '"CanJudge"',
        "table.cell(zoneInspector, 0, nextRow, \"Lifecycle\"",
    ]:
        if needle not in inspector:
            raise AssertionError(f"zone inspector missing lifecycle debug {needle!r}")

    print("SND strategy lifecycle gate static contract passed")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Run the test and verify it fails**

Run:

```bash
python3 scripts/pinescript/tests/test_snd_strategy_lifecycle_gate_static.py
```

Expected: FAIL with a message such as `createZone missing lifecycle anchor 'z.departureEndBarIndex := bar_index'`.

- [ ] **Step 3: Commit the failing test**

```bash
git add scripts/pinescript/tests/test_snd_strategy_lifecycle_gate_static.py
git commit -m "DEV-845: add RD lifecycle gate static contract"
```

---

### Task 2: Anchor Confirmation at Zone Creation

**Files:**
- Modify: `scripts/pinescript/strategies/SND_Strategy.pine`

- [ ] **Step 1: Locate `createZone` initialization and base-end assignment**

Find the block where a new `Core.Zone z = Core.Zone.new()` is initialized and currently sets:

```pine
z.createdBarIndex := baseBarIdx
z.isHistorical := isHistorical
z.startTime := time[baseIdx]
```

Also find the existing base-end assignment later in the same function:

```pine
int baseEndAbsolute = baseBarIdx + actualCandlesInBase - 1
z.baseEndBarIndex := baseEndAbsolute
```

- [ ] **Step 2: Add confirmation/invalidation anchors**

Leave `z.baseEndBarIndex := baseEndAbsolute` where it is, because `baseEndAbsolute` is defined there. Immediately after that assignment, add:

```pine
z.departureEndBarIndex := bar_index
z.firstInvalidBarIndex := bar_index + 1
z.structureBreakBarIndex := na
z.stateReason := "CONFIRMED_WAIT_RUNTIME_DEPARTURE"
```

- [ ] **Step 3: Run the focused test**

Run:

```bash
python3 scripts/pinescript/tests/test_snd_strategy_lifecycle_gate_static.py
```

Expected: still FAIL, now on missing demand/supply lifecycle gate markers.

- [ ] **Step 4: Commit the creation anchor**

```bash
git add scripts/pinescript/strategies/SND_Strategy.pine
git commit -m "DEV-845: anchor RD zone confirmation at creation"
```

---

### Task 3: Gate Demand Invalidation

**Files:**
- Modify: `scripts/pinescript/strategies/SND_Strategy.pine`

- [ ] **Step 1: Locate the demand invalidation loop**

Find the block beginning:

```pine
int demandSize = array.size(demandZones)
if demandSize > 0
```

Inside its per-zone loop, locate the existing decision:

```pine
if returned_before_liq_sweep or returned_invalid_after_left or close_below_zone or wick_below_zone or isTooOld
```

- [ ] **Step 2: Gate early demand pre-sweep mitigation**

Find the earlier demand touch/mitigation block:

```pine
                if is_future_bar and z.leftZone and (closes_inside or breaches_zone) and not current_bar_sweeping and not z.liquiditySwept
                    z.mitigated := true
                    z.lastTouchBar := bar_index
                    array.set(demandZones, i, z)
                    db_updateZoneLiquidity(z)
```

Replace it with:

```pine
                int demandConfirmationBar = not na(z.departureEndBarIndex) ? z.departureEndBarIndex : z.createdBarIndex
                int demandInvalidationStartBar = not na(z.firstInvalidBarIndex) ? z.firstInvalidBarIndex : demandConfirmationBar + 1
                bool canTrackDemandPreSweepMitigation = bar_index >= demandInvalidationStartBar and not na(z.structureBreakBarIndex) and z.structureBreakBarIndex >= demandInvalidationStartBar

                if is_future_bar and z.leftZone and (closes_inside or breaches_zone) and not current_bar_sweeping and not z.liquiditySwept and canTrackDemandPreSweepMitigation
                    z.mitigated := true
                    z.lastTouchBar := bar_index
                    array.set(demandZones, i, z)
                    db_updateZoneLiquidity(z)
```

- [ ] **Step 3: Add lifecycle booleans before the demand invalidation decision**

Insert this immediately before the invalidation `if`:

```pine
                int confirmationBar = not na(z.departureEndBarIndex) ? z.departureEndBarIndex : z.createdBarIndex
                int invalidationStartBar = not na(z.firstInvalidBarIndex) ? z.firstInvalidBarIndex : confirmationBar + 1
                bool afterConfirmation = bar_index >= invalidationStartBar
                if afterConfirmation and na(z.structureBreakBarIndex) and current_close > z.top + zone_departure_buffer_price
                    z.structureBreakBarIndex := bar_index
                    z.stateReason := "RUNTIME_DEPARTED_AFTER_CONFIRMATION"
                    array.set(demandZones, i, z)
                    db_updateZoneLiquidity(z)
                bool departedAfterConfirmation = not na(z.structureBreakBarIndex) and z.structureBreakBarIndex >= invalidationStartBar
                bool canJudgeInvalidation = afterConfirmation and departedAfterConfirmation
                bool validSweepOrProof = z.liquidityValid and z.liquiditySwept
                bool gatedReturnedBeforeLiqSweep = canJudgeInvalidation and not validSweepOrProof and returned_before_liq_sweep
                bool gatedReturnedInvalidAfterLeft = canJudgeInvalidation and not validSweepOrProof and returned_invalid_after_left
                bool gatedCloseBelowZone = canJudgeInvalidation and not validSweepOrProof and close_below_zone
                bool gatedWickBelowZone = canJudgeInvalidation and not validSweepOrProof and invalidate_on_wick and wick_below_zone
```

- [ ] **Step 4: Replace the demand invalidation decision**

Replace the existing invalidation decision with:

```pine
                if gatedReturnedBeforeLiqSweep or gatedReturnedInvalidAfterLeft or gatedCloseBelowZone or gatedWickBelowZone or isTooOld
                    if gatedReturnedBeforeLiqSweep or gatedReturnedInvalidAfterLeft
                        bool sameBarSweepOrder = not na(z.liquiditySweptBarIndex) and bar_index <= z.liquiditySweptBarIndex
                        recordDiag(sameBarSweepOrder ? 303 : 302, true, bar_index - z.createdBarIndex, sameBarSweepOrder ? "same bar sweep order" : "returned pre sweep")
                    else if gatedCloseBelowZone
                        recordDiag(305, true, bar_index - z.createdBarIndex, "close invalidated")
                    else if gatedWickBelowZone
                        recordDiag(304, true, bar_index - z.createdBarIndex, "wick invalidated")
                    else if isTooOld
                        recordDiag(306, true, bar_index - z.createdBarIndex, "expired too early")
                    remove_zone_all_arrays(true, i)
```

- [ ] **Step 5: Run the focused test**

Run:

```bash
python3 scripts/pinescript/tests/test_snd_strategy_lifecycle_gate_static.py
```

Expected: FAIL on missing supply lifecycle gate or inspector debug markers.

- [ ] **Step 6: Commit demand gate**

```bash
git add scripts/pinescript/strategies/SND_Strategy.pine
git commit -m "DEV-845: gate demand zone invalidation"
```

---

### Task 4: Gate Supply Invalidation

**Files:**
- Modify: `scripts/pinescript/strategies/SND_Strategy.pine`

- [ ] **Step 1: Locate the supply invalidation loop**

Find the block beginning:

```pine
int supplySize = array.size(supplyZones)
if supplySize > 0
```

Inside its per-zone loop, locate the existing decision:

```pine
if returned_before_liq_sweep or returned_invalid_after_left or close_above_zone or wick_above_zone or isTooOld
```

- [ ] **Step 2: Gate early supply pre-sweep mitigation**

Find the earlier supply touch/mitigation block:

```pine
                if is_future_bar and z.leftZone and (closes_inside or breaches_zone) and not current_bar_sweeping and not z.liquiditySwept
                    z.mitigated := true
                    z.lastTouchBar := bar_index
                    array.set(supplyZones, i, z)
                    db_updateZoneLiquidity(z)
```

Replace it with:

```pine
                int supplyConfirmationBar = not na(z.departureEndBarIndex) ? z.departureEndBarIndex : z.createdBarIndex
                int supplyInvalidationStartBar = not na(z.firstInvalidBarIndex) ? z.firstInvalidBarIndex : supplyConfirmationBar + 1
                bool canTrackSupplyPreSweepMitigation = bar_index >= supplyInvalidationStartBar and not na(z.structureBreakBarIndex) and z.structureBreakBarIndex >= supplyInvalidationStartBar

                if is_future_bar and z.leftZone and (closes_inside or breaches_zone) and not current_bar_sweeping and not z.liquiditySwept and canTrackSupplyPreSweepMitigation
                    z.mitigated := true
                    z.lastTouchBar := bar_index
                    array.set(supplyZones, i, z)
                    db_updateZoneLiquidity(z)
```

- [ ] **Step 3: Add lifecycle booleans before the supply invalidation decision**

Insert this immediately before the invalidation `if`:

```pine
            int confirmationBar = not na(z.departureEndBarIndex) ? z.departureEndBarIndex : z.createdBarIndex
            int invalidationStartBar = not na(z.firstInvalidBarIndex) ? z.firstInvalidBarIndex : confirmationBar + 1
            bool afterConfirmation = bar_index >= invalidationStartBar
            if afterConfirmation and na(z.structureBreakBarIndex) and current_close < z.bottom - zone_departure_buffer_price
                z.structureBreakBarIndex := bar_index
                z.stateReason := "RUNTIME_DEPARTED_AFTER_CONFIRMATION"
                array.set(supplyZones, i, z)
                db_updateZoneLiquidity(z)
            bool departedAfterConfirmation = not na(z.structureBreakBarIndex) and z.structureBreakBarIndex >= invalidationStartBar
            bool canJudgeInvalidation = afterConfirmation and departedAfterConfirmation
            bool validSweepOrProof = z.liquidityValid and z.liquiditySwept
            bool gatedReturnedBeforeLiqSweep = canJudgeInvalidation and not validSweepOrProof and returned_before_liq_sweep
            bool gatedReturnedInvalidAfterLeft = canJudgeInvalidation and not validSweepOrProof and returned_invalid_after_left
            bool gatedCloseAboveZone = canJudgeInvalidation and not validSweepOrProof and close_above_zone
            bool gatedWickAboveZone = canJudgeInvalidation and not validSweepOrProof and invalidate_on_wick and wick_above_zone
```

- [ ] **Step 4: Replace the supply invalidation decision**

Replace the existing invalidation decision with:

```pine
            if gatedReturnedBeforeLiqSweep or gatedReturnedInvalidAfterLeft or gatedCloseAboveZone or gatedWickAboveZone or isTooOld
                if gatedReturnedBeforeLiqSweep or gatedReturnedInvalidAfterLeft
                    bool sameBarSweepOrder = not na(z.liquiditySweptBarIndex) and bar_index <= z.liquiditySweptBarIndex
                    recordDiag(sameBarSweepOrder ? 303 : 302, false, bar_index - z.createdBarIndex, sameBarSweepOrder ? "same bar sweep order" : "returned pre sweep")
                else if gatedCloseAboveZone
                    recordDiag(305, false, bar_index - z.createdBarIndex, "close invalidated")
                else if gatedWickAboveZone
                    recordDiag(304, false, bar_index - z.createdBarIndex, "wick invalidated")
                else if isTooOld
                    recordDiag(306, false, bar_index - z.createdBarIndex, "expired too early")
                remove_zone_all_arrays(false, i)
```

- [ ] **Step 5: Run the focused test**

Run:

```bash
python3 scripts/pinescript/tests/test_snd_strategy_lifecycle_gate_static.py
```

Expected: FAIL only on missing inspector debug markers.

- [ ] **Step 6: Commit supply gate**

```bash
git add scripts/pinescript/strategies/SND_Strategy.pine
git commit -m "DEV-845: gate supply zone invalidation"
```

---

### Task 5: Add Limited Lifecycle Debug to Zone Inspector

**Files:**
- Modify: `scripts/pinescript/strategies/SND_Strategy.pine`

- [ ] **Step 1: Locate the inspector row block**

Find the zone inspector block near the existing rows:

```pine
table.cell(zoneInspector, 0, nextRow, "Zone Status"
table.cell(zoneInspector, 0, nextRow, "Inactive Reason"
```

- [ ] **Step 2: Add lifecycle debug string**

Before the `Zone Status` row, add:

```pine
        string lifecycleDebug = "N/A"
        if not na(inspectorZone)
            int dbgConfirmBar = not na(inspectorZone.departureEndBarIndex) ? inspectorZone.departureEndBarIndex : inspectorZone.createdBarIndex
            int dbgInvStartBar = not na(inspectorZone.firstInvalidBarIndex) ? inspectorZone.firstInvalidBarIndex : dbgConfirmBar + 1
            bool dbgDeparted = not na(inspectorZone.structureBreakBarIndex) and inspectorZone.structureBreakBarIndex >= dbgInvStartBar
            bool dbgCanJudge = bar_index >= dbgInvStartBar and dbgDeparted
            lifecycleDebug := "Confirm " + str.tostring(dbgConfirmBar) + " | InvStart " + str.tostring(dbgInvStartBar) + " | Left " + (dbgDeparted ? "Yes" : "No") + " | CanJudge " + (dbgCanJudge ? "Yes" : "No")
        else if foundInDB and not na(dbEntry)
            lifecycleDebug := "Confirm N/A | InvStart N/A | CanJudge No"

        table.cell(zoneInspector, 0, nextRow, "Lifecycle", text_color = color.rgb(150, 150, 150), bgcolor = color.new(color.rgb(25, 30, 35), 5), text_halign = text.align_right, text_size = tbl_sz)
        table.cell(zoneInspector, 1, nextRow, lifecycleDebug, text_color = color.rgb(120, 190, 255), bgcolor = color.new(color.rgb(25, 30, 35), 5), text_halign = text.align_left, text_size = tbl_sz)
        nextRow += 1
```

- [ ] **Step 3: Run the focused test**

Run:

```bash
python3 scripts/pinescript/tests/test_snd_strategy_lifecycle_gate_static.py
```

Expected: PASS with `SND strategy lifecycle gate static contract passed`.

- [ ] **Step 4: Commit inspector debug**

```bash
git add scripts/pinescript/strategies/SND_Strategy.pine
git commit -m "DEV-845: expose RD lifecycle gate in zone inspector"
```

---

### Task 6: Validate Pine Compile and Existing Static Contracts

**Files:**
- Modify only if validation exposes a compile/static issue:
  - `scripts/pinescript/strategies/SND_Strategy.pine`
  - `scripts/pinescript/tests/test_snd_strategy_lifecycle_gate_static.py`

- [ ] **Step 1: Run focused static test**

Run:

```bash
python3 scripts/pinescript/tests/test_snd_strategy_lifecycle_gate_static.py
```

Expected: PASS with `SND strategy lifecycle gate static contract passed`.

- [ ] **Step 2: Run related static tests**

Run:

```bash
python3 scripts/pinescript/tests/test_snd_zone_invalidation_static.py
python3 scripts/pinescript/tests/test_snd_zone_rules_static.py
python3 scripts/pinescript/tests/test_snd_live_replay_invalidation_static.py
python3 scripts/pinescript/tests/test_snd_demand_return_before_target_static.py
python3 scripts/pinescript/tests/test_snd_supply_return_before_target_static.py
```

Expected: PASS for tests compatible with the current active strategy. If one fails because it asserts the old ungated wick/return behavior, update that test to assert `canJudgeInvalidation` and the gated booleans, then rerun the same command.

- [ ] **Step 3: Run Pine compile check**

Run:

```bash
node mcp/tradingview-mcp/src/cli/index.js pine check --file scripts/pinescript/strategies/SND_Strategy.pine
```

Expected: PASS. If the checker is unavailable because TradingView MCP cannot connect, record the exact error in the final handoff and complete static validation.

- [ ] **Step 4: Check for mobile copy artifact**

Run:

```bash
rg --files scripts/pinescript | rg 'SND_Strategy_COPY_THIS|COPY_THIS|\\.txt$'
```

Expected: If a copy artifact exists, update it to match `scripts/pinescript/strategies/SND_Strategy.pine`. If no artifact is found, record that no copy file exists in this checkout.

- [ ] **Step 5: Commit validation fixes if needed**

Only commit if Step 2 or Step 3 required code/test fixes:

```bash
git add scripts/pinescript/strategies/SND_Strategy.pine scripts/pinescript/tests/test_snd_strategy_lifecycle_gate_static.py
git commit -m "DEV-845: stabilize RD lifecycle gate validation"
```

---

### Task 7: Manual Acceptance Handoff

**Files:**
- No required edits.

- [ ] **Step 1: Summarize lifecycle behavior**

Prepare a short handoff stating:

```text
RD lifecycle gate behavior:
- Zone creation sets confirmationBar to the creation/confirmation bar.
- Price-action invalidation starts at invalidationStartBar, not at origin candle.
- Runtime departure after confirmation is stored in structureBreakBarIndex.
- Demand close/wick/return invalidation is gated by canJudgeInvalidation.
- Supply close/wick/return invalidation is gated by canJudgeInvalidation.
- Age expiration remains outside the price-action gate.
- Post-sweep return remains mitigation because gated invalidation requires not validSweepOrProof.
```

- [ ] **Step 2: Ask for TradingView replay verification**

Ask the user to verify the target chart case:

```text
Please replay the 01:05 demand zone case and confirm:
- the 214.989 / 214.866 demand zone is not deleted by formation/departure candles,
- the 01:25 wick does not invalidate unless it happens after invalidationStartBar and wick invalidation is enabled,
- a post-sweep return is treated as mitigation.
```

- [ ] **Step 3: Final commit check**

Run:

```bash
git status --short
git log --oneline -5
```

Expected: only intentional files are changed or committed; unrelated dirty files remain untouched.
