# Pine Zone Extension Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make PineScript zones project forward while valid, stop exactly on the first post-leave wick touch, and remain visible after that touch.

**Architecture:** Keep zone drawing state separate from trade state. Replace the current mitigation-named visual cache with a dedicated visual stop cache keyed by zone ID, and evaluate first wick touch in the general zone lifecycle loops that run for every active demand and supply zone.

**Tech Stack:** TradingView Pine Script v5, existing `SND_Strategy.pine`, existing `Core.Zone` imported type, manual TradingView replay verification.

---

## File Structure

- Modify: `scripts/pinescript/strategies/SND_Strategy.pine`
  - Owns zone inputs, visual right-edge helpers, active zone lifecycle loops, box drawing, and cleanup.
- Reference: `docs/superpowers/specs/2026-06-01-pine-zone-extension-design.md`
  - Approved behavior and non-goals.

No new runtime files are required. Pine cannot use a local unit test harness here, so verification is a mix of local diff checks and TradingView replay checks.

## Task 1: Rename And Simplify Visual Stop State

**Files:**
- Modify: `scripts/pinescript/strategies/SND_Strategy.pine:206-253`

- [ ] **Step 1: Replace the current zone extension helpers**

Replace the block starting at the `// Zone extension controls.` comment through `zone_visual_right(Core.Zone z) =>` with:

```pine
// Zone extension controls.
zone_projection_bars = input.int(50, "Unmitigated Zone Projection Bars", minval = 1, maxval = 500, group = "🎨 Display")

var int[] visual_stop_zone_ids = array.new_int()
var int[] visual_stop_bars = array.new_int()

visual_stop_index(int zoneId) =>
    int found = na
    if not na(zoneId)
        int sz = array.size(visual_stop_zone_ids)
        if sz > 0
            for idx = 0 to sz - 1
                if array.get(visual_stop_zone_ids, idx) == zoneId
                    found := idx
                    break
    found

visual_stop_bar(int zoneId) =>
    int idx = visual_stop_index(zoneId)
    not na(idx) ? array.get(visual_stop_bars, idx) : na

record_visual_stop(int zoneId, int stopBar) =>
    if not na(zoneId) and not na(stopBar)
        int idx = visual_stop_index(zoneId)
        if na(idx)
            array.push(visual_stop_zone_ids, zoneId)
            array.push(visual_stop_bars, stopBar)
    stopBar

clear_visual_stop(int zoneId) =>
    int idx = visual_stop_index(zoneId)
    if not na(idx)
        array.remove(visual_stop_zone_ids, idx)
        array.remove(visual_stop_bars, idx)
    true

zone_visual_right(Core.Zone z) =>
    int stopBar = visual_stop_bar(z.id)
    not na(stopBar) ? stopBar : z.createdBarIndex + zone_projection_bars
```

- [ ] **Step 2: Verify old helper names are no longer used**

Run:

```bash
rg -n "zone_mitigation_|set_zone_mitigation_bar|clear_zone_mitigation_bar|zone_box_right|zone_extend_mode|zone_right_padding_bars" scripts/pinescript/strategies/SND_Strategy.pine
```

Expected: no matches.

- [ ] **Step 3: Commit the helper rename**

Run:

```bash
git add scripts/pinescript/strategies/SND_Strategy.pine
git commit -m "DEV-844: isolate Pine zone visual stop state"
```

## Task 2: Update Zone Cleanup To Clear Visual Stops

**Files:**
- Modify: `scripts/pinescript/strategies/SND_Strategy.pine:1529-1550`
- Modify: `scripts/pinescript/strategies/SND_Strategy.pine:1901-1925`

- [ ] **Step 1: Replace cleanup calls in pruning**

In `trimZoneArrays(bool isDemand)`, replace:

```pine
clear_zone_mitigation_bar(z.id)
```

with:

```pine
clear_visual_stop(z.id)
```

This replacement must happen in both the demand and supply pruning branches.

- [ ] **Step 2: Replace cleanup calls in removal**

In `remove_zone_all_arrays(bool isDemand, int idx)`, replace:

```pine
clear_zone_mitigation_bar(z.id)
```

with:

```pine
clear_visual_stop(z.id)
```

This replacement must happen in both the demand and supply removal branches.

- [ ] **Step 3: Verify cleanup uses only the visual helper**

Run:

```bash
rg -n "clear_zone_mitigation_bar|clear_visual_stop" scripts/pinescript/strategies/SND_Strategy.pine
```

Expected: no `clear_zone_mitigation_bar` matches; `clear_visual_stop` appears in the helper definition plus pruning/removal cleanup calls.

- [ ] **Step 4: Commit cleanup changes**

Run:

```bash
git add scripts/pinescript/strategies/SND_Strategy.pine
git commit -m "DEV-844: clear Pine zone visual stops on removal"
```

## Task 3: Remove Visual Stop Writes From Liquidity/Mitigation Branches

**Files:**
- Modify: `scripts/pinescript/strategies/SND_Strategy.pine:2944-3153`

- [ ] **Step 1: Remove visual stop writes from the live demand liquidity loop**

In the `if cached_demand_size > 0 and barstate.isconfirmed` loop, remove this block:

```pine
bool visual_zone_touch = is_future_bar and had_left_zone and low <= z.top and high >= z.bottom
if visual_zone_touch
    set_zone_mitigation_bar(z.id, bar_index)
```

Also remove this line from the demand mitigation branch:

```pine
set_zone_mitigation_bar(z.id, bar_index)
```

- [ ] **Step 2: Remove visual stop writes from the live supply liquidity loop**

In the `if cached_supply_size > 0 and barstate.isconfirmed` loop, remove this block:

```pine
bool visual_zone_touch = is_future_bar and had_left_zone and high >= z.bottom and low <= z.top
if visual_zone_touch
    set_zone_mitigation_bar(z.id, bar_index)
```

Also remove this line from the supply mitigation branch:

```pine
set_zone_mitigation_bar(z.id, bar_index)
```

- [ ] **Step 3: Remove unneeded `had_left_zone` declarations from liquidity loops**

Remove these lines from the live demand and supply liquidity loops:

```pine
bool had_left_zone = z.leftZone
```

These loops skip historical zones and are gated by liquidity/trade state, so they must not own visual stop logic.

- [ ] **Step 4: Verify visual stop writes only use the new helper name**

Run:

```bash
rg -n "set_zone_mitigation_bar|record_visual_stop|visual_zone_touch|had_left_zone" scripts/pinescript/strategies/SND_Strategy.pine
```

Expected: no `set_zone_mitigation_bar` matches. `record_visual_stop`, `visual_zone_touch`, and `had_left_zone` should only appear in the general demand/supply lifecycle loops added in Task 4.

- [ ] **Step 5: Commit branch cleanup**

Run:

```bash
git add scripts/pinescript/strategies/SND_Strategy.pine
git commit -m "DEV-844: remove visual stop writes from liquidity branches"
```

## Task 4: Centralize First Wick Touch In General Lifecycle Loops

**Files:**
- Modify: `scripts/pinescript/strategies/SND_Strategy.pine:3155-3236`

- [ ] **Step 1: Update the general demand lifecycle loop**

In the `int demandSize = array.size(demandZones)` lifecycle block, keep `had_left_zone` before the `leftZone` update and use this exact visual stop section after `returned_invalid_after_left` is calculated:

```pine
bool visual_zone_touch = had_left_zone and current_low <= z.top and current_high >= z.bottom
if visual_zone_touch
    record_visual_stop(z.id, bar_index)
```

In the same demand block, remove this line from the `else if wick_mitigates_zone` branch:

```pine
set_zone_mitigation_bar(z.id, bar_index)
```

The mitigation branch should remain:

```pine
else if wick_mitigates_zone
    z.mitigated := true
    z.lastTouchBar := bar_index
    z.wasTouched := true
    array.set(demandZones, i, z)
    db_updateZoneLiquidity(z)
```

- [ ] **Step 2: Update the general supply lifecycle loop**

In the `int supplySize = array.size(supplyZones)` lifecycle block, keep `had_left_zone` before the `leftZone` update and use this exact visual stop section after `returned_invalid_after_left` is calculated:

```pine
bool visual_zone_touch = had_left_zone and current_high >= z.bottom and current_low <= z.top
if visual_zone_touch
    record_visual_stop(z.id, bar_index)
```

In the same supply block, remove this line from the `else if wick_mitigates_zone` branch:

```pine
set_zone_mitigation_bar(z.id, bar_index)
```

The mitigation branch should remain:

```pine
else if wick_mitigates_zone
    z.mitigated := true
    z.lastTouchBar := bar_index
    z.wasTouched := true
    array.set(supplyZones, i, z)
    db_updateZoneLiquidity(z)
```

- [ ] **Step 3: Verify the lifecycle loops own visual stopping**

Run:

```bash
rg -n "record_visual_stop|visual_zone_touch|had_left_zone|z.isHistorical|continue  // Skip all liquidity validation" scripts/pinescript/strategies/SND_Strategy.pine
```

Expected:

```text
record_visual_stop appears only in the general demand/supply lifecycle loops.
visual_zone_touch appears only in the general demand/supply lifecycle loops.
had_left_zone appears only in the general demand/supply lifecycle loops.
The historical-zone continue statements remain only in the liquidity validation loops.
```

- [ ] **Step 4: Commit lifecycle centralization**

Run:

```bash
git add scripts/pinescript/strategies/SND_Strategy.pine
git commit -m "DEV-844: stop Pine zones on first post-leave wick touch"
```

## Task 5: Verify Drawing Uses Fixed Projection Or Frozen Stop

**Files:**
- Modify: `scripts/pinescript/strategies/SND_Strategy.pine:3238-3280`

- [ ] **Step 1: Confirm demand drawing uses `zone_visual_right(z)`**

The demand drawing block should keep:

```pine
int right_bar_index = zone_visual_right(z)
box.set_right(z.boxId,right_bar_index)
label.set_x(z.idLabel, right_bar_index)
```

Do not use `bar_index`, `lastTouchBar`, or `z.mitigated` in this drawing calculation.

- [ ] **Step 2: Confirm supply drawing uses `zone_visual_right(z)`**

In the supply drawing block, keep the equivalent:

```pine
int right_bar_index = zone_visual_right(z)
box.set_right(z.boxId,right_bar_index)
label.set_x(z.idLabel, right_bar_index)
```

Do not use `bar_index`, `lastTouchBar`, or `z.mitigated` in this drawing calculation.

- [ ] **Step 3: Run local consistency checks**

Run:

```bash
rg -n "zone_visual_right|lastTouchBar|z.mitigated|box.set_right|label.set_x" scripts/pinescript/strategies/SND_Strategy.pine
git diff --check -- scripts/pinescript/strategies/SND_Strategy.pine
```

Expected:

```text
zone_visual_right calculates from visual_stop_bar or createdBarIndex + zone_projection_bars.
box.set_right calls use zone_visual_right result.
label.set_x calls use the same right_bar_index.
git diff --check prints no output.
```

- [ ] **Step 4: Commit drawing verification changes if any were needed**

If Step 1 or Step 2 required edits, run:

```bash
git add scripts/pinescript/strategies/SND_Strategy.pine
git commit -m "DEV-844: use visual zone right edge for Pine drawing"
```

If no edits were needed, do not create an empty commit.

## Task 6: TradingView Replay Verification

**Files:**
- Verify manually in TradingView using `scripts/pinescript/strategies/SND_Strategy.pine`

- [ ] **Step 1: Load the script in TradingView**

Copy the updated `SND_Strategy.pine` into TradingView and confirm Pine compilation succeeds.

Expected: TradingView accepts the script without syntax errors.

- [ ] **Step 2: Verify USDJPY 5m reference sequence**

Use USDJPY 5m around the user-provided sequence from 2026-06-01.

Expected:

```text
D-29164-style demand zone projects 50 bars while untouched.
When the first later wick overlaps the zone, the right edge freezes at that candle.
The shortened zone remains visible after the touch.
Later candles do not move the right edge.
```

- [ ] **Step 3: Verify unmitigated projection**

Find a fresh valid demand or supply zone that has left but has not been touched.

Expected:

```text
The box right edge is createdBarIndex + 50 bars.
The box does not stop at the current candle unless the current candle is also the first post-leave wick touch.
```

- [ ] **Step 4: Verify supply symmetry**

Find a supply zone that leaves and later receives a wick touch.

Expected:

```text
The supply box freezes on the first post-leave wick overlap.
The box remains visible.
Trade labels, liquidity lines, and entries continue using existing strategy state.
```

- [ ] **Step 5: Final local check**

Run:

```bash
git diff --check -- scripts/pinescript/strategies/SND_Strategy.pine
git status --short scripts/pinescript/strategies/SND_Strategy.pine
```

Expected:

```text
git diff --check prints no output.
git status shows only the intended Pine file changes, unless other user-owned changes were already present.
```

- [ ] **Step 6: Final commit**

If Task 6 verification required fixes, commit them:

```bash
git add scripts/pinescript/strategies/SND_Strategy.pine
git commit -m "DEV-844: verify Pine zone extension behavior"
```

If no fixes were needed, do not create an empty commit.
