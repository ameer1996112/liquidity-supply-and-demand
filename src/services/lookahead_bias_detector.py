"""
Sprint 4.2: Look-ahead bias detection.

Enforces: candles/features used at time T must have timestamp <= T.
Flags: future timestamp access, HTF alignment mistakes, inconsistent timezone normalization.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Union

logger = logging.getLogger(__name__)

# HTF bar close alignment: bar at 10:00 includes 09:00-10:00; we can use it only after 10:00
HTF_MINUTES = {"1m": 1, "5m": 5, "15m": 15, "1h": 60, "4h": 240, "1d": 1440}


class LookAheadBiasError(Exception):
    """Raised when look-ahead bias is detected. Backtest must fail with clear error."""

    def __init__(
        self,
        message: str,
        *,
        error_code: str = "",
        future_ts: Optional[float] = None,
        decision_ts: Optional[float] = None,
    ):
        # Attach a machine-readable error code for logs / API error_message.
        full_message = f"[{error_code}] {message}" if error_code else message
        super().__init__(full_message)
        self.error_code = error_code
        self.future_ts = future_ts
        self.decision_ts = decision_ts


def _parse_ts(value: Any) -> Optional[float]:
    """Parse timestamp to Unix seconds (UTC). Handles int/float (unix), ISO string."""
    if value is None:
        return None
    if isinstance(value, (int, float)):
        # Assume already unix seconds (or ms if > 1e12)
        if value > 1e12:
            return value / 1000.0
        return float(value)
    if isinstance(value, str):
        try:
            s = value.replace("Z", "+00:00").replace(" ", "T")
            dt = datetime.fromisoformat(s)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt.timestamp()
        except ValueError:
            return None
    return None


def _ensure_utc(ts: float) -> float:
    """Return ts as-is (assumed UTC). For normalization checks."""
    return ts


def check_future_timestamp(
    data_ts: float,
    decision_ts: float,
    *,
    label: str = "data",
) -> None:
    """
    Raise LookAheadBiasError if data_ts > decision_ts.
    Candles/features used at decision time T must have timestamp <= T.
    """
    if data_ts > decision_ts:
        raise LookAheadBiasError(
            f"Look-ahead bias: {label} timestamp {data_ts} is after decision time {decision_ts}. "
            "Candles/features at time T must have timestamp <= T.",
            error_code="LOOKAHEAD_BIAS_FUTURE_TIMESTAMP",
            future_ts=data_ts,
            decision_ts=decision_ts,
        )


def check_htf_alignment(
    candle_close_ts: float,
    timeframe: str,
    decision_ts: float,
) -> None:
    """
    HTF bar is only available after it closes.
    E.g. 1H bar 09:00-10:00 closes at 10:00; we cannot use it at 09:30.
    """
    mins = HTF_MINUTES.get(timeframe.lower(), 1)
    bar_seconds = mins * 60
    # Bar that closes at candle_close_ts was available only after candle_close_ts
    if decision_ts < candle_close_ts:
        raise LookAheadBiasError(
            f"HTF alignment: {timeframe} bar closing at {candle_close_ts} not yet closed at decision time {decision_ts}. "
            "Cannot use HTF candle until it has closed.",
            error_code="LOOKAHEAD_BIAS_HTF_ALIGNMENT",
            future_ts=candle_close_ts,
            decision_ts=decision_ts,
        )


def check_timezone_normalization(ts: float, expected_tz: str = "UTC") -> None:
    """Flag if timestamp appears to be in wrong timezone (e.g. local vs UTC mismatch)."""
    # Basic sanity: unix ts for 2020-2030 should be 1.5e9 to 2e9
    if ts < 1e9 or ts > 2.5e9:
        logger.warning(
            "LookaheadBiasDetector: timestamp %s outside expected range (2020-2030); possible timezone mismatch",
            ts,
        )


def validate_candles_at_time(
    candles: List[Dict[str, Any]],
    decision_ts: float,
    *,
    timeframe: str = "5m",
    time_key: str = "time",
) -> List[Dict[str, Any]]:
    """
    Validate candles and return only those with timestamp <= decision_ts.
    Raises LookAheadBiasError if any candle has future timestamp.
    """
    valid: List[Dict[str, Any]] = []
    for i, c in enumerate(candles):
        raw = c.get(time_key) or c.get("timestamp")
        ts = _parse_ts(raw)
        if ts is None:
            continue
        check_future_timestamp(ts, decision_ts, label=f"candle[{i}]")
        check_htf_alignment(ts, timeframe, decision_ts)
        check_timezone_normalization(ts)
        valid.append(c)
    return valid


def filter_candles_to_time(
    candles: List[Dict[str, Any]],
    decision_ts: float,
    *,
    timeframe: str = "5m",
    time_key: str = "time",
    strict: bool = True,
) -> List[Dict[str, Any]]:
    """
    Return candles with timestamp <= decision_ts.
    If strict=True, raises LookAheadBiasError on any future candle.
    """
    result: List[Dict[str, Any]] = []
    for i, c in enumerate(candles):
        raw = c.get(time_key) or c.get("timestamp")
        ts = _parse_ts(raw)
        if ts is None:
            continue
        if ts > decision_ts:
            if strict:
                raise LookAheadBiasError(
                    f"Look-ahead bias: candle[{i}] has timestamp {ts} > decision time {decision_ts}. "
                    "Forbid using future bars.",
                    error_code="LOOKAHEAD_BIAS_FUTURE_CANDLE",
                    future_ts=ts,
                    decision_ts=decision_ts,
                )
            continue
        check_htf_alignment(ts, timeframe, decision_ts)
        result.append(c)
    return result


def get_decision_ts_from_signal(sig: Dict[str, Any]) -> float:
    """Extract decision timestamp from signal (created_at or bar_time)."""
    created = sig.get("created_at") or sig.get("bar_time")
    ts = _parse_ts(created)
    if ts is None:
        raise LookAheadBiasError(
            "Signal has no valid timestamp (created_at/bar_time). Cannot enforce look-ahead checks.",
            error_code="LOOKAHEAD_BIAS_SIGNAL_NO_TIMESTAMP",
        )
    return ts
