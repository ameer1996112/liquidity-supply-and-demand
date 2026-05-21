# SND Strategy Visual Modes Design

## Goal

Make `SND_Strategy.pine` readable during replay without losing the deep debugging tools needed to investigate missed or invalid zones.

The current chart can become noisy because active zones, old zones, invalid zones, liquidity lines, labels, entry labels, and inspector/debug objects all compete at the same visual strength. This makes it hard to answer the basic question: "Is the strategy working right now?"

## Approved Direction

Use a balanced three-mode visual system:

1. **Clean**
   - Default mode.
   - Built for replay and trade validation.
   - Shows active actionable zones, entry labels, SL/TP, and the EMA context line.
   - Hides raw liquidity lines, raw fractals, blocked trade labels, inactive zones, and invalid/debug history.

2. **Diagnostic**
   - Built for normal strategy debugging.
   - Shows active zones, recently invalid zones, compact zone labels, inducement/target liquidity lines, and enough state to understand why a trade did or did not happen.
   - Keeps old/invalid visuals muted so they do not compete with live zones.

3. **Forensic**
   - Built for deep bug hunting.
   - Shows everything relevant to lifecycle analysis: raw liquidity, historical/invalid zones, rejection reasons, used zones, blocked trade labels, and model/DNA labels.
   - This mode can be visually dense because the job is investigation, not trading.

## Visual Hierarchy

Live trade opportunities should be strongest.

- Demand zones: calm teal/green.
- Supply zones: muted rose/gray, less dominant than demand entries.
- Accuracy zones: same family as their side, stronger border and slightly stronger fill.
- Used or invalid zones: gray and low contrast.
- Liquidity inducement/target lines: thin amber/gray, visible only outside Clean mode.
- Entry labels: strongest green/red object on chart because they represent actual action.

## Pine Inputs

Add one display input:

```pine
visual_mode = input.string("Clean", "visual_mode", options = ["Clean", "Diagnostic", "Forensic"], group = "Display")
```

Mode-derived booleans should control existing visuals instead of adding many new inputs:

- `visual_clean = visual_mode == "Clean"`
- `visual_diagnostic = visual_mode == "Diagnostic"`
- `visual_forensic = visual_mode == "Forensic"`
- `show_liquidity_guides = visual_diagnostic or visual_forensic`
- `show_invalid_zone_history = visual_diagnostic or visual_forensic`
- `show_raw_debug_objects = visual_forensic`

## Implementation Boundaries

This change must be visual-only.

Do not change:

- Zone creation.
- Liquidity validation.
- Invalidation logic.
- Entry conditions.
- Risk/position sizing.
- Strategy order placement.

Allowed changes:

- Display inputs.
- Color constants.
- `apply_zone_visual()`.
- Liquidity visual update functions.
- Label visibility/text density.
- Inspector/table display behavior if needed.

## Expected Behavior

In Clean mode, the chart should feel close to the other S&D indicator: quiet, readable, focused on live zones and entries.

In Diagnostic mode, it should be easy to inspect one zone and understand:

- Was liquidity valid?
- Was it swept?
- Was the target swept?
- Was the zone touched before sweep?
- Is the zone live, used, invalid, or pruned?

In Forensic mode, the script can expose internal details that are too noisy for normal replay.

## Test Plan

Manual TradingView verification is required because Pine cannot be compiled locally here.

Check these cases:

- GBPJPY 5m zone `23607`: Clean mode should show the actionable zone and entry clearly.
- GBPCAD 5m screenshot case: Clean mode should hide or heavily soften the brown supply/old-zone clutter.
- USDJPY 5m previous good case: Clean mode should preserve the correct demand-zone readability.
- Diagnostic mode should show the liquidity/inducement lines that Clean hides.
- Forensic mode should show enough internal state to debug missed/invalid zones.

## Non-Goals

This design does not attempt to improve win rate, zone detection, invalidation, or trade selection. It only makes the chart easier to read and debug.
