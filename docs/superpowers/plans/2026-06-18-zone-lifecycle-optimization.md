# Zone Lifecycle Optimization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Simplify and optimize the zone lifecycle in SND_Raw_RD_Forex.pine by removing premature invalidation (returnedBeforeSweep) and strictly enforcing boundary invalidation (closeBreak/wickBreak).

**Architecture:** Modifying the `processZone` function in Pine Script to remove complex lifecycle flags that incorrectly kill zones on pullbacks, streamlining it to only invalidate when boundaries are physically breached.

**Tech Stack:** Pine Script v6

---

### Task 1: Update processZone Invalidation Logic

**Files:**
- Modify: `/Users/ameeramer/dev/projects/galilsoftware/sources/trading/scripts/pinescript/indicators/SND_Raw_RD_Forex.pine:840-920`

- [ ] **Step 1: Remove returnedBeforeSweep logic for Demand Zones**

Modify `processZone` around line 850 for `z.demand`:
```pine
            bool closeBreak =
                 afterCreated and
                 close < z.bottom

            bool wickBreak =
                 afterCreated and
                 invalidateOnWick and
                 low < z.bottom

            invalidateNow := closeBreak or wickBreak
```
(Replace the block that included `returnedBeforeSweep`)

- [ ] **Step 2: Remove returnedBeforeSweep logic for Supply Zones**

Modify `processZone` around line 880 for `else` (supply):
```pine
            bool closeBreak =
                 afterCreated and
                 close > z.top

            bool wickBreak =
                 afterCreated and
                 invalidateOnWick and
                 high > z.top

            invalidateNow := closeBreak or wickBreak
```
(Replace the block that included `returnedBeforeSweep`)

- [ ] **Step 3: Update inactiveReason assignment**

Modify the bottom of `processZone` where the zone is invalidated:
```pine
        if invalidateNow
            z.active := false
            z.inactiveReason := "ZONE_BROKEN"
            z.lastInvalidationCheckReason := z.inactiveReason
            hideInactiveZone(z)
```

- [ ] **Step 4: Commit**

```bash
git add scripts/pinescript/indicators/SND_Raw_RD_Forex.pine
git commit -m "fix(pinescript): optimize zone lifecycle by removing premature return-before-sweep invalidation"
```
