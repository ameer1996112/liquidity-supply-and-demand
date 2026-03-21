---
plan: 1
phase: 9
title: Breakeven Buffer Implementation
status: pending
---

# Plan 1: Breakeven Buffer Implementation

## Goal

Modify `BreakevenManager` to shift the SL by a configurable pip buffer above entry (for buys) or below entry (for sells) when firing the breakeven trigger. Eliminate the tiny spread-caused losses (e.g. -$44.14) that occur when price returns exactly to the breakeven level.

## Context

Read before implementing:
- `.planning/phases/09-position-management-overhaul/09-CONTEXT.md`
- `src/services/breakeven_manager.py` (full file)
- `src/core/risk_engine.py` (pip size detection patterns — lines 86-127)
- `config/settings.py` (settings pattern)

## Requirements

- **POS-01**: System moves SL to `entry + N pips` (configurable, default 3) when breakeven is triggered — not exact entry price

## Implementation Steps

### Step 1: Add settings

In `config/settings.py`, add to the Settings class:

```python
# Breakeven buffer — pips above entry for buys, below for sells
breakeven_buffer_pips: float = Field(default=3.0, description="Pips buffer above/below entry when moving SL to breakeven")
```

With env var: `BREAKEVEN_BUFFER_PIPS` (already follows existing pattern).

### Step 2: Update `.env.example`

Add:
```
BREAKEVEN_BUFFER_PIPS=3        # Pips above entry (buys) / below (sells) when breakeven fires
```

### Step 3: Modify `BreakevenManager._evaluate_and_trigger()`

In `src/services/breakeven_manager.py`, update `_evaluate_and_trigger()`:

1. After reading `be_sl_price = float(row["be_sl_price"])`, read settings:
```python
try:
    from config import get_settings
    settings = get_settings()
    buffer_pips = float(getattr(settings, "breakeven_buffer_pips", 3.0))
except Exception:
    buffer_pips = 3.0
```

2. Detect pip size for symbol (reuse pattern from risk_engine.py):
```python
def _get_pip_size(self, symbol: str) -> float:
    symbol_upper = symbol.upper()
    if any(idx in symbol_upper for idx in ["NAS100", "US30", "SPX", "UK100", "GER", "FRA", "JPN225"]):
        return 1.0  # index points
    elif any(c in symbol_upper for c in ["BTC", "ETH", "XRP"]):
        return 1.0
    elif "JPY" in symbol_upper:
        return 0.01
    elif any(p in symbol_upper for p in ["XAU", "GOLD", "XAG", "SILVER"]):
        return 0.01
    else:
        return 0.0001
```

3. Apply buffer to `be_sl_price`:
```python
pip_size = self._get_pip_size(symbol)
buffer = buffer_pips * pip_size
entry = float(row["entry"])

if side == "buy":
    # For buys: be_sl_price should be at or near entry. Add buffer above entry.
    # But only if the Pine-supplied be_sl_price isn't already above entry + buffer
    adjusted_be_sl = entry + buffer
    if be_sl_price < adjusted_be_sl:
        be_sl_price = adjusted_be_sl
        logger.info(
            "BreakevenManager: applied buffer %.1f pips → adjusted be_sl=%.5f (was %.5f)",
            buffer_pips, be_sl_price, float(row["be_sl_price"])
        )
else:  # sell
    adjusted_be_sl = entry - buffer
    if be_sl_price > adjusted_be_sl:
        be_sl_price = adjusted_be_sl
        logger.info(
            "BreakevenManager: applied buffer %.1f pips → adjusted be_sl=%.5f (was %.5f)",
            buffer_pips, be_sl_price, float(row["be_sl_price"])
        )
```

4. Pass adjusted `be_sl_price` to `_modify_broker_sl()` and `_mark_triggered()`.

### Step 4: Update `_fetch_pending()` to include `entry` and `side`

The query in `_fetch_pending()` must include `entry` and `side` columns (needed for buffer calculation):

```python
.select("id, symbol, side, broker_order_id, be_trigger_price, be_sl_price, entry")
```

`side` is already included. Add `entry` if missing.

## Tests

In `tests/`, add or update `test_breakeven_manager.py`:

- Test: buy trade with `be_sl_price = entry` → adjusted to `entry + 3 * 0.0001`
- Test: sell trade with `be_sl_price = entry` → adjusted to `entry - 3 * 0.0001`
- Test: if Pine sends `be_sl_price > entry` for buy, don't reduce it
- Test: `BREAKEVEN_BUFFER_PIPS=0` → no adjustment applied
- Test: JPY pair uses 0.01 pip size correctly

## Verification

After implementing:

```bash
# Run existing tests
PYTHONPATH=/workspace pytest tests/ -v

# Check no new imports or circular deps
PYTHONPATH=/workspace python3 -c "from src.services.breakeven_manager import BreakevenManager; print('OK')"

# Verify settings loads
PYTHONPATH=/workspace python3 -c "from config import get_settings; s = get_settings(); print('Buffer pips:', getattr(s, 'breakeven_buffer_pips', 'NOT FOUND'))"
```

**Success:** All tests pass. Buffer setting loads. No import errors.
