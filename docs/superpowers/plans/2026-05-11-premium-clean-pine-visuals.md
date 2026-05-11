# Premium Clean Pine Visuals Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the S&D Pine strategy default chart clean, premium, and execution-focused without changing trading behavior.

**Architecture:** Keep the visual redesign inside `scripts/pinescript/strategies/SND_Strategy.pine`. Add display-mode-derived booleans, centralize premium visual colors/text helpers, update existing object lifecycle paths, and leave strategy/risk/webhook/backend plots untouched.

**Tech Stack:** Pine Script v6, TradingView strategy overlay, imported `SND_Core` and `SND_Utils` libraries.

---

## Files

- Modify: `scripts/pinescript/strategies/SND_Strategy.pine`
- Do not modify unless blocked: `scripts/pinescript/libraries/SND_Core.pine`
- Do not modify unless blocked: `scripts/pinescript/libraries/SND_Utils.pine`
- Reference only: `docs/superpowers/specs/2026-05-11-premium-clean-pine-visuals-design.md`

## Constraints

- Do not change `strategy.entry`, `strategy.exit`, `strategy.order`, or alert/webhook payload code.
- Do not change zone detection rules, scoring rules, risk calculations, or backend-facing hidden `plot()` series names/meanings.
- Do not change `src/logic.py`, `src/worker.py`, or other backend trading paths.
- Keep default results/performance table visible.
- Keep fractal markers visible, but restyled.
- Keep full zone inspector available outside Clean mode.

## Task 1: Add Display Mode And Clean Defaults

**Files:**
- Modify: `scripts/pinescript/strategies/SND_Strategy.pine:162-199`
- Modify: `scripts/pinescript/strategies/SND_Strategy.pine:229-242`

- [ ] **Step 1: Capture current guarded symbols before editing**

Run:

```bash
rg -n "strategy\\.(entry|exit|order)|WEBHOOK|plot\\(plot_|max_zones|plotLiq|show_fractals|show_liquidity_connectors|showZoneInspector" scripts/pinescript/strategies/SND_Strategy.pine
```

Expected: existing lines are reported. Save the output mentally for comparison after the implementation; strategy/webhook/hidden plot lines must remain behaviorally unchanged.

- [ ] **Step 2: Replace display inputs with mode-derived clean defaults**

In the display/input section, keep internal zone storage separate from visual zone display. Replace the current `max_zones`, `plotLiq`, `show_fractals`, `show_liquidity_connectors`, `showZoneInspector`, and related zone label defaults with this shape:

```pine
display_mode = input.string("Clean", "Display Mode",
     options = ["Clean", "Analysis", "Debug"],
     group = "🎨 Display")
display_is_clean = display_mode == "Clean"
display_is_analysis = display_mode == "Analysis"
display_is_debug = display_mode == "Debug"
display_show_details = display_is_analysis or display_is_debug

invalidate_on_wick   = input.bool(true, "Invalidate on Wick Touch", group = "📐 Zone Detection")
max_zones            = input.int(20, "Max Zones Stored", minval = 1, maxval = 50, group = "📐 Zone Detection")
max_visible_zones_per_side = input.int(4, "Max Visible Zones (Per Side)", minval = 1, maxval = 50, group = "🎨 Display")
zone_right_padding_bars = input.int(10, "Zone Right Padding Bars", minval = 1, maxval = 100, group = "🎨 Display")
min_body_perc        = input.float(50.0, "Min Body %", minval = 0, maxval = 100, group = "📐 Zone Detection")
structure_mode      = input.string("Relaxed (Wicks)", "Structure Detection", options = ["Relaxed (Wicks)", "Standard (Bodies)"], group = "📐 Zone Detection")

plotLiq_user = input.bool(false, "Show Liquidity Pivot Lines", group = "🎨 Display")
plotLiq = display_show_details or plotLiq_user
show_fractals = input.bool(true, "Show Fractal Markers", group = "🎨 Display")

show_liquidity_connectors_user = input.bool(false, "Show Liquidity Connectors & Lines", group = "🎨 Display")
show_liquidity_connectors = display_show_details or show_liquidity_connectors_user

show_zones           = true
show_demand_zones    = true
show_supply_zones    = true
show_entry_labels    = true
show_ai_debug_comment = false
zone_label_style = display_is_clean ? "Compact" : input.string("Compact", "Zone Label Style", options = ["Compact", "Detailed"], group = "🎨 Display")
zone_label_show_metrics = display_show_details and input.bool(true, "Zone Label: Show Grade/Score", group = "🎨 Display")
show_blocked_trade_labels = input.bool(false, "Show Blocked Trade Labels", group = "🎨 Display")
```

If Pine rejects conditional `input.*` assignment for `zone_label_style`, use this compile-safe fallback:

```pine
zone_label_style_input = input.string("Compact", "Zone Label Style", options = ["Compact", "Detailed"], group = "🎨 Display")
zone_label_style = display_is_clean ? "Compact" : zone_label_style_input
zone_label_show_metrics_input = input.bool(true, "Zone Label: Show Grade/Score", group = "🎨 Display")
zone_label_show_metrics = display_show_details and zone_label_show_metrics_input
```

- [ ] **Step 3: Gate debug panels and full inspector by display mode**

Near the existing debug variables, change debug panel booleans to include `Debug` mode without making `Clean` noisy:

```pine
debug_enabled   = display_is_debug or debug_level != "None"
debug_full      = display_is_debug or (debug_level == "Full") or (debug_level != "None" and debug_mode)
debug_basic     = debug_level == "Basic"
showDebugPanels = display_is_debug or (debug_level != "None")
showZoneInspector = input.bool(false, "Zone Inspector Panel", group = "🎨 Display") or display_show_details
showCompactStatusPanel = input.bool(true, "Compact Status Panel", group = "🎨 Display") and display_is_clean
```

If `showZoneInspector` already exists earlier in the file, do not create a duplicate variable. Move this exact assignment to that existing input location and remove the older `input.bool(true, "Zone Inspector Panel", ...)`.

- [ ] **Step 4: Run static checks**

Run:

```bash
rg -n "input\\.int\\(20, \"Max Zones Displayed\"|input\\.bool\\(true, \"Show Liquidity Pivot Lines\"|input\\.bool\\(true, \"Show Liquidity Connectors|input\\.bool\\(true, \"Zone Inspector Panel\"" scripts/pinescript/strategies/SND_Strategy.pine
```

Expected: no matches. `input.int(20, "Max Zones Stored", ...)` is allowed because it preserves the pre-existing internal zone array cap used by strategy processing.

- [ ] **Step 5: Commit Task 1**

```bash
git add scripts/pinescript/strategies/SND_Strategy.pine
git commit -m "DEV-385: add Pine display mode defaults"
```

## Task 2: Add Premium Visual Palette And Label Helpers

**Files:**
- Modify: `scripts/pinescript/strategies/SND_Strategy.pine:429-437`
- Modify: `scripts/pinescript/strategies/SND_Strategy.pine` near the color constants

- [ ] **Step 1: Replace the zone color constants**

Replace the current teal/red plus loud accuracy blue/purple constants with this light-theme palette:

```pine
col_demand_bg     = color.new(#2BA8A0, 91)
col_demand_border = color.new(#127C86, 24)

col_supply_bg     = color.new(#D9687C, 91)
col_supply_border = color.new(#A83F52, 24)

col_acc_demand_bg     = color.new(#2BA8A0, 86)
col_acc_demand_border = color.new(#0E6672, 8)
col_acc_supply_bg     = color.new(#D9687C, 86)
col_acc_supply_border = color.new(#8E3142, 8)

col_zone_label_bg = color.new(color.rgb(28, 34, 42), 4)
col_zone_label_text = color.rgb(245, 248, 250)
col_fractal_high = color.new(#A83F52, 18)
col_fractal_low = color.new(#127C86, 18)
col_liq_inducement = color.new(#D89B35, 25)
col_liq_target = color.new(#6E7FAF, 25)
```

- [ ] **Step 2: Add helper functions below the color constants**

Add:

```pine
get_zone_bg_color(bool isDemand, bool isAccuracy) =>
    isDemand ? (isAccuracy ? col_acc_demand_bg : col_demand_bg) : (isAccuracy ? col_acc_supply_bg : col_supply_bg)

get_zone_border_color(bool isDemand, bool isAccuracy) =>
    isDemand ? (isAccuracy ? col_acc_demand_border : col_demand_border) : (isAccuracy ? col_acc_supply_border : col_supply_border)

get_zone_border_width(bool isAccuracy) =>
    isAccuracy ? 2 : 1

get_zone_label_text(bool isDemand, int zoneId) =>
    (isDemand ? "D-" : "S-") + str.tostring(zoneId)

get_zone_label_color(bool isDemand, bool isAccuracy) =>
    display_is_clean ? col_zone_label_bg : (isDemand ? (isAccuracy ? col_acc_demand_border : col_demand_border) : (isAccuracy ? col_acc_supply_border : col_supply_border))
```

- [ ] **Step 3: Run a duplicate color check**

Run:

```bash
rg -n "#2196F3|#AB47BC|#26a69a|#ef5350|color\\.green|color\\.red" scripts/pinescript/strategies/SND_Strategy.pine
```

Expected: old zone color constants and fractal marker colors should be gone from visual code after later tasks. Some unrelated table or trade colors may remain; do not change unrelated table/trade semantics.

- [ ] **Step 4: Commit Task 2**

```bash
git add scripts/pinescript/strategies/SND_Strategy.pine
git commit -m "DEV-385: add premium Pine visual palette"
```

## Task 3: Update Zone Creation Visuals

**Files:**
- Modify: `scripts/pinescript/strategies/SND_Strategy.pine:1658-1725`

- [ ] **Step 1: Change new box right edge and colors**

In `createZone(...)`, replace the local color selection block and `box.new(...)` right edge with:

```pine
zoneBorderWidth := get_zone_border_width(isAccuracy)
zoneBgColor := get_zone_bg_color(isDemand, isAccuracy)
zoneBorderColorFinal := get_zone_border_color(isDemand, isAccuracy)
int zoneRightBar = bar_index + zone_right_padding_bars

box b = box.new(left = baseBarIdx, top = zTop, right = zoneRightBar, bottom = zBottom,
     border_color = zoneBorderColorFinal,
     border_width = zoneBorderWidth,
     bgcolor = zoneBgColor,
     xloc = xloc.bar_index)
```

- [ ] **Step 2: Change new label to right-edge ID-only**

Replace `accTag`, detailed label construction, and `label.new(...)` with:

```pine
string id_text = " " + get_zone_label_text(isDemand, zoneUZID) + " "
float mid = (zTop + zBottom) / 2.0
label idLbl = label.new(x = zoneRightBar, y = mid, text = id_text,
     style = label.style_label_left,
     textcolor = col_zone_label_text,
     color = get_zone_label_color(isDemand, isAccuracy),
     size = size.tiny,
     textalign = text.align_center,
     xloc = xloc.bar_index)
```

Do not include star, grade, score, or `ACC` text in Clean mode labels.

- [ ] **Step 3: Verify no creation-time old label text remains**

Run:

```bash
rg -n "accTag|detailedText|compactText|⭐ ACC|Demand \"|Supply \"" scripts/pinescript/strategies/SND_Strategy.pine
```

Expected: no matches in the zone creation block. If matches remain elsewhere for inspector text, leave them only if they are not chart labels.

- [ ] **Step 4: Commit Task 3**

```bash
git add scripts/pinescript/strategies/SND_Strategy.pine
git commit -m "DEV-385: clean Pine zone creation visuals"
```

## Task 4: Update Active Zone Refresh Loop

**Files:**
- Modify: `scripts/pinescript/strategies/SND_Strategy.pine:2928-3006`

- [ ] **Step 1: Change demand active zone right edge**

In the demand visual refresh loop, replace:

```pine
int right_bar_index = left_bar_index + extend_bars
```

with:

```pine
int right_bar_index = bar_index + zone_right_padding_bars
```

Then replace the repeated demand color block with:

```pine
box.set_right(z.boxId, right_bar_index)
box.set_bgcolor(z.boxId, get_zone_bg_color(true, z.isAccuracy))
box.set_border_width(z.boxId, get_zone_border_width(z.isAccuracy))
box.set_border_color(z.boxId, get_zone_border_color(true, z.isAccuracy))
```

- [ ] **Step 2: Change demand label refresh**

Replace demand label text/style updates with:

```pine
float lbl_mid = (z.top + z.bottom) / 2
label.set_x(z.idLabel, right_bar_index)
label.set_y(z.idLabel, lbl_mid)
label.set_text(z.idLabel, " " + get_zone_label_text(true, z.id) + " ")
label.set_style(z.idLabel, label.style_label_left)
label.set_textcolor(z.idLabel, col_zone_label_text)
label.set_color(z.idLabel, get_zone_label_color(true, z.isAccuracy))
label.set_size(z.idLabel, size.tiny)
label.set_textalign(z.idLabel, text.align_center)
```

- [ ] **Step 3: Change supply active zone right edge and label refresh**

Apply the same pattern in the supply loop:

```pine
int right_bar_index = bar_index + zone_right_padding_bars
box.set_right(z.boxId, right_bar_index)
box.set_bgcolor(z.boxId, get_zone_bg_color(false, z.isAccuracy))
box.set_border_width(z.boxId, get_zone_border_width(z.isAccuracy))
box.set_border_color(z.boxId, get_zone_border_color(false, z.isAccuracy))

float lbl_mid = (z.top + z.bottom) / 2
label.set_x(z.idLabel, right_bar_index)
label.set_y(z.idLabel, lbl_mid)
label.set_text(z.idLabel, " " + get_zone_label_text(false, z.id) + " ")
label.set_style(z.idLabel, label.style_label_left)
label.set_textcolor(z.idLabel, col_zone_label_text)
label.set_color(z.idLabel, get_zone_label_color(false, z.isAccuracy))
label.set_size(z.idLabel, size.tiny)
label.set_textalign(z.idLabel, text.align_center)
```

- [ ] **Step 4: Verify fixed extension is no longer used for active visuals**

Run:

```bash
rg -n "left_bar_index \\+ extend_bars|label\\.set_x\\(z\\.idLabel, bar_index\\)|label\\.set_size\\(z\\.idLabel, size\\.normal\\)" scripts/pinescript/strategies/SND_Strategy.pine
```

Expected: no matches.

- [ ] **Step 5: Commit Task 4**

```bash
git add scripts/pinescript/strategies/SND_Strategy.pine
git commit -m "DEV-385: keep active Pine zones near price"
```

## Task 5: Hide Inactive Visual Objects In Clean Mode

**Files:**
- Modify: `scripts/pinescript/strategies/SND_Strategy.pine:1450-1510`
- Modify: `scripts/pinescript/strategies/SND_Strategy.pine:2260-2315`
- Modify: `scripts/pinescript/strategies/SND_Strategy.pine:2928-3006`

- [ ] **Step 1: Add a clear helper near existing zone cleanup helpers**

Add:

```pine
clear_zone_visual_objects(Core.Zone z, bool includeTargetLine) =>
    if not na(z.boxId)
        box.delete(z.boxId)
        z.boxId := na
    if not na(z.connectorLine)
        line.delete(z.connectorLine)
        z.connectorLine := na
    if includeTargetLine and not na(z.targetLine)
        line.delete(z.targetLine)
        z.targetLine := na
    if not na(z.inducementHLine)
        line.delete(z.inducementHLine)
        z.inducementHLine := na
    if not na(z.targetHLine)
        line.delete(z.targetHLine)
        z.targetHLine := na
    if not na(z.idLabel)
        label.delete(z.idLabel)
        z.idLabel := na
    z
```

- [ ] **Step 2: Use helper in deactivate demand**

Replace `deactivateDemandZone(idx)` body after `z.active := false` with:

```pine
if display_is_clean
    z := clear_zone_visual_objects(z, false)
else if not na(z.boxId)
    box.set_bgcolor(z.boxId, color.new(col_demand_bg, 96))
    box.set_border_color(z.boxId, color.new(col_demand_border, 75))
array.set(demandZones, idx, z)
```

- [ ] **Step 3: Use helper in deactivate supply**

Replace `deactivateSupplyZone(idx)` body after `z.active := false` with:

```pine
if display_is_clean
    z := clear_zone_visual_objects(z, true)
else if not na(z.boxId)
    box.set_bgcolor(z.boxId, color.new(col_supply_bg, 96))
    box.set_border_color(z.boxId, color.new(col_supply_border, 75))
array.set(supplyZones, idx, z)
```

- [ ] **Step 4: Use helper in trim loops**

In `trimZoneArrays(...)`, replace repeated `box.delete`, `line.delete`, and `label.delete` blocks with:

```pine
z := clear_zone_visual_objects(z, false)
```

for demand and:

```pine
z := clear_zone_visual_objects(z, true)
```

for supply. The popped zone does not need `array.set`.

- [ ] **Step 5: Apply visual cap without pruning zone arrays**

In the demand active zone visual refresh block, add an active-zone display counter before the loop:

```pine
int demand_visible_count = 0
```

Inside the loop, immediately after `if z.active`, increment and gate display-only objects:

```pine
demand_visible_count += 1
bool should_show_zone_visual = demand_visible_count <= max_visible_zones_per_side
if not should_show_zone_visual
    z := clear_zone_visual_objects(z, false)
    array.set(demandZones, i, z)
    continue
```

In the supply block, mirror this with:

```pine
int supply_visible_count = 0
```

and inside `if z.active`:

```pine
supply_visible_count += 1
bool should_show_zone_visual = supply_visible_count <= max_visible_zones_per_side
if not should_show_zone_visual
    z := clear_zone_visual_objects(z, true)
    array.set(supplyZones, i, z)
    continue
```

This display cap must not call `array.pop`, `array.remove`, `db_markInactive`, or entry-validation code.

- [ ] **Step 6: Verify helper usage**

Run:

```bash
rg -n "clear_zone_visual_objects|deactivateDemandZone|deactivateSupplyZone|trimZoneArrays|max_visible_zones_per_side|visible_count" scripts/pinescript/strategies/SND_Strategy.pine
```

Expected: helper exists, all lifecycle paths reference it, and the visual cap uses `max_visible_zones_per_side` without pruning zone arrays.

- [ ] **Step 7: Commit Task 5**

```bash
git add scripts/pinescript/strategies/SND_Strategy.pine
git commit -m "DEV-385: hide inactive Pine zones in clean mode"
```

## Task 6: Restyle Fractals And Analysis Liquidity Lines

**Files:**
- Modify: `scripts/pinescript/strategies/SND_Strategy.pine:943-944`
- Modify: `scripts/pinescript/strategies/SND_Strategy.pine:2443-2558`
- Modify: `scripts/pinescript/strategies/SND_Strategy.pine:4328-4357`

- [ ] **Step 1: Restyle fractal markers**

Replace the two `plotshape(...)` calls with:

```pine
plotshape(show_fractals and not na(fractalHigh), style = shape.triangledown, location = location.abovebar, color = col_fractal_high, size = size.tiny, offset = -fractalsPeriod)
plotshape(show_fractals and not na(fractalLow),  style = shape.triangleup,   location = location.belowbar, color = col_fractal_low,  size = size.tiny, offset = -fractalsPeriod)
```

- [ ] **Step 2: Restyle demand liquidity visuals for Analysis/Debug**

Inside `updateDemandLiquidityVisual(idx)`, replace orange/lime/gray line colors with:

```pine
color indColor = z.liquiditySwept ? color.new(col_liq_inducement, 0) : col_liq_inducement
color tgtColor = z.targetSwept ? color.new(col_liq_target, 0) : col_liq_target
```

Keep the existing deletion branch when `show_liquidity_connectors` is false.

- [ ] **Step 3: Restyle supply liquidity visuals for Analysis/Debug**

Inside `updateSupplyLiquidityVisual(idx)`, use the same `indColor` and `tgtColor` pattern:

```pine
color indColor = z.liquiditySwept ? color.new(col_liq_inducement, 0) : col_liq_inducement
color tgtColor = z.targetSwept ? color.new(col_liq_target, 0) : col_liq_target
targetColor = color.new(col_liq_target, 40)
```

- [ ] **Step 4: Restyle liquidity pivot lines**

Set pivot line colors near the existing `pvtTopColor` and `pvtBtmColor` assignments:

```pine
pvtTopColor = col_fractal_high
pvtBtmColor = col_fractal_low
```

- [ ] **Step 5: Verify default liquidity clutter is off**

Run:

```bash
rg -n "plotLiq = display_show_details|show_liquidity_connectors = display_show_details|size = size\\.small|color\\.orange|color\\.lime" scripts/pinescript/strategies/SND_Strategy.pine
```

Expected: mode-derived liquidity booleans exist, old fractal `size.small` is gone, and remaining orange/lime uses are unrelated trade/table semantics.

- [ ] **Step 6: Commit Task 6**

```bash
git add scripts/pinescript/strategies/SND_Strategy.pine
git commit -m "DEV-385: restyle Pine fractal and liquidity visuals"
```

## Task 7: Add Compact Status Panel

**Files:**
- Modify: `scripts/pinescript/strategies/SND_Strategy.pine` near table helper functions
- Modify: `scripts/pinescript/strategies/SND_Strategy.pine:4878-4905`

- [ ] **Step 1: Add compact status helpers**

Add near other table/helper functions:

```pine
count_active_zones(array<Core.Zone> zones) =>
    int count = 0
    for i = 0 to array.size(zones) - 1
        Core.Zone z = array.get(zones, i)
        if z.active
            count += 1
    count

get_latest_zone_id_text() =>
    string latest = "N/A"
    if array.size(demandZones) > 0
        Core.Zone dz = array.get(demandZones, 0)
        if dz.active
            latest := "D-" + str.tostring(dz.id)
    if latest == "N/A" and array.size(supplyZones) > 0
        Core.Zone sz = array.get(supplyZones, 0)
        if sz.active
            latest := "S-" + str.tostring(sz.id)
    latest
```

- [ ] **Step 2: Add compact table draw function**

Add:

```pine
draw_compact_status_table(table t) =>
    if showCompactStatusPanel
        if na(t)
            t := table.new(position.bottom_right, 2, 5,
                 bgcolor = color.new(color.rgb(24, 29, 36), 8),
                 frame_color = color.new(color.rgb(90, 100, 110), 75), frame_width = 1,
                 border_color = color.new(color.rgb(70, 80, 90), 65), border_width = 1)
        if barstate.isconfirmed
            int activeDemandCount = count_active_zones(demandZones)
            int activeSupplyCount = count_active_zones(supplyZones)
            string aiState = enable_ai_quality_filter ? "ON" : "OFF"
            string hoursState = is_outside_trading_hours() ? "Closed" : "Open"
            table.cell(t, 0, 0, "STATUS", text_color = color.white, bgcolor = color.new(color.rgb(35, 42, 50), 0), text_size = size.tiny, text_halign = text.align_left)
            table.cell(t, 1, 0, display_mode, text_color = color.rgb(210, 225, 235), bgcolor = color.new(color.rgb(35, 42, 50), 0), text_size = size.tiny, text_halign = text.align_right)
            table.cell(t, 0, 1, "Demand", text_color = TBL_LBL, bgcolor = TBL_DBG, text_size = size.tiny, text_halign = text.align_right)
            table.cell(t, 1, 1, str.tostring(activeDemandCount), text_color = col_demand_border, bgcolor = TBL_DBG, text_size = size.tiny, text_halign = text.align_left)
            table.cell(t, 0, 2, "Supply", text_color = TBL_LBL, bgcolor = TBL_DBG, text_size = size.tiny, text_halign = text.align_right)
            table.cell(t, 1, 2, str.tostring(activeSupplyCount), text_color = col_supply_border, bgcolor = TBL_DBG, text_size = size.tiny, text_halign = text.align_left)
            table.cell(t, 0, 3, "Latest", text_color = TBL_LBL, bgcolor = TBL_DBG, text_size = size.tiny, text_halign = text.align_right)
            table.cell(t, 1, 3, get_latest_zone_id_text(), text_color = color.rgb(220, 225, 230), bgcolor = TBL_DBG, text_size = size.tiny, text_halign = text.align_left)
            table.cell(t, 0, 4, "AI / Hours", text_color = TBL_LBL, bgcolor = TBL_DBG, text_size = size.tiny, text_halign = text.align_right)
            table.cell(t, 1, 4, aiState + " / " + hoursState, text_color = hoursState == "Open" ? color.rgb(80, 190, 140) : color.rgb(210, 150, 80), bgcolor = TBL_DBG, text_size = size.tiny, text_halign = text.align_left)
    else
        if not na(t)
            table.delete(t)
            t := na
    t
```

- [ ] **Step 3: Draw compact status after full inspector block**

After the full inspector deletion branch and before `performanceTable := draw_performance_table(performanceTable)`, add:

```pine
var table compactStatusTable = na
compactStatusTable := draw_compact_status_table(compactStatusTable)
```

- [ ] **Step 4: Ensure full inspector remains hidden in Clean**

Run:

```bash
rg -n "showZoneInspector|showCompactStatusPanel|compactStatusTable|draw_compact_status_table|table\\.new\\(position\\.bottom_right" scripts/pinescript/strategies/SND_Strategy.pine
```

Expected: full `zoneInspector` is gated by `showZoneInspector and debug_enabled`, compact status exists separately, and Clean mode uses compact status.

- [ ] **Step 5: Commit Task 7**

```bash
git add scripts/pinescript/strategies/SND_Strategy.pine
git commit -m "DEV-385: add compact Pine status panel"
```

## Task 8: Final Verification And Ticket Close

**Files:**
- Verify: `scripts/pinescript/strategies/SND_Strategy.pine`
- Verify: `docs/superpowers/specs/2026-05-11-premium-clean-pine-visuals-design.md`

- [ ] **Step 1: Run guard diff checks**

Run:

```bash
git log --oneline -8 -- scripts/pinescript/strategies/SND_Strategy.pine
git show --stat --oneline HEAD
rg -n "strategy\\.(entry|exit|order)|WEBHOOK|plot\\(plot_" scripts/pinescript/strategies/SND_Strategy.pine
```

Expected: recent commits are DEV-385 visual commits. Strategy orders, webhook constants/payloads, and hidden backend plot names/meanings are still present and behaviorally unchanged.

- [ ] **Step 2: Run whitespace/static checks**

Run:

```bash
git diff --check
rg -n "input\\.int\\(20, \"Max Zones Displayed\"|left_bar_index \\+ extend_bars|label\\.set_x\\(z\\.idLabel, bar_index\\)|size = size\\.small" scripts/pinescript/strategies/SND_Strategy.pine
```

Expected: `git diff --check` is clean. The second command returns no old default/old visual matches, except unrelated `size.small` table/label code if it is not a fractal or zone ID label.

- [ ] **Step 3: TradingView manual compile checklist**

Paste/update the changed Pine files in TradingView and compile.

Expected:

- No Pine syntax errors.
- Strategy loads with `Display Mode = Clean`.
- Results table is visible.
- Compact status panel is visible.
- Full Zone Inspector is hidden in Clean.
- Recent active zones are visually capped by `Max Visible Zones (Per Side)` without pruning stored zone arrays.
- Inactive/invalidated zones are hidden in Clean.
- Zone boxes end at current bar plus padding.
- Zone ID labels appear on the right edge.
- Fractal markers remain visible and smaller.
- Liquidity/target/connector lines are hidden in Clean and visible in Analysis/Debug.

- [ ] **Step 4: Commit any verification fixes**

If verification required edits:

```bash
git add scripts/pinescript/strategies/SND_Strategy.pine
git commit -m "DEV-385: verify premium Pine clean visuals"
```

If no edits were required, do not create an empty commit.

- [ ] **Step 5: Close Jira ticket after implementation is complete**

Run:

```bash
curl -s -X POST "http://localhost:8000/api/tickets/DEV-385/ai-update" \
  -H "Content-Type: application/json" \
  -d '{"new_status":"done","summary_of_work":"Implemented premium clean Pine strategy visuals: Clean/Analysis/Debug display modes, subtle zone palette, right-edge ID labels, active zone padding, hidden inactive visuals, compact status panel, and restyled fractal/liquidity visuals.","agent":"codex"}'
```

Expected: local ticket API accepts the status update. If the local API is not running, report that ticket closure could not be completed locally.

## Self-Review Checklist

- Spec coverage: all approved defaults, palette, label placement, inactive-zone behavior, fractal visibility, analysis liquidity gating, results table, and compact/full inspector behavior are mapped to tasks.
- Completion scan: no empty markers or deferred-work phrases are present.
- Type consistency: helper names are consistent across tasks: `display_is_clean`, `display_show_details`, `zone_right_padding_bars`, `get_zone_bg_color`, `get_zone_border_color`, `get_zone_label_text`, `clear_zone_visual_objects`, and `draw_compact_status_table`.
