# ILP_Pro17_refactor_tokenfix.pine - Refactor Notes

## Overview

This file is a token-optimized version of `supply_and_demand_optimized.pine`.

**Purpose**: Reduce compiled IL tokens from ~101,603 to under 100,000 while maintaining identical trading behavior.

## Changes Made

### A) Token Reduction (Debug Tables Removed)

The following debug/UI tables were removed to save ~120 `table.cell` calls:

| Section Removed       | Lines Saved | table.cell Saved | Reason                        |
| --------------------- | ----------- | ---------------- | ----------------------------- |
| Debug Table           | ~210        | ~18              | Debug-only, no trading impact |
| Zone Inspector        | ~600        | ~80              | Debug-only, no trading impact |
| Position Sizing Table | ~125        | ~24              | Debug-only, no trading impact |
| Profile Status Table  | ~60         | ~16              | Debug-only, no trading impact |

**Total**: ~995 lines removed, ~120 `table.cell` calls eliminated

**Kept**: Results Table (18 calls) - essential for viewing strategy performance

### B) Warning Fixes (Series Consistency)

Added global warm-up calls for functions that access series data with variable indices:

```pine
// Line 1298-1299: Warm-up calls for series consistency
float _warmup_departure = calculate_departure_strength(1, true)
float _warmup_return = calculate_return_strength(0, bar_index, true)

// Line 2719: Warm-up call for createZone
createZone(false, 1, true, false, 1, 1, 0)
```

These ensure Pine Script's series buffers are properly maintained every bar.

### C) createZone_impl Modification

Modified `createZone_impl` to:

1. Accept `doCreate` as first parameter
2. Use `safeBaseIdx` for all series access (runs every bar)
3. Side effects (box/label creation, array modification) only when `doCreate=true`

## Trading Behavior

**NO CHANGES** to:

- Entry/exit conditions
- Zone detection/selection logic
- RR/SL/TP calculations
- Position sizing logic
- Filter logic

## Verification Checklist

- [ ] Compile succeeds (< 100,000 tokens)
- [ ] Zero "should be called on each calculation" warnings
- [ ] Same total trades on test chart
- [ ] Same net profit on test chart
- [ ] Same win rate on test chart

## Files

- `supply_and_demand_optimized.pine` - Original (keep as reference)
- `ILP_Pro17_refactor_tokenfix.pine` - Token-optimized version

## To Restore Debug Tables

Copy the removed sections from the original file if needed for debugging.
