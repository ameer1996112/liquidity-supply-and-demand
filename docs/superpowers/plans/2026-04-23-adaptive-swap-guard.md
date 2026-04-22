# Adaptive Swap Guard Recovery Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the timer-only post-swap unblock behavior with a per-symbol spread-recovery guard that keeps entries blocked until live broker spreads normalize.

**Architecture:** Keep `SwapScheduler` focused on pre-swap position closing, but refactor `SwapGuard` into a small state machine with three phases: pre-swap blackout, minimum post-swap floor, and per-symbol recovery. Inject a `spread_provider` callable from the worker so unit tests can drive recovery behavior without importing the full broker stack.

**Tech Stack:** Python, Pydantic settings, pytest, MetaApi adapter integration through `execution_adapter.get_symbol_spread`

---

## File Structure

- Modify `src/core/guard_rails/swap_guard.py`
  - Replace the blackout-only `SwapGuard` logic with an adaptive recovery state machine.
  - Keep `SwapScheduler` behavior intact for pre-swap closing.
- Modify `src/worker.py`
  - Pass the new swap settings and `execution_adapter.get_symbol_spread` into the guard.
  - Keep the scheduler tick responsible only for pre-swap closing.
- Modify `config/settings.py`
  - Replace `swap_block_after_min` with adaptive-recovery settings.
  - Add asset-class spread thresholds plus exact-symbol override config.
- Modify `tests/test_swap_guard.py`
  - Replace the fixed-window-only tests with adaptive guard coverage and keep scheduler regressions.

### Task 1: Lock In Adaptive Guard Behavior With Failing Tests

**Files:**
- Modify: `tests/test_swap_guard.py:1-123`
- Test: `tests/test_swap_guard.py`

- [ ] **Step 1: Rewrite the guard tests around the adaptive phases**

Replace the current blackout-only guard tests with focused adaptive tests and a deterministic fake spread provider.

```python
from collections import defaultdict
from unittest.mock import MagicMock, patch


class FakeSpreadProvider:
    def __init__(self, default: float | None = None):
        self.default = default
        self.values: dict[str, list[float | None]] = defaultdict(list)

    def queue(self, symbol: str, *spreads: float | None) -> None:
        self.values[symbol].extend(spreads)

    def __call__(self, symbol: str) -> float | None:
        queued = self.values.get(symbol)
        if queued:
            return queued.pop(0)
        return self.default


class TestAdaptiveSwapGuard:
    def setup_method(self):
        self.spreads = FakeSpreadProvider(default=0.00020)
        self.guard = SwapGuard(
            swap_time="00:00",
            timezone_name="Asia/Jerusalem",
            close_before_minutes=15,
            min_block_after_minutes=45,
            max_block_after_minutes=240,
            recovery_consecutive_checks=3,
            recovery_window_seconds=300,
            spread_provider=self.spreads,
            asset_class_thresholds={
                "fx": 0.00030,
                "jpy": 0.030,
                "gold": 0.50,
                "default": 0.00050,
            },
            symbol_threshold_overrides={"GBPUSD": 0.00025},
        )

    def test_rejects_inside_pre_swap_window(self):
        self.guard._now = lambda: _make_dt(23, 50)
        passed, reason = self.guard.check({"symbol": "GBPUSD"})
        assert passed is False
        assert reason.startswith("SWAP_PRE_BLACKOUT")

    def test_rejects_inside_post_swap_min_floor(self):
        self.guard._now = lambda: _make_dt(0, 30)
        passed, reason = self.guard.check({"symbol": "GBPUSD"})
        assert passed is False
        assert reason.startswith("SWAP_POST_MIN_FLOOR")

    def test_quotes_unavailable_stays_blocked(self):
        self.spreads.queue("GBPUSD", None)
        self.guard._now = lambda: _make_dt(0, 50)
        passed, reason = self.guard.check({"symbol": "GBPUSD"})
        assert passed is False
        assert reason.startswith("SWAP_QUOTES_UNAVAILABLE")

    def test_releases_symbol_after_consecutive_healthy_spreads(self):
        self.spreads.queue("GBPUSD", 0.00020, 0.00020, 0.00020)
        self.guard._now = lambda: _make_dt(0, 50)
        assert self.guard.check({"symbol": "GBPUSD"})[0] is False
        self.guard._now = lambda: _make_dt(0, 52)
        assert self.guard.check({"symbol": "GBPUSD"})[0] is False
        self.guard._now = lambda: _make_dt(0, 54)
        passed, reason = self.guard.check({"symbol": "GBPUSD"})
        assert passed is True
        assert reason.startswith("SWAP_RECOVERED")

    def test_bad_spread_resets_partial_recovery(self):
        self.spreads.queue("GBPUSD", 0.00020, 0.00080, 0.00020, 0.00020, 0.00020)
        self.guard._now = lambda: _make_dt(0, 50)
        assert self.guard.check({"symbol": "GBPUSD"})[0] is False
        self.guard._now = lambda: _make_dt(0, 51)
        passed, reason = self.guard.check({"symbol": "GBPUSD"})
        assert passed is False
        assert reason.startswith("SWAP_SPREAD_STILL_WIDE")

    def test_recovery_is_independent_per_symbol(self):
        self.spreads.queue("GBPUSD", 0.00020, 0.00020, 0.00020)
        self.spreads.queue("XAUUSD", 0.90)
        self.guard._now = lambda: _make_dt(0, 50)
        self.guard.check({"symbol": "GBPUSD"})
        self.guard._now = lambda: _make_dt(0, 51)
        self.guard.check({"symbol": "GBPUSD"})
        self.guard._now = lambda: _make_dt(0, 52)
        assert self.guard.check({"symbol": "GBPUSD"})[0] is True
        self.guard._now = lambda: _make_dt(0, 52)
        passed, reason = self.guard.check({"symbol": "XAUUSD"})
        assert passed is False
        assert reason.startswith("SWAP_SPREAD_STILL_WIDE")

    def test_hard_cap_releases_when_quotes_never_return(self):
        self.spreads.queue("GBPUSD", None)
        self.guard._now = lambda: _make_dt(4, 5)
        passed, reason = self.guard.check({"symbol": "GBPUSD"})
        assert passed is True
        assert reason.startswith("SWAP_MAX_CAP_RELEASE")
```

- [ ] **Step 2: Run the focused swap-guard tests to verify they fail**

Run: `PYTHONPATH=. pytest tests/test_swap_guard.py -v`

Expected: FAIL with constructor errors such as `TypeError: SwapGuard.__init__() got an unexpected keyword argument 'min_block_after_minutes'` and failing assertions for the new reason codes.

- [ ] **Step 3: Commit the red test state**

```bash
git add tests/test_swap_guard.py
git commit -m "DEV-201: add adaptive swap guard tests"
```

### Task 2: Implement The Adaptive SwapGuard State Machine

**Files:**
- Modify: `src/core/guard_rails/swap_guard.py:17-103`
- Test: `tests/test_swap_guard.py`

- [ ] **Step 1: Add explicit recovery-state and threshold helpers**

Introduce a small dataclass and helper methods near the top of `src/core/guard_rails/swap_guard.py`.

```python
from dataclasses import dataclass
from typing import Callable


@dataclass
class SwapRecoveryState:
    blocked_since: datetime
    last_spread: float | None = None
    healthy_check_count: int = 0
    last_healthy_at: datetime | None = None
    last_reason: str = ""
    released_at: datetime | None = None


def _asset_class_for_symbol(symbol: str) -> str:
    upper = str(symbol or "").upper()
    if upper.endswith("JPY"):
        return "jpy"
    if upper.startswith("XAU"):
        return "gold"
    return "fx"
```

- [ ] **Step 2: Replace the old constructor and blackout logic with adaptive phases**

Refactor `SwapGuard` to accept a spread callback and recovery settings, then centralize the decision flow in `check`.

```python
class SwapGuard:
    def __init__(
        self,
        swap_time: str,
        timezone_name: str,
        close_before_minutes: int,
        min_block_after_minutes: int,
        max_block_after_minutes: int,
        recovery_consecutive_checks: int,
        recovery_window_seconds: int,
        spread_provider: Callable[[str], float | None],
        asset_class_thresholds: dict[str, float],
        symbol_threshold_overrides: dict[str, float] | None = None,
    ):
        self.swap_time = swap_time
        self.timezone_name = timezone_name
        self.close_before_minutes = close_before_minutes
        self.min_block_after_minutes = min_block_after_minutes
        self.max_block_after_minutes = max_block_after_minutes
        self.recovery_consecutive_checks = recovery_consecutive_checks
        self.recovery_window_seconds = recovery_window_seconds
        self._spread_provider = spread_provider
        self._asset_class_thresholds = asset_class_thresholds
        self._symbol_threshold_overrides = symbol_threshold_overrides or {}
        self._recovery_state: dict[str, SwapRecoveryState] = {}
        self._tz = pytz.timezone(timezone_name)
```

```python
    def check(self, payload: dict) -> Tuple[bool, str]:
        symbol = str(payload.get("symbol") or "UNKNOWN").upper()
        now = self._now()
        swap_dt = self._active_swap_dt(now)
        pre_start = swap_dt - timedelta(minutes=self.close_before_minutes)
        min_floor_end = swap_dt + timedelta(minutes=self.min_block_after_minutes)
        max_cap_end = swap_dt + timedelta(minutes=self.max_block_after_minutes)
        state = self._recovery_state.get(symbol)

        if pre_start <= now < swap_dt:
            return False, self._reason("SWAP_PRE_BLACKOUT", symbol, "pre-swap blackout active")

        if swap_dt <= now < min_floor_end:
            self._ensure_state(symbol, swap_dt)
            return False, self._reason("SWAP_POST_MIN_FLOOR", symbol, "minimum post-swap floor active")

        if now >= max_cap_end and state is not None:
            self._recovery_state.pop(symbol, None)
            return True, self._reason("SWAP_MAX_CAP_RELEASE", symbol, "hard max cap reached")

        if now < pre_start:
            self._recovery_state.pop(symbol, None)
            return True, ""

        self._ensure_state(symbol, swap_dt)
        spread = self._spread_provider(symbol)
        if spread is None or spread < 0:
            self._reset_progress(symbol, now, spread, "SWAP_QUOTES_UNAVAILABLE")
            return False, self._reason("SWAP_QUOTES_UNAVAILABLE", symbol, "live spread unavailable")

        threshold = self._threshold_for_symbol(symbol)
        if spread > threshold:
            self._reset_progress(symbol, now, spread, "SWAP_SPREAD_STILL_WIDE")
            return False, self._reason("SWAP_SPREAD_STILL_WIDE", symbol, f"spread={spread:.5f} threshold={threshold:.5f}")

        if self._record_healthy_check(symbol, now, spread):
            self._recovery_state.pop(symbol, None)
            return True, self._reason("SWAP_RECOVERED", symbol, f"spread={spread:.5f} threshold={threshold:.5f}")

        return False, self._reason("SWAP_SPREAD_STILL_WIDE", symbol, "waiting for sustained healthy spreads")
```

Add the missing helper methods directly under the constructor so later steps do not invent new seams.

```python
    def _active_swap_dt(self, now: datetime) -> datetime:
        today_swap = now.replace(
            hour=self._swap_hour,
            minute=self._swap_minute,
            second=0,
            microsecond=0,
        )
        pre_start_today = today_swap - timedelta(minutes=self.close_before_minutes)
        if now >= pre_start_today:
            return today_swap
        return (today_swap - timedelta(days=0)) + timedelta(days=1)

    def _reason(self, code: str, symbol: str, detail: str) -> str:
        return f"{code}: {symbol} signal rejected — {detail}"

    def _ensure_state(self, symbol: str, swap_dt: datetime) -> None:
        self._recovery_state.setdefault(symbol, SwapRecoveryState(blocked_since=swap_dt))

    def _reset_progress(self, symbol: str, now: datetime, spread: float | None, reason: str) -> None:
        state = self._recovery_state.setdefault(symbol, SwapRecoveryState(blocked_since=now))
        state.last_spread = spread
        state.healthy_check_count = 0
        state.last_healthy_at = None
        state.last_reason = reason

    def _threshold_for_symbol(self, symbol: str) -> float:
        upper = symbol.upper()
        if upper in self._symbol_threshold_overrides:
            return self._symbol_threshold_overrides[upper]
        asset_class = _asset_class_for_symbol(upper)
        if asset_class in self._asset_class_thresholds:
            return self._asset_class_thresholds[asset_class]
        return self._asset_class_thresholds["default"]

    def _record_healthy_check(self, symbol: str, now: datetime, spread: float) -> bool:
        state = self._recovery_state.setdefault(symbol, SwapRecoveryState(blocked_since=now))
        if state.last_healthy_at and (now - state.last_healthy_at).total_seconds() > self.recovery_window_seconds:
            state.healthy_check_count = 0
        state.last_spread = spread
        state.last_healthy_at = now
        state.healthy_check_count += 1
        state.last_reason = "SWAP_RECOVERED"
        return state.healthy_check_count >= self.recovery_consecutive_checks
```

- [ ] **Step 3: Keep scheduler behavior as-is except for comments and naming clarity**

Do not change the close-order retry logic. Only clarify that `reset_if_outside_window` is scheduler-only idempotency, not post-swap release policy.

```python
    def reset_if_outside_window(self, in_window: bool) -> None:
        """Reset scheduler idempotency after the close window ends."""
        if not in_window:
            self._close_triggered = False
```

- [ ] **Step 4: Run the focused tests and make them pass**

Run: `PYTHONPATH=. pytest tests/test_swap_guard.py -v`

Expected: PASS with the new adaptive guard tests and existing scheduler tests all green.

- [ ] **Step 5: Commit the guard implementation**

```bash
git add src/core/guard_rails/swap_guard.py tests/test_swap_guard.py
git commit -m "DEV-201: implement adaptive swap guard"
```

### Task 3: Add Adaptive Swap Settings And Threshold Configuration

**Files:**
- Modify: `config/settings.py:487-492`
- Modify: `src/core/guard_rails/swap_guard.py:17-103`
- Test: `tests/test_swap_guard.py`

- [ ] **Step 1: Add a failing override-parser regression test**

Extend `tests/test_swap_guard.py` with a pure-function test for the JSON override parser.

```python
def test_parse_symbol_threshold_overrides_normalizes_keys():
    parsed = parse_symbol_threshold_overrides('{"gbpusd": 0.00025, "XAUUSD": 0.50}')
    assert parsed == {"GBPUSD": 0.00025, "XAUUSD": 0.50}


def test_parse_symbol_threshold_overrides_invalid_json_returns_empty_dict():
    assert parse_symbol_threshold_overrides("{bad-json") == {}
```

- [ ] **Step 2: Run the focused parser tests to verify the helper is still missing**

Run: `PYTHONPATH=. pytest tests/test_swap_guard.py -k "parse_symbol_threshold_overrides" -v`

Expected: FAIL with `NameError` or `AttributeError` until the parser helper exists and handles invalid JSON safely.

- [ ] **Step 3: Replace the old swap timer setting with adaptive knobs in `config/settings.py`**

Edit the swap settings block to match the approved design.

```python
    enable_swap_guard: bool = Field(default=True, description="Block new entries and close positions around broker rollover time")
    swap_time: str = Field(default="00:00", description="Broker rollover time in HH:MM format (server time)")
    swap_timezone: str = Field(default="Asia/Jerusalem", description="Timezone for swap_time (e.g. Asia/Jerusalem, UTC, Europe/Athens)")
    swap_close_before_min: int = Field(default=15, ge=1, le=60, description="Minutes before swap to close all open positions")
    swap_min_block_after_min: int = Field(default=45, ge=1, le=360, description="Minimum minutes after swap to keep entries blocked")
    swap_max_block_after_min: int = Field(default=240, ge=30, le=480, description="Hard cap on post-swap blocking when quote recovery data is unavailable")
    swap_recovery_consecutive_checks: int = Field(default=3, ge=1, le=10, description="Consecutive healthy spread checks required before unblocking a symbol")
    swap_recovery_window_seconds: int = Field(default=300, ge=30, le=1800, description="Maximum age of partial recovery progress before the healthy counter resets")
    swap_fx_max_spread: float = Field(default=0.00030, gt=0.0, description="Maximum healthy spread in price terms for standard FX pairs")
    swap_jpy_max_spread: float = Field(default=0.030, gt=0.0, description="Maximum healthy spread in price terms for JPY pairs")
    swap_gold_max_spread: float = Field(default=0.50, gt=0.0, description="Maximum healthy spread in price terms for gold symbols")
    swap_default_max_spread: float = Field(default=0.00050, gt=0.0, description="Fallback healthy spread threshold in price terms when no asset class matches")
    swap_symbol_spread_overrides_json: str = Field(default="", description="Optional JSON object mapping symbols to max healthy spread values")
```

- [ ] **Step 4: Add the parser helper and keep threshold resolution explicit**

Update the helper near the top of `swap_guard.py` so invalid JSON degrades safely and exact-symbol overrides still take precedence.

```python
def parse_symbol_threshold_overrides(raw: str) -> dict[str, float]:
    if not raw:
        return {}
    try:
        parsed = json.loads(raw)
    except Exception:  # noqa: BLE001
        return {}
    return {
        str(symbol).upper(): float(value)
        for symbol, value in parsed.items()
        if value is not None
    }


    def _threshold_for_symbol(self, symbol: str) -> float:
        upper = symbol.upper()
        if upper in self._symbol_threshold_overrides:
            return self._symbol_threshold_overrides[upper]

        asset_class = _asset_class_for_symbol(upper)
        if asset_class in self._asset_class_thresholds:
            return self._asset_class_thresholds[asset_class]

        return self._asset_class_thresholds["default"]
```

- [ ] **Step 5: Re-run the targeted parser tests**

Run: `PYTHONPATH=. pytest tests/test_swap_guard.py -k "parse_symbol_threshold_overrides" -v`

Expected: PASS with normalized uppercase symbols and safe fallback to `{}` on invalid JSON.

- [ ] **Step 6: Commit the configuration surface**

```bash
git add config/settings.py src/core/guard_rails/swap_guard.py tests/test_swap_guard.py
git commit -m "DEV-201: add swap recovery settings"
```

### Task 4: Wire The Worker To The New Guard API

**Files:**
- Modify: `src/worker.py:1432-1455`
- Modify: `src/worker.py:1960-2070`
- Modify: `src/core/guard_rails/swap_guard.py:27-103`

- [ ] **Step 1: Update the signal-path guard construction to pass the new settings and spread provider**

Replace the old `block_after_minutes` constructor call in the signal pipeline block.

```python
            swap_guard = SwapGuard(
                swap_time=getattr(s, "swap_time", "00:00"),
                timezone_name=getattr(s, "swap_timezone", "Asia/Jerusalem"),
                close_before_minutes=getattr(s, "swap_close_before_min", 15),
                min_block_after_minutes=getattr(s, "swap_min_block_after_min", 45),
                max_block_after_minutes=getattr(s, "swap_max_block_after_min", 240),
                recovery_consecutive_checks=getattr(s, "swap_recovery_consecutive_checks", 3),
                recovery_window_seconds=getattr(s, "swap_recovery_window_seconds", 300),
                spread_provider=execution_adapter.get_symbol_spread if execution_adapter else (lambda _symbol: None),
                asset_class_thresholds={
                    "fx": getattr(s, "swap_fx_max_spread", 0.00030),
                    "jpy": getattr(s, "swap_jpy_max_spread", 0.030),
                    "gold": getattr(s, "swap_gold_max_spread", 0.50),
                    "default": getattr(s, "swap_default_max_spread", 0.00050),
                },
                symbol_threshold_overrides=_load_swap_symbol_overrides(getattr(s, "swap_symbol_spread_overrides_json", "")),
            )
```

- [ ] **Step 2: Reuse the shared parser helper from `swap_guard.py`**

Import `parse_symbol_threshold_overrides` alongside `SwapGuard` and `SwapScheduler`, then replace the inline JSON parsing with the shared helper.

```python
            from src.core.guard_rails.swap_guard import (
                SwapGuard,
                SwapScheduler,
                parse_symbol_threshold_overrides,
            )
```

- [ ] **Step 3: Update the scheduler-side guard construction and log message**

Keep scheduler behavior the same, but instantiate the guard with the new settings so its phase helpers remain consistent with the signal path.

```python
            logger.info(
                "SwapGuard scheduler initialized: rollover=%s %s, close_before=%dmin min_after=%dmin max_after=%dmin",
                s.swap_time,
                s.swap_timezone,
                s.swap_close_before_min,
                s.swap_min_block_after_min,
                s.swap_max_block_after_min,
            )
```

- [ ] **Step 4: Verify the worker and guard modules at import time**

Run: `python -m py_compile src/core/guard_rails/swap_guard.py src/worker.py config/settings.py`

Expected: no output and exit code `0`.

- [ ] **Step 5: Run the focused swap guard test suite one more time**

Run: `PYTHONPATH=. pytest tests/test_swap_guard.py -v`

Expected: PASS.

- [ ] **Step 6: Commit the worker wiring**

```bash
git add src/worker.py src/core/guard_rails/swap_guard.py config/settings.py tests/test_swap_guard.py
git commit -m "DEV-201: wire adaptive swap recovery"
```

### Task 5: Final Verification And Rollout Notes

**Files:**
- Modify: `docs/superpowers/plans/2026-04-23-adaptive-swap-guard.md`
- Test: `tests/test_swap_guard.py`

- [ ] **Step 1: Run the full targeted verification set**

Run:

```bash
PYTHONPATH=. pytest tests/test_swap_guard.py -v
python -m py_compile src/core/guard_rails/swap_guard.py src/worker.py config/settings.py
```

Expected:

- `tests/test_swap_guard.py` passes
- `py_compile` exits cleanly with no output

- [ ] **Step 2: Smoke-check the final settings block against the approved defaults**

Confirm the code uses these runtime defaults:

```python
swap_close_before_min = 15
swap_min_block_after_min = 45
swap_max_block_after_min = 240
swap_recovery_consecutive_checks = 3
swap_recovery_window_seconds = 300
```

- [ ] **Step 3: Create the final implementation commit**

```bash
git add src/core/guard_rails/swap_guard.py src/worker.py config/settings.py tests/test_swap_guard.py
git commit -m "DEV-201: finalize adaptive swap guard rollout"
```

## Coverage Check

- Spec summary and goals map to Tasks 1-4.
- Per-symbol recovery state maps to Task 2.
- New settings and threshold strategy map to Task 3.
- Worker integration and scheduler separation map to Task 4.
- Testing and rollout defaults map to Task 5.
