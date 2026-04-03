"""
Market Holiday Guard
Rejects signals for instruments whose underlying exchange is closed.

Problem:
    TradingView still generates signals on holidays (chart data from pre-market
    or overnight feeds), but the broker correctly rejects with
    TRADE_RETCODE_MARKET_CLOSED (10018). This wastes API calls and creates
    noisy EXECUTION_FAILED alerts.

Solution:
    Check if the current date is a known market holiday for the instrument's
    asset class. Reject the signal early in the pipeline, before it reaches
    the execution engine.

Supported calendars:
    - US Equity holidays (for NAS100, US30, SPX500, US2000)
    - Early close days (e.g. day before Independence Day, day after Thanksgiving)

Author: Trinity Engine v3.1
"""

from datetime import date, timedelta, datetime, timezone
from typing import Tuple, Set, Optional
import logging

logger = logging.getLogger(__name__)


# ══════════════════════════════════════════════════════════
# US MARKET HOLIDAY CALENDAR
# ══════════════════════════════════════════════════════════

# US equity exchanges (NYSE/NASDAQ) are closed on these holidays.
# CFD brokers follow the same schedule for index CFDs.
#
# Fixed-date holidays:
#   - New Year's Day (Jan 1)
#   - Juneteenth (Jun 19)
#   - Independence Day (Jul 4)
#   - Christmas Day (Dec 25)
#
# Floating holidays:
#   - MLK Day (3rd Monday of Jan)
#   - Presidents' Day (3rd Monday of Feb)
#   - Good Friday (Friday before Easter)
#   - Memorial Day (last Monday of May)
#   - Labor Day (1st Monday of Sep)
#   - Thanksgiving (4th Thursday of Nov)
#
# Weekend rule: if a fixed holiday falls on Saturday, the market is closed
# on Friday; if it falls on Sunday, the market is closed on Monday.


def _nth_weekday(year: int, month: int, weekday: int, n: int) -> date:
    """Return the nth occurrence of a weekday in a given month.

    Args:
        weekday: 0=Monday, 6=Sunday
        n: 1-based (1=first, 2=second, etc.)
    """
    first_day = date(year, month, 1)
    # Days until first occurrence of target weekday
    days_ahead = (weekday - first_day.weekday()) % 7
    first_occurrence = first_day + timedelta(days=days_ahead)
    return first_occurrence + timedelta(weeks=n - 1)


def _last_weekday(year: int, month: int, weekday: int) -> date:
    """Return the last occurrence of a weekday in a given month."""
    # Start from the last day of the month
    if month == 12:
        last_day = date(year + 1, 1, 1) - timedelta(days=1)
    else:
        last_day = date(year, month + 1, 1) - timedelta(days=1)
    days_back = (last_day.weekday() - weekday) % 7
    return last_day - timedelta(days=days_back)


def _easter_sunday(year: int) -> date:
    """Compute Easter Sunday using the Anonymous Gregorian algorithm."""
    a = year % 19
    b, c = divmod(year, 100)
    d, e = divmod(b, 4)
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i, k = divmod(c, 4)
    l = (32 + 2 * e + 2 * i - h - k) % 7  # noqa: E741
    m = (a + 11 * h + 22 * l) // 451
    month, day = divmod(h + l - 7 * m + 114, 31)
    return date(year, month, day + 1)


def _adjust_for_weekend(d: date) -> date:
    """If a holiday falls on Saturday, observe Friday; Sunday, observe Monday."""
    if d.weekday() == 5:  # Saturday
        return d - timedelta(days=1)
    elif d.weekday() == 6:  # Sunday
        return d + timedelta(days=1)
    return d


def get_us_market_holidays(year: int) -> Set[date]:
    """Return all US equity market holidays for a given year."""
    holidays = set()

    # Fixed holidays (with weekend adjustment)
    holidays.add(_adjust_for_weekend(date(year, 1, 1)))    # New Year's Day
    holidays.add(_adjust_for_weekend(date(year, 6, 19)))   # Juneteenth
    holidays.add(_adjust_for_weekend(date(year, 7, 4)))    # Independence Day
    holidays.add(_adjust_for_weekend(date(year, 12, 25)))  # Christmas Day

    # Floating holidays
    holidays.add(_nth_weekday(year, 1, 0, 3))   # MLK Day (3rd Monday Jan)
    holidays.add(_nth_weekday(year, 2, 0, 3))   # Presidents' Day (3rd Monday Feb)
    holidays.add(_last_weekday(year, 5, 0))      # Memorial Day (last Monday May)
    holidays.add(_nth_weekday(year, 9, 0, 1))   # Labor Day (1st Monday Sep)
    holidays.add(_nth_weekday(year, 11, 3, 4))  # Thanksgiving (4th Thursday Nov)

    # Good Friday (Friday before Easter Sunday)
    easter = _easter_sunday(year)
    holidays.add(easter - timedelta(days=2))

    return holidays


def get_us_early_close_dates(year: int) -> Set[date]:
    """Return dates when US markets close early (typically 1:00 PM ET).

    CFD brokers may close indices entirely on these days, or may have
    reduced liquidity / wider spreads.
    """
    early_close = set()

    # Day before Independence Day (Jul 3, unless it falls on weekend)
    jul3 = date(year, 7, 3)
    if jul3.weekday() < 5:  # Mon-Fri
        early_close.add(jul3)

    # Day after Thanksgiving (Black Friday)
    thanksgiving = _nth_weekday(year, 11, 3, 4)
    early_close.add(thanksgiving + timedelta(days=1))

    # Christmas Eve (Dec 24, if weekday)
    dec24 = date(year, 12, 24)
    if dec24.weekday() < 5:
        early_close.add(dec24)

    return early_close


# ══════════════════════════════════════════════════════════
# INDEX SYMBOL DETECTION
# ══════════════════════════════════════════════════════════

_US_INDEX_FRAGMENTS = [
    "NAS100", "US100", "NDX", "USTEC",
    "US30", "DJ30", "DJI", "DOW",
    "SPX", "SP500", "US500", "SPY",
    "US2000", "RUS2000", "RTY",
]


def is_us_index(symbol: str) -> bool:
    """Check if a symbol is a US stock index (CFD or futures)."""
    upper = symbol.upper().replace(".", "").replace("/", "")
    return any(frag in upper for frag in _US_INDEX_FRAGMENTS)


# ══════════════════════════════════════════════════════════
# HOLIDAY GUARD
# ══════════════════════════════════════════════════════════

# Cache holidays per year to avoid recomputation every signal
_holiday_cache: dict[int, Set[date]] = {}
_early_close_cache: dict[int, Set[date]] = {}


def _get_holidays(year: int) -> Set[date]:
    if year not in _holiday_cache:
        _holiday_cache[year] = get_us_market_holidays(year)
    return _holiday_cache[year]


def _get_early_close(year: int) -> Set[date]:
    if year not in _early_close_cache:
        _early_close_cache[year] = get_us_early_close_dates(year)
    return _early_close_cache[year]


class HolidayGuard:
    """Rejects signals for instruments whose exchange is closed today.

    Currently supports US equity index holidays. Forex and metals trade
    nearly 24/5 and are not affected (broker handles weekends).
    """

    def __init__(
        self,
        block_early_close: bool = False,
        early_close_after_utc_hour: int = 18,
    ):
        """
        Args:
            block_early_close: If True, also block trades on early-close days
                after the specified UTC hour.
            early_close_after_utc_hour: UTC hour after which to block on
                early-close days (default 18 = 1 PM ET).
        """
        self.block_early_close = block_early_close
        self.early_close_after_utc_hour = early_close_after_utc_hour

    def check(self, payload: dict) -> Tuple[bool, str]:
        """Check if the signal should be blocked due to a market holiday.

        Args:
            payload: Signal payload with 'symbol' key.

        Returns:
            (passed, reason) — passed=True means signal is OK.
        """
        symbol = payload.get("symbol", "")

        # Only check US index instruments
        if not is_us_index(symbol):
            return True, ""

        now_utc = datetime.now(timezone.utc)
        today = now_utc.date()

        # Weekend check (Saturday=5, Sunday=6)
        if today.weekday() >= 5:
            return False, f"US_MARKET_WEEKEND: {symbol} market closed (weekend)"

        # Full holiday check
        holidays = _get_holidays(today.year)
        if today in holidays:
            return False, f"US_MARKET_HOLIDAY: {symbol} market closed today ({today.isoformat()})"

        # Early close check (optional)
        if self.block_early_close:
            early_close = _get_early_close(today.year)
            if today in early_close and now_utc.hour >= self.early_close_after_utc_hour:
                return (
                    False,
                    f"US_MARKET_EARLY_CLOSE: {symbol} market closed early today "
                    f"(after {self.early_close_after_utc_hour}:00 UTC)",
                )

        return True, ""
