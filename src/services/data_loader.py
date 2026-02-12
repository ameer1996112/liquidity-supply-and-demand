"""
MetaApi Historical Data Loader

Fetches OHLC candles from MetaApi REST API and converts to pandas DataFrame
for backtesting.py consumption.

Usage:
    from src.services.data_loader import MetaApiDataLoader

    loader = MetaApiDataLoader(token="your-token", account_id="your-account")
    df = loader.fetch_candles("EURUSD", "2024-01-01", "2024-12-31", "5m")
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import pandas as pd
import requests

logger = logging.getLogger(__name__)


class MetaApiDataLoader:
    """
    Historical candle data loader using MetaApi REST API.

    Supports multiple timeframes: 1m, 5m, 15m, 30m, 1h, 4h, 1d
    Returns standardized pandas DataFrame with OHLC + Volume.
    """

    # Timeframe mapping: human-readable -> MetaApi format
    TIMEFRAME_MAP = {
        "1m": "1m",
        "5m": "5m",
        "15m": "15m",
        "30m": "30m",
        "1h": "1h",
        "4h": "4h",
        "1d": "1d",
        "M5": "5m",  # TradingView format
        "M15": "15m",
        "H1": "1h",
        "H4": "4h",
        "D1": "1d",
    }

    def __init__(
        self,
        token: str,
        account_id: str,
        region: str = "new-york",
    ) -> None:
        """
        Initialize MetaApi data loader.

        Args:
            token: MetaApi auth token
            account_id: MetaApi account ID
            region: MetaApi region (default: "new-york")
        """
        if not token or not account_id:
            raise ValueError("MetaApiDataLoader requires non-empty token and account_id")

        self.token = token.strip()
        self.account_id = account_id.strip()
        self.base_url = f"https://mt-market-data-client-api-v1.{region}.agiliumtrade.ai"

        logger.info(
            "MetaApiDataLoader initialized: account=%s region=%s base_url=%s",
            self.account_id,
            region,
            self.base_url,
        )

    def _headers(self) -> Dict[str, str]:
        """Build HTTP headers for MetaApi requests."""
        return {
            "auth-token": self.token,
            "Content-Type": "application/json",
        }

    def _align_to_candle_boundary(self, dt: datetime, timeframe: str, is_end: bool = True) -> datetime:
        """
        Align datetime to a valid candle boundary. MetaApi rejects times like 23:59:59.

        For is_end=True (e.g. date-only "2024-01-31"): use last candle of that day.
        """
        tf = self._normalize_timeframe(timeframe)
        dt = dt.replace(second=0, microsecond=0)
        if is_end and dt.hour == 0 and dt.minute == 0:
            # Date-only: use last candle of day
            if tf == "1m":
                return dt.replace(hour=23, minute=59)
            if tf == "5m":
                return dt.replace(hour=23, minute=55)
            if tf == "15m":
                return dt.replace(hour=23, minute=45)
            if tf == "30m":
                return dt.replace(hour=23, minute=30)
            if tf == "1h":
                return dt.replace(hour=23, minute=0)
            if tf == "4h":
                return dt.replace(hour=20, minute=0)
            if tf == "1d":
                return dt  # 00:00 is the open of that day's candle
        if tf == "5m":
            m = (dt.minute // 5) * 5
            return dt.replace(minute=m)
        if tf == "15m":
            m = (dt.minute // 15) * 15
            return dt.replace(minute=m)
        if tf == "30m":
            m = 30 if dt.minute >= 30 else 0
            return dt.replace(minute=m)
        if tf == "4h":
            h = (dt.hour // 4) * 4
            return dt.replace(hour=h, minute=0)
        return dt

    def _normalize_timeframe(self, timeframe: str) -> str:
        """
        Convert timeframe to MetaApi format.

        Args:
            timeframe: Human-readable timeframe (e.g., "5m", "M5", "1h", "H1")

        Returns:
            MetaApi timeframe string (e.g., "5m", "1h")

        Raises:
            ValueError: If timeframe is not supported
        """
        tf = timeframe.strip()
        if tf in self.TIMEFRAME_MAP:
            return self.TIMEFRAME_MAP[tf]

        # Try case-insensitive match
        for key, value in self.TIMEFRAME_MAP.items():
            if key.lower() == tf.lower():
                return value

        raise ValueError(
            f"Unsupported timeframe '{timeframe}'. "
            f"Supported: {', '.join(self.TIMEFRAME_MAP.keys())}"
        )

    def _parse_timestamp(self, ts: str) -> datetime:
        """
        Parse ISO 8601 timestamp to datetime (UTC).

        Args:
            ts: ISO 8601 timestamp string (e.g., "2024-01-01T00:00:00.000Z")

        Returns:
            datetime object in UTC timezone
        """
        # Handle both with and without milliseconds
        for fmt in ("%Y-%m-%dT%H:%M:%S.%fZ", "%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%d"):
            try:
                dt = datetime.strptime(ts.strip(), fmt)
                return dt.replace(tzinfo=timezone.utc)
            except ValueError:
                continue

        # Fallback: parse ISO format
        try:
            dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
            return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
        except Exception as exc:
            logger.error("Failed to parse timestamp '%s': %s", ts, exc)
            raise ValueError(f"Invalid timestamp format: {ts}") from exc

    def fetch_candles(
        self,
        symbol: str,
        start_time: str | datetime,
        end_time: str | datetime | None = None,
        timeframe: str = "5m",
        limit: int = 10000,
    ) -> pd.DataFrame:
        """
        Fetch historical candles from MetaApi.

        Args:
            symbol: Trading symbol (e.g., "EURUSD", "XAUUSD")
            start_time: Start time (ISO 8601 string or datetime)
            end_time: End time (ISO 8601 string, datetime, or None for now)
            timeframe: Candle timeframe (e.g., "5m", "M5", "1h", "H1")
            limit: Maximum number of candles to fetch (default: 10000)

        Returns:
            pandas DataFrame with columns:
                - Open, High, Low, Close, Volume (float)
                - Index: DatetimeIndex (UTC)

        Example:
            >>> loader = MetaApiDataLoader(token="...", account_id="...")
            >>> df = loader.fetch_candles("EURUSD", "2024-01-01", "2024-01-31", "5m")
            >>> print(df.head())
                                    Open     High      Low    Close  Volume
            2024-01-01 00:00:00  1.10450  1.10480  1.10420  1.10455   1200
        """
        # Normalize inputs
        tf = self._normalize_timeframe(timeframe)

        # Convert start_time to ISO 8601 string (MetaApi format: YYYY-MM-DDTHH:MM:SSZ - no milliseconds!)
        if isinstance(start_time, datetime):
            start_str = start_time.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        else:
            start_str = start_time.strip()
            # Convert simple date to full timestamp
            if not "T" in start_str:
                # Simple date like "2024-01-01" → "2024-01-01T00:00:00Z"
                try:
                    dt = datetime.strptime(start_str, "%Y-%m-%d")
                    start_str = dt.strftime("%Y-%m-%dT%H:%M:%SZ")
                except ValueError:
                    pass  # Already in correct format or will fail later
            # Remove milliseconds if present (.000Z, .999Z, etc.)
            start_str = start_str.replace(".000Z", "Z").replace(".999Z", "Z")
            if ".Z" in start_str:
                start_str = start_str.split(".")[0] + "Z"

        # MetaApi candles API loads BACKWARDS from startTime (no endTime parameter).
        # Use our end_time as API startTime; align to candle boundary.
        if end_time is None:
            api_start_dt = datetime.now(timezone.utc)
        elif isinstance(end_time, datetime):
            api_start_dt = end_time.astimezone(timezone.utc)
        else:
            end_str = end_time.strip()
            if "T" in end_str:
                try:
                    api_start_dt = datetime.fromisoformat(end_str.replace("Z", "+00:00"))
                except ValueError:
                    api_start_dt = datetime.now(timezone.utc)
            else:
                try:
                    api_start_dt = datetime.strptime(end_str, "%Y-%m-%d").replace(tzinfo=timezone.utc)
                except ValueError:
                    api_start_dt = datetime.now(timezone.utc)

        # Align to last valid candle of day for timeframe (MetaApi rejects 23:59:59)
        api_start_dt = self._align_to_candle_boundary(api_start_dt, tf, is_end=True)
        api_start_str = api_start_dt.strftime("%Y-%m-%dT%H:%M:%SZ")

        # Build API URL
        # MetaApi only accepts startTime + limit (candles load backwards from startTime)
        url = (
            f"{self.base_url}/users/current/accounts/{self.account_id}/"
            f"historical-market-data/symbols/{symbol}/timeframes/{tf}/candles"
        )

        max_per_request = 1000  # MetaApi max per request
        all_candles: List[Dict[str, Any]] = []
        current_start = api_start_str
        target_limit = min(limit, 50000)  # Cap total to avoid excessive requests

        while len(all_candles) < target_limit:
            params = {
                "startTime": current_start,
                "limit": max_per_request,
            }

            logger.info(
                "Fetching candles: symbol=%s timeframe=%s startTime=%s limit=%s (loads backwards)",
                symbol,
                tf,
                current_start,
                params["limit"],
            )

            try:
                response = requests.get(
                    url,
                    headers=self._headers(),
                    params=params,
                    timeout=30,
                )
                response.raise_for_status()
            except requests.exceptions.RequestException as exc:
                logger.error("MetaApi candles request failed: %s", exc)
                if hasattr(exc, "response") and exc.response is not None:
                    logger.error("Response body: %s", exc.response.text[:500])
                raise RuntimeError(f"Failed to fetch candles from MetaApi: {exc}") from exc

            try:
                candles_raw = response.json()
            except ValueError as exc:
                logger.error("Invalid JSON response: %s", response.text[:500])
                raise RuntimeError("MetaApi returned invalid JSON") from exc

            if not isinstance(candles_raw, list):
                logger.error("Expected list of candles, got: %s", type(candles_raw).__name__)
                raise RuntimeError(f"Unexpected response format: {type(candles_raw).__name__}")

            if not candles_raw:
                break

            logger.info("Received %d candles from MetaApi", len(candles_raw))
            all_candles.extend(candles_raw)

            if len(candles_raw) < max_per_request:
                break

            # Next batch: start from oldest candle in this batch (load backwards)
            oldest = min(c["time"] for c in candles_raw)
            current_start = oldest.replace(".000Z", "Z").replace(".999Z", "Z")
            if ".Z" in current_start and "." in current_start.split("Z")[0]:
                current_start = current_start.split(".")[0] + "Z"

            # Check if we've passed start_time
            if start_str:
                try:
                    start_dt = self._parse_timestamp(start_str)
                    oldest_dt = self._parse_timestamp(oldest)
                    if oldest_dt <= start_dt:
                        break
                except (ValueError, TypeError):
                    pass

        if not all_candles:
            logger.warning("No candles returned for %s %s", symbol, tf)
            return pd.DataFrame(columns=["Open", "High", "Low", "Close", "Volume"])

        # Convert to DataFrame
        df = self._candles_to_dataframe(all_candles)

        # Filter to requested start_time (API returns backwards; we may have extra)
        if start_str and not df.empty:
            try:
                start_dt = self._parse_timestamp(start_str)
                df = df[df.index >= start_dt]
            except (ValueError, TypeError):
                pass

        return df

    def _candles_to_dataframe(self, candles: List[Dict[str, Any]]) -> pd.DataFrame:
        """
        Convert MetaApi candles JSON to pandas DataFrame.

        Args:
            candles: List of candle dicts from MetaApi:
                [
                    {
                        "time": "2024-01-01T00:00:00.000Z",
                        "open": 1.10450,
                        "high": 1.10480,
                        "low": 1.10420,
                        "close": 1.10455,
                        "tickVolume": 1200,
                        "realVolume": 0  # Optional
                    },
                    ...
                ]

        Returns:
            pandas DataFrame with DatetimeIndex and OHLCV columns
        """
        records = []
        for candle in candles:
            try:
                timestamp = self._parse_timestamp(candle["time"])
                records.append(
                    {
                        "timestamp": timestamp,
                        "Open": float(candle["open"]),
                        "High": float(candle["high"]),
                        "Low": float(candle["low"]),
                        "Close": float(candle["close"]),
                        "Volume": float(candle.get("tickVolume") or candle.get("realVolume") or 0),
                    }
                )
            except (KeyError, ValueError, TypeError) as exc:
                logger.warning("Skipping invalid candle: %s (error: %s)", candle, exc)
                continue

        if not records:
            logger.warning("No valid candles found in response")
            return pd.DataFrame(columns=["Open", "High", "Low", "Close", "Volume"])

        df = pd.DataFrame(records)
        df.set_index("timestamp", inplace=True)
        df.sort_index(inplace=True)

        # Remove duplicates (same timestamp)
        df = df[~df.index.duplicated(keep="first")]

        logger.info(
            "DataFrame created: %d rows, date range: %s to %s",
            len(df),
            df.index[0] if len(df) > 0 else "N/A",
            df.index[-1] if len(df) > 0 else "N/A",
        )

        return df

    def get_latest_price(self, symbol: str) -> Dict[str, float]:
        """
        Fetch current bid/ask prices for a symbol.

        Args:
            symbol: Trading symbol (e.g., "EURUSD")

        Returns:
            Dict with keys: bid, ask, time

        Example:
            >>> loader.get_latest_price("EURUSD")
            {'bid': 1.10450, 'ask': 1.10455, 'time': '2024-01-15T12:34:56.789Z'}
        """
        url = (
            f"{self.base_url}/users/current/accounts/{self.account_id}/"
            f"symbols/{symbol}/current-price"
        )

        try:
            response = requests.get(
                url,
                headers=self._headers(),
                timeout=10,
            )
            response.raise_for_status()
            data = response.json()

            return {
                "bid": float(data.get("bid", 0.0)),
                "ask": float(data.get("ask", 0.0)),
                "time": data.get("time", ""),
            }
        except Exception as exc:
            logger.error("Failed to fetch latest price for %s: %s", symbol, exc)
            raise RuntimeError(f"Failed to fetch latest price: {exc}") from exc
