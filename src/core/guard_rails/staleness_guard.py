"""
Signal Staleness Guard
Rejects outdated signals to prevent slippage on delayed webhooks.

CRITICAL: TradingView webhook latency can cause signals to arrive 3-10 seconds late.
If market moved 5+ pips during that delay, executing at the original entry price
will result in significant slippage or immediate stop-out.

This guard validates:
1. Signal Age: bar_time vs current time (reject if >5 seconds old)
2. Price Deviation: signal entry vs current market price (reject if >3 pips moved)

Author: Trinity Engine v3.0
"""

from datetime import datetime, timezone
from typing import Tuple, Optional
import logging

logger = logging.getLogger(__name__)


class StalenessGuard:
    """
    Validates signal freshness and price deviation.

    SLIPPAGE PROTECTION:
    - Webhook latency: TradingView -> API -> Redis -> Worker can take 2-10 seconds
    - Market volatility: NFP/CPI news can move 20+ pips in 5 seconds
    - Prop firm impact: 5 pip slippage on 0.5% risk = instant -0.1% drawdown
    - This guard prevents execution on stale signals

    Usage:
        guard = StalenessGuard(max_age_seconds=5, max_price_deviation_pips=3.0)
        passed, reason = guard.check(payload)

        if not passed:
            reject_trade(reason)
    """

    def __init__(self, max_age_seconds: int = 5, max_price_deviation_pips: float = 3.0):
        """
        Initialize staleness guard.

        Args:
            max_age_seconds: Maximum allowed signal age (default: 5 seconds)
            max_price_deviation_pips: Max price movement from signal entry (default: 3 pips)
        """
        self.max_age_seconds = max_age_seconds
        self.max_price_deviation_pips = max_price_deviation_pips

    def check(self, payload: dict) -> Tuple[bool, str]:
        """
        Check if signal is fresh and price hasn't moved significantly.

        Args:
            payload: Signal data with 'bar_time', 'symbol', 'entry', 'side'

        Returns:
            (passed, rejection_reason)
            - passed=True: Signal is fresh, OK to execute
            - passed=False: Signal is stale or price moved too much
        """
        # 1. Check signal age
        age_check = self._check_signal_age(payload)
        if not age_check[0]:
            return age_check

        # 2. Check current price vs signal price
        price_check = self._check_price_deviation(payload)
        if not price_check[0]:
            return price_check

        return True, ""

    def _check_signal_age(self, payload: dict) -> Tuple[bool, str]:
        """
        Validate that signal is not too old (webhook latency check).

        Args:
            payload: Must contain 'bar_time' (ISO timestamp from Pine Script)

        Returns:
            (passed, rejection_reason)
        """
        bar_time = payload.get("bar_time")
        if not bar_time:
            logger.warning("No bar_time in payload, skipping staleness check (fail-open)")
            return True, ""

        try:
            # Parse bar_time (ISO format from Pine)
            if isinstance(bar_time, str):
                # Remove timezone suffixes for parsing
                cleaned = bar_time.replace("+00:00", "").replace("Z", "").split("+")[0]

                # Try multiple datetime formats
                signal_time = None
                for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M:%S.%f"):
                    try:
                        signal_time = datetime.strptime(cleaned, fmt).replace(tzinfo=timezone.utc)
                        break
                    except ValueError:
                        continue

                # Fallback to dateutil parser
                if signal_time is None:
                    try:
                        from dateutil.parser import parse
                        signal_time = parse(bar_time)
                        if signal_time.tzinfo is None:
                            signal_time = signal_time.replace(tzinfo=timezone.utc)
                    except Exception as e:
                        logger.warning(f"Failed to parse bar_time with dateutil: {e}")
                        return True, ""  # Fail-open
            else:
                logger.warning(f"bar_time is not string: {type(bar_time)}")
                return True, ""

            # Calculate age
            now = datetime.now(timezone.utc)
            age_seconds = (now - signal_time).total_seconds()

            # Log all signal ages for monitoring
            logger.info(f"Signal age: {age_seconds:.2f}s (symbol: {payload.get('symbol')})")

            if age_seconds > self.max_age_seconds:
                return False, (
                    f"Signal staleness: {age_seconds:.1f}s old (max {self.max_age_seconds}s). "
                    f"Webhook delivery delay detected. Rejecting to prevent slippage."
                )

            # Warning for signals approaching limit (>3s but <5s)
            if age_seconds > self.max_age_seconds * 0.6:
                logger.warning(
                    f"⚠️ Signal age warning: {age_seconds:.1f}s (approaching {self.max_age_seconds}s limit)"
                )

        except Exception as e:
            logger.warning(f"Failed to parse bar_time '{bar_time}': {e} (fail-open)")
            return True, ""

        return True, ""

    def _check_price_deviation(self, payload: dict) -> Tuple[bool, str]:
        """
        Check if current market price has moved significantly from signal entry.

        Args:
            payload: Must contain 'symbol', 'entry', 'side'

        Returns:
            (passed, rejection_reason)
        """
        try:
            from src.adapters.market_data import get_current_price

            symbol = payload.get("symbol")
            signal_entry = float(payload.get("entry", 0))

            if not symbol or signal_entry == 0:
                return True, ""

            current_price = get_current_price(symbol)
            if not current_price:
                logger.warning(f"No market data for {symbol}, skipping price check (fail-open)")
                return True, ""

            # Calculate price deviation in pips
            if "JPY" in symbol:
                pip_size = 0.01
            elif "XAU" in symbol or "GOLD" in symbol:
                pip_size = 0.01
            else:
                pip_size = 0.0001

            price_diff_pips = abs(current_price - signal_entry) / pip_size

            logger.info(
                f"Price deviation: {price_diff_pips:.1f} pips "
                f"(signal: {signal_entry}, current: {current_price}, symbol: {symbol})"
            )

            if price_diff_pips > self.max_price_deviation_pips:
                return False, (
                    f"Price deviation: {price_diff_pips:.1f} pips from signal entry "
                    f"(signal: {signal_entry}, current: {current_price}). "
                    f"Market moved too much during webhook latency. Rejecting to prevent slippage."
                )

            # Warning zone: >2 pips but <3 pips
            if price_diff_pips > self.max_price_deviation_pips * 0.66:
                logger.warning(
                    f"⚠️ Price deviation warning: {price_diff_pips:.1f} pips "
                    f"(approaching {self.max_price_deviation_pips} pip limit)"
                )

        except Exception as e:
            logger.error(f"Price deviation check failed: {e} (fail-open)")
            return True, ""

        return True, ""

    def get_diagnostics(self, payload: dict) -> dict:
        """
        Get detailed diagnostics for signal staleness analysis.

        Returns:
            {
                'signal_time': datetime,
                'current_time': datetime,
                'age_seconds': float,
                'signal_entry': float,
                'current_price': float,
                'price_deviation_pips': float,
                'passed': bool,
                'warnings': List[str]
            }
        """
        diagnostics = {
            "signal_time": None,
            "current_time": datetime.now(timezone.utc),
            "age_seconds": None,
            "signal_entry": payload.get("entry"),
            "current_price": None,
            "price_deviation_pips": None,
            "passed": True,
            "warnings": [],
        }

        # Parse signal time
        bar_time = payload.get("bar_time")
        if bar_time and isinstance(bar_time, str):
            try:
                cleaned = bar_time.replace("+00:00", "").replace("Z", "").split("+")[0]
                for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M:%S.%f"):
                    try:
                        diagnostics["signal_time"] = datetime.strptime(cleaned, fmt).replace(tzinfo=timezone.utc)
                        break
                    except ValueError:
                        continue

                if diagnostics["signal_time"]:
                    diagnostics["age_seconds"] = (
                        diagnostics["current_time"] - diagnostics["signal_time"]
                    ).total_seconds()

                    if diagnostics["age_seconds"] > self.max_age_seconds:
                        diagnostics["passed"] = False
                        diagnostics["warnings"].append(f"Signal too old: {diagnostics['age_seconds']:.1f}s")
            except Exception as e:
                diagnostics["warnings"].append(f"Failed to parse bar_time: {e}")

        # Check price deviation
        try:
            from src.adapters.market_data import get_current_price

            symbol = payload.get("symbol")
            if symbol and diagnostics["signal_entry"]:
                diagnostics["current_price"] = get_current_price(symbol)

                if diagnostics["current_price"]:
                    pip_size = 0.01 if "JPY" in symbol else 0.0001
                    diagnostics["price_deviation_pips"] = (
                        abs(diagnostics["current_price"] - diagnostics["signal_entry"]) / pip_size
                    )

                    if diagnostics["price_deviation_pips"] > self.max_price_deviation_pips:
                        diagnostics["passed"] = False
                        diagnostics["warnings"].append(
                            f"Price moved too much: {diagnostics['price_deviation_pips']:.1f} pips"
                        )
        except Exception as e:
            diagnostics["warnings"].append(f"Price check failed: {e}")

        return diagnostics
