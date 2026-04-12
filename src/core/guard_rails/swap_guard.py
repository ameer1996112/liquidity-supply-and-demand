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
import time as _time

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
        """Return True if the given datetime falls inside the blackout window.

        Checks against today's AND tomorrow's swap time to handle the case where
        now=23:50 and swap=00:00 — the relevant swap is tomorrow midnight.
        """
        for day_offset in (0, 1):
            swap_dt = (now + timedelta(days=day_offset)).replace(
                hour=self._swap_hour,
                minute=self._swap_minute,
                second=0,
                microsecond=0,
            )
            window_start = swap_dt - timedelta(minutes=self.close_before_minutes)
            window_end = swap_dt + timedelta(minutes=self.block_after_minutes)
            if window_start <= now < window_end:
                return True
        return False

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
