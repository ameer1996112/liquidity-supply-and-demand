---
plan: 2
phase: 9
title: Trailing Stop Auto-Activation After Breakeven
status: pending
---

# Plan 2: Trailing Stop Auto-Activation After Breakeven

## Goal

After `BreakevenManager` marks a position as triggered, automatically activate a trailing stop via `TrailingStopManager.add_trailing_stop()`. The trailing stop uses per-symbol configurable distances so forex and indices behave differently. All lifecycle events are logged to `trade_events`.

## Context

Read before implementing:
- `.planning/phases/09-position-management-overhaul/09-CONTEXT.md`
- `src/services/breakeven_manager.py` (full file)
- `src/services/trailing_stop_manager.py` (focus: `add_trailing_stop()` method, lines 330-400)
- `src/worker.py` lines 100-145 (manager initialization)
- `config/settings.py`

## Requirements

- **POS-02**: System activates trailing stop automatically after breakeven fires on any position
- **POS-03**: Trailing stop distance is configurable per instrument type
- **POS-04**: Trailing stop has configurable activation threshold
- **POS-05**: Full position lifecycle is logged to `trade_events` table

## Implementation Steps

### Step 1: Add settings

In `config/settings.py`, add to the Settings class:

```python
# Trailing stop activation after breakeven
trail_distance_pips_forex: float = Field(default=15.0, description="Trail distance in pips for forex pairs")
trail_distance_points_indices: float = Field(default=30.0, description="Trail distance in points for index CFDs")
trail_distance_pips_gold: float = Field(default=50.0, description="Trail distance in pips for XAUUSD/GOLD")
trail_activation_pips: float = Field(default=0.0, description="Pips from entry before trailing starts (0 = start immediately from BE)")
```

### Step 2: Update `.env.example`

Add:
```
TRAIL_DISTANCE_PIPS_FOREX=15      # Trailing distance for forex (EURUSD, GBPUSD, etc.)
TRAIL_DISTANCE_POINTS_INDICES=30  # Trailing distance for indices (NAS100, US30, etc.)
TRAIL_DISTANCE_PIPS_GOLD=50       # Trailing distance for gold (XAUUSD)
TRAIL_ACTIVATION_PIPS=0           # Min pips from entry before trailing starts (0 = immediate)
```

### Step 3: Inject `TrailingStopManager` into `BreakevenManager`

Update `BreakevenManager.__init__()`:

```python
def __init__(self, supabase_client, adapter=None, trailing_stop_manager=None):
    self.client = supabase_client
    self.adapter = adapter
    self.trailing_stop_manager = trailing_stop_manager  # NEW
```

### Step 4: Update `src/worker.py` initialization

In `worker.py`, after both managers are initialized (around line 136), pass the trailing_stop_manager reference:

```python
trailing_stop_manager = TrailingStopManager(supabase, adapter)
breakeven_manager = BreakevenManager(supabase, adapter, trailing_stop_manager=trailing_stop_manager)
```

### Step 5: Add `_get_trail_distance()` helper to `BreakevenManager`

```python
def _get_trail_distance(self, symbol: str) -> float:
    """Return trail distance in pips/points based on symbol type."""
    try:
        from config import get_settings
        s = get_settings()
        symbol_upper = symbol.upper()
        if any(idx in symbol_upper for idx in ["NAS100", "US30", "SPX", "UK100", "GER", "FRA", "JPN225", "AUS200"]):
            return float(getattr(s, "trail_distance_points_indices", 30.0))
        elif any(p in symbol_upper for p in ["XAU", "GOLD", "XAG", "SILVER"]):
            return float(getattr(s, "trail_distance_pips_gold", 50.0))
        else:
            return float(getattr(s, "trail_distance_pips_forex", 15.0))
    except Exception:
        return 15.0
```

### Step 6: Activate trailing stop in `_mark_triggered()`

After the DB update in `_mark_triggered()`, add trailing stop activation:

```python
def _mark_triggered(self, signal_id: int, new_sl: float, broker_ok: bool, row: dict = None) -> None:
    """Persist be_triggered=TRUE, update sl, activate trailing stop."""
    try:
        update = {
            "be_triggered": True,
            "sl": new_sl,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        self.client.table("trading_signals").update(update).eq("id", signal_id).execute()

        # Emit breakeven_triggered event (existing)
        try:
            from src.services.trade_events import log_event
            log_event(signal_id, "breakeven_triggered", "breakeven_manager", {
                "new_sl": new_sl,
                "broker_updated": broker_ok,
            })
        except Exception:
            pass

        # Auto-activate trailing stop (NEW)
        if self.trailing_stop_manager and row and broker_ok:
            self._activate_trailing_stop(signal_id, row, new_sl)

    except Exception as exc:
        logger.error("BreakevenManager: failed to mark signal %s as triggered: %s", signal_id, exc)

def _activate_trailing_stop(self, signal_id: int, row: dict, be_sl_price: float) -> None:
    """Activate trailing stop after breakeven fires."""
    try:
        from config import get_settings
        s = get_settings()
        symbol = row["symbol"]
        side = (row.get("side") or "").lower()
        entry = float(row["entry"])
        pip_size = self._get_pip_size(symbol)
        trail_pips = self._get_trail_distance(symbol)
        activation_pips = float(getattr(s, "trail_activation_pips", 0.0))

        # Activation price: entry + N pips (for buys). 0 = activate immediately.
        if activation_pips > 0:
            if side == "buy":
                activation_price = entry + (activation_pips * pip_size)
            else:
                activation_price = entry - (activation_pips * pip_size)
        else:
            activation_price = None  # Start trailing immediately

        ts_id = self.trailing_stop_manager.add_trailing_stop(
            signal_id=signal_id,
            symbol=symbol,
            side=side,
            trail_distance_pips=trail_pips,
            activation_price=activation_price,
            entry_price=entry,
        )

        if ts_id:
            logger.info(
                "BreakevenManager: trailing stop activated for signal %s (%s %s) "
                "trail=%.1f pips, activation=%s",
                signal_id, side, symbol, trail_pips,
                f"{activation_price:.5f}" if activation_price else "immediate"
            )
            # Log trail_started event
            try:
                from src.services.trade_events import log_event
                log_event(signal_id, "trail_started", "breakeven_manager", {
                    "trail_distance_pips": trail_pips,
                    "activation_price": activation_price,
                    "entry_price": entry,
                    "symbol": symbol,
                })
            except Exception:
                pass
        else:
            logger.warning("BreakevenManager: failed to activate trailing stop for signal %s", signal_id)

    except Exception as exc:
        logger.error("BreakevenManager: trailing stop activation failed for signal %s: %s", signal_id, exc)
```

### Step 7: Pass `row` to `_mark_triggered()`

Update `_evaluate_and_trigger()` call to pass the full `row`:

```python
self._mark_triggered(signal_id, be_sl_price, broker_ok, row=row)
```

## Tests

Add to `tests/test_breakeven_manager.py`:

- Test: after BE fires, `trailing_stop_manager.add_trailing_stop()` is called with correct args
- Test: if `trailing_stop_manager` is None, no error raised (graceful)
- Test: forex symbol → uses `trail_distance_pips_forex`
- Test: NAS100 symbol → uses `trail_distance_points_indices`
- Test: XAUUSD → uses `trail_distance_pips_gold`
- Test: `trail_activation_pips=5` → activation_price = entry + 5 pips
- Test: `trail_activation_pips=0` → activation_price = None (immediate)
- Test: `trail_started` event logged after activation

## Verification

```bash
# All tests pass
PYTHONPATH=/workspace pytest tests/ -v

# Check imports
PYTHONPATH=/workspace python3 -c "
from src.services.breakeven_manager import BreakevenManager
from src.services.trailing_stop_manager import TrailingStopManager
b = BreakevenManager(None, None, None)
print('BreakevenManager accepts trailing_stop_manager param:', True)
"

# Confirm settings load all new vars
PYTHONPATH=/workspace python3 -c "
from config import get_settings
s = get_settings()
for attr in ['trail_distance_pips_forex', 'trail_distance_points_indices', 'trail_distance_pips_gold', 'trail_activation_pips']:
    print(f'{attr}: {getattr(s, attr, \"NOT FOUND\")}')
"
```

**Success:** All tests pass. Settings load. TrailingStopManager called correctly on BE trigger. `trail_started` event in trade_events.
