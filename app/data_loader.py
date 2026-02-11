"""
Enhanced data loader with multiple fallback strategies.

Priority order:
1. Local Parquet cache
2. Local CSV cache
3. FXCM REST API (Israel-friendly)
4. MetaApi (Vantage/MT5)

All data is converted to UTC and cached as Parquet for future runs.
"""

from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import pandas as pd
import requests

logger = logging.getLogger(__name__)

# ========== FXCM REST API Configuration ==========
FXCM_API_URL = "https://api-demo.fxcm.com"  # Demo API
FXCM_SYMBOLS = {
    "XAUUSD": "XAUUSD",
    "EURUSD": "EUR/USD",
    "GBPUSD": "GBP/USD",
    "USDJPY": "USD/JPY",
    "AUDUSD": "AUD/USD",
    "USDCAD": "USD/CAD"
}

# Timeframe mapping
FXCM_TIMEFRAMES = {
    "M1": "m1", "M5": "m5", "M15": "m15", "M30": "m30",
    "H1": "H1", "H4": "H4", "D1": "D1"
}


def load_from_parquet(path: Path) -> Optional[pd.DataFrame]:
    """Load candles from Parquet file."""
    if not path.exists():
        return None

    try:
        df = pd.read_parquet(path)
        df["time"] = pd.to_datetime(df["time"], utc=True)
        logger.info(f"Loaded {len(df)} candles from {path}")
        return df
    except Exception as e:
        logger.warning(f"Failed to load Parquet: {e}")
        return None


def load_from_csv(path: Path) -> Optional[pd.DataFrame]:
    """Load candles from CSV file."""
    if not path.exists():
        return None

    try:
        df = pd.read_csv(path)
        df["time"] = pd.to_datetime(df["time"], utc=True)
        logger.info(f"Loaded {len(df)} candles from {path}")
        return df
    except Exception as e:
        logger.warning(f"Failed to load CSV: {e}")
        return None


def fetch_fxcm_candles(
    symbol: str,
    timeframe: str,
    from_date: datetime,
    to_date: datetime,
    api_token: Optional[str] = None
) -> Optional[pd.DataFrame]:
    """
    Fetch candles from FXCM REST API.

    FXCM offers free demo API access (good for Israel region).

    Args:
        symbol: Trading symbol (e.g., "XAUUSD")
        timeframe: Timeframe (e.g., "M5")
        from_date: Start date (UTC)
        to_date: End date (UTC)
        api_token: FXCM API token (optional for demo)

    Returns:
        DataFrame with candles or None if failed
    """
    try:
        # Map symbol to FXCM format
        fxcm_symbol = FXCM_SYMBOLS.get(symbol, symbol)
        fxcm_tf = FXCM_TIMEFRAMES.get(timeframe, "m5")

        # FXCM API endpoint
        url = f"{FXCM_API_URL}/candles/{fxcm_symbol}/{fxcm_tf}"

        headers = {}
        if api_token:
            headers["Authorization"] = f"Bearer {api_token}"

        params = {
            "from": int(from_date.timestamp()),
            "to": int(to_date.timestamp()),
        }

        logger.info(f"Fetching {symbol} from FXCM ({fxcm_symbol}, {fxcm_tf})...")
        resp = requests.get(url, headers=headers, params=params, timeout=60)

        if resp.status_code != 200:
            logger.warning(f"FXCM API error: {resp.status_code} {resp.text[:200]}")
            return None

        data = resp.json()

        # Parse FXCM response
        candles = []
        for candle in data.get("candles", []):
            candles.append({
                "time": pd.to_datetime(candle["timestamp"], unit="s", utc=True),
                "open": float(candle["bidopen"]),
                "high": float(candle["bidhigh"]),
                "low": float(candle["bidlow"]),
                "close": float(candle["bidclose"]),
                "volume": int(candle.get("tickqty", 0))
            })

        if not candles:
            logger.warning(f"No candles returned from FXCM for {symbol}")
            return None

        df = pd.DataFrame(candles)
        df = df.sort_values("time").drop_duplicates(subset=["time"], keep="last")
        df = df[(df["time"] >= from_date) & (df["time"] <= to_date)]

        logger.info(f"Fetched {len(df)} candles from FXCM")
        return df

    except Exception as e:
        logger.error(f"FXCM fetch failed: {e}")
        return None


def fetch_metaapi_candles(
    symbol: str,
    timeframe: str,
    from_date: datetime,
    to_date: datetime,
    token: str,
    account_id: str
) -> Optional[pd.DataFrame]:
    """
    Fetch candles from MetaApi (existing implementation).

    Fallback option if FXCM fails.
    """
    from app.data import fetch_metaapi_candles as _fetch_metaapi

    try:
        return _fetch_metaapi(symbol, timeframe, from_date, to_date, token, account_id)
    except Exception as e:
        logger.error(f"MetaApi fetch failed: {e}")
        return None


def get_candles_robust(
    symbol: str,
    from_date: datetime,
    to_date: datetime,
    timeframe: str = "M5",
    data_dir: Optional[Path] = None,
    fxcm_token: Optional[str] = None,
    metaapi_token: Optional[str] = None,
    metaapi_account_id: Optional[str] = None
) -> pd.DataFrame:
    """
    Load candles with robust fallback strategy.

    Priority:
    1. Local Parquet cache
    2. Local CSV cache
    3. FXCM API (Israel-friendly)
    4. MetaApi (MT5/Vantage)

    Args:
        symbol: Trading symbol
        from_date: Start date (UTC)
        to_date: End date (UTC)
        timeframe: Timeframe (M5, M15, etc.)
        data_dir: Cache directory (default: data/backtest_candles)
        fxcm_token: FXCM API token (optional)
        metaapi_token: MetaApi token (optional)
        metaapi_account_id: MetaApi account ID (optional)

    Returns:
        DataFrame with candles

    Raises:
        ValueError: If all sources fail
    """
    if data_dir is None:
        data_dir = Path("data/backtest_candles")
    data_dir = Path(data_dir)
    data_dir.mkdir(parents=True, exist_ok=True)

    # File paths
    from_str = from_date.strftime("%Y-%m-%d")
    to_str = to_date.strftime("%Y-%m-%d")
    parquet_path = data_dir / symbol / timeframe / f"{from_str}_{to_str}.parquet"
    csv_path = data_dir / symbol / timeframe / f"{from_str}_{to_str}.csv"

    # 1. Try Parquet cache
    df = load_from_parquet(parquet_path)
    if df is not None and len(df) > 0:
        return df

    # 2. Try CSV cache
    df = load_from_csv(csv_path)
    if df is not None and len(df) > 0:
        return df

    # 3. Try FXCM API
    logger.info("No local cache found. Trying FXCM API...")
    df = fetch_fxcm_candles(symbol, timeframe, from_date, to_date, fxcm_token)

    if df is not None and len(df) > 0:
        # Save to Parquet
        parquet_path.parent.mkdir(parents=True, exist_ok=True)
        df.to_parquet(parquet_path, index=False)
        logger.info(f"Saved {len(df)} candles to {parquet_path}")
        return df

    # 4. Fallback to MetaApi
    if metaapi_token and metaapi_account_id:
        logger.info("FXCM failed. Trying MetaApi...")
        df = fetch_metaapi_candles(
            symbol, timeframe, from_date, to_date,
            metaapi_token, metaapi_account_id
        )

        if df is not None and len(df) > 0:
            # Save to Parquet
            parquet_path.parent.mkdir(parents=True, exist_ok=True)
            df.to_parquet(parquet_path, index=False)
            logger.info(f"Saved {len(df)} candles to {parquet_path}")
            return df

    # All sources failed
    raise ValueError(
        f"Failed to load candles for {symbol} from all sources:\n"
        f"- Local cache: Not found\n"
        f"- FXCM API: Failed\n"
        f"- MetaApi: {'Not configured' if not metaapi_token else 'Failed'}"
    )


# ========== Auto-detect credentials from environment ==========
def get_candles_auto(
    symbol: str,
    from_date: datetime,
    to_date: datetime,
    timeframe: str = "M5",
    data_dir: Optional[Path] = None
) -> pd.DataFrame:
    """
    Convenience wrapper that auto-detects API credentials from environment.

    Environment variables:
    - FXCM_API_TOKEN (optional)
    - META_API_TOKEN (optional)
    - META_API_ACCOUNT_ID (optional)
    """
    fxcm_token = os.getenv("FXCM_API_TOKEN")
    metaapi_token = os.getenv("META_API_TOKEN") or os.getenv("META_API_TOKEN_VANTAGE")
    metaapi_account = os.getenv("META_API_ACCOUNT_ID") or os.getenv("META_API_ACCOUNT_ID_VANTAGE")

    return get_candles_robust(
        symbol=symbol,
        from_date=from_date,
        to_date=to_date,
        timeframe=timeframe,
        data_dir=data_dir,
        fxcm_token=fxcm_token,
        metaapi_token=metaapi_token,
        metaapi_account_id=metaapi_account
    )
