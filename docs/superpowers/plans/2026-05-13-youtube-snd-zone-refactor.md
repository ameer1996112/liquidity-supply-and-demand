# YouTube S&D Zone Refactor Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rebuild the Pine zone engine so zones follow the approved RD Forex / ArgerFX / Mangoe liquidity supply-and-demand rules with explainable lifecycle states.

**Architecture:** Keep the existing strategy and library files, but add a deterministic zone state machine. Zone detection, liquidity confirmation, invalidation, drawing, and entry gating become separate helper surfaces inside `SND_Strategy.pine`; the `SND_Core.Zone` model receives the minimum fields required to explain state and reasons.

**Tech Stack:** Pine Script v6, TradingView strategy runtime, existing `SND_Core` / `SND_Utils` libraries, Python static verification scripts.

---

## File Structure

- Modify `scripts/pinescript/libraries/SND_Core.pine`
  - Add zone lifecycle fields to `Zone`.
  - Add lifecycle fields to `ZoneDBEntry` so debug/inspector data can survive replay.

- Modify `scripts/pinescript/strategies/SND_Strategy.pine`
  - Add lifecycle constants, state helpers, zone bounds helpers, liquidity/BOS helpers, and entry gates.
  - Replace current mixed zone creation/mitigation/invalidation with state transitions.
  - Keep existing trade execution, risk, webhook, and performance-table behavior unless entry eligibility requires a state check.

- Create `scripts/pinescript/tests/test_snd_zone_rules_static.py`
  - Static contract checks for lifecycle fields, helper functions, and dangerous Pine patterns.

- Keep `scripts/pinescript/libraries/SND_Utils.pine` unchanged unless implementation discovers a reusable helper that belongs there. Do not move logic into `SND_Utils.pine` during the first pass.

---

### Task 1: Add Static Contract Test

**Files:**
- Create: `scripts/pinescript/tests/test_snd_zone_rules_static.py`
- Test: `scripts/pinescript/tests/test_snd_zone_rules_static.py`

- [ ] **Step 1: Create the failing static contract**

Create `scripts/pinescript/tests/test_snd_zone_rules_static.py` with this content:

```python
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
STRATEGY = ROOT / "scripts/pinescript/strategies/SND_Strategy.pine"
CORE = ROOT / "scripts/pinescript/libraries/SND_Core.pine"


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def require(text: str, needle: str, label: str) -> None:
    if needle not in text:
        raise AssertionError(f"Missing {label}: {needle}")


def reject(text: str, needle: str, label: str) -> None:
    if needle in text:
        raise AssertionError(f"Forbidden {label}: {needle}")


def main() -> None:
    strategy = read(STRATEGY)
    core = read(CORE)

    for field in [
        "int   state",
        "string stateReason",
        "int   originBarIndex",
        "int   departureEndBarIndex",
        "int   firstInvalidBarIndex",
        "int   liquiditySwingBarIndex",
        "int   structureBreakBarIndex",
        "int   entryEligibleBarIndex",
    ]:
        require(core, field, "Core.Zone lifecycle field")

    for field in [
        "int   state",
        "string stateReason",
    ]:
        require(core, field, "Core.ZoneDBEntry lifecycle field")

    for helper in [
        "const int ZONE_STATE_CANDIDATE",
        "const int ZONE_STATE_ARMED",
        "zone_state_name(int state)",
        "zone_set_state(Core.Zone z, int state, string reason)",
        "youtube_zone_bounds(bool isDemand, int originIdx, int reactionIdx)",
        "zone_is_armed_for_entry(Core.Zone z)",
        "zone_pre_entry_invalidated(Core.Zone z, bool isDemand)",
        "zone_update_expiry(Core.Zone z)",
    ]:
        require(strategy, helper, "strategy lifecycle helper")

    reject(strategy, "to 0 by -1", "negative Pine loop step")
    reject(strategy, " by -", "negative Pine loop step")

    print("SND zone rule static contract passed")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Run the contract and verify it fails**

Run:

```bash
python3 scripts/pinescript/tests/test_snd_zone_rules_static.py
```

Expected result:

```text
AssertionError: Missing Core.Zone lifecycle field: int   state
```

- [ ] **Step 3: Commit the failing contract**

Run:

```bash
git add scripts/pinescript/tests/test_snd_zone_rules_static.py
git commit -m "DEV-421: add SND zone rule static contract"
```

---

### Task 2: Extend Zone Data Model

**Files:**
- Modify: `scripts/pinescript/libraries/SND_Core.pine`
- Test: `scripts/pinescript/tests/test_snd_zone_rules_static.py`

- [ ] **Step 1: Add lifecycle fields to `Core.Zone`**

In `scripts/pinescript/libraries/SND_Core.pine`, inside `export type Zone`, immediately after `int   startTime`, add:

```pine
    // Lifecycle state machine
    int   state
    string stateReason
    int   originBarIndex
    int   departureEndBarIndex
    int   firstInvalidBarIndex
    int   liquiditySwingBarIndex
    int   structureBreakBarIndex
    int   entryEligibleBarIndex
```

- [ ] **Step 2: Add lifecycle fields to `Core.ZoneDBEntry`**

Inside `export type ZoneDBEntry`, immediately after `string inactiveReason`, add:

```pine
    int   state
    string stateReason
```

- [ ] **Step 3: Run the static contract and capture the next failure**

Run:

```bash
python3 scripts/pinescript/tests/test_snd_zone_rules_static.py
```

Expected result:

```text
AssertionError: Missing strategy lifecycle helper: const int ZONE_STATE_CANDIDATE
```

- [ ] **Step 4: Commit the data model change**

Run:

```bash
git add scripts/pinescript/libraries/SND_Core.pine
git commit -m "DEV-421: add lifecycle fields to SND zones"
```

---

### Task 3: Add Lifecycle Constants and State Helpers

**Files:**
- Modify: `scripts/pinescript/strategies/SND_Strategy.pine`
- Test: `scripts/pinescript/tests/test_snd_zone_rules_static.py`

- [ ] **Step 1: Add state constants**

In `scripts/pinescript/strategies/SND_Strategy.pine`, near the existing `const int` declarations, add:

```pine
const int ZONE_STATE_CANDIDATE = 0
const int ZONE_STATE_FRESH = 1
const int ZONE_STATE_LIQUIDITY_FORMED = 2
const int ZONE_STATE_CONFIRMED = 3
const int ZONE_STATE_ARMED = 4
const int ZONE_STATE_MITIGATED = 5
const int ZONE_STATE_USED = 6
const int ZONE_STATE_INVALID = 7
const int ZONE_STATE_EXPIRED = 8
```

- [ ] **Step 2: Add lifecycle helper functions**

Below the color/helper utility area and before zone arrays are first mutated, add:

```pine
zone_state_name(int state) =>
    switch state
        ZONE_STATE_CANDIDATE => "Candidate"
        ZONE_STATE_FRESH => "Fresh"
        ZONE_STATE_LIQUIDITY_FORMED => "Liquidity"
        ZONE_STATE_CONFIRMED => "Confirmed"
        ZONE_STATE_ARMED => "Armed"
        ZONE_STATE_MITIGATED => "Mitigated"
        ZONE_STATE_USED => "Used"
        ZONE_STATE_INVALID => "Invalid"
        ZONE_STATE_EXPIRED => "Expired"
        => "Unknown"

zone_set_state(Core.Zone z, int state, string reason) =>
    z.state := state
    z.stateReason := reason
    if state == ZONE_STATE_INVALID or state == ZONE_STATE_EXPIRED
        z.active := false
        if na(z.firstInvalidBarIndex)
            z.firstInvalidBarIndex := bar_index
        z.inactiveReason := reason
    z

zone_is_terminal(Core.Zone z) =>
    z.state == ZONE_STATE_INVALID or z.state == ZONE_STATE_EXPIRED or z.state == ZONE_STATE_USED

zone_is_armed_for_entry(Core.Zone z) =>
    z.active and z.state == ZONE_STATE_ARMED and na(z.lastEntryBar)

zone_is_visible_clean(Core.Zone z) =>
    z.active and (z.state == ZONE_STATE_FRESH or z.state == ZONE_STATE_LIQUIDITY_FORMED or z.state == ZONE_STATE_CONFIRMED or z.state == ZONE_STATE_ARMED or z.state == ZONE_STATE_MITIGATED or z.state == ZONE_STATE_USED)
```

- [ ] **Step 3: Run the static contract**

Run:

```bash
python3 scripts/pinescript/tests/test_snd_zone_rules_static.py
```

Expected result:

```text
AssertionError: Missing strategy lifecycle helper: youtube_zone_bounds(bool isDemand, int originIdx, int reactionIdx)
```

- [ ] **Step 4: Run Pine parameter contract**

Run:

```bash
python3 -m scripts.optimizer.param_contract
```

Expected result: command exits with code `0`.

- [ ] **Step 5: Commit lifecycle helpers**

Run:

```bash
git add scripts/pinescript/strategies/SND_Strategy.pine
git commit -m "DEV-421: add SND zone lifecycle helpers"
```

---

### Task 4: Replace Zone Bounds With YouTube Normal/Accuracy Rules

**Files:**
- Modify: `scripts/pinescript/strategies/SND_Strategy.pine`
- Test: `scripts/pinescript/tests/test_snd_zone_rules_static.py`

- [ ] **Step 1: Add YouTube zone detection inputs**

Near existing zone detection inputs, add:

```pine
youtube_snd_rules = input.bool(true, "YouTube S&D Zone Rules", group = "📐 Zone Detection")
youtube_accuracy_zones = input.bool(true, "YouTube Accuracy Zones", group = "📐 Zone Detection")
youtube_strict_departure = input.bool(false, "Strict 3-Candle Departure", group = "📐 Zone Detection")
youtube_min_liq_candles = input.int(2, "Min Liquidity Candles", minval = 1, maxval = 5, group = "💧 Liquidity")
youtube_close_based_bos = input.bool(true, "Close-Based BOS", group = "💧 Liquidity")
youtube_zone_lifetime_hours = input.float(24.0, "Zone Lifetime Hours", minval = 0.0, maxval = 168.0, step = 1.0, group = "📐 Zone Detection")
```

- [ ] **Step 2: Add candle and bounds helpers**

Below lifecycle helpers, add:

```pine
candle_is_bullish(int idx) =>
    close[idx] > open[idx]

candle_is_bearish(int idx) =>
    close[idx] < open[idx]

candle_body_high(int idx) =>
    math.max(open[idx], close[idx])

candle_body_low(int idx) =>
    math.min(open[idx], close[idx])

youtube_accuracy_applies(bool isDemand, int originIdx, int reactionIdx) =>
    bool applies = false
    if youtube_accuracy_zones and reactionIdx >= 0
        if isDemand
            applies := high[originIdx] > high[reactionIdx]
        else
            applies := low[originIdx] < low[reactionIdx]
    applies

youtube_zone_bounds(bool isDemand, int originIdx, int reactionIdx) =>
    bool isAccuracy = youtube_accuracy_applies(isDemand, originIdx, reactionIdx)
    float zTop = high[originIdx]
    float zBottom = low[originIdx]
    if isAccuracy
        if isDemand
            zTop := candle_body_high(originIdx)
            zBottom := low[originIdx]
        else
            zTop := high[originIdx]
            zBottom := candle_body_low(originIdx)
    [zTop, zBottom, isAccuracy]
```

- [ ] **Step 3: Replace `createZone()` bounds logic**

Inside `createZone()`, replace the current `isAccuracy`, `zTop`, and `zBottom` calculation block with:

```pine
        bool isAccuracy = false
        float zTop = na
        float zBottom = na

        if proceed_creation
            int reactionIdx = baseIdx - 1
            if youtube_snd_rules
                [ytTop, ytBottom, ytAccuracy] = youtube_zone_bounds(isDemand, baseIdx, reactionIdx)
                zTop := ytTop
                zBottom := ytBottom
                isAccuracy := ytAccuracy
            else
                int reactionIdxLegacy = baseIdx - 1
                if should_use_accuracy_zones and reactionIdxLegacy >= 0
                    if isDemand and high[baseIdx] > high[reactionIdxLegacy]
                        isAccuracy := true
                    if not isDemand and low[baseIdx] < low[reactionIdxLegacy]
                        isAccuracy := true
                if isAccuracy
                    if isDemand
                        zTop := baseOpen
                        zBottom := baseLow
                    else
                        zTop := baseHigh
                        zBottom := baseOpen
                else
                    zTop := baseHigh
                    zBottom := baseLow
```

- [ ] **Step 4: Initialize new zone state in `createZone()`**

After assigning `z.startTime`, add:

```pine
            z.state := ZONE_STATE_CANDIDATE
            z.stateReason := "Origin detected"
            z.originBarIndex := baseBarIdx
            z.departureEndBarIndex := bar_index
            z.firstInvalidBarIndex := na
            z.liquiditySwingBarIndex := na
            z.structureBreakBarIndex := na
            z.entryEligibleBarIndex := na
            z := zone_set_state(z, ZONE_STATE_FRESH, "Fresh departure zone")
```

- [ ] **Step 5: Run static checks**

Run:

```bash
python3 scripts/pinescript/tests/test_snd_zone_rules_static.py
python3 -m scripts.optimizer.param_contract
git diff --check -- scripts/pinescript/strategies/SND_Strategy.pine scripts/pinescript/libraries/SND_Core.pine
```

Expected result: static contract may still fail on lifecycle helpers not yet added in later tasks; `param_contract` and `git diff --check` exit with code `0`.

- [ ] **Step 6: Commit bounds changes**

Run:

```bash
git add scripts/pinescript/strategies/SND_Strategy.pine
git commit -m "DEV-421: apply YouTube normal and accuracy zone bounds"
```

---

### Task 5: Add Departure, Premature Tap, and Expiry Rules

**Files:**
- Modify: `scripts/pinescript/strategies/SND_Strategy.pine`
- Test: `scripts/pinescript/tests/test_snd_zone_rules_static.py`

- [ ] **Step 1: Add departure validation helpers**

Below `youtube_zone_bounds()`, add:

```pine
youtube_departure_valid(bool isDemand, int originIdx, int legCandles) =>
    bool directionOk = false
    if isDemand
        directionOk := legCandles >= 1 and candle_is_bullish(originIdx - 1)
        if youtube_strict_departure and originIdx - 2 >= 0
            directionOk := directionOk and candle_is_bullish(originIdx - 2)
    else
        directionOk := legCandles >= 1 and candle_is_bearish(originIdx - 1)
        if youtube_strict_departure and originIdx - 2 >= 0
            directionOk := directionOk and candle_is_bearish(originIdx - 2)
    directionOk

zone_touching(Core.Zone z) =>
    high >= z.bottom and low <= z.top

zone_close_inside(Core.Zone z) =>
    close <= z.top and close >= z.bottom

zone_distal_broken(Core.Zone z, bool isDemand) =>
    isDemand ? close < z.bottom : close > z.top

zone_is_departure_bar(Core.Zone z) =>
    not na(z.departureEndBarIndex) and bar_index <= z.departureEndBarIndex

zone_same_direction_departure_touch_allowed(bool isDemand) =>
    isDemand ? candle_is_bullish(0) : candle_is_bearish(0)
```

- [ ] **Step 2: Add invalidation and expiry helpers**

Add:

```pine
zone_pre_entry_invalidated(Core.Zone z, bool isDemand) =>
    bool invalid = false
    string reason = ""
    bool touching = zone_touching(z)
    bool closeInside = zone_close_inside(z)
    bool distalBroken = zone_distal_broken(z, isDemand)
    bool departureException = zone_is_departure_bar(z) and zone_same_direction_departure_touch_allowed(isDemand)
    if touching and not departureException and z.state < ZONE_STATE_ARMED
        invalid := true
        reason := "Touched before liquidity+BOS"
    if closeInside and z.state < ZONE_STATE_ARMED
        invalid := true
        reason := "Closed inside before entry"
    if distalBroken
        invalid := true
        reason := "Distal break"
    [invalid, reason]

zone_has_open_trade(Core.Zone z) =>
    strategy.position_size != 0 and not na(trade_zone_id) and trade_zone_id == z.id

zone_update_expiry(Core.Zone z) =>
    Core.Zone updated = z
    if youtube_zone_lifetime_hours > 0 and not na(z.startTime) and not zone_has_open_trade(z)
        float maxAgeMs = youtube_zone_lifetime_hours * 60.0 * 60.0 * 1000.0
        if (time - z.startTime) > maxAgeMs and z.state != ZONE_STATE_USED
            updated := zone_set_state(updated, ZONE_STATE_EXPIRED, "Zone lifetime expired")
    updated
```

- [ ] **Step 3: Apply departure validation inside `createZone()`**

Before drawing the box in `createZone()`, add:

```pine
            bool departureOk = not youtube_snd_rules or youtube_departure_valid(isDemand, baseIdx, legCandles)
            proceed_creation := proceed_creation and departureOk
```

- [ ] **Step 4: Replace hard removal for pre-entry closes**

In the demand and supply invalidation loops around the current `remove_zone_all_arrays(...)` calls, replace direct boolean invalidation with:

```pine
                [preInvalid, preInvalidReason] = zone_pre_entry_invalidated(z, true)
                z := zone_update_expiry(z)
                if preInvalid
                    z := zone_set_state(z, ZONE_STATE_INVALID, preInvalidReason)
                    array.set(demandZones, i, z)
                    db_markInactive(z.id, preInvalidReason)
                    remove_zone_all_arrays(true, i)
                else if z.state == ZONE_STATE_EXPIRED
                    array.set(demandZones, i, z)
                    db_markInactive(z.id, z.stateReason)
                    remove_zone_all_arrays(true, i)
```

For supply, use `false` and `supplyZones`:

```pine
                [preInvalid, preInvalidReason] = zone_pre_entry_invalidated(z, false)
                z := zone_update_expiry(z)
                if preInvalid
                    z := zone_set_state(z, ZONE_STATE_INVALID, preInvalidReason)
                    array.set(supplyZones, i, z)
                    db_markInactive(z.id, preInvalidReason)
                    remove_zone_all_arrays(false, i)
                else if z.state == ZONE_STATE_EXPIRED
                    array.set(supplyZones, i, z)
                    db_markInactive(z.id, z.stateReason)
                    remove_zone_all_arrays(false, i)
```

- [ ] **Step 5: Run verification**

Run:

```bash
python3 scripts/pinescript/tests/test_snd_zone_rules_static.py
python3 -m scripts.optimizer.param_contract
git diff --check -- scripts/pinescript/strategies/SND_Strategy.pine
```

Expected result: static contract may still fail on liquidity/BOS helpers until Task 6; other commands exit with code `0`.

- [ ] **Step 6: Commit invalidation helpers**

Run:

```bash
git add scripts/pinescript/strategies/SND_Strategy.pine
git commit -m "DEV-421: add YouTube zone invalidation and expiry rules"
```

---

### Task 6: Replace Liquidity and BOS State Updates

**Files:**
- Modify: `scripts/pinescript/strategies/SND_Strategy.pine`
- Test: `scripts/pinescript/tests/test_snd_zone_rules_static.py`

- [ ] **Step 1: Add liquidity validation helpers**

Below expiry helpers, add:

```pine
zone_liquidity_touches_zone(Core.Zone z, bool isDemand) =>
    bool touches = false
    if isDemand and not na(z.liqLowPrice)
        touches := z.liqLowPrice <= z.top and z.liqLowPrice >= z.bottom
    if not isDemand and not na(z.liqHighPrice)
        touches := z.liqHighPrice <= z.top and z.liqHighPrice >= z.bottom
    touches

zone_liquidity_has_min_candles(Core.Zone z) =>
    z.liquidityCandleCount >= youtube_min_liq_candles

zone_liquidity_ready(Core.Zone z, bool isDemand) =>
    bool hasLevel = isDemand ? not na(z.liqLowPrice) : not na(z.liqHighPrice)
    hasLevel and z.liquidityValid and zone_liquidity_has_min_candles(z) and not zone_liquidity_touches_zone(z, isDemand)

zone_structure_broken(Core.Zone z, bool isDemand) =>
    bool broken = false
    if not na(z.structureSweepLevel)
        if isDemand
            broken := youtube_close_based_bos ? close > z.structureSweepLevel : high > z.structureSweepLevel
        else
            broken := youtube_close_based_bos ? close < z.structureSweepLevel : low < z.structureSweepLevel
    broken
```

- [ ] **Step 2: Add lifecycle updater for liquidity and BOS**

Add:

```pine
zone_update_liquidity_and_bos(Core.Zone z, bool isDemand) =>
    Core.Zone updated = z
    if zone_liquidity_touches_zone(updated, isDemand)
        updated := zone_set_state(updated, ZONE_STATE_INVALID, "Liquidity touched zone")
    else if zone_liquidity_ready(updated, isDemand) and updated.state == ZONE_STATE_FRESH
        updated.liquiditySwingBarIndex := isDemand ? updated.liqLowBar : updated.liqHighBar
        updated := zone_set_state(updated, ZONE_STATE_LIQUIDITY_FORMED, "Valid visual liquidity")
    if updated.state == ZONE_STATE_LIQUIDITY_FORMED and zone_structure_broken(updated, isDemand)
        updated.structureBreakBarIndex := bar_index
        updated := zone_set_state(updated, ZONE_STATE_CONFIRMED, "Liquidity broke own structure")
    if updated.state == ZONE_STATE_CONFIRMED and updated.liquiditySwept
        updated.entryEligibleBarIndex := bar_index
        updated := zone_set_state(updated, ZONE_STATE_ARMED, "Liquidity swept; entry allowed")
    updated
```

- [ ] **Step 3: Wire demand liquidity update**

In the demand zone management loop, immediately after `f_check_demand_sweeps(i)`, add:

```pine
            z := array.get(demandZones, i)
            z := zone_update_liquidity_and_bos(z, true)
            array.set(demandZones, i, z)
            if z.state == ZONE_STATE_INVALID
                db_markInactive(z.id, z.stateReason)
                remove_zone_all_arrays(true, i)
                continue
```

- [ ] **Step 4: Wire supply liquidity update**

In the supply zone management loop, immediately after `f_check_supply_sweeps(i)`, add:

```pine
            z := array.get(supplyZones, i)
            z := zone_update_liquidity_and_bos(z, false)
            array.set(supplyZones, i, z)
            if z.state == ZONE_STATE_INVALID
                db_markInactive(z.id, z.stateReason)
                remove_zone_all_arrays(false, i)
                continue
```

- [ ] **Step 5: Run all static checks**

Run:

```bash
python3 scripts/pinescript/tests/test_snd_zone_rules_static.py
python3 -m scripts.optimizer.param_contract
git diff --check -- scripts/pinescript/strategies/SND_Strategy.pine
```

Expected result:

```text
SND zone rule static contract passed
```

and both remaining commands exit with code `0`.

- [ ] **Step 6: Commit liquidity/BOS lifecycle**

Run:

```bash
git add scripts/pinescript/strategies/SND_Strategy.pine scripts/pinescript/tests/test_snd_zone_rules_static.py
git commit -m "DEV-421: add YouTube liquidity and BOS zone states"
```

---

### Task 7: Gate Entries and Drawing by Zone State

**Files:**
- Modify: `scripts/pinescript/strategies/SND_Strategy.pine`
- Test: `scripts/pinescript/tests/test_snd_zone_rules_static.py`

- [ ] **Step 1: Gate validation by `Armed` state**

In `validate_entry_conditions(bool isDemand, int idx)`, after loading `z`, add:

```pine
        if canEnter and youtube_snd_rules and not zone_is_armed_for_entry(z)
            canEnter := false
            reason := "Zone not armed: " + zone_state_name(z.state) + " / " + z.stateReason
```

- [ ] **Step 2: Mark zone as used after a long entry**

In the successful long entry block, after `z.lastEntryBar := bar_index`, add:

```pine
                        z := zone_set_state(z, ZONE_STATE_USED, "Long entry opened")
```

- [ ] **Step 3: Mark zone as used after a short entry**

In the successful short entry block, after `z.lastEntryBar := bar_index`, add:

```pine
                        z := zone_set_state(z, ZONE_STATE_USED, "Short entry opened")
```

- [ ] **Step 4: Hide invalid zones in clean drawing loops**

In demand and supply drawing loops, replace `if z.active` with:

```pine
        if z.active and (display_is_debug or zone_is_visible_clean(z))
```

- [ ] **Step 5: Show state in debug labels**

Where demand/supply label text is built, add this suffix only when debug labels are enabled:

```pine
                        string stateSuffix = show_debug_labels ? ("\n" + zone_state_name(z.state) + ": " + z.stateReason) : ""
```

Then append `stateSuffix` to the label text used by `label.set_text(...)`.

- [ ] **Step 6: Run verification**

Run:

```bash
python3 scripts/pinescript/tests/test_snd_zone_rules_static.py
python3 -m scripts.optimizer.param_contract
git diff --check -- scripts/pinescript/strategies/SND_Strategy.pine
```

Expected result: all commands exit with code `0`.

- [ ] **Step 7: Commit entry and drawing gates**

Run:

```bash
git add scripts/pinescript/strategies/SND_Strategy.pine
git commit -m "DEV-421: gate entries and drawings by zone state"
```

---

### Task 8: Optimize Pine Runtime and Object Safety

**Files:**
- Modify: `scripts/pinescript/strategies/SND_Strategy.pine`
- Test: `scripts/pinescript/tests/test_snd_zone_rules_static.py`

- [ ] **Step 1: Ensure loops use cached sizes and positive steps**

Search:

```bash
rg -n "for .* by -|to 0 by|array\\.size\\(.*\\).*for" scripts/pinescript/strategies/SND_Strategy.pine
```

Expected result: no `by -` or `to 0 by` matches.

- [ ] **Step 2: Convert any new reverse scans to `while`**

If a new reverse scan is needed, use this exact pattern:

```pine
int scanIdx = array.size(supplyZones) - 1
while scanIdx >= 0
    Core.Zone scanZone = array.get(supplyZones, scanIdx)
    // read or update scanZone here
    scanIdx -= 1
```

- [ ] **Step 3: Ensure removed zones clear objects**

Before any `array.remove(...)` call for zones, ensure the code calls:

```pine
z := clear_zone_visual_objects(z, isSupply)
```

Use `isSupply = false` for demand and `isSupply = true` for supply.

- [ ] **Step 4: Run verification**

Run:

```bash
python3 scripts/pinescript/tests/test_snd_zone_rules_static.py
python3 -m scripts.optimizer.param_contract
git diff --check -- scripts/pinescript/strategies/SND_Strategy.pine scripts/pinescript/libraries/SND_Core.pine
```

Expected result: all commands exit with code `0`.

- [ ] **Step 5: Commit runtime safety**

Run:

```bash
git add scripts/pinescript/strategies/SND_Strategy.pine
git commit -m "DEV-421: harden SND zone runtime safety"
```

---

### Task 9: TradingView Paste and Replay Verification

**Files:**
- Modify: none
- Test: TradingView Pine Editor and Bar Replay

- [ ] **Step 1: Copy strategy to clipboard**

Run:

```bash
pbcopy < scripts/pinescript/strategies/SND_Strategy.pine
```

Expected result: command exits with code `0`.

- [ ] **Step 2: Paste into TradingView**

In TradingView Pine Editor:

1. Select all strategy code.
2. Paste clipboard content.
3. Save.
4. Add to chart.

Expected result: no compiled-token error and no runtime error.

- [ ] **Step 3: Verify XAUUSD 5m replay scenarios**

Use the user’s replay cases:

- Supply zone where price closes inside before confirmation: zone must disappear or show `Invalid` in debug mode.
- Demand zone where same-direction departure wicks enter the zone: zone must remain valid.
- Liquidity made by one opposite candle: zone must not become `Armed`.
- Liquidity touches the zone before BOS: zone must become `Invalid`.
- Confirmed zone returns after sweep and rejects: zone becomes `Armed`, then `Mitigated` or `Used`.

- [ ] **Step 4: Record remaining mismatches**

If a mismatch appears, capture:

```text
Symbol:
Timeframe:
Replay date/time:
Zone label:
Expected state:
Actual state:
Screenshot:
```

- [ ] **Step 5: Final commit if replay verification required small fixes**

If verification required code changes, run the static checks again and commit:

```bash
python3 scripts/pinescript/tests/test_snd_zone_rules_static.py
python3 -m scripts.optimizer.param_contract
git diff --check -- scripts/pinescript/strategies/SND_Strategy.pine scripts/pinescript/libraries/SND_Core.pine
git add scripts/pinescript/strategies/SND_Strategy.pine scripts/pinescript/libraries/SND_Core.pine scripts/pinescript/tests/test_snd_zone_rules_static.py
git commit -m "DEV-421: align SND zone refactor with replay checks"
```

---

## Self-Review

Spec coverage:

- Source priority is covered by Task 4 using YouTube rules as the active path.
- Formation and accuracy zones are covered by Task 4.
- Fresh/untapped, premature tap, close-inside, distal break, and expiry invalidation are covered by Task 5.
- Liquidity, minimum opposite candles, liquidity touching zone, and BOS state changes are covered by Task 6.
- Entry eligibility, used state, and clean/debug display gates are covered by Task 7.
- Runtime constraints and TradingView verification are covered by Tasks 8 and 9.

Placeholder scan:

- The plan contains no empty placeholders, no missing function definitions, and no skipped implementation steps.

Type consistency:

- Lifecycle fields are defined in Task 2 before strategy helpers use them in Task 3.
- Helper names in the static contract match the helper definitions in Tasks 3 through 5.
- `ZONE_STATE_ARMED` is the only entry-eligible state by Task 7.
