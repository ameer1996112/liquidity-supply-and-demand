#!/usr/bin/env python3
"""
Fetch historical candle data from MetaAPI for any symbol and timeframe.

Usage:
    python scripts/fetch_historical_data.py --symbol EURUSD --timeframes 1h,4h,1d --start 2024-01-01 --end 2024-02-11
    python scripts/fetch_historical_data.py --symbol XAUUSD,EURUSD --timeframes 1m,5m,15m,1h,4h --start 2024-01-01 --end 2024-02-11

Features:
- Fetch data for multiple symbols and timeframes
- Specify date range (from/to dates)
- Save to CSV files organized by symbol/timeframe
- Automatic retry on failures
- Progress indicators

Environment Variables Required:
- META_API_TOKEN_VANTAGE: Your MetaAPI access token
- META_API_ACCOUNT_ID_VANTAGE: Your MetaAPI account ID
"""

import argparse
import logging
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas as pd
import requests
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("fetch_historical_data.log")
    ]
)
logger = logging.getLogger(__name__)


class MetaAPIHistoricalFetcher:
    """Fetch historical candle data from MetaAPI."""

    # MetaAPI timeframe mappings (MetaAPI format)
    TIMEFRAME_MAP = {
        "1m": "1m",
        "5m": "5m",
        "15m": "15m",
        "30m": "30m",
        "1h": "1h",
        "4h": "4h",
        "1d": "1d",
        "1w": "1w",
        "1M": "1mn",  # MetaAPI uses "1mn" for 1 month
    }

    def __init__(
        self,
        token: str,
        account_id: str,
        region: str = "new-york"
    ):
        """
        Initialize MetaAPI client.

        Args:
            token: MetaAPI access token
            account_id: MetaAPI account ID
            region: MetaAPI region (default: new-york)
        """
        self.token = token.strip()
        self.account_id = account_id.strip()
        self.region = region.strip()
        # Historical data uses a different base URL (market-data-client)
        self.base_url = f"https://mt-market-data-client-api-v1.{self.region}.agiliumtrade.ai"

        if not self.token or not self.account_id:
            raise ValueError("Token and account_id are required")

        logger.info(f"MetaAPI initialized: region={region}, account_id={account_id[:8]}...")

    def _headers(self) -> Dict[str, str]:
        """Build request headers."""
        return {
            "auth-token": self.token,
            "Content-Type": "application/json",
        }

    def _validate_timeframe(self, timeframe: str) -> str:
        """
        Validate and convert timeframe to MetaAPI format.

        Args:
            timeframe: Timeframe string (e.g., "1h", "4h", "1d")

        Returns:
            MetaAPI-compatible timeframe string

        Raises:
            ValueError: If timeframe is invalid
        """
        tf_lower = timeframe.lower()
        if tf_lower not in self.TIMEFRAME_MAP:
            valid_tfs = ", ".join(self.TIMEFRAME_MAP.keys())
            raise ValueError(
                f"Invalid timeframe '{timeframe}'. "
                f"Valid options: {valid_tfs}"
            )
        return self.TIMEFRAME_MAP[tf_lower]

    def _calculate_candles_needed(
        self,
        timeframe: str,
        start_time: datetime,
        end_time: datetime
    ) -> int:
        """
        Calculate approximate number of candles needed for date range.

        Args:
            timeframe: Timeframe string (e.g., "1h", "4h", "1d")
            start_time: Start datetime
            end_time: End datetime

        Returns:
            Approximate number of candles
        """
        delta = end_time - start_time
        hours = delta.total_seconds() / 3600

        # Candles per hour for each timeframe
        candles_per_hour = {
            "1m": 60,
            "5m": 12,
            "15m": 4,
            "30m": 2,
            "1h": 1,
            "4h": 0.25,
            "1d": 1/24,
            "1w": 1/168,
            "1M": 1/720,  # Approximate
        }

        tf_lower = timeframe.lower()
        if tf_lower not in candles_per_hour:
            # Default: assume 1h
            return int(hours)

        candles = int(hours * candles_per_hour[tf_lower])
        # Add 10% buffer for weekends/gaps
        return int(candles * 1.1)

    def fetch_candles(
        self,
        symbol: str,
        timeframe: str,
        start_time: datetime,
        end_time: datetime,
        max_retries: int = 3
    ) -> Optional[pd.DataFrame]:
        """
        Fetch historical candles for a symbol and timeframe.

        Note: MetaAPI loads candles BACKWARDS from startTime.
        This method handles pagination for large date ranges.

        Args:
            symbol: Trading symbol (e.g., "EURUSD", "XAUUSD")
            timeframe: Timeframe (e.g., "1h", "4h", "1d")
            start_time: Start datetime (UTC) - earliest time wanted
            end_time: End datetime (UTC) - latest time wanted
            max_retries: Maximum number of retries on failure

        Returns:
            DataFrame with columns: time, open, high, low, close, volume
            Returns None on failure after retries
        """
        # Validate timeframe
        meta_timeframe = self._validate_timeframe(timeframe)

        # Calculate approximate candles needed
        candles_needed = self._calculate_candles_needed(timeframe, start_time, end_time)

        logger.info(
            f"Fetching {symbol} {timeframe} from {start_time.date()} to {end_time.date()} "
            f"(~{candles_needed} candles)..."
        )

        # MetaAPI loads backwards, so we start from end_time and load backwards
        all_candles = []
        current_start_time = end_time
        max_limit = 1000  # MetaAPI max limit per request
        remaining_candles = candles_needed

        # Pagination loop - fetch in chunks of 1000
        page = 0
        while remaining_candles > 0:
            page += 1
            limit = min(remaining_candles, max_limit)

            # Format timestamp (ISO 8601)
            start_iso = current_start_time.strftime("%Y-%m-%dT%H:%M:%S.000Z")

            # Build URL
            url = (
                f"{self.base_url}/users/current/accounts/{self.account_id}/"
                f"historical-market-data/symbols/{symbol}/timeframes/{meta_timeframe}/candles"
            )
            params = {
                "startTime": start_iso,
                "limit": limit,
            }

            logger.info(f"  Page {page}: Fetching up to {limit} candles from {start_iso}...")

            # Retry logic for this page
            page_candles = None
            for attempt in range(max_retries):
                try:
                    response = requests.get(
                        url,
                        headers=self._headers(),
                        params=params,
                        timeout=60  # Increased timeout for historical data
                    )

                    if response.status_code == 200:
                        data = response.json()

                        # MetaAPI returns list of candles or dict with "candles" key
                        if isinstance(data, dict):
                            page_candles = data.get("candles", [])
                        else:
                            page_candles = data if isinstance(data, list) else []

                        logger.info(f"  ✅ Fetched {len(page_candles)} candles")
                        break

                    elif response.status_code == 429:
                        wait_time = 60
                        logger.warning(f"Rate limited (429). Waiting {wait_time}s before retry...")
                        time.sleep(wait_time)
                        continue

                    elif response.status_code >= 500:
                        wait_time = 2 ** attempt
                        logger.warning(
                            f"Server error {response.status_code}. "
                            f"Retry {attempt + 1}/{max_retries} in {wait_time}s..."
                        )
                        time.sleep(wait_time)
                        continue

                    else:
                        logger.error(
                            f"Failed to fetch page {page}: "
                            f"HTTP {response.status_code} - {response.text[:200]}"
                        )
                        break

                except requests.exceptions.Timeout:
                    logger.warning(f"Timeout on attempt {attempt + 1}/{max_retries}")
                    if attempt < max_retries - 1:
                        time.sleep(2 ** attempt)
                        continue
                    break

                except Exception as e:
                    logger.error(f"Error fetching page {page}: {e}")
                    if attempt < max_retries - 1:
                        time.sleep(2)
                        continue
                    break

            # If page failed, return what we have so far
            if page_candles is None:
                logger.warning(f"Page {page} failed after {max_retries} retries")
                break

            # If no candles returned, we've reached the end
            if not page_candles:
                logger.info(f"No more candles available (reached end of data)")
                break

            # Add candles to collection
            all_candles.extend(page_candles)

            # Update current_start_time to the oldest candle time for next page
            oldest_candle_time = min(c.get("time") or c.get("brokerTime") for c in page_candles)
            current_start_time = pd.to_datetime(oldest_candle_time)

            # Check if we've gone past start_time
            if current_start_time <= start_time:
                logger.info(f"Reached start_time, stopping pagination")
                break

            # Update remaining candles
            remaining_candles -= len(page_candles)

            # Small delay between pages
            time.sleep(0.5)

        # Check if we got any candles
        if not all_candles:
            logger.warning(f"No data returned for {symbol} {timeframe}")
            return None

        # Convert to DataFrame
        df = pd.DataFrame(all_candles)

        # Ensure we have a time column (prefer 'time', fallback to 'brokerTime')
        if "time" not in df.columns and "brokerTime" in df.columns:
            df["time"] = df["brokerTime"]

        # Ensure we have a volume column (prefer 'volume', fallback to 'tickVolume')
        if "volume" not in df.columns and "tickVolume" in df.columns:
            df["volume"] = df["tickVolume"]

        # Ensure required columns exist
        required_cols = ["time", "open", "high", "low", "close", "volume"]
        for col in required_cols:
            if col not in df.columns:
                logger.error(f"Missing column '{col}' in response")
                return None

        # Select and reorder columns
        df = df[required_cols]

        # Convert time to datetime
        df["time"] = pd.to_datetime(df["time"])

        # Filter to requested date range
        df = df[(df["time"] >= start_time) & (df["time"] <= end_time)]

        # Remove duplicates and sort
        df = df.drop_duplicates(subset=["time"]).sort_values("time").reset_index(drop=True)

        logger.info(f"✅ Total fetched: {len(df)} candles for {symbol} {timeframe}")
        return df

    def save_to_csv(
        self,
        df: pd.DataFrame,
        symbol: str,
        timeframe: str,
        output_dir: str = "data/historical"
    ) -> Optional[str]:
        """
        Save DataFrame to CSV file.

        Args:
            df: DataFrame with OHLCV data
            symbol: Trading symbol
            timeframe: Timeframe
            output_dir: Output directory (default: data/historical)

        Returns:
            Path to saved file, or None on failure
        """
        try:
            # Create output directory structure: data/historical/{symbol}/
            output_path = Path(output_dir) / symbol
            output_path.mkdir(parents=True, exist_ok=True)

            # Filename: SYMBOL_TIMEFRAME_START_END.csv
            start_date = df["time"].min().strftime("%Y%m%d")
            end_date = df["time"].max().strftime("%Y%m%d")
            filename = f"{symbol}_{timeframe}_{start_date}_{end_date}.csv"
            filepath = output_path / filename

            # Save to CSV
            df.to_csv(filepath, index=False)
            logger.info(f"💾 Saved to: {filepath}")

            return str(filepath)

        except Exception as e:
            logger.error(f"Error saving {symbol} {timeframe} to CSV: {e}")
            return None


def parse_args():
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Fetch historical data from MetaAPI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Single symbol, single timeframe
  python scripts/fetch_historical_data.py --symbol EURUSD --timeframes 1h --start 2024-01-01 --end 2024-02-11

  # Single symbol, multiple timeframes
  python scripts/fetch_historical_data.py --symbol XAUUSD --timeframes 1m,5m,15m,1h,4h --start 2024-01-01 --end 2024-02-11

  # Multiple symbols, multiple timeframes
  python scripts/fetch_historical_data.py --symbol EURUSD,XAUUSD,GBPUSD --timeframes 1h,4h,1d --start 2023-01-01 --end 2024-02-11

  # Custom output directory
  python scripts/fetch_historical_data.py --symbol EURUSD --timeframes 1h --start 2024-01-01 --end 2024-02-11 --output data/backtest
        """
    )

    parser.add_argument(
        "--symbol",
        type=str,
        required=True,
        help="Trading symbol(s), comma-separated (e.g., EURUSD,XAUUSD,GBPUSD)"
    )

    parser.add_argument(
        "--timeframes",
        type=str,
        required=True,
        help="Timeframe(s), comma-separated (e.g., 1m,5m,15m,1h,4h,1d). Max 5 timeframes."
    )

    parser.add_argument(
        "--start",
        type=str,
        required=True,
        help="Start date (YYYY-MM-DD or YYYY-MM-DD HH:MM:SS)"
    )

    parser.add_argument(
        "--end",
        type=str,
        required=True,
        help="End date (YYYY-MM-DD or YYYY-MM-DD HH:MM:SS)"
    )

    parser.add_argument(
        "--output",
        type=str,
        default="data/historical",
        help="Output directory (default: data/historical)"
    )

    parser.add_argument(
        "--region",
        type=str,
        default="new-york",
        help="MetaAPI region (default: new-york)"
    )

    return parser.parse_args()


def parse_datetime(date_str: str) -> datetime:
    """
    Parse date string to datetime.

    Supports formats:
    - YYYY-MM-DD
    - YYYY-MM-DD HH:MM:SS

    Args:
        date_str: Date string

    Returns:
        Datetime object (UTC)
    """
    # Try with time first
    for fmt in ["%Y-%m-%d %H:%M:%S", "%Y-%m-%d"]:
        try:
            dt = datetime.strptime(date_str, fmt)
            # Make timezone-aware (UTC)
            return dt.replace(tzinfo=timezone.utc)
        except ValueError:
            continue

    raise ValueError(f"Invalid date format: {date_str}. Use YYYY-MM-DD or YYYY-MM-DD HH:MM:SS")


def main():
    """Main entry point."""
    args = parse_args()

    # Get environment variables
    token = os.getenv("META_API_TOKEN_VANTAGE")
    account_id = os.getenv("META_API_ACCOUNT_ID_VANTAGE")

    if not token or not account_id:
        logger.error(
            "Missing required environment variables:\n"
            "  - META_API_TOKEN_VANTAGE\n"
            "  - META_API_ACCOUNT_ID_VANTAGE\n"
            "Please add them to your .env file."
        )
        sys.exit(1)

    # Parse symbols and timeframes
    symbols = [s.strip() for s in args.symbol.split(",")]
    timeframes = [tf.strip() for tf in args.timeframes.split(",")]

    if len(timeframes) > 5:
        logger.error("Maximum 5 timeframes allowed. Please reduce the number of timeframes.")
        sys.exit(1)

    # Parse dates
    try:
        start_time = parse_datetime(args.start)
        end_time = parse_datetime(args.end)
    except ValueError as e:
        logger.error(str(e))
        sys.exit(1)

    if start_time >= end_time:
        logger.error("Start date must be before end date")
        sys.exit(1)

    # Initialize fetcher
    logger.info("=" * 80)
    logger.info("MetaAPI Historical Data Fetcher")
    logger.info("=" * 80)
    logger.info(f"Symbols: {', '.join(symbols)}")
    logger.info(f"Timeframes: {', '.join(timeframes)}")
    logger.info(f"Date Range: {start_time.date()} to {end_time.date()}")
    logger.info(f"Output Dir: {args.output}")
    logger.info("=" * 80)

    try:
        fetcher = MetaAPIHistoricalFetcher(
            token=token,
            account_id=account_id,
            region=args.region
        )
    except ValueError as e:
        logger.error(f"Failed to initialize fetcher: {e}")
        sys.exit(1)

    # Fetch data for all symbols and timeframes
    total_tasks = len(symbols) * len(timeframes)
    completed_tasks = 0
    failed_tasks = 0
    saved_files = []

    for symbol in symbols:
        for timeframe in timeframes:
            completed_tasks += 1
            logger.info(f"\n[{completed_tasks}/{total_tasks}] Processing {symbol} {timeframe}...")

            # Fetch candles
            df = fetcher.fetch_candles(
                symbol=symbol,
                timeframe=timeframe,
                start_time=start_time,
                end_time=end_time
            )

            if df is not None and not df.empty:
                # Save to CSV
                filepath = fetcher.save_to_csv(
                    df=df,
                    symbol=symbol,
                    timeframe=timeframe,
                    output_dir=args.output
                )

                if filepath:
                    saved_files.append(filepath)
                else:
                    failed_tasks += 1
            else:
                failed_tasks += 1

            # Rate limiting: wait between requests
            if completed_tasks < total_tasks:
                time.sleep(1)  # 1 second between requests

    # Summary
    logger.info("\n" + "=" * 80)
    logger.info("SUMMARY")
    logger.info("=" * 80)
    logger.info(f"Total tasks: {total_tasks}")
    logger.info(f"Successful: {len(saved_files)}")
    logger.info(f"Failed: {failed_tasks}")

    if saved_files:
        logger.info("\nSaved files:")
        for filepath in saved_files:
            logger.info(f"  - {filepath}")

    logger.info("=" * 80)
    logger.info("✅ Done!")


if __name__ == "__main__":
    main()
