
import requests
from datetime import datetime, timedelta
import logging
import pytz
import re
import time

# Configure Logging
logger = logging.getLogger(__name__)

class NewsFilter:
    def __init__(self, block_minutes_before=30, block_minutes_after=30):
        self.block_minutes_before = block_minutes_before
        self.block_minutes_after = block_minutes_after
        self.cache = {}
        self.last_fetch = 0
        self.CACHE_DURATION = 3600  # Refresh calendar every hour

        # Mapping of common currency pairs to their base/quote currencies
        # Events usually affect "USD", "EUR", "GBP", etc.
        self.major_currencies = ["USD", "EUR", "GBP", "JPY", "AUD", "CAD", "CHF", "NZD"]

    def _fetch_calendar(self):
        """
        Fetches the calendar data.
        Since scraping ForexFactory can be tricky with bot protection,
        we initially try a direct approach, but if that fails, we return an empty list
        to avoid blocking trading erroneously (fail-open).
        """
        now = time.time()
        if now - self.last_fetch < self.CACHE_DURATION and self.cache:
            return self.cache

        url = "https://nfs.faireconomy.media/ff_calendar_thisweek.json"
        # This is the JSON endpoint ForexFactory widgets often use, much cleaner than scraping HTML.

        try:
            logger.info("Fetching news calendar...")
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
            }
            response = requests.get(url, headers=headers, timeout=10)
            response.raise_for_status()

            data = response.json()
            # Structure of ff_calendar_thisweek.json:
            # [{"title": "Unemployment Rate", "country": "USD", "date": "2024-01-01T08:30:00-04:00", "impact": "High", "forecast": "", "previous": ""}, ...]

            self.cache = data
            self.last_fetch = now
            logger.info(f"News calendar updated. {len(data)} events found.")
            return self.cache

        except Exception as e:
            logger.error(f"Failed to fetch news calendar: {e}")
            # If fetch fails, keep old cache if available, else empty
            return self.cache if self.cache else []

    def is_news_imminent(self, symbol: str) -> bool:
        """
        Checks if high-impact news is imminent for the given symbol.
        Returns True if trading should be BLOCKED.
        """
        try:
            events = self._fetch_calendar()
            if not events:
                return False  # Fail open: if no data, allow trading

            # 1. Identify relevant currencies from the symbol (e.g. "EURUSD" -> ["EUR", "USD"])
            relevant_currencies = []
            symbol = symbol.upper()

            # Gold
            if "XAU" in symbol or "GOLD" in symbol:
                relevant_currencies.append("USD") # USD news affects Gold
            # Indices
            elif "US30" in symbol or "NAS100" in symbol or "SPX" in symbol:
                relevant_currencies.append("USD")
            # Forex Pairs
            else:
                for curr in self.major_currencies:
                    if curr in symbol:
                        relevant_currencies.append(curr)

            # If no currencies matched (e.g. BTC), maybe default to USD or None
            if not relevant_currencies:
                relevant_currencies = ["USD"] # Default to USD for unknown assets

            # 2. Check time
            # Parse current UTC time
            now_utc = datetime.now(pytz.utc)

            for event in events:
                # Filter by Impact: "High" or maybe "Medium" if desired.
                # The JSON often uses "High", "Medium", "Low" strings.
                impact = event.get('impact', 'Low')
                if impact != 'High':
                    continue

                # Filter by Currency
                country = event.get('country', '') # e.g., "USD"
                if country not in relevant_currencies:
                    continue

                # Parse Event Time
                # Format is usually ISO 8601: "2024-01-01T08:30:00-04:00"
                event_date_str = event.get('date', '')
                try:
                    # Remove the colon in timezone offset for older Python versions if needed,
                    # but dateutil or modern datetime handles it usually.
                    # Simple fix for +00:00 vs +0000 compatible with %z
                    if ":" == event_date_str[-3]:
                        event_date_str = event_date_str[:-3] + event_date_str[-2:]

                    event_time = datetime.strptime(event_date_str, "%Y-%m-%dT%H:%M:%S%z")
                    # Convert to UTC to match 'now_utc'
                    event_time_utc = event_time.astimezone(pytz.utc)

                except ValueError:
                    continue

                # 3. Check Range
                # Block = [Event - Pre_Wait] to [Event + Post_Wait]
                lower_bound = event_time_utc - timedelta(minutes=self.block_minutes_before)
                upper_bound = event_time_utc + timedelta(minutes=self.block_minutes_after)

                if lower_bound <= now_utc <= upper_bound:
                    logger.warning(f"NEWS BLOCK: High impact event '{event.get('title')}' for {country} at {event_time_utc} is active.")
                    return True

            return False

        except Exception as e:
            logger.error(f"Error checking news filter: {e}")
            return False

# Quick test if run directly
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    nf = NewsFilter()
    print("Is USD news imminent?", nf.is_news_imminent("EURUSD"))
