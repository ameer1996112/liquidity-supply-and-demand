# Clean SND Detector Prototype Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a new visual-only Pine v6 indicator that detects cleaner supply/demand zones and liquidity without changing the current live strategy.

**Architecture:** Add one isolated prototype indicator under `scripts/pinescript/indicators/`. The indicator owns a small zone state machine, sparse rendering, and internal/external liquidity selection; it has no strategy orders and no production alert path. The current live strategy and shared libraries stay unchanged.

**Tech Stack:** TradingView Pine Script v6, source-level shell checks with `rg`, manual TradingView compile/visual validation.

---

## File Structure

- Create: `scripts/pinescript/indicators/SND_Clean_Zones_Prototype.pine`
  - Visual-only overlay indicator.
  - Owns `CleanZone` state, detection helpers, zone lifecycle, liquidity selection, and rendering.
- Do not modify: `scripts/pinescript/strategies/SND_Strategy.pine`
  - Live strategy remains untouched.
- Do not modify: `scripts/pinescript/libraries/SND_Core.pine`
  - Shared logic remains untouched for this prototype.
- Do not modify: `scripts/pinescript/libraries/SND_Utils.pine`
  - Shared utilities remain untouched for this prototype.

## Task 1: Add The Visual-Only Indicator Skeleton

**Files:**
- Create: `scripts/pinescript/indicators/SND_Clean_Zones_Prototype.pine`

- [ ] **Step 1: Verify the prototype file does not already exist**

Run:

```bash
test ! -f scripts/pinescript/indicators/SND_Clean_Zones_Prototype.pine
```

Expected: exit code `0`.

- [ ] **Step 2: Create the initial Pine file**

Create `scripts/pinescript/indicators/SND_Clean_Zones_Prototype.pine` with this exact content:

```pine
// This Pine Script code is subject to the terms of the Mozilla Public License 2.0 at https://mozilla.org/MPL/2.0/
// Clean SND detector prototype.
// Visual-only shadow indicator. It does not place trades and does not emit production alerts.

//@version=6
indicator("SND Clean Zones Prototype", shorttitle="SND Clean Zones", overlay=true, max_boxes_count=120, max_lines_count=240, max_labels_count=120, max_bars_back=1000)

const int SIDE_DEMAND = 1
const int SIDE_SUPPLY = -1

const int STATE_WAITING_BOS = 1
const int STATE_VALID = 2
const int STATE_TESTED = 3
const int STATE_INVALID = 4

const int LIQ_NONE = 0
const int LIQ_INTERNAL = 1
const int LIQ_EXTERNAL = 2

grpDetection = "Zone Detection"
max_zones = input.int(8, "Max Zones", minval=1, maxval=30, group=grpDetection)
base_max_candles = input.int(4, "Max Base Candles", minval=1, maxval=8, group=grpDetection)
base_body_max_pct = input.float(50.0, "Max Base Body %", minval=5.0, maxval=90.0, step=1.0, group=grpDetection)
base_range_atr_max = input.float(1.15, "Max Base Range ATR", minval=0.1, maxval=5.0, step=0.05, group=grpDetection)
displacement_atr_min = input.float(0.80, "Min Displacement ATR", minval=0.1, maxval=5.0, step=0.05, group=grpDetection)
bos_lookback = input.int(20, "BOS Lookback", minval=5, maxval=100, group=grpDetection)
strict_bos_close_beyond_level = input.bool(false, "Strict BOS Close Beyond Level", group=grpDetection)
enable_accuracy_zones = input.bool(true, "Enable Accuracy Zones", group=grpDetection)

grpLiquidity = "Liquidity Detection"
enable_one_candle_liquidity = input.bool(true, "Enable One Candle Liquidity", group=grpLiquidity)
liquidity_scan_bars = input.int(120, "Liquidity Scan Bars", minval=20, maxval=500, group=grpLiquidity)
max_internal_liquidity_atr = input.float(0.618, "Max Internal Liquidity Distance ATR", minval=0.05, maxval=5.0, step=0.001, group=grpLiquidity)
max_external_liquidity_atr = input.float(1.414, "Max External Liquidity Distance ATR", minval=0.05, maxval=8.0, step=0.001, group=grpLiquidity)
external_structure_max_percent_of_move = input.float(30.0, "External Structure Max % Of Move", minval=1.0, maxval=100.0, step=1.0, group=grpLiquidity)
show_target_liquidity = input.bool(true, "Show Target Liquidity", group=grpLiquidity)

grpDisplay = "Display"
show_waiting_bos = input.bool(false, "Show Waiting BOS Zones", group=grpDisplay)
show_invalid_zones = input.bool(false, "Show Invalid Zones", group=grpDisplay)
show_state_labels = input.bool(false, "Show State Labels", group=grpDisplay)
show_debug = input.bool(false, "Debug Mode", group=grpDisplay)

atr14 = ta.atr(14)

type CleanZone
    int id
    int side
    int state
    int createdBar
    int baseStartBar
    int baseEndBar
    float top
    float bottom
    float bosLevel
    int bosBar
    bool isAccuracy
    float inducementPrice
    int inducementBar
    int liquidityMode
    bool inducementSwept
    float targetPrice
    int targetBar
    bool targetSwept
    int touchCount
    int lastTouchBar
    box zoneBox
    line inducementLine
    line targetLine
    label stateLabel

var CleanZone[] zones = array.new<CleanZone>()
var int[] next_zone_id = array.new_int(1, 1)
```

- [ ] **Step 3: Run source checks for visual-only safety**

Run:

```bash
rg -n "strategy\\.(entry|order|exit|close)|alertcondition\\(|alert\\(" scripts/pinescript/indicators/SND_Clean_Zones_Prototype.pine
```

Expected: no matches and exit code `1`.

- [ ] **Step 4: Commit the skeleton**

Run:

```bash
git add scripts/pinescript/indicators/SND_Clean_Zones_Prototype.pine
git commit -m "DEV-328: add clean SND detector skeleton"
```

Expected: commit succeeds with only the new prototype file.

## Task 2: Add Detector Helpers

**Files:**
- Modify: `scripts/pinescript/indicators/SND_Clean_Zones_Prototype.pine`

- [ ] **Step 1: Append helper functions after `var int[] next_zone_id = array.new_int(1, 1)`**

Append this exact block:

```pine
f_pip_size() =>
    bool is_jpy_pair = str.contains(syminfo.ticker, "JPY")
    syminfo.type == "forex" ? (is_jpy_pair ? 0.01 : 0.0001) : syminfo.mintick

pip_size = f_pip_size()

f_body_pct(int off) =>
    float candleRange = high[off] - low[off]
    candleRange > 0.0 ? math.abs(close[off] - open[off]) / candleRange * 100.0 : 100.0

f_is_base_candle(int off) =>
    float candleRange = high[off] - low[off]
    bool smallBody = f_body_pct(off) <= base_body_max_pct
    bool controlledRange = na(atr14) or atr14 <= 0.0 ? true : candleRange <= atr14 * base_range_atr_max
    smallBody and controlledRange

f_base_count() =>
    int count = 0
    for off = 1 to base_max_candles
        if off > bar_index
            break
        if f_is_base_candle(off)
            count += 1
        else
            break
    count

f_base_bounds(int baseCount) =>
    float bodyHigh = math.max(open[1], close[1])
    float bodyLow = math.min(open[1], close[1])
    float wickHigh = high[1]
    float wickLow = low[1]

    if baseCount > 1
        for off = 2 to baseCount
            bodyHigh := math.max(bodyHigh, math.max(open[off], close[off]))
            bodyLow := math.min(bodyLow, math.min(open[off], close[off]))
            wickHigh := math.max(wickHigh, high[off])
            wickLow := math.min(wickLow, low[off])

    [bodyHigh, bodyLow, wickHigh, wickLow]

f_displacement_ok(bool isDemand, float bodyHigh, float bodyLow, float wickHigh, float wickLow) =>
    float candleRange = high - low
    bool rangeOk = na(atr14) or atr14 <= 0.0 ? true : candleRange >= atr14 * displacement_atr_min
    bool directionOk = isDemand ? close > open : close < open
    bool leftBase = isDemand ? close > wickHigh : close < wickLow
    rangeOk and directionOk and leftBase and bodyHigh >= bodyLow

f_bos_level(bool isDemand, int baseCount) =>
    int startOffset = baseCount + 1
    float level = isDemand ? high[startOffset] : low[startOffset]
    int levelBar = bar_index - startOffset

    for off = startOffset to startOffset + bos_lookback - 1
        if off > bar_index
            break
        if isDemand
            if high[off] > level
                level := high[off]
                levelBar := bar_index - off
        else
            if low[off] < level
                level := low[off]
                levelBar := bar_index - off

    [level, levelBar]

f_breaks_bos(bool isDemand, float level) =>
    if na(level)
        false
    else if strict_bos_close_beyond_level
        isDemand ? close > level : close < level
    else
        isDemand ? high > level : low < level

f_state_name(int state) =>
    state == STATE_WAITING_BOS ? "WAITING_BOS" :
      state == STATE_VALID ? "VALID" :
      state == STATE_TESTED ? "TESTED" :
      state == STATE_INVALID ? "INVALID" : "UNKNOWN"

f_side_name(int side) =>
    side == SIDE_DEMAND ? "DEMAND" : "SUPPLY"
```

- [ ] **Step 2: Run helper source checks**

Run:

```bash
rg -n "f_base_count|f_base_bounds|f_displacement_ok|f_bos_level|f_breaks_bos" scripts/pinescript/indicators/SND_Clean_Zones_Prototype.pine
```

Expected: matches for all five helper names.

- [ ] **Step 3: Commit detector helpers**

Run:

```bash
git add scripts/pinescript/indicators/SND_Clean_Zones_Prototype.pine
git commit -m "DEV-328: add clean detector helper functions"
```

Expected: commit succeeds with only the prototype file.

## Task 3: Add Zone Creation And BOS Promotion

**Files:**
- Modify: `scripts/pinescript/indicators/SND_Clean_Zones_Prototype.pine`

- [ ] **Step 1: Append zone creation functions after `f_side_name`**

Append this exact block:

```pine
f_overlaps_existing(float top, float bottom, int side) =>
    bool overlaps = false
    if array.size(zones) > 0
        for i = 0 to array.size(zones) - 1
            CleanZone existing = array.get(zones, i)
            bool sameSide = existing.side == side
            bool liveState = existing.state == STATE_WAITING_BOS or existing.state == STATE_VALID or existing.state == STATE_TESTED
            bool rangesOverlap = not (existing.top < bottom or existing.bottom > top)
            if sameSide and liveState and rangesOverlap
                overlaps := true
                break
    overlaps

f_trim_zones() =>
    while array.size(zones) > max_zones
        CleanZone old = array.pop(zones)
        if not na(old.zoneBox)
            box.delete(old.zoneBox)
        if not na(old.inducementLine)
            line.delete(old.inducementLine)
        if not na(old.targetLine)
            line.delete(old.targetLine)
        if not na(old.stateLabel)
            label.delete(old.stateLabel)

f_create_zone(bool isDemand, int baseCount, float bodyHigh, float bodyLow, float wickHigh, float wickLow) =>
    int side = isDemand ? SIDE_DEMAND : SIDE_SUPPLY
    float top = na
    float bottom = na
    bool isAccuracy = false

    if isDemand
        isAccuracy := enable_accuracy_zones and high[1] > high
        top := isAccuracy ? math.max(open[1], close[1]) : wickHigh
        bottom := wickLow
    else
        isAccuracy := enable_accuracy_zones and low[1] < low
        top := wickHigh
        bottom := isAccuracy ? math.min(open[1], close[1]) : wickLow

    [bosLevel, bosBar] = f_bos_level(isDemand, baseCount)
    bool bosNow = f_breaks_bos(isDemand, bosLevel)
    int state = bosNow ? STATE_VALID : STATE_WAITING_BOS
    bool validBounds = not na(top) and not na(bottom) and top > bottom
    bool duplicate = validBounds ? f_overlaps_existing(top, bottom, side) : true

    if validBounds and not duplicate
        CleanZone z = CleanZone.new()
        int zoneId = array.get(next_zone_id, 0)
        z.id := zoneId
        z.side := side
        z.state := state
        z.createdBar := bar_index
        z.baseStartBar := bar_index - baseCount
        z.baseEndBar := bar_index - 1
        z.top := top
        z.bottom := bottom
        z.bosLevel := bosLevel
        z.bosBar := bosNow ? bar_index : bosBar
        z.isAccuracy := isAccuracy
        z.inducementPrice := na
        z.inducementBar := na
        z.liquidityMode := LIQ_NONE
        z.inducementSwept := false
        z.targetPrice := na
        z.targetBar := na
        z.targetSwept := false
        z.touchCount := 0
        z.lastTouchBar := na
        array.unshift(zones, z)
        array.set(next_zone_id, 0, zoneId + 1)
        f_trim_zones()

f_try_detect_zone(bool isDemand) =>
    int baseCount = f_base_count()
    if baseCount > 0
        [bodyHigh, bodyLow, wickHigh, wickLow] = f_base_bounds(baseCount)
        if f_displacement_ok(isDemand, bodyHigh, bodyLow, wickHigh, wickLow)
            f_create_zone(isDemand, baseCount, bodyHigh, bodyLow, wickHigh, wickLow)

f_promote_waiting_zones() =>
    if array.size(zones) > 0
        for i = 0 to array.size(zones) - 1
            CleanZone z = array.get(zones, i)
            if z.state == STATE_WAITING_BOS
                bool isDemand = z.side == SIDE_DEMAND
                if f_breaks_bos(isDemand, z.bosLevel)
                    z.state := STATE_VALID
                    z.bosBar := bar_index
                    array.set(zones, i, z)
```

- [ ] **Step 2: Append the detection call block at the end of the file**

Append this exact block:

```pine
if barstate.isconfirmed and bar_index > bos_lookback + base_max_candles + 5
    f_try_detect_zone(true)
    f_try_detect_zone(false)
    f_promote_waiting_zones()
```

- [ ] **Step 3: Run zone creation source checks**

Run:

```bash
rg -n "f_create_zone|STATE_WAITING_BOS|STATE_VALID|f_try_detect_zone|f_promote_waiting_zones" scripts/pinescript/indicators/SND_Clean_Zones_Prototype.pine
```

Expected: matches for all five names.

- [ ] **Step 4: Commit zone state creation**

Run:

```bash
git add scripts/pinescript/indicators/SND_Clean_Zones_Prototype.pine
git commit -m "DEV-328: add clean zone state creation"
```

Expected: commit succeeds with only the prototype file.

## Task 4: Add Internal And External Liquidity Selection

**Files:**
- Modify: `scripts/pinescript/indicators/SND_Clean_Zones_Prototype.pine`

- [ ] **Step 1: Insert liquidity helpers before the final detection call block**

Insert this exact block above `if barstate.isconfirmed and bar_index > bos_lookback + base_max_candles + 5`:

```pine
f_is_pivot_low(int off) =>
    bool enoughBars = off >= 1 and off + 1 <= bar_index
    bool twoCandle = enoughBars and low[off] < low[off - 1] and low[off] < low[off + 1]
    bool oneCandle = enoughBars and low[off] < low[off + 1]
    twoCandle or (enable_one_candle_liquidity and oneCandle)

f_is_pivot_high(int off) =>
    bool enoughBars = off >= 1 and off + 1 <= bar_index
    bool twoCandle = enoughBars and high[off] > high[off - 1] and high[off] > high[off + 1]
    bool oneCandle = enoughBars and high[off] > high[off + 1]
    twoCandle or (enable_one_candle_liquidity and oneCandle)

f_highest_between(int startBar, int endBar) =>
    float best = na
    int bestBar = na
    if not na(startBar) and not na(endBar) and endBar >= startBar
        for b = startBar to endBar
            int off = bar_index - b
            if off < 0 or off > bar_index
                continue
            if na(best) or high[off] > best
                best := high[off]
                bestBar := b
    [best, bestBar]

f_lowest_between(int startBar, int endBar) =>
    float best = na
    int bestBar = na
    if not na(startBar) and not na(endBar) and endBar >= startBar
        for b = startBar to endBar
            int off = bar_index - b
            if off < 0 or off > bar_index
                continue
            if na(best) or low[off] < best
                best := low[off]
                bestBar := b
    [best, bestBar]

f_liquidity_mode_from_distance(float distance) =>
    float internalMax = atr14 * max_internal_liquidity_atr
    float externalMax = atr14 * max_external_liquidity_atr
    distance <= internalMax ? LIQ_INTERNAL : distance <= externalMax ? LIQ_EXTERNAL : LIQ_NONE

f_scan_liquidity_for_zone(int idx) =>
    CleanZone z = array.get(zones, idx)
    if z.state == STATE_VALID or z.state == STATE_TESTED
        bool isDemand = z.side == SIDE_DEMAND
        float bestPrice = na
        int bestBar = na
        int bestMode = LIQ_NONE
        float bestScore = 1.0e10
        int maxOff = math.min(liquidity_scan_bars, bar_index - z.createdBar)

        if maxOff >= 1
            for off = 1 to maxOff
                int candidateBar = bar_index - off
                bool afterZone = candidateBar > z.createdBar
                bool isPivot = isDemand ? f_is_pivot_low(off) : f_is_pivot_high(off)
                float candidatePrice = isDemand ? low[off] : high[off]
                bool correctSide = isDemand ? candidatePrice > z.top : candidatePrice < z.bottom
                float distance = isDemand ? candidatePrice - z.top : z.bottom - candidatePrice
                int mode = distance > 0.0 ? f_liquidity_mode_from_distance(distance) : LIQ_NONE
                float moveSize = math.abs(z.bosLevel - (isDemand ? z.bottom : z.top))
                bool externalPercentOk = mode != LIQ_EXTERNAL or moveSize <= 0.0 ? true : distance <= moveSize * external_structure_max_percent_of_move / 100.0
                float score = distance + (mode == LIQ_INTERNAL ? 0.0 : atr14 * 0.25)

                if afterZone and isPivot and correctSide and mode != LIQ_NONE and externalPercentOk
                    if score < bestScore
                        bestScore := score
                        bestPrice := candidatePrice
                        bestBar := candidateBar
                        bestMode := mode

        if not na(bestPrice)
            bool changed = na(z.inducementPrice) or z.inducementPrice != bestPrice or z.inducementBar != bestBar
            z.inducementPrice := bestPrice
            z.inducementBar := bestBar
            z.liquidityMode := bestMode
            if changed
                z.inducementSwept := false
                z.targetSwept := false

            if isDemand
                [target, targetBar] = f_highest_between(z.createdBar, bestBar - 1)
                z.targetPrice := target
                z.targetBar := targetBar
            else
                [target, targetBar] = f_lowest_between(z.createdBar, bestBar - 1)
                z.targetPrice := target
                z.targetBar := targetBar

            array.set(zones, idx, z)

f_update_liquidity_sweeps(int idx) =>
    CleanZone z = array.get(zones, idx)
    if z.state == STATE_VALID or z.state == STATE_TESTED
        bool isDemand = z.side == SIDE_DEMAND
        if not na(z.inducementPrice) and not z.inducementSwept
            if isDemand ? low <= z.inducementPrice : high >= z.inducementPrice
                z.inducementSwept := true
        if show_target_liquidity and not na(z.targetPrice) and not z.targetSwept
            if isDemand ? high >= z.targetPrice : low <= z.targetPrice
                z.targetSwept := true
        array.set(zones, idx, z)

f_update_all_liquidity() =>
    if array.size(zones) > 0
        for i = 0 to array.size(zones) - 1
            CleanZone z = array.get(zones, i)
            if (z.state == STATE_VALID or z.state == STATE_TESTED) and na(z.inducementPrice)
                f_scan_liquidity_for_zone(i)
            f_update_liquidity_sweeps(i)
```

- [ ] **Step 2: Update the final detection call block**

Replace the final block with this exact block:

```pine
if barstate.isconfirmed and bar_index > bos_lookback + base_max_candles + 5
    f_try_detect_zone(true)
    f_try_detect_zone(false)
    f_promote_waiting_zones()
    f_update_all_liquidity()
```

- [ ] **Step 3: Run liquidity source checks**

Run:

```bash
rg -n "enable_one_candle_liquidity|max_internal_liquidity_atr|max_external_liquidity_atr|f_scan_liquidity_for_zone|f_update_all_liquidity" scripts/pinescript/indicators/SND_Clean_Zones_Prototype.pine
```

Expected: matches for all five names.

- [ ] **Step 4: Commit liquidity selection**

Run:

```bash
git add scripts/pinescript/indicators/SND_Clean_Zones_Prototype.pine
git commit -m "DEV-328: add clean liquidity selection"
```

Expected: commit succeeds with only the prototype file.

## Task 5: Add Zone Lifecycle And Quiet Rendering

**Files:**
- Modify: `scripts/pinescript/indicators/SND_Clean_Zones_Prototype.pine`

- [ ] **Step 1: Insert lifecycle and rendering functions before the final detection call block**

Insert this exact block above `if barstate.isconfirmed and bar_index > bos_lookback + base_max_candles + 5`:

```pine
f_zone_bg(CleanZone z) =>
    if z.state == STATE_WAITING_BOS
        z.side == SIDE_DEMAND ? color.new(color.teal, 88) : color.new(color.orange, 88)
    else if z.state == STATE_VALID
        z.side == SIDE_DEMAND ? color.new(color.green, 78) : color.new(color.red, 78)
    else if z.state == STATE_TESTED
        z.side == SIDE_DEMAND ? color.new(color.aqua, 76) : color.new(color.yellow, 76)
    else
        color.new(color.gray, 92)

f_zone_border(CleanZone z) =>
    if z.state == STATE_WAITING_BOS
        color.new(color.gray, 30)
    else if z.state == STATE_VALID
        z.side == SIDE_DEMAND ? color.new(color.green, 5) : color.new(color.red, 5)
    else if z.state == STATE_TESTED
        z.side == SIDE_DEMAND ? color.new(color.aqua, 5) : color.new(color.yellow, 5)
    else
        color.new(color.gray, 60)

f_should_show_zone(CleanZone z) =>
    z.state == STATE_VALID or z.state == STATE_TESTED or (show_waiting_bos and z.state == STATE_WAITING_BOS) or (show_invalid_zones and z.state == STATE_INVALID)

f_update_zone_lifecycle(int idx) =>
    CleanZone z = array.get(zones, idx)
    bool isDemand = z.side == SIDE_DEMAND
    bool liveState = z.state == STATE_WAITING_BOS or z.state == STATE_VALID or z.state == STATE_TESTED

    if liveState
        bool invalidated = isDemand ? close < z.bottom : close > z.top
        bool touched = isDemand ? low <= z.top and low >= z.bottom : high >= z.bottom and high <= z.top

        if invalidated
            z.state := STATE_INVALID
        else if z.state == STATE_VALID and touched
            z.state := STATE_TESTED
            z.touchCount += 1
            z.lastTouchBar := bar_index
        else if z.state == STATE_TESTED and touched and z.lastTouchBar != bar_index
            z.touchCount += 1
            z.lastTouchBar := bar_index

        array.set(zones, idx, z)

f_render_zone(int idx) =>
    CleanZone z = array.get(zones, idx)
    bool showZone = f_should_show_zone(z)

    if showZone
        if na(z.zoneBox)
            z.zoneBox := box.new(left=z.baseStartBar, top=z.top, right=bar_index + 20, bottom=z.bottom, border_color=f_zone_border(z), bgcolor=f_zone_bg(z), border_width=z.isAccuracy ? 2 : 1, xloc=xloc.bar_index)
        else
            box.set_right(z.zoneBox, bar_index + 20)
            box.set_top(z.zoneBox, z.top)
            box.set_bottom(z.zoneBox, z.bottom)
            box.set_bgcolor(z.zoneBox, f_zone_bg(z))
            box.set_border_color(z.zoneBox, f_zone_border(z))
            box.set_border_width(z.zoneBox, z.isAccuracy ? 2 : 1)

        if not na(z.inducementPrice)
            color liqColor = z.inducementSwept ? color.new(color.fuchsia, 0) : color.new(color.fuchsia, 35)
            if na(z.inducementLine)
                z.inducementLine := line.new(x1=z.inducementBar, y1=z.inducementPrice, x2=bar_index + 20, y2=z.inducementPrice, color=liqColor, width=1, xloc=xloc.bar_index)
            else
                line.set_x2(z.inducementLine, bar_index + 20)
                line.set_y1(z.inducementLine, z.inducementPrice)
                line.set_y2(z.inducementLine, z.inducementPrice)
                line.set_color(z.inducementLine, liqColor)

        if show_target_liquidity and not na(z.targetPrice)
            color targetColor = z.targetSwept ? color.new(color.gray, 0) : color.new(color.gray, 45)
            if na(z.targetLine)
                z.targetLine := line.new(x1=z.targetBar, y1=z.targetPrice, x2=bar_index + 20, y2=z.targetPrice, color=targetColor, width=1, style=line.style_dotted, xloc=xloc.bar_index)
            else
                line.set_x2(z.targetLine, bar_index + 20)
                line.set_y1(z.targetLine, z.targetPrice)
                line.set_y2(z.targetLine, z.targetPrice)
                line.set_color(z.targetLine, targetColor)

        if show_state_labels
            string txt = f_side_name(z.side) + " " + str.tostring(z.id) + " " + f_state_name(z.state)
            float labelY = (z.top + z.bottom) / 2.0
            if na(z.stateLabel)
                z.stateLabel := label.new(x=bar_index, y=labelY, text=txt, style=label.style_label_left, textcolor=color.white, color=f_zone_border(z), size=size.tiny, xloc=xloc.bar_index)
            else
                label.set_x(z.stateLabel, bar_index)
                label.set_y(z.stateLabel, labelY)
                label.set_text(z.stateLabel, txt)
                label.set_color(z.stateLabel, f_zone_border(z))
        else if not na(z.stateLabel)
            label.delete(z.stateLabel)
            z.stateLabel := na
    else
        if not na(z.zoneBox)
            box.delete(z.zoneBox)
            z.zoneBox := na
        if not na(z.inducementLine)
            line.delete(z.inducementLine)
            z.inducementLine := na
        if not na(z.targetLine)
            line.delete(z.targetLine)
            z.targetLine := na
        if not na(z.stateLabel)
            label.delete(z.stateLabel)
            z.stateLabel := na

    array.set(zones, idx, z)

f_update_lifecycle_and_render() =>
    if array.size(zones) > 0
        for i = 0 to array.size(zones) - 1
            f_update_zone_lifecycle(i)
            f_render_zone(i)
```

- [ ] **Step 2: Update the final detection call block**

Replace the final block with this exact block:

```pine
if barstate.isconfirmed and bar_index > bos_lookback + base_max_candles + 5
    f_try_detect_zone(true)
    f_try_detect_zone(false)
    f_promote_waiting_zones()
    f_update_all_liquidity()
    f_update_lifecycle_and_render()
```

- [ ] **Step 3: Run rendering source checks**

Run:

```bash
rg -n "box\\.new|line\\.new|label\\.new|f_update_lifecycle_and_render|STATE_TESTED|STATE_INVALID" scripts/pinescript/indicators/SND_Clean_Zones_Prototype.pine
```

Expected: matches for rendering calls and state transitions.

- [ ] **Step 4: Commit lifecycle and rendering**

Run:

```bash
git add scripts/pinescript/indicators/SND_Clean_Zones_Prototype.pine
git commit -m "DEV-328: render clean zone lifecycle"
```

Expected: commit succeeds with only the prototype file.

## Task 6: Add Debug Markers And Source Safety Checks

**Files:**
- Modify: `scripts/pinescript/indicators/SND_Clean_Zones_Prototype.pine`

- [ ] **Step 1: Insert debug plotting before `f_try_detect_zone`**

Insert this exact block above the existing `f_try_detect_zone(bool isDemand) =>` function:

```pine
f_debug_candidate_marker(bool isDemand, int baseCount) =>
    if show_debug and baseCount > 0
        string txt = isDemand ? "D base" : "S base"
        color markerColor = isDemand ? color.new(color.green, 0) : color.new(color.red, 0)
        float markerPrice = isDemand ? low : high
        label.new(x=bar_index, y=markerPrice, text=txt, style=isDemand ? label.style_label_up : label.style_label_down, textcolor=color.white, color=markerColor, size=size.tiny, xloc=xloc.bar_index)

f_debug_rejected_marker(bool isDemand, string reason) =>
    if show_debug
        color markerColor = color.new(color.gray, 35)
        float markerPrice = isDemand ? low : high
        label.new(x=bar_index, y=markerPrice, text=reason, style=isDemand ? label.style_label_up : label.style_label_down, textcolor=color.white, color=markerColor, size=size.tiny, xloc=xloc.bar_index)
```

- [ ] **Step 2: Replace `f_try_detect_zone` with the debug-aware version**

Replace the existing `f_try_detect_zone` function with this exact function:

```pine
f_try_detect_zone(bool isDemand) =>
    int baseCount = f_base_count()
    if baseCount > 0
        [bodyHigh, bodyLow, wickHigh, wickLow] = f_base_bounds(baseCount)
        bool displaced = f_displacement_ok(isDemand, bodyHigh, bodyLow, wickHigh, wickLow)
        if displaced
            f_debug_candidate_marker(isDemand, baseCount)
            f_create_zone(isDemand, baseCount, bodyHigh, bodyLow, wickHigh, wickLow)
        else
            f_debug_rejected_marker(isDemand, isDemand ? "D no displacement" : "S no displacement")
```

- [ ] **Step 3: Run source-level safety checks**

Run:

```bash
test -z "$(git diff -- scripts/pinescript/strategies/SND_Strategy.pine)"
```

Expected: exit code `0`.

Run:

```bash
rg -n "strategy\\.(entry|order|exit|close)|alertcondition\\(|alert\\(" scripts/pinescript/indicators/SND_Clean_Zones_Prototype.pine
```

Expected: no matches and exit code `1`.

Run:

```bash
rg -n "request\\.seed|toodegrees|forex_factory" scripts/pinescript/indicators/SND_Clean_Zones_Prototype.pine
```

Expected: no matches and exit code `1`.

Run:

```bash
rg -n "for .* to .*5000|while " scripts/pinescript/indicators/SND_Clean_Zones_Prototype.pine
```

Expected: no matches and exit code `1`, except this command may show the bounded `while array.size(zones) > max_zones` loop. If it shows only that bounded loop, the check is acceptable.

- [ ] **Step 4: Commit debug and safety checks**

Run:

```bash
git add scripts/pinescript/indicators/SND_Clean_Zones_Prototype.pine
git commit -m "DEV-328: add clean detector debug markers"
```

Expected: commit succeeds with only the prototype file.

## Task 7: Manual TradingView Validation And Tuning Notes

**Files:**
- Modify: `scripts/pinescript/indicators/SND_Clean_Zones_Prototype.pine`

- [ ] **Step 1: Copy the indicator into TradingView Pine Editor**

Use the full content of:

```text
scripts/pinescript/indicators/SND_Clean_Zones_Prototype.pine
```

Expected: TradingView Pine Editor compiles as Pine v6 with zero errors.

- [ ] **Step 2: Validate on GBPJPY 5m**

Chart setup:

```text
Symbol: GBPJPY
Timeframe: 5m
Indicators visible: SND Clean Zones Prototype, current S&D Pro, Zones Liq S/D - Myrtille
Prototype debug mode: off
Prototype show waiting BOS: off
Prototype show invalid zones: off
```

Expected:

- The prototype shows fewer zones than the current strategy.
- The prototype shows no fractal marker clutter.
- Valid demand zones appear below price after bullish displacement and BOS.
- Valid supply zones appear above price after bearish displacement and BOS.
- Each valid zone has at most one inducement line.
- Tested zones change color after the first retest.

- [ ] **Step 3: Tune default inputs only if the chart is too sparse or too noisy**

If no zones appear on GBPJPY 5m across one full trading day, adjust:

```pine
displacement_atr_min = input.float(0.65, "Min Displacement ATR", minval=0.1, maxval=5.0, step=0.05, group=grpDetection)
```

If too many zones appear on GBPJPY 5m across one full trading day, adjust:

```pine
displacement_atr_min = input.float(1.00, "Min Displacement ATR", minval=0.1, maxval=5.0, step=0.05, group=grpDetection)
```

If liquidity lines are too far from zones, adjust:

```pine
max_external_liquidity_atr = input.float(1.000, "Max External Liquidity Distance ATR", minval=0.05, maxval=8.0, step=0.001, group=grpLiquidity)
```

If liquidity lines are missing near obvious one-candle swings, keep:

```pine
enable_one_candle_liquidity = input.bool(true, "Enable One Candle Liquidity", group=grpLiquidity)
```

- [ ] **Step 4: Re-run source-level safety checks**

Run:

```bash
test -z "$(git diff -- scripts/pinescript/strategies/SND_Strategy.pine)"
rg -n "strategy\\.(entry|order|exit|close)|alertcondition\\(|alert\\(" scripts/pinescript/indicators/SND_Clean_Zones_Prototype.pine
```

Expected: first command exits `0`; second command has no matches and exits `1`.

- [ ] **Step 5: Commit validation tuning**

Run:

```bash
git add scripts/pinescript/indicators/SND_Clean_Zones_Prototype.pine
git commit -m "DEV-328: tune clean detector prototype"
```

Expected: commit succeeds if tuning changed the file. If no tuning changed the file, skip this commit.

## Spec Coverage Self-Review

- New visual-only Pine file: Task 1.
- No changes to current live strategy: Tasks 1, 6, and 7 safety checks.
- Zone state machine: Tasks 1, 3, and 5.
- Sparse zone detection with BOS: Tasks 2 and 3.
- One best inducement line per zone: Task 4.
- Internal and external liquidity settings: Tasks 1 and 4.
- One-candle liquidity setting: Tasks 1 and 4.
- Quiet default visuals: Task 5.
- Debug mode: Task 6.
- No backend decision movement into Pine: Task 1 safety checks and Task 7 validation.
