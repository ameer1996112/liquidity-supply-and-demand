# SND Visual Modes Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add Clean, Diagnostic, and Forensic visual modes to `SND_Strategy.pine` so replay is readable by default while debugging overlays remain available on demand.

**Architecture:** Keep this visual-only. Add one `visual_mode` display input, derive mode booleans from it, and route existing chart objects through those booleans. Do not change zone creation, liquidity validation, invalidation, entry conditions, risk, sizing, or order placement.

**Tech Stack:** TradingView Pine Script v6, existing `SND_Strategy.pine`, existing `Core.Zone` visual object fields.

---

## File Structure

- Modify: `scripts/pinescript/strategies/SND_Strategy.pine`
  - Add the mode input and derived booleans near the current Display inputs.
  - Update display color constants.
  - Gate raw pivot liquidity plotting.
  - Gate demand/supply inducement liquidity guide lines.
  - Update `zone_should_show_visual()` and `apply_zone_visual()` to respect mode visibility.
  - Update zone labels to show compact text in Clean/Diagnostic and more detail in Forensic.
- Manual test only: TradingView Pine compile and replay screenshots. Pine cannot be compiled locally from this repo.

## Scope Guard

Before editing, capture the strategy-logic guardrail:

```bash
git diff -- scripts/pinescript/strategies/SND_Strategy.pine > /tmp/snd-before-visual-modes.diff
```

After editing, inspect the diff and confirm changed hunks are limited to:

- Display inputs and display booleans.
- Color constants.
- Visual object creation/update/deletion.
- Label text/visibility.

No hunk should touch `strategy.entry`, `strategy.exit`, `validate_entry_conditions`, `createZone`, liquidity validation predicates, or position sizing.

### Task 1: Add Visual Mode Input

**Files:**
- Modify: `scripts/pinescript/strategies/SND_Strategy.pine` near the existing Display inputs around `plotLiq`, `show_fractals`, `show_active_zones_only`, and `show_relevant_zones_only`.

- [ ] **Step 1: Add the mode input and derived booleans**

Add this block after `showRawLiquidityLevels = plotLiq` or directly before `show_active_zones_only`:

```pine
visual_mode = input.string("Clean", "visual_mode", options = ["Clean", "Diagnostic", "Forensic"], group = "🎨 Display")
visual_clean = visual_mode == "Clean"
visual_diagnostic = visual_mode == "Diagnostic"
visual_forensic = visual_mode == "Forensic"
show_liquidity_guides = visual_diagnostic or visual_forensic
show_invalid_zone_history = visual_diagnostic or visual_forensic
show_raw_debug_objects = visual_forensic
```

- [ ] **Step 2: Keep legacy debug inputs but route them through mode booleans**

Do not delete `plotLiq`, `show_fractals`, `show_blocked_trade_labels`, or `debug_level`. They may be useful later. The implementation should use `show_raw_debug_objects` as the stronger default gate, then still respect the existing raw toggles:

```pine
showChartFractals = show_fractals and show_raw_debug_objects
showRawLiquidityLevels = plotLiq and show_raw_debug_objects
```

- [ ] **Step 3: Verify no strategy behavior changed**

Run:

```bash
git diff -- scripts/pinescript/strategies/SND_Strategy.pine | rg -n "visual_mode|show_liquidity_guides|show_invalid_zone_history|show_raw_debug_objects|showRawLiquidityLevels|showChartFractals"
```

Expected: only display input and derived display booleans are shown.

### Task 2: Tune Visual Hierarchy Colors

**Files:**
- Modify: `scripts/pinescript/strategies/SND_Strategy.pine` near the color constants around `col_demand_bg`, `col_supply_bg`, and `liq_inducement_level_color`.

- [ ] **Step 1: Keep live demand readable and soften supply/debug colors**

Use this palette. It preserves the current green/teal demand language and makes supply/old lines less visually dominant:

```pine
color liq_inducement_level_color = color.new(#7A6A4D, 58)

col_demand_bg     = color.new(#8FA6A0, 91)
col_demand_border = color.new(#3F6860, 24)

col_supply_bg     = color.new(#A88F95, 96)
col_supply_border = color.new(#7A5860, 68)

col_acc_demand_bg     = color.new(#8FA6A0, 88)
col_acc_demand_border = color.new(#2F655B, 14)
col_acc_supply_bg     = color.new(#A88F95, 94)
col_acc_supply_border = color.new(#6E4852, 52)
```

- [ ] **Step 2: Keep used/invalid zones quieter than live zones**

Use these constants if the current values are stronger than this:

```pine
col_used_zone_bg      = color.new(#9ca3af, 96)
col_used_zone_border  = color.new(#9ca3af, 78)
col_invalid_zone_bg   = color.new(#6b7280, 98)
col_invalid_zone_border = color.new(#6b7280, 86)
```

- [ ] **Step 3: Verify the color diff is display-only**

Run:

```bash
git diff -- scripts/pinescript/strategies/SND_Strategy.pine | rg -n "color|col_|liq_inducement"
```

Expected: only color constant lines appear.

### Task 3: Gate Liquidity Guide Lines By Mode

**Files:**
- Modify: `scripts/pinescript/strategies/SND_Strategy.pine` in `updateDemandLiquidityVisual()` and `updateSupplyLiquidityVisual()`.

- [ ] **Step 1: Hide inducement guide lines in Clean mode**

In both liquidity update functions, after deleting existing `inducementHLine` / `targetHLine`, only recreate the line when `show_liquidity_guides` is true.

Demand should read:

```pine
        if show_liquidity_guides and not na(z.createdBarIndex)
            if not na(z.liqLowPrice) and not na(z.liqLowBar)
                int indEndBar = liquidity_level_end_bar(z)
                z.inducementHLine := line.new(x1 = z.liqLowBar, y1 = z.liqLowPrice,
                                               x2 = indEndBar, y2 = z.liqLowPrice,
                                               xloc = xloc.bar_index, extend = extend.none,
                                               color = liq_inducement_level_color, style = line.style_solid, width = 1)
```

Supply should read:

```pine
        if show_liquidity_guides and not na(z.createdBarIndex)
            if not na(z.liqHighPrice) and not na(z.liqHighBar)
                int indEndBar = liquidity_level_end_bar(z)
                z.inducementHLine := line.new(x1 = z.liqHighBar, y1 = z.liqHighPrice,
                                               x2 = indEndBar, y2 = z.liqHighPrice,
                                               xloc = xloc.bar_index, extend = extend.none,
                                               color = liq_inducement_level_color, style = line.style_solid, width = 1)
```

- [ ] **Step 2: Keep raw pivot plotting Forensic-only**

The existing raw pivot plotting should continue using `showRawLiquidityLevels`, now derived as `plotLiq and show_raw_debug_objects`. Do not alter the `line.new()` logic for raw pivots.

- [ ] **Step 3: Verify liquidity guides are mode-gated**

Run:

```bash
rg -n "show_liquidity_guides|showRawLiquidityLevels|line\\.new" scripts/pinescript/strategies/SND_Strategy.pine
```

Expected: inducement guide line creation checks `show_liquidity_guides`; raw pivot line creation still checks `showRawLiquidityLevels`.

### Task 4: Apply Mode Visibility To Zones

**Files:**
- Modify: `scripts/pinescript/strategies/SND_Strategy.pine` in `zone_should_show_visual()` and `apply_zone_visual()`.

- [ ] **Step 1: Make Clean mode show live and used-entry archive only**

Update `zone_should_show_visual()` so invalid/history zones require `show_invalid_zone_history`:

```pine
zone_should_show_visual(Core.Zone z, bool isDemand) =>
    bool invalidOrRejected = zone_is_invalid_or_rejected(z)
    bool entryUsedArchive = not na(z.lastEntryBar) and not invalidOrRejected
    bool activeDisplayZone = z.active and not z.mitigated and not invalidOrRejected and zone_is_relevant_visual(z, isDemand)
    bool diagnosticHistoryZone = show_invalid_zone_history and (invalidOrRejected or (zone_is_used_or_mitigated(z) and not entryUsedArchive))
    bool visible = activeDisplayZone or entryUsedArchive or diagnosticHistoryZone
    visible
```

- [ ] **Step 2: Make Diagnostic history quiet and Forensic more explicit**

Inside `apply_zone_visual()`, keep active zone styling as-is from Task 2. For used/mitigated or invalid/rejected zones, choose opacity by mode:

```pine
            else if usedOrMitigated
                bgColor := visual_forensic ? color.new(#9ca3af, 92) : col_used_zone_bg
                borderColor := visual_forensic ? color.new(#9ca3af, 62) : col_used_zone_border
                borderWidth := 1
            else if invalidOrRejected
                bgColor := visual_forensic ? color.new(#6b7280, 94) : col_invalid_zone_bg
                borderColor := visual_forensic ? color.new(#6b7280, 74) : col_invalid_zone_border
                borderWidth := 1
```

- [ ] **Step 3: Verify no zone lifecycle logic changed**

Run:

```bash
git diff -- scripts/pinescript/strategies/SND_Strategy.pine | rg -n "zone_should_show_visual|apply_zone_visual|active|mitigated|lastEntryBar|inactiveReason|strategy\\.entry|strategy\\.exit"
```

Expected: changes appear only inside visual functions. There should be no changes to order submission.

### Task 5: Mode-Aware Labels

**Files:**
- Modify: `scripts/pinescript/strategies/SND_Strategy.pine` in the demand and supply zone label update loops.

- [ ] **Step 1: Compact labels in Clean mode**

For demand labels, replace the label text construction with:

```pine
                        string demandAccTag = z.isAccuracy ? "ACC " : ""
                        string demandCompact = demandAccTag + "D-" + str.tostring(z.id)
                        string demandDetailed = "Demand " + demandCompact
                        string demandMetrics = zone_label_show_metrics or visual_forensic ? (" [" + z.grade + "|" + str.tostring(z.score, "#") + "]") : ""
                        string demandText = visual_clean ? demandCompact : (zone_label_style == "Detailed" or visual_forensic ? (demandDetailed + demandMetrics) : demandCompact)
                        label.set_text(z.idLabel, " " + demandText + " ")
```

For supply labels, use the matching supply code:

```pine
                        string supplyAccTag = z.isAccuracy ? "ACC " : ""
                        string supplyCompact = supplyAccTag + "S-" + str.tostring(z.id)
                        string supplyDetailed = "Supply " + supplyCompact
                        string supplyMetrics = zone_label_show_metrics or visual_forensic ? (" [" + z.grade + "|" + str.tostring(z.score, "#") + "]") : ""
                        string supplyText = visual_clean ? supplyCompact : (zone_label_style == "Detailed" or visual_forensic ? (supplyDetailed + supplyMetrics) : supplyCompact)
                        label.set_text(z.idLabel, " " + supplyText + " ")
```

- [ ] **Step 2: Keep blocked trade labels Forensic-only**

Where blocked trade labels are drawn, change the display check from:

```pine
if not can_enter and show_blocked_trade_labels and debug_level != "None" and isRecentBarForDebug()
```

to:

```pine
if not can_enter and show_blocked_trade_labels and show_raw_debug_objects and debug_level != "None" and isRecentBarForDebug()
```

Apply this to both long and short blocked-label blocks.

- [ ] **Step 3: Verify label text does not affect entry labels**

Run:

```bash
git diff -- scripts/pinescript/strategies/SND_Strategy.pine | rg -n "label\\.set_text|show_blocked_trade_labels|LONG|SHORT|strategy\\.entry"
```

Expected: zone label text and blocked-label gates change. Entry labels and `strategy.entry` should not change.

### Task 6: Verification

**Files:**
- No additional source files.

- [ ] **Step 1: Static diff check**

Run:

```bash
git diff --check -- scripts/pinescript/strategies/SND_Strategy.pine
```

Expected: no output and exit code 0.

- [ ] **Step 2: Guard against trading-logic edits**

Run:

```bash
git diff -- scripts/pinescript/strategies/SND_Strategy.pine | rg -n "strategy\\.entry|strategy\\.exit|validate_entry_conditions|createZone|validate_.*liquidity|position_size|risk|stop_loss|take_profit"
```

Expected: no matches except unchanged context lines if a nearby visual hunk includes them. If actual edited lines include these terms, stop and inspect.

- [ ] **Step 3: TradingView compile**

Paste the updated script into TradingView.

Expected:

- No Pine compile errors.
- No warnings caused by unused mode variables.
- `visual_mode` appears under the Display group.

- [ ] **Step 4: TradingView replay cases**

Replay these exact visual checks:

- GBPJPY 5m zone `23607`: Clean mode shows the active demand zone and entry clearly.
- GBPCAD 5m screenshot case: Clean mode hides or heavily softens the brown supply/old-zone clutter.
- USDJPY 5m good case: Clean mode preserves the correct demand-zone readability.
- Diagnostic mode shows inducement/liquidity guide lines that Clean hides.
- Forensic mode shows raw/debug objects when the legacy toggles are enabled.

- [ ] **Step 5: Commit only visual changes**

Before committing, inspect:

```bash
git status --short
git diff --stat
```

Commit only the plan-approved visual changes:

```bash
git add scripts/pinescript/strategies/SND_Strategy.pine
git commit -m "DEV-634: add SND visual modes"
```
