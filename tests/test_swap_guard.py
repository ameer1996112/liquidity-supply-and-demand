"""Tests for adaptive swap guard behavior and scheduler regressions."""
from collections import defaultdict
from datetime import datetime
import importlib.util
import sys
from unittest.mock import MagicMock, patch

import pytz

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
parse_symbol_threshold_overrides = _mod.parse_symbol_threshold_overrides


def _make_dt(hour: int, minute: int, tz_name: str = "Asia/Jerusalem") -> datetime:
    tz = pytz.timezone(tz_name)
    return tz.localize(
        datetime.now().replace(hour=hour, minute=minute, second=0, microsecond=0)
    )


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
        self.spreads.queue(
            "GBPUSD",
            0.00020,
            0.00080,
            0.00020,
            0.00020,
            0.00020,
        )
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
        with patch("src.adapters.discord.send_guard_notification_async") as mock_alert:
            s.close_all_positions()
            mock_alert.assert_called_once()
            call_kwargs = mock_alert.call_args
            assert "EURUSD" in str(call_kwargs)

    def test_idempotency_flag_prevents_double_close(self):
        s = self._make_scheduler()
        s._close_triggered = True
        s.close_all_positions_if_needed()
        assert s._adapter.close_order.call_count == 0

    def test_flag_resets_outside_window(self):
        s = self._make_scheduler()
        s._close_triggered = True
        s.reset_if_outside_window(in_window=False)
        assert s._close_triggered is False


def test_parse_symbol_threshold_overrides_normalizes_keys():
    parsed = parse_symbol_threshold_overrides(
        '{"gbpusd": 0.00025, "XAUUSD": 0.50}'
    )
    assert parsed == {"GBPUSD": 0.00025, "XAUUSD": 0.50}


def test_parse_symbol_threshold_overrides_invalid_json_returns_empty_dict():
    assert parse_symbol_threshold_overrides("{bad-json") == {}
