"""
Swap / Rollover Guard
Blocks new trade signals around broker rollover and releases symbols
only after spreads normalize or a hard cap is reached.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta
import json
from typing import Callable, Tuple

import logging
import time as _time

import pytz

logger = logging.getLogger(__name__)


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


def parse_symbol_threshold_overrides(raw: str) -> dict[str, float]:
    if not raw:
        return {}
    try:
        parsed = json.loads(raw)
    except Exception:  # noqa: BLE001
        return {}
    if not isinstance(parsed, dict):
        return {}
    return {
        str(symbol).upper(): float(value)
        for symbol, value in parsed.items()
        if value is not None
    }


class SwapGuard:
    """Rejects signals during broker rollover and adaptive recovery phases."""

    def __init__(
        self,
        swap_time: str,
        timezone_name: str,
        close_before_minutes: int,
        block_after_minutes: int | None = None,
        *,
        min_block_after_minutes: int | None = None,
        max_block_after_minutes: int | None = None,
        recovery_consecutive_checks: int = 3,
        recovery_window_seconds: int = 300,
        spread_provider: Callable[[str], float | None] | None = None,
        asset_class_thresholds: dict[str, float] | None = None,
        symbol_threshold_overrides: dict[str, float] | None = None,
    ):
        """Create a swap guard.

        `block_after_minutes` is kept for backward compatibility while the worker
        still uses the legacy fixed-window settings.
        """
        if min_block_after_minutes is None:
            min_block_after_minutes = block_after_minutes if block_after_minutes is not None else 15
        if max_block_after_minutes is None:
            max_block_after_minutes = min_block_after_minutes
        if min_block_after_minutes < 0 or max_block_after_minutes < min_block_after_minutes:
            raise ValueError("SwapGuard block windows must satisfy 0 <= min <= max")
        if recovery_consecutive_checks < 1:
            raise ValueError("recovery_consecutive_checks must be >= 1")
        if recovery_window_seconds < 1:
            raise ValueError("recovery_window_seconds must be >= 1")

        self.swap_time = swap_time
        self.timezone_name = timezone_name
        self.close_before_minutes = close_before_minutes
        self.block_after_minutes = min_block_after_minutes
        self.min_block_after_minutes = min_block_after_minutes
        self.max_block_after_minutes = max_block_after_minutes
        self.recovery_consecutive_checks = recovery_consecutive_checks
        self.recovery_window_seconds = recovery_window_seconds
        self._spread_provider = spread_provider or (lambda _symbol: None)
        self._asset_class_thresholds = {
            "fx": 0.00030,
            "jpy": 0.030,
            "gold": 0.50,
            "default": 0.00050,
        }
        if asset_class_thresholds:
            self._asset_class_thresholds.update(
                {str(name).lower(): float(value) for name, value in asset_class_thresholds.items()}
            )
        if isinstance(symbol_threshold_overrides, str):
            self._symbol_threshold_overrides = parse_symbol_threshold_overrides(
                symbol_threshold_overrides
            )
        else:
            self._symbol_threshold_overrides = {
                str(symbol).upper(): float(value)
                for symbol, value in (symbol_threshold_overrides or {}).items()
            }
        self._recovery_state: dict[str, SwapRecoveryState] = {}
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

    def _active_swap_dt(self, now: datetime) -> datetime:
        """Return the swap cycle relevant to the current timestamp."""
        today_swap = now.replace(
            hour=self._swap_hour,
            minute=self._swap_minute,
            second=0,
            microsecond=0,
        )
        candidates = (
            today_swap - timedelta(days=1),
            today_swap,
            today_swap + timedelta(days=1),
        )
        for candidate in candidates:
            pre_start = candidate - timedelta(minutes=self.close_before_minutes)
            max_cap_end = candidate + timedelta(minutes=self.max_block_after_minutes)
            if pre_start <= now < max_cap_end:
                return candidate
        if now < today_swap - timedelta(minutes=self.close_before_minutes):
            return today_swap
        return today_swap + timedelta(days=1)

    def _reason(self, code: str, symbol: str, detail: str) -> str:
        verdict = "signal allowed" if code in {"SWAP_MAX_CAP_RELEASE", "SWAP_RECOVERED"} else "signal rejected"
        return f"{code}: {symbol} {verdict} — {detail}"

    def _ensure_state(self, symbol: str, swap_dt: datetime) -> SwapRecoveryState:
        state = self._recovery_state.get(symbol)
        if state is None or state.blocked_since != swap_dt:
            state = SwapRecoveryState(blocked_since=swap_dt)
            self._recovery_state[symbol] = state
        return state

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

    def is_in_blackout_window(self, now: datetime) -> bool:
        """Return the fixed scheduler blackout window used for close idempotency."""
        swap_dt = self._active_swap_dt(now)
        window_start = swap_dt - timedelta(minutes=self.close_before_minutes)
        window_end = swap_dt + timedelta(minutes=self.min_block_after_minutes)
        return window_start <= now < window_end

    def check(self, payload: dict) -> Tuple[bool, str]:
        """Check whether a symbol can trade through the current swap cycle."""
        symbol = str(payload.get("symbol") or "UNKNOWN").upper()
        now = self._now()
        swap_dt = self._active_swap_dt(now)
        pre_start = swap_dt - timedelta(minutes=self.close_before_minutes)
        min_floor_end = swap_dt + timedelta(minutes=self.min_block_after_minutes)
        state = self._recovery_state.get(symbol)

        if state is not None and state.blocked_since < swap_dt and now >= pre_start:
            self._recovery_state.pop(symbol, None)
            state = None

        if pre_start <= now < swap_dt:
            reason = self._reason("SWAP_PRE_BLACKOUT", symbol, "pre-swap blackout active")
            logger.info(reason)
            return False, reason

        if swap_dt <= now < min_floor_end:
            self._ensure_state(symbol, swap_dt)
            reason = self._reason("SWAP_POST_MIN_FLOOR", symbol, "minimum post-swap floor active")
            logger.info(reason)
            return False, reason

        if state is not None:
            max_cap_end = state.blocked_since + timedelta(minutes=self.max_block_after_minutes)
            if now >= max_cap_end:
                self._recovery_state.pop(symbol, None)
                reason = self._reason("SWAP_MAX_CAP_RELEASE", symbol, "hard max cap reached")
                logger.info(reason)
                return True, reason

        if now < pre_start:
            self._recovery_state.pop(symbol, None)
            previous_swap_dt = swap_dt - timedelta(days=1)
            previous_cap_end = previous_swap_dt + timedelta(minutes=self.max_block_after_minutes)
            release_grace_end = previous_cap_end + timedelta(seconds=self.recovery_window_seconds)
            if previous_cap_end <= now <= release_grace_end:
                reason = self._reason("SWAP_MAX_CAP_RELEASE", symbol, "hard max cap reached")
                logger.info(reason)
                return True, reason
            return True, ""

        self._ensure_state(symbol, swap_dt)
        spread = self._spread_provider(symbol)
        if spread is None or spread < 0:
            self._reset_progress(symbol, now, spread, "SWAP_QUOTES_UNAVAILABLE")
            reason = self._reason("SWAP_QUOTES_UNAVAILABLE", symbol, "live spread unavailable")
            logger.info(reason)
            return False, reason

        threshold = self._threshold_for_symbol(symbol)
        if spread > threshold:
            self._reset_progress(symbol, now, spread, "SWAP_SPREAD_STILL_WIDE")
            reason = self._reason(
                "SWAP_SPREAD_STILL_WIDE",
                symbol,
                f"spread={spread:.5f} threshold={threshold:.5f}",
            )
            logger.info(reason)
            return False, reason

        if self._record_healthy_check(symbol, now, spread):
            self._recovery_state.pop(symbol, None)
            reason = self._reason(
                "SWAP_RECOVERED",
                symbol,
                f"spread={spread:.5f} threshold={threshold:.5f}",
            )
            logger.info(reason)
            return True, reason

        reason = self._reason(
            "SWAP_SPREAD_STILL_WIDE",
            symbol,
            "waiting for sustained healthy spreads",
        )
        logger.info(reason)
        return False, reason


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
        """Reset scheduler idempotency after the close window cycle ends."""
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
