# Swap Guard Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Protect the trading bot from broker spread spikes during rollover/swap time by closing all open positions 15 minutes before rollover and blocking all new signal entries during a configurable 30-minute blackout window.

**Architecture:** A `SwapGuard` plugs into the existing guard_rails pipeline to reject signals during the blackout window. A `SwapScheduler` runs as a background APScheduler job (alongside the existing `digest_scheduler`) and closes all open positions before the window using `meta_api_adapter.close_order()`. Both are driven by configurable settings.

**Tech Stack:** Python, APScheduler (already installed), `pytz` (for Israel timezone), existing `MetaApiAdapter`, `send_guard_notification_async`, Pydantic settings.

---

## File Map

| File | Action | Responsibility |
|---|---|---|
| `src/core/guard_rails/swap_guard.py` | Create | Blackout window check — rejects signals |
| `src/core/guard_rails/guard_registry.py` | Modify | Register swap_guard definition |
| `config/settings.py` | Modify | Add 4 swap config fields |
| `src/worker.py` | Modify | Initialize SwapScheduler as APScheduler background job |
| `tests/test_swap_guard.py` | Create | Unit tests for SwapGuard and SwapScheduler |

---

## Task 1: Config fields in `settings.py`

**Files:**
- Modify: `config/settings.py:447-450` (after `holiday_early_close_utc_hour`)

- [ ] **Step 1: Add swap config fields after the holiday guard block**

Find the line `holiday_early_close_utc_hour: int = ...` (around line 450) and add immediately after:

```python
    # ── Swap / Rollover Guard ─────────────────────────────
    enable_swap_guard: bool = Field(default=True, description="Block new entries and close positions around broker rollover time")
    swap_time: str = Field(default="00:00", description="Broker rollover time in HH:MM format (server time)")
    swap_timezone: str = Field(default="Asia/Jerusalem", description="Timezone for swap_time (e.g. Asia/Jerusalem, UTC, Europe/Athens)")
    swap_close_before_min: int = Field(default=15, ge=1, le=60, description="Minutes before swap to close all open positions")
    swap_block_after_min: int = Field(default=15, ge=1, le=60, description="Minutes after swap to block new entries")
```

- [ ] **Step 2: Verify settings load**

```bash
cd /Users/ameeramer/dev/projects/galilsoftware/sources/trading
python -c "from config.settings import get_settings; s = get_settings(); print(s.swap_time, s.swap_timezone, s.swap_close_before_min, s.swap_block_after_min)"
```

Expected output: `00:00 Asia/Jerusalem 15 15`

- [ ] **Step 3: Commit**

```bash
git add config/settings.py
git commit -m "feat: add swap guard config fields to settings"
```

---

## Task 2: `SwapGuard` — signal blackout check

**Files:**
- Create: `src/core/guard_rails/swap_guard.py`
- Create: `tests/test_swap_guard.py` (partial — guard tests only)

- [ ] **Step 1: Write the failing tests first**

Create `tests/test_swap_guard.py`:

```python
"""Tests for SwapGuard blackout window logic."""
from datetime import datetime, timezone
import pytz
import pytest

from src.core.guard_rails.swap_guard import SwapGuard


def _make_dt(hour: int, minute: int, tz_name: str = "Asia/Jerusalem") -> datetime:
    tz = pytz.timezone(tz_name)
    return tz.localize(datetime.now().replace(hour=hour, minute=minute, second=0, microsecond=0))


class TestSwapGuardBlackout:
    def setup_method(self):
        # swap at 00:00 Asia/Jerusalem, close 15 min before, block 15 min after
        self.guard = SwapGuard(
            swap_time="00:00",
            timezone_name="Asia/Jerusalem",
            close_before_minutes=15,
            block_after_minutes=15,
        )

    def test_outside_window_allowed(self):
        dt = _make_dt(22, 0)  # 22:00 — well outside window
        assert self.guard.is_in_blackout_window(dt) is False

    def test_inside_pre_swap_window_blocked(self):
        dt = _make_dt(23, 50)  # 23:50 — 10 min before swap
        assert self.guard.is_in_blackout_window(dt) is True

    def test_at_swap_time_blocked(self):
        dt = _make_dt(0, 0)  # exactly 00:00
        assert self.guard.is_in_blackout_window(dt) is True

    def test_inside_post_swap_window_blocked(self):
        dt = _make_dt(0, 10)  # 00:10 — 10 min after swap
        assert self.guard.is_in_blackout_window(dt) is True

    def test_after_window_allowed(self):
        dt = _make_dt(0, 16)  # 00:16 — just past the window
        assert self.guard.is_in_blackout_window(dt) is False

    def test_check_returns_false_during_blackout(self):
        guard = SwapGuard("00:00", "Asia/Jerusalem", 15, 15)
        # Monkeypatch _now to return a time inside the window
        import types
        guard._now = lambda: _make_dt(23, 55)
        passed, reason = guard.check({"symbol": "EURUSD"})
        assert passed is False
        assert "SWAP_BLACKOUT" in reason

    def test_check_returns_true_outside_blackout(self):
        guard = SwapGuard("00:00", "Asia/Jerusalem", 15, 15)
        guard._now = lambda: _make_dt(12, 0)
        passed, reason = guard.check({"symbol": "EURUSD"})
        assert passed is True
        assert reason == ""
```

- [ ] **Step 2: Run tests — verify they fail**

```bash
cd /Users/ameeramer/dev/projects/galilsoftware/sources/trading
python -m pytest tests/test_swap_guard.py -v 2>&1 | head -30
```

Expected: `ModuleNotFoundError` or `ImportError` — file doesn't exist yet.

- [ ] **Step 3: Implement `swap_guard.py`**

Create `src/core/guard_rails/swap_guard.py`:

```python
"""
Swap / Rollover Guard
Rejects new trade signals during the broker rollover blackout window.

Problem:
    Broker spreads widen 5-10x around the daily rollover (swap) time.
    TradingView continues firing signals regardless, leading to trades
    being opened or held through the spread spike.

Solution:
    Reject all incoming signals during a configurable window:
    [swap_time - close_before_minutes, swap_time + block_after_minutes]

Author: Trinity Engine v3.2
"""

from datetime import datetime, timedelta
from typing import Tuple

import pytz
import logging

logger = logging.getLogger(__name__)


class SwapGuard:
    """Rejects signals during broker rollover blackout window.

    Integrates with the guard_rails pipeline via .check(payload).
    """

    def __init__(
        self,
        swap_time: str,
        timezone_name: str,
        close_before_minutes: int,
        block_after_minutes: int,
    ):
        """
        Args:
            swap_time: Rollover time in "HH:MM" format (broker server time)
            timezone_name: pytz timezone string (e.g. "Asia/Jerusalem")
            close_before_minutes: Minutes before swap to start blocking entries
            block_after_minutes: Minutes after swap to continue blocking entries
        """
        self.swap_time = swap_time
        self.timezone_name = timezone_name
        self.close_before_minutes = close_before_minutes
        self.block_after_minutes = block_after_minutes
        self._tz = pytz.timezone(timezone_name)

        try:
            parts = swap_time.split(":")
            self._swap_hour = int(parts[0])
            self._swap_minute = int(parts[1])
        except (ValueError, IndexError) as e:
            raise ValueError(f"Invalid swap_time '{swap_time}', expected HH:MM") from e

    def _now(self) -> datetime:
        """Return current time in the configured timezone. Overridable in tests."""
        return datetime.now(self._tz)

    def is_in_blackout_window(self, now: datetime) -> bool:
        """Return True if the given datetime falls inside the blackout window."""
        # Build today's swap datetime in the configured timezone
        swap_dt = now.replace(
            hour=self._swap_hour,
            minute=self._swap_minute,
            second=0,
            microsecond=0,
        )

        window_start = swap_dt - timedelta(minutes=self.close_before_minutes)
        window_end = swap_dt + timedelta(minutes=self.block_after_minutes)

        return window_start <= now < window_end

    def check(self, payload: dict) -> Tuple[bool, str]:
        """Check if a signal should be blocked due to the swap blackout window.

        Args:
            payload: Signal payload (symbol not required — all instruments blocked)

        Returns:
            (passed, reason) — passed=True means signal is OK to proceed
        """
        now = self._now()

        if self.is_in_blackout_window(now):
            symbol = payload.get("symbol", "UNKNOWN")
            reason = (
                f"SWAP_BLACKOUT: {symbol} signal rejected — broker rollover window "
                f"({self.swap_time} {self.timezone_name} ±{self.close_before_minutes}/{self.block_after_minutes}min)"
            )
            logger.info(reason)
            return False, reason

        return True, ""
```

- [ ] **Step 4: Run tests — verify they pass**

```bash
cd /Users/ameeramer/dev/projects/galilsoftware/sources/trading
python -m pytest tests/test_swap_guard.py -v
```

Expected: All 7 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add src/core/guard_rails/swap_guard.py tests/test_swap_guard.py
git commit -m "feat: add SwapGuard — rejects signals during rollover blackout window"
```

---

## Task 3: Register `swap_guard` in `guard_registry.py`

**Files:**
- Modify: `src/core/guard_rails/guard_registry.py` (after `holiday_guard` block, ~line 308)

- [ ] **Step 1: Add swap_guard registration after holiday_guard**

Find the `_register(GuardDefinition(guard_id="holiday_guard", ...))` block (ends around line 308) and add immediately after:

```python
_register(GuardDefinition(
    guard_id="swap_guard",
    setting_key="enable_swap_guard",
    name="Swap / Rollover Guard",
    description="Closes positions and blocks entries during broker rollover spread spike",
    user_description="Closes all open trades 15 minutes before broker rollover and blocks new entries for 15 minutes after. Protects against the extreme spread widening that occurs at daily swap time.",
    tier="important",
    group="scheduling",
    value_type="bool",
    default=True,
    thresholds=[
        ThresholdDef("swap_time", "Rollover Time (HH:MM)", "str", "00:00", None, None, ""),
        ThresholdDef("swap_timezone", "Rollover Timezone", "str", "Asia/Jerusalem", None, None, ""),
        ThresholdDef("swap_close_before_min", "Close Positions Before (min)", "int", 15, 1, 60, "min"),
        ThresholdDef("swap_block_after_min", "Block Entries After (min)", "int", 15, 1, 60, "min"),
    ],
))
```

- [ ] **Step 2: Verify registry loads**

```bash
cd /Users/ameeramer/dev/projects/galilsoftware/sources/trading
python -c "from src.core.guard_rails.guard_registry import GUARD_REGISTRY; print('swap_guard' in GUARD_REGISTRY)"
```

Expected: `True`

- [ ] **Step 3: Commit**

```bash
git add src/core/guard_rails/guard_registry.py
git commit -m "feat: register swap_guard in guard registry"
```

---

## Task 4: Wire `SwapGuard` into the signal pipeline

**Files:**
- Modify: `src/worker.py` (find where `HolidayGuard` is instantiated and called)

- [ ] **Step 1: Find where HolidayGuard is used in worker.py**

```bash
cd /Users/ameeramer/dev/projects/galilsoftware/sources/trading
grep -n "HolidayGuard\|holiday_guard" src/worker.py | head -20
```

Note the line numbers returned.

- [ ] **Step 2: Add SwapGuard instantiation alongside HolidayGuard**

Find where `HolidayGuard` is instantiated (something like `holiday_guard = HolidayGuard(...)`). Add immediately after:

```python
        # Swap/Rollover Guard
        from src.core.guard_rails.swap_guard import SwapGuard
        swap_guard = SwapGuard(
            swap_time=getattr(s, "swap_time", "00:00"),
            timezone_name=getattr(s, "swap_timezone", "Asia/Jerusalem"),
            close_before_minutes=getattr(s, "swap_close_before_min", 15),
            block_after_minutes=getattr(s, "swap_block_after_min", 15),
        ) if getattr(s, "enable_swap_guard", True) else None
```

- [ ] **Step 3: Add swap_guard.check() call alongside holiday_guard.check()**

Find where `holiday_guard.check(payload)` is called. Add immediately after (or before, keeping the same pattern):

```python
        if swap_guard:
            passed, reason = swap_guard.check(payload)
            if not passed:
                logger.info("SwapGuard blocked signal: %s", reason)
                return {"status": "rejected", "reason": reason}
```

- [ ] **Step 4: Verify worker imports cleanly**

```bash
cd /Users/ameeramer/dev/projects/galilsoftware/sources/trading
python -c "import src.worker; print('worker imports OK')"
```

Expected: `worker imports OK` (no import errors)

- [ ] **Step 5: Commit**

```bash
git add src/worker.py
git commit -m "feat: wire SwapGuard into signal processing pipeline"
```

---

## Task 5: `SwapScheduler` — background position closer

**Files:**
- Modify: `src/worker.py` (add scheduler init alongside `digest_scheduler` block ~line 1824)
- Modify: `tests/test_swap_guard.py` (add scheduler tests)

- [ ] **Step 1: Write failing tests for SwapScheduler**

Add to `tests/test_swap_guard.py`:

```python
from unittest.mock import MagicMock, patch, call
from src.core.guard_rails.swap_guard import SwapScheduler


class TestSwapScheduler:
    def _make_scheduler(self):
        adapter = MagicMock()
        adapter.get_open_positions.return_value = [
            {"id": "pos1", "symbol": "EURUSD"},
            {"id": "pos2", "symbol": "XAUUSD"},
        ]
        adapter.close_order.return_value = MagicMock(status="filled")
        return SwapScheduler(adapter=adapter, max_retries=3, retry_delay_seconds=0)

    def test_close_all_positions_success(self):
        s = self._make_scheduler()
        s.close_all_positions()
        assert s._adapter.close_order.call_count == 2

    def test_close_retries_on_failure_then_succeeds(self):
        adapter = MagicMock()
        adapter.get_open_positions.return_value = [{"id": "pos1", "symbol": "EURUSD"}]
        fail_result = MagicMock(status="failed")
        success_result = MagicMock(status="filled")
        adapter.close_order.side_effect = [fail_result, fail_result, success_result]
        s = SwapScheduler(adapter=adapter, max_retries=3, retry_delay_seconds=0)
        s.close_all_positions()
        assert adapter.close_order.call_count == 3

    def test_close_alerts_after_max_retries(self):
        adapter = MagicMock()
        adapter.get_open_positions.return_value = [{"id": "pos1", "symbol": "EURUSD"}]
        adapter.close_order.return_value = MagicMock(status="failed")
        s = SwapScheduler(adapter=adapter, max_retries=3, retry_delay_seconds=0)
        with patch("src.core.guard_rails.swap_guard.send_guard_notification_async") as mock_alert:
            s.close_all_positions()
            mock_alert.assert_called_once()
            call_kwargs = mock_alert.call_args
            assert "EURUSD" in str(call_kwargs)

    def test_idempotency_flag_prevents_double_close(self):
        s = self._make_scheduler()
        s._close_triggered = True  # already ran this cycle
        s.close_all_positions_if_needed()
        assert s._adapter.close_order.call_count == 0

    def test_flag_resets_outside_window(self):
        s = self._make_scheduler()
        s._close_triggered = True
        # Simulate tick when outside window
        s.reset_if_outside_window(in_window=False)
        assert s._close_triggered is False
```

- [ ] **Step 2: Run tests — verify they fail**

```bash
cd /Users/ameeramer/dev/projects/galilsoftware/sources/trading
python -m pytest tests/test_swap_guard.py::TestSwapScheduler -v 2>&1 | head -20
```

Expected: `ImportError` — `SwapScheduler` not yet defined.

- [ ] **Step 3: Add `SwapScheduler` class to `swap_guard.py`**

Append to `src/core/guard_rails/swap_guard.py`:

```python
import time as _time


class SwapScheduler:
    """Closes all open broker positions before the swap window.

    Designed to be called on a recurring tick (every 60s) from the worker loop.
    Uses an idempotency flag to avoid closing positions multiple times per cycle.
    """

    def __init__(
        self,
        adapter,  # MetaApiAdapter instance
        max_retries: int = 3,
        retry_delay_seconds: int = 5,
    ):
        self._adapter = adapter
        self._max_retries = max_retries
        self._retry_delay = retry_delay_seconds
        self._close_triggered = False

    def reset_if_outside_window(self, in_window: bool) -> None:
        """Reset the idempotency flag when the window ends."""
        if not in_window:
            self._close_triggered = False

    def close_all_positions_if_needed(self) -> None:
        """Call this from the scheduler tick. Closes positions once per window cycle."""
        if self._close_triggered:
            return
        self._close_triggered = True
        self.close_all_positions()

    def close_all_positions(self) -> None:
        """Fetch all open positions and attempt to close each one."""
        from src.adapters.discord import send_guard_notification_async
        from src.adapters.execution.interfaces import CloseRequest

        positions = self._adapter.get_open_positions()
        if not positions:
            logger.info("SwapScheduler: no open positions to close")
            return

        logger.info("SwapScheduler: closing %d positions before swap window", len(positions))

        for pos in positions:
            position_id = str(pos.get("id", ""))
            symbol = pos.get("symbol", "UNKNOWN")

            success = False
            for attempt in range(1, self._max_retries + 1):
                req = CloseRequest(
                    client_order_id=f"swap-close-{position_id}",
                    signal_id=0,
                    symbol=symbol,
                    broker_order_id=position_id,
                    notes="SwapGuard auto-close before rollover",
                )
                result = self._adapter.close_order(req)

                if result.status in ("filled", "submitted"):
                    logger.info(
                        "SwapScheduler: closed %s (positionId=%s) on attempt %d",
                        symbol, position_id, attempt,
                    )
                    success = True
                    break

                logger.warning(
                    "SwapScheduler: close attempt %d/%d failed for %s (positionId=%s): %s",
                    attempt, self._max_retries, symbol, position_id, result.message,
                )

                if attempt < self._max_retries and self._retry_delay > 0:
                    _time.sleep(self._retry_delay)

            if not success:
                logger.error(
                    "SwapScheduler: failed to close %s after %d retries — alerting",
                    symbol, self._max_retries,
                )
                send_guard_notification_async(
                    signal_id=0,
                    symbol=symbol,
                    reason=f"SWAP_GUARD: Failed to close {symbol} (positionId={position_id}) after {self._max_retries} retries — manual action required",
                )
```

- [ ] **Step 4: Run tests — verify they pass**

```bash
cd /Users/ameeramer/dev/projects/galilsoftware/sources/trading
python -m pytest tests/test_swap_guard.py -v
```

Expected: All tests PASS.

- [ ] **Step 5: Commit**

```bash
git add src/core/guard_rails/swap_guard.py tests/test_swap_guard.py
git commit -m "feat: add SwapScheduler — closes positions before rollover with retry + alert"
```

---

## Task 6: Wire `SwapScheduler` into worker background loop

**Files:**
- Modify: `src/worker.py` (~line 1824, alongside `digest_scheduler` init block)

- [ ] **Step 1: Add SwapScheduler init after digest_scheduler block (~line 1872)**

Find the comment `last_watchdog_ts = time.time()` (around line 1874). Add before it:

```python
    # Initialize Swap Guard scheduler
    swap_scheduler = None
    swap_guard_instance = None
    if getattr(s, "enable_swap_guard", True):
        try:
            from src.core.guard_rails.swap_guard import SwapGuard, SwapScheduler
            swap_guard_instance = SwapGuard(
                swap_time=getattr(s, "swap_time", "00:00"),
                timezone_name=getattr(s, "swap_timezone", "Asia/Jerusalem"),
                close_before_minutes=getattr(s, "swap_close_before_min", 15),
                block_after_minutes=getattr(s, "swap_block_after_min", 15),
            )
            swap_scheduler = SwapScheduler(
                adapter=execution_adapter,
                max_retries=3,
                retry_delay_seconds=5,
            )
            logger.info(
                "SwapGuard scheduler initialized: rollover=%s %s, window=-%d/+%dmin",
                s.swap_time, s.swap_timezone,
                s.swap_close_before_min, s.swap_block_after_min,
            )
        except Exception as exc:
            logger.warning("SwapGuard scheduler init failed: %s", exc)
```

- [ ] **Step 2: Add swap scheduler tick inside the `if now - last_watchdog_ts >= 60:` block**

Find the periodic 60-second tick block (around line 1883). Inside it, add:

```python
            # Swap Guard: close positions if entering the pre-swap window
            if swap_scheduler and swap_guard_instance:
                try:
                    now_dt = swap_guard_instance._now()
                    # Close window = close_before_minutes before swap only
                    from datetime import timedelta
                    import pytz
                    tz = pytz.timezone(s.swap_timezone)
                    swap_dt = now_dt.replace(
                        hour=swap_guard_instance._swap_hour,
                        minute=swap_guard_instance._swap_minute,
                        second=0, microsecond=0,
                    )
                    in_close_window = (
                        swap_dt - timedelta(minutes=s.swap_close_before_min)
                        <= now_dt
                        < swap_dt
                    )
                    in_full_window = swap_guard_instance.is_in_blackout_window(now_dt)
                    swap_scheduler.reset_if_outside_window(in_window=in_full_window)
                    if in_close_window:
                        swap_scheduler.close_all_positions_if_needed()
                except Exception as exc:
                    logger.warning("SwapGuard tick error: %s", exc)
```

- [ ] **Step 3: Verify worker starts without errors**

```bash
cd /Users/ameeramer/dev/projects/galilsoftware/sources/trading
python -c "import src.worker; print('worker OK')"
```

Expected: `worker OK`

- [ ] **Step 4: Run full test suite to check for regressions**

```bash
cd /Users/ameeramer/dev/projects/galilsoftware/sources/trading
python -m pytest tests/test_swap_guard.py -v
```

Expected: All tests PASS, no regressions.

- [ ] **Step 5: Commit**

```bash
git add src/worker.py
git commit -m "feat: wire SwapScheduler into worker 60s tick — closes positions before rollover"
```

---

## Task 7: Update worklog and docs

**Files:**
- Modify: `docs/worklog.md`

- [ ] **Step 1: Add worklog entry**

Append to `docs/worklog.md`:

```markdown
## 2026-04-12 — Swap Guard (Rollover Protection)

**Problem:** Trades held through broker rollover (00:00 Israel time) were losing due to
spread spikes of 5-10x normal. TradingView signals were also arriving during the window.

**Solution:**
- `SwapGuard` in `src/core/guard_rails/swap_guard.py` — rejects all incoming signals
  during a configurable blackout window (default: 15min before + 15min after rollover)
- `SwapScheduler` in same file — closes all open positions 15min before rollover,
  retries 3x on failure, alerts Discord/Telegram if all retries fail
- Config: `enable_swap_guard`, `swap_time`, `swap_timezone`, `swap_close_before_min`, `swap_block_after_min`
- Wired into `src/worker.py` periodic tick and registered in `guard_registry.py`

**Default:** 00:00 Asia/Jerusalem ±15min, all instruments, all positions closed.
```

- [ ] **Step 2: Commit**

```bash
git add docs/worklog.md
git commit -m "docs: add swap guard worklog entry"
```

---

## Self-Review Checklist

- [x] Config fields: `enable_swap_guard`, `swap_time`, `swap_timezone`, `swap_close_before_min`, `swap_block_after_min` — covered in Task 1
- [x] `SwapGuard.check()` rejects signals in blackout window — Task 2
- [x] Guard registered in `guard_registry.py` — Task 3
- [x] Guard wired into signal pipeline in `worker.py` — Task 4
- [x] `SwapScheduler` closes all positions — Task 5
- [x] Retry 3x on failure — Task 5
- [x] Alert via `send_guard_notification_async` after 3x failure — Task 5
- [x] Block entries regardless of close success — Task 4 (SwapGuard is independent of SwapScheduler)
- [x] Idempotency flag prevents double-close — Task 5
- [x] Scheduler wired into worker 60s tick — Task 6
- [x] Applies to all instruments — confirmed (SwapGuard has no symbol filter)
- [x] Worklog updated — Task 7
