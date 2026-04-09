# Trailing Stop R-Ladder Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix the broken trailing stop auto-activation and add an R-multiple profit ladder so profits are locked in progressively as a trade moves in our favour.

**Architecture:** Three layered changes: (1) fix a one-line call-site bug in `breakeven_manager.py` that prevents trailing stops from ever being created automatically, (2) add a DB migration with two new columns (`sl_distance_pips`, `r2_locked`, `r3_locked`) required by the R-ladder, (3) extend `TrailingStopManager` to check R-milestones on every update tick and move SL + fire Discord notifications when milestones are hit.

**Tech Stack:** Python 3.11, Supabase (PostgreSQL), MetaAPI broker adapter, Discord webhook via `src/adapters/discord.py`

**Jira:** DEV-79

---

## File Map

| Action | File | What changes |
|--------|------|--------------|
| Modify | `src/services/breakeven_manager.py` | Fix `add_trailing_stop()` call — remove 3 invalid kwargs; compute trail_pips as 50% of original SL distance |
| Modify | `src/services/trailing_stop_manager.py` | Add `sl_distance_pips`, `r2_locked`, `r3_locked` to `TrailingStop` dataclass; add `_check_r_ladder()` helper; call it inside `_update_single_trailing_stop()`; pass `sl_distance_pips` in `add_trailing_stop()` insert |
| Create | `migrations/068_trailing_stop_r_ladder.sql` | Add 3 new columns to `trailing_stops` table |
| Create | `tests/test_trailing_stop_r_ladder.py` | Tests for bug fix + R-ladder milestone logic |

---

## Task 1: Database migration

**Files:**
- Create: `migrations/068_trailing_stop_r_ladder.sql`

- [ ] **Step 1: Write the migration**

```sql
-- migrations/068_trailing_stop_r_ladder.sql
-- Adds columns needed for the R-multiple profit ladder.
-- sl_distance_pips: original SL distance in pips at time of trailing stop creation.
--                   Used to compute 1R/2R/3R price levels.
-- r2_locked / r3_locked: prevent double-firing when a milestone is revisited.

ALTER TABLE public.trailing_stops
  ADD COLUMN IF NOT EXISTS sl_distance_pips  REAL    DEFAULT NULL,
  ADD COLUMN IF NOT EXISTS r2_locked         BOOLEAN DEFAULT FALSE,
  ADD COLUMN IF NOT EXISTS r3_locked         BOOLEAN DEFAULT FALSE;

COMMENT ON COLUMN public.trailing_stops.sl_distance_pips IS
  'Original SL distance in pips when trailing stop was created. Basis for R-multiple calculations.';
COMMENT ON COLUMN public.trailing_stops.r2_locked IS
  'TRUE after SL has been moved to lock in 1R profit (price reached 2R).';
COMMENT ON COLUMN public.trailing_stops.r3_locked IS
  'TRUE after SL has been moved to lock in 2R profit (price reached 3R).';
```

- [ ] **Step 2: Apply the migration in Supabase SQL editor or psql**

```bash
# If using psql directly:
psql "$DATABASE_URL" -f migrations/068_trailing_stop_r_ladder.sql
# Or paste into Supabase dashboard → SQL Editor → Run
```

Expected: `ALTER TABLE` with no errors. Verify with:
```sql
SELECT column_name FROM information_schema.columns
WHERE table_name = 'trailing_stops'
  AND column_name IN ('sl_distance_pips','r2_locked','r3_locked');
```
Expected: 3 rows returned.

- [ ] **Step 3: Commit**

```bash
git add migrations/068_trailing_stop_r_ladder.sql
git commit -m "feat: [DEV-79] add sl_distance_pips + r2/r3 lock columns to trailing_stops"
```

---

## Task 2: Write tests (red phase)

**Files:**
- Create: `tests/test_trailing_stop_r_ladder.py`

- [ ] **Step 1: Write all failing tests**

```python
# tests/test_trailing_stop_r_ladder.py
"""
Tests for:
1. Bug fix: breakeven_manager._activate_trailing_stop uses correct params
2. R-ladder: 2R milestone locks in 1R profit
3. R-ladder: 3R milestone locks in 2R profit
4. R-ladder: milestones do not fire twice (r2_locked / r3_locked guards)
"""
import pytest
from unittest.mock import MagicMock, call, patch
from src.services.trailing_stop_manager import TrailingStopManager, TrailingStop


def _make_ts(
    side="buy",
    entry_price=1.10000,
    current_sl=1.09500,
    sl_distance_pips=50.0,      # 50-pip original SL
    trail_distance_pips=25.0,   # 50% of 50 pips
    highest_price_seen=None,
    lowest_price_seen=None,
    r2_locked=False,
    r3_locked=False,
    times_moved=0,
) -> TrailingStop:
    return TrailingStop(
        id=1,
        signal_id=42,
        symbol="EURUSD",
        side=side,
        trail_distance_pips=trail_distance_pips,
        activation_price=None,
        wait_for_breakeven=False,
        is_active=True,
        is_activated=True,
        current_sl=current_sl,
        highest_price_seen=highest_price_seen,
        lowest_price_seen=lowest_price_seen,
        entry_price=entry_price,
        times_moved=times_moved,
        sl_distance_pips=sl_distance_pips,
        r2_locked=r2_locked,
        r3_locked=r3_locked,
    )


# ---------------------------------------------------------------------------
# Task 1 bug fix: breakeven_manager calls add_trailing_stop without extra kwargs
# ---------------------------------------------------------------------------

def test_activate_trailing_stop_passes_only_valid_kwargs():
    """
    _activate_trailing_stop must call add_trailing_stop with only:
    signal_id, trail_distance_pips, activation_price, sl_distance_pips.
    It must NOT pass symbol, side, or entry_price (those don't exist in the signature).
    """
    from src.services.breakeven_manager import BreakevenManager

    mock_supabase = MagicMock()
    mock_adapter = MagicMock()
    mock_tsm = MagicMock()
    mock_tsm.add_trailing_stop.return_value = 99

    bm = BreakevenManager(mock_supabase, mock_adapter, trailing_stop_manager=mock_tsm)

    row = {
        "symbol": "EURUSD",
        "side": "buy",
        "entry": 1.10000,
        "sl": 1.09500,   # original SL → 50 pip distance
    }

    with patch("src.services.breakeven_manager.get_settings") as mock_settings:
        mock_settings.return_value.trail_activation_pips = 0.0
        bm._activate_trailing_stop(signal_id=42, row=row, be_sl_price=1.10000)

    mock_tsm.add_trailing_stop.assert_called_once()
    kwargs = mock_tsm.add_trailing_stop.call_args.kwargs

    # Must NOT contain invalid kwargs
    assert "symbol" not in kwargs, "symbol must not be passed to add_trailing_stop"
    assert "side" not in kwargs, "side must not be passed to add_trailing_stop"
    assert "entry_price" not in kwargs, "entry_price must not be passed to add_trailing_stop"

    # Must contain valid kwargs
    assert kwargs["signal_id"] == 42
    assert "trail_distance_pips" in kwargs
    assert "sl_distance_pips" in kwargs


def test_trail_distance_is_50_percent_of_sl_distance():
    """Trail distance computed from original SL distance (50% rule)."""
    from src.services.breakeven_manager import BreakevenManager

    mock_tsm = MagicMock()
    mock_tsm.add_trailing_stop.return_value = 1
    bm = BreakevenManager(MagicMock(), MagicMock(), trailing_stop_manager=mock_tsm)

    row = {"symbol": "EURUSD", "side": "buy", "entry": 1.10000, "sl": 1.09500}
    # Original SL distance = 1.10000 - 1.09500 = 0.00500 = 50 pips (pip_size=0.0001)
    # Expected trail = 50 * 0.5 = 25 pips

    with patch("src.services.breakeven_manager.get_settings") as mock_settings:
        mock_settings.return_value.trail_activation_pips = 0.0
        bm._activate_trailing_stop(signal_id=42, row=row, be_sl_price=1.10000)

    kwargs = mock_tsm.add_trailing_stop.call_args.kwargs
    assert abs(kwargs["trail_distance_pips"] - 25.0) < 0.1, (
        f"Expected trail_distance_pips=25.0, got {kwargs['trail_distance_pips']}"
    )
    assert abs(kwargs["sl_distance_pips"] - 50.0) < 0.1


# ---------------------------------------------------------------------------
# R-Ladder: 2R milestone
# ---------------------------------------------------------------------------

def test_r_ladder_2r_locks_1r_profit_for_buy():
    """
    When a BUY reaches 2R (price = entry + 2 * sl_distance), SL must move to
    entry + 1 * sl_distance (locking 1R profit). r2_locked must be set to True.
    """
    mock_client = MagicMock()
    mock_adapter = MagicMock()
    mock_adapter.modify_position.return_value = MagicMock(status="success")

    tsm = TrailingStopManager(mock_client, mock_adapter)

    # entry=1.10000, sl_distance=50 pips (0.0050), so:
    # 1R target = 1.10500, 2R target = 1.11000
    ts = _make_ts(
        side="buy",
        entry_price=1.10000,
        current_sl=1.10000,  # already at breakeven
        sl_distance_pips=50.0,
        trail_distance_pips=25.0,
    )

    # Simulate price at exactly 2R: entry + 2 * 50 pips = 1.11000
    current_price = 1.11000

    with patch.object(tsm, "_get_broker_order_id", return_value="broker-123"), \
         patch.object(tsm, "_lock_r_milestone") as mock_lock, \
         patch.object(tsm, "_move_stop_loss") as mock_move:
        tsm._check_r_ladder(ts, current_price)

    mock_lock.assert_called_once_with(ts.id, milestone=2)
    # SL should be locked at entry + 1R = 1.10000 + 0.0050 = 1.10500
    mock_move.assert_called_once()
    new_sl_arg = mock_move.call_args.args[1]
    assert abs(new_sl_arg - 1.10500) < 0.00001, f"Expected 1.10500, got {new_sl_arg}"


def test_r_ladder_2r_does_not_fire_twice():
    """Once r2_locked=True, _check_r_ladder must not move SL again."""
    tsm = TrailingStopManager(MagicMock(), MagicMock())
    ts = _make_ts(
        entry_price=1.10000, current_sl=1.10500,
        sl_distance_pips=50.0, r2_locked=True,
    )

    with patch.object(tsm, "_move_stop_loss") as mock_move, \
         patch.object(tsm, "_lock_r_milestone") as mock_lock:
        tsm._check_r_ladder(ts, current_price=1.11000)

    mock_move.assert_not_called()
    mock_lock.assert_not_called()


# ---------------------------------------------------------------------------
# R-Ladder: 3R milestone
# ---------------------------------------------------------------------------

def test_r_ladder_3r_locks_2r_profit_for_buy():
    """
    When a BUY reaches 3R (price = entry + 3 * sl_distance), SL must move to
    entry + 2 * sl_distance (locking 2R profit). r3_locked must be set to True.
    """
    tsm = TrailingStopManager(MagicMock(), MagicMock())
    ts = _make_ts(
        entry_price=1.10000, current_sl=1.10500,
        sl_distance_pips=50.0, r2_locked=True, r3_locked=False,
    )

    # 3R = entry + 3 * 50 pips = 1.11500
    current_price = 1.11500

    with patch.object(tsm, "_lock_r_milestone") as mock_lock, \
         patch.object(tsm, "_move_stop_loss") as mock_move:
        tsm._check_r_ladder(ts, current_price)

    mock_lock.assert_called_once_with(ts.id, milestone=3)
    # SL should lock at entry + 2R = 1.10000 + 0.0100 = 1.11000
    new_sl_arg = mock_move.call_args.args[1]
    assert abs(new_sl_arg - 1.11000) < 0.00001, f"Expected 1.11000, got {new_sl_arg}"


def test_r_ladder_3r_does_not_fire_twice():
    """Once r3_locked=True, _check_r_ladder must not fire again."""
    tsm = TrailingStopManager(MagicMock(), MagicMock())
    ts = _make_ts(
        entry_price=1.10000, current_sl=1.11000,
        sl_distance_pips=50.0, r2_locked=True, r3_locked=True,
    )

    with patch.object(tsm, "_move_stop_loss") as mock_move:
        tsm._check_r_ladder(ts, current_price=1.12000)

    mock_move.assert_not_called()


# ---------------------------------------------------------------------------
# SELL side
# ---------------------------------------------------------------------------

def test_r_ladder_2r_locks_1r_profit_for_sell():
    """
    SELL: entry=1.10000, sl=1.10500 → sl_distance=50 pips.
    2R target: entry - 2*50pips = 1.09000.
    Lock SL at: entry - 1*50pips = 1.09500.
    """
    tsm = TrailingStopManager(MagicMock(), MagicMock())
    ts = _make_ts(
        side="sell",
        entry_price=1.10000,
        current_sl=1.10000,  # at breakeven
        sl_distance_pips=50.0,
        trail_distance_pips=25.0,
        r2_locked=False,
    )

    current_price = 1.09000  # 2R move down

    with patch.object(tsm, "_lock_r_milestone") as mock_lock, \
         patch.object(tsm, "_move_stop_loss") as mock_move:
        tsm._check_r_ladder(ts, current_price)

    mock_lock.assert_called_once_with(ts.id, milestone=2)
    new_sl_arg = mock_move.call_args.args[1]
    assert abs(new_sl_arg - 1.09500) < 0.00001, f"Expected 1.09500, got {new_sl_arg}"


def test_r_ladder_no_action_below_2r():
    """If price hasn't reached 2R yet, _check_r_ladder does nothing."""
    tsm = TrailingStopManager(MagicMock(), MagicMock())
    ts = _make_ts(entry_price=1.10000, current_sl=1.10000, sl_distance_pips=50.0)

    # 1.5R = 1.10000 + 0.0075 = 1.10750 — not enough to trigger 2R
    with patch.object(tsm, "_move_stop_loss") as mock_move:
        tsm._check_r_ladder(ts, current_price=1.10750)

    mock_move.assert_not_called()


def test_r_ladder_skipped_when_sl_distance_missing():
    """If sl_distance_pips is None or 0, skip R-ladder to avoid division errors."""
    tsm = TrailingStopManager(MagicMock(), MagicMock())
    ts = _make_ts(sl_distance_pips=0.0)

    with patch.object(tsm, "_move_stop_loss") as mock_move:
        tsm._check_r_ladder(ts, current_price=1.15000)

    mock_move.assert_not_called()
```

- [ ] **Step 2: Run tests to confirm they all fail**

```bash
cd /Users/ameeramer/dev/projects/galilsoftware/sources/trading
python -m pytest tests/test_trailing_stop_r_ladder.py -v 2>&1 | head -60
```

Expected: All tests FAIL. Common errors:
- `TypeError: TrailingStop.__init__() got unexpected keyword argument 'sl_distance_pips'`
- `AttributeError: 'TrailingStopManager' object has no attribute '_check_r_ladder'`
- `TypeError: _activate_trailing_stop() ... unexpected keyword argument`

- [ ] **Step 3: Commit the tests**

```bash
git add tests/test_trailing_stop_r_ladder.py
git commit -m "test: [DEV-79] add failing tests for trailing stop bug fix + R-ladder"
```

---

## Task 3: Fix the breakeven → trailing stop bug

**Files:**
- Modify: `src/services/breakeven_manager.py:317-324`

- [ ] **Step 1: Replace the broken `add_trailing_stop` call**

In `src/services/breakeven_manager.py`, find `_activate_trailing_stop` (around line 288) and replace the entire method body from the `pip_size` calculation onwards:

Find this block (lines ~305–324):
```python
            pip_size = self._get_pip_size(symbol)
            trail_pips = self._get_trail_distance(symbol)
            activation_pips = float(getattr(s, "trail_activation_pips", 0.0))

            # Compute activation threshold (None = trail starts immediately)
            activation_price: Optional[float] = None
            if activation_pips > 0:
                if side == "buy":
                    activation_price = entry + (activation_pips * pip_size)
                else:
                    activation_price = entry - (activation_pips * pip_size)

            ts_id = self.trailing_stop_manager.add_trailing_stop(
                signal_id=signal_id,
                symbol=symbol,
                side=side,
                trail_distance_pips=trail_pips,
                activation_price=activation_price,
                entry_price=entry,
            )
```

Replace with:
```python
            pip_size = self._get_pip_size(symbol)
            activation_pips = float(getattr(s, "trail_activation_pips", 0.0))

            # Compute original SL distance in pips (before breakeven was applied).
            # row["sl"] is the original SL price (snapshot before BE moved it).
            original_sl = float(row.get("sl") or 0)
            if original_sl <= 0:
                logger.warning(
                    "BreakevenManager: cannot compute R-ladder for signal %s — no original SL",
                    signal_id,
                )
                return

            sl_distance_pips = abs(entry - original_sl) / pip_size
            # Trail at 50% of original SL distance so the trade has room to breathe
            trail_pips = sl_distance_pips * 0.5

            # Compute activation threshold (None = trail starts immediately)
            activation_price: Optional[float] = None
            if activation_pips > 0:
                if side == "buy":
                    activation_price = entry + (activation_pips * pip_size)
                else:
                    activation_price = entry - (activation_pips * pip_size)

            ts_id = self.trailing_stop_manager.add_trailing_stop(
                signal_id=signal_id,
                trail_distance_pips=trail_pips,
                activation_price=activation_price,
                sl_distance_pips=sl_distance_pips,
            )
```

- [ ] **Step 2: Run the bug-fix tests**

```bash
python -m pytest tests/test_trailing_stop_r_ladder.py::test_activate_trailing_stop_passes_only_valid_kwargs tests/test_trailing_stop_r_ladder.py::test_trail_distance_is_50_percent_of_sl_distance -v
```

Expected: Both tests still FAIL because `add_trailing_stop` doesn't accept `sl_distance_pips` yet. That's correct — we implement the receiver next.

- [ ] **Step 3: Commit**

```bash
git add src/services/breakeven_manager.py
git commit -m "fix: [DEV-79] remove invalid kwargs from add_trailing_stop call in breakeven_manager"
```

---

## Task 4: Update TrailingStop dataclass and add_trailing_stop

**Files:**
- Modify: `src/services/trailing_stop_manager.py`

- [ ] **Step 1: Add new fields to the TrailingStop dataclass**

Find the `TrailingStop` dataclass (lines 21–38) and add three fields at the end:

```python
@dataclass
class TrailingStop:
    """Represents an active trailing stop configuration."""
    id: int
    signal_id: int
    symbol: str
    side: str  # "buy" or "sell"
    trail_distance_pips: float
    activation_price: Optional[float]
    wait_for_breakeven: bool
    is_active: bool
    is_activated: bool
    current_sl: float
    highest_price_seen: Optional[float]
    lowest_price_seen: Optional[float]
    entry_price: float
    times_moved: int
    # R-ladder fields (added by migration 068)
    sl_distance_pips: Optional[float] = None
    r2_locked: bool = False
    r3_locked: bool = False
```

- [ ] **Step 2: Update `get_active_trailing_stops` to populate new fields**

Find where the `TrailingStop` object is constructed inside `get_active_trailing_stops` (around line 92) and add the three new fields:

```python
                ts = TrailingStop(
                    id=row["id"],
                    signal_id=row["signal_id"],
                    symbol=signal["symbol"],
                    side=signal["side"].lower(),
                    trail_distance_pips=row["trail_distance_pips"],
                    activation_price=row.get("activation_price"),
                    wait_for_breakeven=row.get("wait_for_breakeven", False),
                    is_active=row["is_active"],
                    is_activated=row.get("is_activated", False),
                    current_sl=row["current_sl"],
                    highest_price_seen=row.get("highest_price_seen"),
                    lowest_price_seen=row.get("lowest_price_seen"),
                    entry_price=signal.get("entry", 0),
                    times_moved=row.get("times_moved", 0),
                    sl_distance_pips=row.get("sl_distance_pips"),
                    r2_locked=row.get("r2_locked", False),
                    r3_locked=row.get("r3_locked", False),
                )
```

- [ ] **Step 3: Update `add_trailing_stop` to accept and store `sl_distance_pips`**

Find the method signature (line 331) and add the new parameter:

```python
    def add_trailing_stop(
        self,
        signal_id: int,
        trail_distance_pips: float,
        activation_price: Optional[float] = None,
        wait_for_breakeven: bool = False,
        sl_distance_pips: Optional[float] = None,
    ) -> Optional[int]:
```

Then find the `data = { ... }` dict inside the method (around line 368) and add the field:

```python
            data = {
                "signal_id": signal_id,
                "trail_distance_pips": trail_distance_pips,
                "current_sl": current_sl,
                "is_active": True,
                "is_activated": False if (activation_price or wait_for_breakeven) else True,
            }

            if sl_distance_pips is not None:
                data["sl_distance_pips"] = sl_distance_pips

            if activation_price:
                data["activation_price"] = activation_price

            if wait_for_breakeven:
                data["wait_for_breakeven"] = True
```

- [ ] **Step 4: Run the two bug-fix tests — they should now pass**

```bash
python -m pytest tests/test_trailing_stop_r_ladder.py::test_activate_trailing_stop_passes_only_valid_kwargs tests/test_trailing_stop_r_ladder.py::test_trail_distance_is_50_percent_of_sl_distance -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/services/trailing_stop_manager.py
git commit -m "feat: [DEV-79] add sl_distance_pips field to TrailingStop + add_trailing_stop accepts it"
```

---

## Task 5: Implement the R-ladder

**Files:**
- Modify: `src/services/trailing_stop_manager.py`

- [ ] **Step 1: Add `_check_r_ladder` method**

Add this method to `TrailingStopManager` class, just before `_update_single_trailing_stop`:

```python
    def _check_r_ladder(self, ts: TrailingStop, current_price: float) -> None:
        """
        Check R-multiple milestones and lock in profit when hit.

        2R reached → move SL to entry + 1R (lock 1R profit)
        3R reached → move SL to entry + 2R (lock 2R profit)

        Only fires once per milestone (guarded by r2_locked / r3_locked).
        Skipped if sl_distance_pips is missing or zero.
        """
        if not ts.sl_distance_pips or ts.sl_distance_pips <= 0:
            return

        if ts.entry_price <= 0:
            return

        pip_size = self._get_pip_size(ts.symbol)
        sl_distance_price = ts.sl_distance_pips * pip_size  # in price units

        if ts.side == "buy":
            r2_price = ts.entry_price + 2 * sl_distance_price
            r3_price = ts.entry_price + 3 * sl_distance_price

            if not ts.r3_locked and current_price >= r3_price:
                new_sl = ts.entry_price + 2 * sl_distance_price
                logger.info(
                    "R-Ladder [%s %s]: 3R hit at %.5f → locking SL at %.5f (2R profit)",
                    ts.symbol, ts.side, current_price, new_sl,
                )
                if new_sl > ts.current_sl:
                    self._move_stop_loss(ts, new_sl, r_milestone=3)
                self._lock_r_milestone(ts.id, milestone=3)

            elif not ts.r2_locked and current_price >= r2_price:
                new_sl = ts.entry_price + 1 * sl_distance_price
                logger.info(
                    "R-Ladder [%s %s]: 2R hit at %.5f → locking SL at %.5f (1R profit)",
                    ts.symbol, ts.side, current_price, new_sl,
                )
                if new_sl > ts.current_sl:
                    self._move_stop_loss(ts, new_sl, r_milestone=2)
                self._lock_r_milestone(ts.id, milestone=2)

        else:  # sell
            r2_price = ts.entry_price - 2 * sl_distance_price
            r3_price = ts.entry_price - 3 * sl_distance_price

            if not ts.r3_locked and current_price <= r3_price:
                new_sl = ts.entry_price - 2 * sl_distance_price
                logger.info(
                    "R-Ladder [%s %s]: 3R hit at %.5f → locking SL at %.5f (2R profit)",
                    ts.symbol, ts.side, current_price, new_sl,
                )
                if new_sl < ts.current_sl:
                    self._move_stop_loss(ts, new_sl, r_milestone=3)
                self._lock_r_milestone(ts.id, milestone=3)

            elif not ts.r2_locked and current_price <= r2_price:
                new_sl = ts.entry_price - 1 * sl_distance_price
                logger.info(
                    "R-Ladder [%s %s]: 2R hit at %.5f → locking SL at %.5f (1R profit)",
                    ts.symbol, ts.side, current_price, new_sl,
                )
                if new_sl < ts.current_sl:
                    self._move_stop_loss(ts, new_sl, r_milestone=2)
                self._lock_r_milestone(ts.id, milestone=2)
```

- [ ] **Step 2: Add `_lock_r_milestone` helper**

Add this method right after `_check_r_ladder`:

```python
    def _lock_r_milestone(self, trailing_stop_id: int, milestone: int) -> None:
        """Persist r2_locked or r3_locked to DB to prevent double-firing."""
        column = f"r{milestone}_locked"
        try:
            self.client.table("trailing_stops").update({
                column: True,
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }).eq("id", trailing_stop_id).execute()
        except Exception as e:
            logger.error("Failed to set %s for trailing stop %s: %s", column, trailing_stop_id, e)
```

- [ ] **Step 3: Update `_move_stop_loss` signature to accept optional `r_milestone`**

Find `def _move_stop_loss(self, ts: TrailingStop, new_sl: float):` and update:

```python
    def _move_stop_loss(self, ts: TrailingStop, new_sl: float, r_milestone: Optional[int] = None):
```

Inside `_move_stop_loss`, after the existing `logger.info(...)` line (around line 276), add Discord notification for R-milestone events:

```python
            # Discord notification for R-milestone profit locks
            if r_milestone is not None:
                self._notify_r_milestone(ts, new_sl, r_milestone)
```

- [ ] **Step 4: Add `_notify_r_milestone` method**

Add this method anywhere in the class:

```python
    def _notify_r_milestone(self, ts: TrailingStop, new_sl: float, milestone: int) -> None:
        """Send Discord notification when R-milestone profit is locked in."""
        try:
            from src.adapters.discord import send_discord_async
            from src.models.notification import NotificationPayload

            locked_r = milestone - 1  # at 2R we lock 1R; at 3R we lock 2R
            pip_size = self._get_pip_size(ts.symbol)
            locked_pips = abs(new_sl - ts.entry_price) / pip_size

            payload = NotificationPayload(
                title=f"🔒 {ts.symbol} — {locked_r}R Profit Locked",
                description=(
                    f"**{ts.side.upper()}** reached **{milestone}R**\n"
                    f"SL moved to **{new_sl:.5f}** (locking {locked_r}R / {locked_pips:.1f} pips profit)\n"
                    f"Entry: {ts.entry_price:.5f}"
                ),
                color=0x00FF88 if milestone == 2 else 0xFFAA00,
                fields=[
                    {"name": "Milestone", "value": f"{milestone}R hit", "inline": True},
                    {"name": "Profit Locked", "value": f"{locked_r}R", "inline": True},
                    {"name": "New SL", "value": f"{new_sl:.5f}", "inline": True},
                ],
            )
            send_discord_async(payload, alert_id=0, mode="r_milestone")
        except Exception as e:
            logger.warning("R-milestone Discord notify failed (non-critical): %s", e)
```

- [ ] **Step 5: Call `_check_r_ladder` inside `_update_single_trailing_stop`**

Find `_update_single_trailing_stop` (around line 170). After the activation checks pass and **before** the existing buy/sell trailing logic, add:

```python
        # R-ladder: lock in profit at 2R and 3R milestones
        self._check_r_ladder(ts, current_price)
```

The final structure of `_update_single_trailing_stop` should be:
```python
    def _update_single_trailing_stop(self, ts, current_price):
        pip_size = self._get_pip_size(ts.symbol)

        # Wait for breakeven checks...  (existing code, don't touch)
        if ts.wait_for_breakeven and not ts.is_activated:
            ...

        # Activation price check...  (existing code, don't touch)
        if ts.activation_price and not ts.is_activated:
            ...

        # R-ladder: lock in profit at 2R and 3R milestones  ← ADD THIS
        self._check_r_ladder(ts, current_price)

        # Standard trail: move SL behind price  (existing code, don't touch)
        if ts.side == "buy":
            ...
        else:
            ...
```

- [ ] **Step 6: Run all R-ladder tests**

```bash
python -m pytest tests/test_trailing_stop_r_ladder.py -v
```

Expected: All 9 tests PASS.

- [ ] **Step 7: Commit**

```bash
git add src/services/trailing_stop_manager.py
git commit -m "feat: [DEV-79] implement R-ladder — lock 1R at 2R, lock 2R at 3R with Discord notifications"
```

---

## Task 6: Run full test suite and final checks

- [ ] **Step 1: Run existing test suite to catch regressions**

```bash
python -m pytest tests/ -v --tb=short -x 2>&1 | tail -40
```

Expected: All existing tests pass. If any fail related to `TrailingStop` construction, it's because existing tests don't pass `sl_distance_pips` — that's fine since the field has `default=None`.

- [ ] **Step 2: Quick sanity check — verify no `symbol/side/entry_price` kwargs remain in breakeven_manager**

```bash
grep -n "symbol=symbol\|side=side\|entry_price=entry" src/services/breakeven_manager.py
```

Expected: No output (the invalid kwargs are gone).

- [ ] **Step 3: Verify trailing stop update loop calls `_check_r_ladder`**

```bash
grep -n "_check_r_ladder" src/services/trailing_stop_manager.py
```

Expected: At least 2 lines — the definition and the call inside `_update_single_trailing_stop`.

- [ ] **Step 4: Add progress comment to Jira**

```bash
node scripts/jira-agent.js add-progress DEV-79 "Implementation complete: bug fix + R-ladder (2R/3R milestone locking) + Discord notifications. All tests passing."
```

- [ ] **Step 5: Final commit and transition ticket**

```bash
git add -A
git commit -m "chore: [DEV-79] final cleanup and test run"
node scripts/autonomous-jira-cli.js finish-feature "DEV-79" "Fixed trailing stop auto-activation bug + implemented R-multiple profit ladder (lock 1R at 2R, lock 2R at 3R) with Discord notifications"
```

---

## Self-Review Checklist

- [x] Bug fix covered: `breakeven_manager` call-site fixed (Task 3)
- [x] Trail distance = 50% of original SL distance (Task 3, Step 1)
- [x] DB migration for new columns (Task 1)
- [x] `sl_distance_pips` flows from creation → DB → TrailingStop object (Tasks 1, 4)
- [x] R-ladder fires at 2R and 3R (Task 5)
- [x] R-ladder doesn't double-fire (r2_locked / r3_locked guards, Task 5 + tests)
- [x] SELL side covered (test_r_ladder_2r_locks_1r_profit_for_sell)
- [x] Discord notification on milestone (Task 5, Step 4)
- [x] No new settings added — hardcoded 50% / 2R / 3R defaults (YAGNI)
- [x] No regressions (Task 6)
- [x] Jira ticket updated (Task 6)
