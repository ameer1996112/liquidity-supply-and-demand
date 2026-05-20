# Clean Strategy Mode Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Simplify `SND_Strategy.pine` display behavior so it looks clean by default, removes visual mode inputs, and keeps zones that fired entries visible as grey archive zones.

**Architecture:** Keep all trading, risk, SL/TP, alert, webhook, and order logic unchanged. Modify only the display classification helpers, entry-used zone persistence, and the static Pine guard test. Reuse existing zone arrays and ZoneDB; do not add new arrays or loops.

**Tech Stack:** Pine Script v6 strategy, Python static guard test, TradingView manual compile verification.

---

## Files

- Modify: `/Users/ameeramer/dev/projects/galilsoftware/sources/trading/scripts/pinescript/strategies/SND_Strategy.pine`
- Modify: `/Users/ameeramer/dev/projects/galilsoftware/sources/trading/scripts/pinescript/tests/test_snd_zone_rules_static.py`
- Reference: `/Users/ameeramer/dev/projects/galilsoftware/sources/trading/docs/superpowers/specs/2026-05-18-clean-strategy-mode-design.md`

## Task 1: Update Static Guard For Clean Display Contract

**Files:**
- Modify: `/Users/ameeramer/dev/projects/galilsoftware/sources/trading/scripts/pinescript/tests/test_snd_zone_rules_static.py`

- [ ] **Step 1: Add required clean-display assertions**

In the final `_require(..., "Entry-used zone archive display")` block, replace the current expected strings:

```python
[
    'show_entry_used_zones = input.bool(true, "show_entry_used_zones"',
    'z.inactiveReason := "MITIGATED:USED_FOR_ENTRY"',
    "array.set(demandZones, i, z)",
    "array.set(supplyZones, i, z)",
    'db_markInactive(z.id, "MITIGATED:USED_FOR_ENTRY")',
    "bool entryUsedArchive = show_entry_used_zones and not na(z.lastEntryBar) and not invalidOrRejected",
    "allowedByState := activeDisplayZone or entryUsedArchive",
    "allowedByState := activeDisplayZone or entryUsedArchive or (show_mitigated_zones and usedOrMitigated)",
]
```

with:

```python
[
    'z.inactiveReason := "MITIGATED:USED_FOR_ENTRY"',
    "array.set(demandZones, i, z)",
    "array.set(supplyZones, i, z)",
    'db_markInactive(z.id, "MITIGATED:USED_FOR_ENTRY")',
    "bool entryUsedArchive = not na(z.lastEntryBar) and not invalidOrRejected",
    "bool visible = activeDisplayZone or entryUsedArchive",
    "visible",
]
```

- [ ] **Step 2: Add forbidden removed-input assertions**

Extend the existing `_forbid(..., "Removed session and daily trade limit settings")` call or add a new `_forbid(...)` call immediately after it:

```python
_forbid(
    strategy,
    [
        "zone_lab_mode",
        "show_invalid_zones",
        "show_mitigated_zones",
        "show_candidate_zones",
        "show_rejection_reason_labels",
        "show_entry_used_zones",
    ],
    "Removed visual mode inputs",
)
```

- [ ] **Step 3: Run the static guard and verify it fails before implementation**

Run:

```bash
python3 scripts/pinescript/tests/test_snd_zone_rules_static.py
```

Expected before implementation:

```text
AssertionError
```

The failure should mention missing clean-display strings or forbidden visual mode inputs still present.

## Task 2: Remove Visual Mode Inputs

**Files:**
- Modify: `/Users/ameeramer/dev/projects/galilsoftware/sources/trading/scripts/pinescript/strategies/SND_Strategy.pine`

- [ ] **Step 1: Remove display mode input declarations**

In the display settings block, remove these lines:

```pine
zone_lab_mode = input.bool(false, "zone_lab_mode", group = "🎨 Display")
show_invalid_zones = input.bool(false, "show_invalid_zones", group = "🎨 Display")
show_mitigated_zones = input.bool(false, "show_mitigated_zones", group = "🎨 Display")
show_entry_used_zones = input.bool(true, "show_entry_used_zones", group = "🎨 Display")
show_candidate_zones = input.bool(false, "show_candidate_zones", group = "🎨 Display")
show_rejection_reason_labels = input.bool(false, "show_rejection_reason_labels", group = "🎨 Display")
```

Keep these existing settings:

```pine
show_active_zones_only = input.bool(true, "show_active_zones_only", group = "🎨 Display")
show_relevant_zones_only = input.bool(true, "show_relevant_zones_only", group = "🎨 Display")
relevant_zone_atr_distance = input.float(25.0, "relevant_zone_atr_distance", minval = 0.0, maxval = 100.0, step = 0.5, group = "🎨 Display")
zone_label_style = input.string("Compact", "zone_label_style", options = ["Compact", "Detailed"], group = "🎨 Display")
zone_label_show_metrics = input.bool(false, "zone_label_show_metrics", group = "🎨 Display")
show_blocked_trade_labels = input.bool(false, "show_blocked_trade_labels", group = "🎨 Display")
```

- [ ] **Step 2: Replace references to `zone_lab_mode` in visual loops**

Replace demand/supply visual-loop gates of this shape:

```pine
if z.active or zone_lab_mode
```

with:

```pine
if z.active or not na(z.lastEntryBar)
```

This keeps entry-used archive zones updateable without a debug mode flag.

- [ ] **Step 3: Replace metric label condition**

Replace:

```pine
zone_lab_mode and zone_label_show_metrics
```

with:

```pine
debug_enabled and zone_label_show_metrics
```

This keeps metric labels tied to `debug_level`, not to a removed display mode.

## Task 3: Simplify Zone Display Classification

**Files:**
- Modify: `/Users/ameeramer/dev/projects/galilsoftware/sources/trading/scripts/pinescript/strategies/SND_Strategy.pine`

- [ ] **Step 1: Replace `zone_should_show_visual()` body**

Replace the current function:

```pine
zone_should_show_visual(Core.Zone z, bool isDemand) =>
    bool activeTradable = zone_is_active_tradable(z)
    bool usedOrMitigated = zone_is_used_or_mitigated(z)
    bool invalidOrRejected = zone_is_invalid_or_rejected(z)
    bool entryUsedArchive = show_entry_used_zones and not na(z.lastEntryBar) and not invalidOrRejected
    bool activeDisplayZone = z.active and not z.mitigated and not invalidOrRejected and zone_is_relevant_visual(z, isDemand)
    bool candidate = not activeDisplayZone and not usedOrMitigated and not invalidOrRejected
    bool allowedByState = activeDisplayZone or entryUsedArchive
    if zone_lab_mode
        allowedByState := activeDisplayZone or entryUsedArchive or (show_mitigated_zones and usedOrMitigated) or (show_invalid_zones and invalidOrRejected) or (show_candidate_zones and candidate)
    else
        allowedByState := activeDisplayZone or entryUsedArchive
    allowedByState
```

with:

```pine
zone_should_show_visual(Core.Zone z, bool isDemand) =>
    bool invalidOrRejected = zone_is_invalid_or_rejected(z)
    bool entryUsedArchive = not na(z.lastEntryBar) and not invalidOrRejected
    bool activeDisplayZone = z.active and not z.mitigated and not invalidOrRejected and zone_is_relevant_visual(z, isDemand)
    bool visible = activeDisplayZone or entryUsedArchive
    visible
```

- [ ] **Step 2: Keep grey archive styling in `apply_zone_visual()`**

Confirm this block remains unchanged:

```pine
if usedOrMitigated
    bgColor := col_used_zone_bg
    borderColor := col_used_zone_border
    borderWidth := 1
```

This is what makes entry-used zones appear as muted grey archive zones.

- [ ] **Step 3: Confirm invalid/rejected reasons do not classify mitigated used zones as invalid**

Keep this logic in `zone_is_invalid_or_rejected()`:

```pine
str.length(reason) > 0 and not zone_has_pending_reason(reason) and not str.contains(reason, "MITIGATED:")
```

This prevents `MITIGATED:USED_FOR_ENTRY` from hiding an archive zone as an invalid zone.

## Task 4: Persist Entry-Used Zones Without Touching Orders

**Files:**
- Modify: `/Users/ameeramer/dev/projects/galilsoftware/sources/trading/scripts/pinescript/strategies/SND_Strategy.pine`

- [ ] **Step 1: Confirm long-entry used state persists after order logic**

In `process_long_entries()`, after:

```pine
z.lastEntryBar := bar_index
z.active := false
z.primed := false  // Reset just in case
```

ensure these lines exist immediately after:

```pine
z.mitigated := true
z.inactiveReason := "MITIGATED:USED_FOR_ENTRY"
array.set(demandZones, i, z)
db_markInactive(z.id, "MITIGATED:USED_FOR_ENTRY")
```

Do not move or alter any `strategy.entry`, `alert`, `strategy.exit`, position sizing, webhook, SL, or TP code.

- [ ] **Step 2: Confirm short-entry used state persists after order logic**

In `process_short_entries()`, after:

```pine
z.lastEntryBar := bar_index
z.active := false
z.primed := false  // Reset just in case
```

ensure these lines exist immediately after:

```pine
z.mitigated := true
z.inactiveReason := "MITIGATED:USED_FOR_ENTRY"
array.set(supplyZones, i, z)
db_markInactive(z.id, "MITIGATED:USED_FOR_ENTRY")
```

Do not move or alter any `strategy.entry`, `alert`, `strategy.exit`, position sizing, webhook, SL, or TP code.

## Task 5: Remove Remaining Mode References

**Files:**
- Modify: `/Users/ameeramer/dev/projects/galilsoftware/sources/trading/scripts/pinescript/strategies/SND_Strategy.pine`
- Modify: `/Users/ameeramer/dev/projects/galilsoftware/sources/trading/scripts/pinescript/tests/test_snd_zone_rules_static.py`

- [ ] **Step 1: Search for removed identifiers**

Run:

```bash
rg -n "zone_lab_mode|show_invalid_zones|show_mitigated_zones|show_candidate_zones|show_rejection_reason_labels|show_entry_used_zones" scripts/pinescript/strategies/SND_Strategy.pine scripts/pinescript/tests/test_snd_zone_rules_static.py
```

Expected after implementation:

```text
```

No matches.

- [ ] **Step 2: Search for trading logic changes before committing**

Run:

```bash
git diff -- scripts/pinescript/strategies/SND_Strategy.pine | rg -n "strategy\\.entry|strategy\\.exit|build_webhook_payload|build_exit_webhook_payload|validate_position_size|get_tp_ratio|stop_loss|take_profit|risk"
```

Expected:

Only unchanged context lines may appear. There should be no added or removed lines changing order execution, risk, SL/TP, or webhook calls.

## Task 6: Verify

**Files:**
- Test: `/Users/ameeramer/dev/projects/galilsoftware/sources/trading/scripts/pinescript/tests/test_snd_zone_rules_static.py`

- [ ] **Step 1: Run static guard**

Run:

```bash
python3 scripts/pinescript/tests/test_snd_zone_rules_static.py
```

Expected:

```text
SND displacement scanner static contract passed
```

- [ ] **Step 2: Run whitespace diff check**

Run:

```bash
git diff --check -- scripts/pinescript/strategies/SND_Strategy.pine scripts/pinescript/tests/test_snd_zone_rules_static.py
```

Expected:

```text
```

No output.

- [ ] **Step 3: Review final diff scope**

Run:

```bash
git diff --stat -- scripts/pinescript/strategies/SND_Strategy.pine scripts/pinescript/tests/test_snd_zone_rules_static.py
```

Expected:

```text
 scripts/pinescript/strategies/SND_Strategy.pine       | ...
 scripts/pinescript/tests/test_snd_zone_rules_static.py | ...
```

Only the strategy and static guard test should be listed.

- [ ] **Step 4: Manual TradingView verification**

Paste/save the updated Pine script in TradingView and verify:

```text
1. Script compiles.
2. Normal chart shows active zones cleanly.
3. A zone that fires an entry remains visible as grey archive.
4. Used-entry archive zones do not fire another trade.
5. debug_level = None hides the inspector.
6. debug_level = Basic or Full shows the inspector.
7. Risk, SL/TP, webhooks, and orders behave unchanged.
```

## Task 7: Commit Implementation

**Files:**
- Modify: `/Users/ameeramer/dev/projects/galilsoftware/sources/trading/scripts/pinescript/strategies/SND_Strategy.pine`
- Modify: `/Users/ameeramer/dev/projects/galilsoftware/sources/trading/scripts/pinescript/tests/test_snd_zone_rules_static.py`

- [ ] **Step 1: Stage only implementation files**

Run:

```bash
git add scripts/pinescript/strategies/SND_Strategy.pine scripts/pinescript/tests/test_snd_zone_rules_static.py
```

- [ ] **Step 2: Commit**

Run:

```bash
git commit -m "DEV-530: simplify Pine clean display mode"
```

Expected:

```text
[feature/DEV-512-pine-zone-liquidity-state-engine ...] DEV-530: simplify Pine clean display mode
```

Do not stage unrelated `mcp/tradingview-mcp` changes.
