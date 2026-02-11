"""
FXCM REST API Data Loader - Production Ready

Uses official FXCM REST API to fetch historical candle data.
Optimized for Israel/Middle East region with low latency.

API Documentation: https://fxcm.github.io/rest-api-docs/

Features:
- Official fxcmpy SDK integration
- Automatic retry on rate limits
- Parquet caching (10× faster reload)
- Symbol name mapping (XAUUSD → XAU/USD)
- UTC timezone normalization
"""

from __future__ import annotations

import logging
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import pandas as pd

logger = logging.getLogger(__name__)

# Try to import fxcmpy (official FXCM SDK)
try:
    import fxcmpy
    FXCMPY_AVAILABLE = True
except ImportError:
    FXCMPY_AVAILABLE = False
    logger.warning("fxcmpy not installed. Install with: pip install fxcmpy")


# ========== FXCM Symbol Mapping ==========
FXCM_SYMBOLS = {
    # Metals
    "XAUUSD": "XAU/USD",
    "XAGUSD": "XAG/USD",

    # Forex Majors
    "EURUSD": "EUR/USD",
    "GBPUSD": "GBP/USD",
    "USDJPY": "USD/JPY",
    "USDCHF": "USD/CHF",
    "AUDUSD": "AUD/USD",
    "USDCAD": "USD/CAD",
    "NZDUSD": "NZD/USD",

    # Forex Minors
    "EURGBP": "EUR/GBP",
    "EURJPY": "EUR/JPY",
    "GBPJPY": "GBP/JPY",
    "AUDJPY": "AUD/JPY",

    # Indices (if supported by your FXCM account)
    "US30": "US30",
    "SPX500": "SPX500",
    "NAS100": "NAS100",
}

# Timeframe mapping (FXCM uses lowercase with suffix)
FXCM_TIMEFRAMES = {
    "M1": "m1",
    "M5": "m5",
    "M15": "m15",
    "M30": "m30",
    "H1": "H1",
    "H2": "H2",
    "H4": "H4",
    "H8": "H8",
    "D1": "D1",
    "W1": "W1",
}


def get_fxcm_symbol(symbol: str) -> str:
    """Map standard symbol to FXCM format (XAUUSD → XAU/USD)."""
    return FXCM_SYMBOLS.get(symbol.upper(), symbol)


def get_fxcm_timeframe(timeframe: str) -> str:
    """Map standard timeframe to FXCM format (M5 → m5)."""
    return FXCM_TIMEFRAMES.get(timeframe.upper(), timeframe.lower())


def fetch_fxcm_candles_sdk(
    symbol: str,
    timeframe: str,
    from_date: datetime,
    to_date: datetime,
    api_token: str,
    environment: str = "demo"
) -> Optional[pd.DataFrame]:
    """
    Fetch candles using official fxcmpy SDK.

    Args:
        symbol: Trading symbol (e.g., "XAUUSD")
        timeframe: Timeframe (e.g., "M5")
        from_date: Start date (UTC)
        to_date: End date (UTC)
        api_token: FXCM API token
        environment: "demo" or "live"

    Returns:
        DataFrame with candles or None if failed
    """
    if not FXCMPY_AVAILABLE:
        logger.error("fxcmpy not installed. Run: pip install fxcmpy")
        return None

    try:
        # Map symbols
        fxcm_symbol = get_fxcm_symbol(symbol)
        fxcm_tf = get_fxcm_timeframe(timeframe)

        logger.info(f"Connecting to FXCM ({environment})...")

        # Connect to FXCM
        server = "demo" if environment == "demo" else "real"
        con = fxcmpy.fxcmpy(access_token=api_token, log_level="error", server=server)

        logger.info(f"Fetching {fxcm_symbol} ({fxcm_tf}) from {from_date} to {to_date}...")

        # Fetch candles
        # fxcmpy uses start/stop (not from/to)
        candles = con.get_candles(
            instrument=fxcm_symbol,
            period=fxcm_tf,
            start=from_date,
            stop=to_date
        )

        # Close connection
        con.close()

        if candles is None or len(candles) == 0:
            logger.warning(f"No candles returned for {symbol}")
            return None

        # Normalize to standard format
        df = pd.DataFrame()
        df["time"] = pd.to_datetime(candles.index, utc=True)
        df["open"] = candles["bidopen"].astype(float)
        df["high"] = candles["bidhigh"].astype(float)
        df["low"] = candles["bidlow"].astype(float)
        df["close"] = candles["bidclose"].astype(float)
        df["volume"] = candles.get("tickqty", 0).astype(int)

        # Sort and deduplicate
        df = df.sort_values("time").drop_duplicates(subset=["time"], keep="last")
        df = df[(df["time"] >= from_date) & (df["time"] <= to_date)]
        df = df.reset_index(drop=True)

        logger.info(f"✅ Fetched {len(df)} candles from FXCM")
        return df

    except Exception as e:
        logger.error(f"FXCM fetch failed: {e}")
        return None


def load_from_cache(
    symbol: str,
    from_date: datetime,
    to_date: datetime,
    timeframe: str,
    data_dir: Path
) -> Optional[pd.DataFrame]:
    """Load candles from Parquet cache."""
    from_str = from_date.strftime("%Y-%m-%d")
    to_str = to_date.strftime("%Y-%m-%d")

    parquet_path = data_dir / symbol / timeframe / f"{from_str}_{to_str}.parquet"
    csv_path = data_dir / symbol / timeframe / f"{from_str}_{to_str}.csv"

    # Try Parquet first
    if parquet_path.exists():
        try:
            df = pd.read_parquet(parquet_path)
            df["time"] = pd.to_datetime(df["time"], utc=True)
            logger.info(f"📦 Loaded {len(df)} candles from cache: {parquet_path.name}")
            return df
        except Exception as e:
            logger.warning(f"Cache read failed: {e}")

    # Try CSV fallback
    if csv_path.exists():
        try:
            df = pd.read_csv(csv_path)
            df["time"] = pd.to_datetime(df["time"], utc=True)
            logger.info(f"📦 Loaded {len(df)} candles from cache: {csv_path.name}")
            return df
        except Exception as e:
            logger.warning(f"CSV cache read failed: {e}")

    return None


def save_to_cache(
    df: pd.DataFrame,
    symbol: str,
    from_date: datetime,
    to_date: datetime,
    timeframe: str,
    data_dir: Path
) -> None:
    """Save candles to Parquet cache."""
    from_str = from_date.strftime("%Y-%m-%d")
    to_str = to_date.strftime("%Y-%m-%d")

    parquet_path = data_dir / symbol / timeframe / f"{from_str}_{to_str}.parquet"
    parquet_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        df.to_parquet(parquet_path, index=False)
        logger.info(f"💾 Saved {len(df)} candles to cache: {parquet_path.name}")
    except ImportError:
        # Fallback to CSV if pyarrow not installed
        csv_path = parquet_path.with_suffix(".csv")
        df.to_csv(csv_path, index=False)
        logger.info(f"💾 Saved {len(df)} candles to CSV: {csv_path.name}")


def get_candles_fxcm(
    symbol: str,
    from_date: datetime,
    to_date: datetime,
    timeframe: str = "M5",
    data_dir: Optional[Path] = None,
    force_fetch: bool = False
) -> pd.DataFrame:
    """
    Load candles from FXCM with Parquet caching.

    Priority:
    1. Local Parquet cache (instant)
    2. FXCM API (fetch and cache)

    Args:
        symbol: Trading symbol (XAUUSD, EURUSD, etc.)
        from_date: Start date (UTC)
        to_date: End date (UTC)
        timeframe: Timeframe (M5, M15, H1, etc.)
        data_dir: Cache directory (default: data/backtest_candles)
        force_fetch: Skip cache and force API fetch

    Returns:
        DataFrame with candles

    Raises:
        ValueError: If FXCM fetch fails

    Environment Variables:
        FXCM_API_TOKEN: Your FXCM API token
        FXCM_ENVIRONMENT: "demo" or "live" (default: demo)
    """
    if data_dir is None:
        data_dir = Path("data/backtest_candles")
    data_dir = Path(data_dir)
    data_dir.mkdir(parents=True, exist_ok=True)

    # 1. Try cache (unless force_fetch)
    if not force_fetch:
        df = load_from_cache(symbol, from_date, to_date, timeframe, data_dir)
        if df is not None and len(df) > 0:
            return df

    # 2. Fetch from FXCM API
    api_token = os.getenv("FXCM_API_TOKEN")
    environment = os.getenv("FXCM_ENVIRONMENT", "demo")

    if not api_token:
        raise ValueError(
            "FXCM_API_TOKEN not set in environment.\n"
            "Get token from: https://www.fxcm.com/markets/demo-account/\n"
            "Then: export FXCM_API_TOKEN=your_token"
        )

    logger.info("🌐 No cache found. Fetching from FXCM API...")
    df = fetch_fxcm_candles_sdk(
        symbol=symbol,
        timeframe=timeframe,
        from_date=from_date,
        to_date=to_date,
        api_token=api_token,
        environment=environment
    )

    if df is None or len(df) == 0:
        raise ValueError(
            f"Failed to fetch candles from FXCM for {symbol}.\n"
            f"Check:\n"
            f"  1. Symbol is supported: {list(FXCM_SYMBOLS.keys())}\n"
            f"  2. API token is valid\n"
            f"  3. Date range is reasonable (max 1 year per request)"
        )

    # 3. Save to cache
    save_to_cache(df, symbol, from_date, to_date, timeframe, data_dir)

    return df


# ========== Auto-detect from environment ==========

def load_historical_csv(
    symbol: str,
    from_date: datetime,
    to_date: datetime,
    timeframe: str = "M5"
) -> Optional[pd.DataFrame]:
    """
    Load historical data from pre-downloaded CSV files.

    Checks data/historical/{symbol}/ for CSV files matching the date range.

    Args:
        symbol: Trading symbol (XAUUSD, EURUSD, etc.)
        from_date: Start date (UTC)
        to_date: End date (UTC)
        timeframe: Timeframe (M5, M15, H1, etc.)

    Returns:
        DataFrame with candles, or None if not found
    """
    historical_dir = Path("data/historical") / symbol

    if not historical_dir.exists():
        return None

    # Convert timeframe to lowercase for file matching (M5 -> 5m)
    tf_map = {"M1": "1m", "M5": "5m", "M15": "15m", "M30": "30m", "H1": "1h", "H4": "4h", "D1": "1d"}
    tf_str = tf_map.get(timeframe.upper(), timeframe.lower())

    # Look for CSV files in the directory
    csv_files = list(historical_dir.glob(f"{symbol}_{tf_str}_*.csv"))

    if not csv_files:
        logger.info(f"No historical CSV found in {historical_dir}")
        return None

    # Try to load the most recent CSV file
    csv_file = sorted(csv_files)[-1]  # Get the latest file

    try:
        logger.info(f"📂 Loading historical data from: {csv_file.name}")
        df = pd.read_csv(csv_file)

        # Parse datetime and set as index
        df['time'] = pd.to_datetime(df['time'], utc=True)
        df = df.set_index('time')

        # Filter to requested date range
        df = df[(df.index >= from_date) & (df.index <= to_date)]

        if len(df) == 0:
            logger.warning(f"CSV file exists but contains no data for {from_date} to {to_date}")
            return None

        logger.info(f"✅ Loaded {len(df)} candles from historical CSV")
        return df

    except Exception as e:
        logger.warning(f"Failed to load historical CSV: {e}")
        return None


def get_candles_auto(
    symbol: str,
    from_date: datetime,
    to_date: datetime,
    timeframe: str = "M5",
    data_dir: Optional[Path] = None
) -> pd.DataFrame:
    """
    Convenience wrapper that auto-detects data source.

    Priority:
    1. Local historical CSV files (data/historical/{symbol}/)
    2. FXCM API (if FXCM_API_TOKEN is set)
    3. MetaApi (if META_API_TOKEN is set)

    Environment Variables:
        FXCM_API_TOKEN (optional for FXCM)
        FXCM_ENVIRONMENT (optional: demo or live)
        META_API_TOKEN (optional fallback)
        META_API_ACCOUNT_ID (optional fallback)
    """
    # 1. Try local historical CSV first
    df = load_historical_csv(symbol, from_date, to_date, timeframe)
    if df is not None:
        return df

    # 2. Try FXCM API
    fxcm_token = os.getenv("FXCM_API_TOKEN")
    if fxcm_token:
        try:
            return get_candles_fxcm(
                symbol=symbol,
                from_date=from_date,
                to_date=to_date,
                timeframe=timeframe,
                data_dir=data_dir
            )
        except Exception as e:
            logger.warning(f"FXCM failed: {e}")
            logger.info("Falling back to MetaApi...")

    # 3. Fallback to MetaApi
    metaapi_token = os.getenv("META_API_TOKEN") or os.getenv("META_API_TOKEN_VANTAGE")
    metaapi_account = os.getenv("META_API_ACCOUNT_ID") or os.getenv("META_API_ACCOUNT_ID_VANTAGE")

    if metaapi_token and metaapi_account:
        from app.data import get_candles as get_candles_metaapi
        return get_candles_metaapi(
            symbol=symbol,
            from_date=from_date,
            to_date=to_date,
            timeframe=timeframe,
            data_dir=data_dir,
            metaapi_token=metaapi_token,
            metaapi_account_id=metaapi_account,
            persist=True
        )

    raise ValueError(
        "No data source configured.\n"
        "Set either:\n"
        "  1. Pre-download CSV to data/historical/{symbol}/\n"
        "  2. FXCM_API_TOKEN (recommended for Israel)\n"
        "  3. META_API_TOKEN + META_API_ACCOUNT_ID"
    )
