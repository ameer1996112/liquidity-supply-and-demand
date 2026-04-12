"""Tests for SwapGuard blackout window logic."""
from datetime import datetime, timezone
import importlib.util
import sys
import pytz
import pytest

# Load swap_guard directly to avoid triggering guard_rails/__init__.py
# which pulls in yfinance and other heavy deps not installed in test env
_spec = importlib.util.spec_from_file_location(
    "swap_guard",
    "src/core/guard_rails/swap_guard.py",
)
_mod = importlib.util.module_from_spec(_spec)
sys.modules["src.core.guard_rails.swap_guard"] = _mod
_spec.loader.exec_module(_mod)

SwapGuard = _mod.SwapGuard
SwapScheduler = _mod.SwapScheduler


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


from unittest.mock import MagicMock, patch


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
