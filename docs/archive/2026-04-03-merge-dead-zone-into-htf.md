# Merge Dead Zone into HTF Candle Filter — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Remove the redundant Dead Zone guard and add its functionality as a boolean sub-toggle ("Block before hourly close") inside the HTF Candle Filter.

**Architecture:** The Dead Zone guard (blocks :50-:59 every hour) is a subset of what HTF Candle Filter already does. We merge it as a new `block_before_hourly_close` boolean toggle inside the HTF filter's DB config and worker logic. The separate dead_zone guard entry is removed from the guard registry. The frontend GuardsPanel renders it automatically from the new threshold definition.

**Tech Stack:** Python (FastAPI, Pydantic), TypeScript (React, TanStack Query), Supabase (system_config table)

---

### Task 1: Add `block_before_hourly_close` to HTF filter cache and settings loader

**Files:**
- Modify: `src/worker.py:118-160`

**Step 1: Add the new key to the HTF filter cache**

In `src/worker.py`, update the cache dict at line 119:

```python
_htf_filter_cache: dict = {"enabled": None, "minutes": None, "period": None, "hourly_close": None, "loaded_at": 0.0}
```

**Step 2: Update `_get_htf_filter_settings` to return the new field**

Change the function signature and body to also fetch/return `block_before_hourly_close`:

```python
def _get_htf_filter_settings(s) -> tuple[bool, int, int, bool]:
    """Return (htf_enabled, htf_block_minutes, htf_period, block_hourly_close) from DB (30s cache)."""
    now = time.time()
    if now - _htf_filter_cache["loaded_at"] < _SYSTEM_MODE_CACHE_TTL and _htf_filter_cache["enabled"] is not None:
        return _htf_filter_cache["enabled"], _htf_filter_cache["minutes"], _htf_filter_cache["period"], _htf_filter_cache["hourly_close"]
    try:
        sb = _get_fresh_supabase()
        if sb:
            rows = (
                sb.table("system_config")
                .select("key,value")
                .in_("key", ["pine_htf_candle_filter_enabled", "pine_htf_candle_block_minutes", "pine_htf_candle_period", "pine_block_before_hourly_close"])
                .execute()
            )
            kv = {r["key"]: r["value"] for r in (rows.data or [])}
            enabled = kv.get("pine_htf_candle_filter_enabled", None)
            minutes = kv.get("pine_htf_candle_block_minutes", None)
            period = kv.get("pine_htf_candle_period", None)
            hourly_close = kv.get("pine_block_before_hourly_close", None)
            htf_enabled = (enabled.lower() != "false") if enabled is not None else getattr(s, "pine_htf_candle_filter_enabled", True)
            htf_minutes = int(minutes) if minutes is not None else getattr(s, "pine_htf_candle_block_minutes", 10)
            htf_period = int(period) if period is not None else 15
            if htf_period not in (30, 60):
                htf_period = 30
            htf_hourly_close = (hourly_close.lower() != "false") if hourly_close is not None else getattr(s, "pine_block_dead_zone", True)
        else:
            htf_enabled = getattr(s, "pine_htf_candle_filter_enabled", True)
            htf_minutes = getattr(s, "pine_htf_candle_block_minutes", 10)
            htf_period = 30
            htf_hourly_close = getattr(s, "pine_block_dead_zone", True)
    except Exception:
        htf_enabled = getattr(s, "pine_htf_candle_filter_enabled", True)
        htf_minutes = getattr(s, "pine_htf_candle_block_minutes", 10)
        htf_period = 15
        htf_hourly_close = getattr(s, "pine_block_dead_zone", True)
    _htf_filter_cache["enabled"] = htf_enabled
    _htf_filter_cache["minutes"] = htf_minutes
    _htf_filter_cache["period"] = htf_period
    _htf_filter_cache["hourly_close"] = htf_hourly_close
    _htf_filter_cache["loaded_at"] = now
    return htf_enabled, htf_minutes, htf_period, htf_hourly_close
```

**Step 3: Commit**

```bash
git add src/worker.py
git commit -m "refactor: add block_before_hourly_close to HTF filter cache and loader"
```

---

### Task 2: Merge Dead Zone logic into HTF block and remove standalone dead zone check

**Files:**
- Modify: `src/worker.py:811-841`

**Step 1: Remove the standalone dead zone block (lines 811-820)**

Delete this entire block:
```python
    # --- Dead zone (xx:50-xx:00) --- [legacy fallback, only active if pine_block_dead_zone=true]
    if s.pine_block_dead_zone:
        bar_time = payload.get("bar_time")
        if bar_time and isinstance(bar_time, str):
            try:
                dt = _parse_dt(bar_time)
                if dt.minute >= 50:
                    return f"Dead zone: bar_time {bar_time} is in last 10 min of hour (minute={dt.minute})"
            except Exception:
                pass  # fail-open
```

**Step 2: Update the HTF block to unpack the new 4th return value and add hourly close check**

Replace the HTF block (was lines 822-841) with:

```python
    # --- HTF candle boundary protection ---
    # Combines two time-based filters into one:
    #   1. Pre-candle block: blocks entries in the last N minutes before each HTF candle open
    #   2. Hourly close block: blocks entries at xx:50-xx:59 (last 10 min of each hour)
    _htf_enabled, _htf_block_mins, _htf_period, _htf_hourly_close = _get_htf_filter_settings(s)
    bar_time = payload.get("bar_time")
    if bar_time and isinstance(bar_time, str):
        try:
            dt = _parse_dt(bar_time)
            # Hourly close protection (merged from dead zone)
            if _htf_hourly_close and dt.minute >= 50:
                return f"HTF hourly close block: entry rejected in last 10 min of hour (minute={dt.minute})"
            # HTF pre-candle open protection
            if _htf_enabled:
                candle_offset = dt.minute % _htf_period
                if candle_offset >= (_htf_period - _htf_block_mins):
                    next_candle_min = ((dt.minute // _htf_period) + 1) * _htf_period % 60
                    return (
                        f"HTF pre-candle block: entry rejected {_htf_period - candle_offset}m before "
                        f"{_htf_period}m HTF candle open at :{next_candle_min:02d} "
                        f"(bar_time minute={dt.minute}, block_mins={_htf_block_mins})"
                    )
        except Exception:
            pass  # fail-open
```

**Step 3: Commit**

```bash
git add src/worker.py
git commit -m "refactor: merge dead zone into HTF candle filter as hourly close sub-toggle"
```

---

### Task 3: Remove dead_zone from guard registry, add threshold to HTF guard

**Files:**
- Modify: `src/core/guard_rails/guard_registry.py:249-306`

**Step 1: Add the hourly close threshold to the HTF guard definition**

Update the HTF guard at lines 249-262 to include the new threshold:

```python
_register(GuardDefinition(
    guard_id="htf_candle_filter",
    setting_key="pine_htf_candle_filter_enabled",
    name="HTF Candle Filter",
    description="Blocks entries near candle boundaries (HTF opens + hourly close)",
    user_description="Protects against whipsaws near candle boundaries. Blocks entries before HTF candle opens and optionally in the last 10 minutes of each hour.",
    tier="important",
    group="trade_quality",
    value_type="bool",
    default=True,
    thresholds=[
        ThresholdDef("pine_htf_candle_block_minutes", "Block Minutes Before", "int", 5, 1, 14, "min"),
        ThresholdDef("pine_block_before_hourly_close", "Block Before Hourly Close", "bool", True, None, None, ""),
    ],
))
```

**Step 2: Remove the dead_zone guard definition (lines 296-306)**

Delete:
```python
_register(GuardDefinition(
    guard_id="dead_zone",
    setting_key="pine_block_dead_zone",
    name="Dead Zone Filter",
    description="Blocks entries at xx:50-xx:00 (candle boundary)",
    user_description="Avoids entering trades in the last 10 minutes of each hour, when price often whipsaws around the candle close.",
    tier="convenience",
    group="scheduling",
    value_type="bool",
    default=False,
))
```

**Step 3: Commit**

```bash
git add src/core/guard_rails/guard_registry.py
git commit -m "refactor: remove dead_zone guard, add hourly close toggle to HTF guard"
```

---

### Task 4: Update API models and endpoints for the new field

**Files:**
- Modify: `src/api_config.py:46-187`

**Step 1: Add DB key constant**

At line 107, add:
```python
_HOURLY_CLOSE_KEY = "pine_block_before_hourly_close"
```

**Step 2: Add field to response model**

In `HtfFilterResponse` (line 46), add:
```python
    block_before_hourly_close: bool
```

**Step 3: Add field to patch request model**

In `PatchHtfFilterRequest` (line 54), add:
```python
    block_before_hourly_close: bool | None = None
```

**Step 4: Update GET endpoint to fetch the new key**

In `get_pine_filters()`, add `_HOURLY_CLOSE_KEY` to the `.in_()` list and parse it:
```python
hourly_close = kv.get(_HOURLY_CLOSE_KEY, "true").lower() != "false"
```
Add to the return dict:
```python
"block_before_hourly_close": hourly_close,
```

**Step 5: Update PATCH endpoint to persist the new key**

In `patch_pine_filters()`, add after the period upsert block:
```python
        if body.block_before_hourly_close is not None:
            sb.table("system_config").upsert(
                {"key": _HOURLY_CLOSE_KEY, "value": str(body.block_before_hourly_close).lower()},
                on_conflict="key",
            ).execute()
```

**Step 6: Commit**

```bash
git add src/api_config.py
git commit -m "feat: add block_before_hourly_close to pine-filters API"
```

---

### Task 5: Update frontend hook and type

**Files:**
- Modify: `frontend/src/hooks/useHtfFilter.ts`

**Step 1: Add field to interface**

In `HtfFilterSettings`, add:
```typescript
  block_before_hourly_close: boolean;
```

**Step 2: Add default value**

In the `settings` default at line 49, add:
```typescript
block_before_hourly_close: true
```

**Step 3: Commit**

```bash
git add frontend/src/hooks/useHtfFilter.ts
git commit -m "feat: add block_before_hourly_close to HtfFilterSettings type"
```

---

### Task 6: Remove dead_zone icon from GuardsPanel

**Files:**
- Modify: `frontend/src/components/rules/GuardsPanel.tsx:94`

**Step 1: Remove the dead_zone entry from GUARD_ICONS**

Delete line 94:
```typescript
  dead_zone: Clock,
```

**Step 2: Commit**

```bash
git add frontend/src/components/rules/GuardsPanel.tsx
git commit -m "refactor: remove dead_zone icon from GuardsPanel (merged into HTF)"
```

---

### Task 7: Clean up risk monitor references

**Files:**
- Modify: `src/api_risk_monitor.py:58,220`
- Modify: `frontend/src/hooks/useRiskMonitor.ts:41`
- Modify: `frontend/src/app/risk/page.tsx:519-521`

**Step 1: In `src/api_risk_monitor.py`, replace `dead_zone_block_enabled` with `hourly_close_block_enabled`**

Line 58: rename field to `hourly_close_block_enabled: bool`

Line 220: change to read from DB-backed setting instead of Pydantic:
```python
hourly_close_block_enabled=settings.pine_block_dead_zone,
```

**Step 2: In `frontend/src/hooks/useRiskMonitor.ts`, rename the field**

Line 41: `dead_zone_block_enabled` → `hourly_close_block_enabled`

**Step 3: In `frontend/src/app/risk/page.tsx`, update the label and field reference**

Lines 519-521: change label from `'Dead Zone Block'` to `'Hourly Close Block'` and field from `data.dead_zone_block_enabled` to `data.hourly_close_block_enabled`.

**Step 4: Commit**

```bash
git add src/api_risk_monitor.py frontend/src/hooks/useRiskMonitor.ts frontend/src/app/risk/page.tsx
git commit -m "refactor: rename dead_zone_block_enabled to hourly_close_block_enabled in risk monitor"
```

---

### Task 8: Deprecate the `pine_block_dead_zone` Pydantic setting

**Files:**
- Modify: `config/settings.py:304`

**Step 1: Mark as deprecated but keep for backward compat**

Change line 304 to:
```python
pine_block_dead_zone: bool = Field(default=True, description="[Deprecated: merged into HTF Candle Filter as 'Block Before Hourly Close'. DB key: pine_block_before_hourly_close] Legacy fallback for hourly close block.")
```

**Step 2: Commit**

```bash
git add config/settings.py
git commit -m "refactor: deprecate pine_block_dead_zone setting (merged into HTF filter)"
```

---

## Decision Log

| Decision | Alternatives | Why |
|----------|-------------|-----|
| Fixed 10-min window for hourly close | Configurable minutes | YAGNI — 10 min has always worked, no need to add UI complexity |
| Boolean toggle inside HTF guard | Separate guard with shared UI | Simpler — one guard, one card, no redundancy |
| Keep `pine_block_dead_zone` in settings.py | Delete entirely | Backward compat — existing env vars / .env files won't break |
| Default ON for hourly close | Default OFF | Matches current behavior (settings.py default=True) |
| Hourly close independent of HTF enabled | Tied to HTF toggle | User may want hourly close protection even if HTF open blocking is off |
