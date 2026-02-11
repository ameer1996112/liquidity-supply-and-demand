"""
Data pipeline: MetaApi → canonical candles.

- Load from local Parquet/CSV if present, else fetch from MetaApi and persist
- Canonical schema: time (UTC, bar close time), open, high, low, close, volume
- Strictly increasing timestamps, de-duplicated, aligned to timeframe boundaries
- Symbol adapter for MT5 name differences (XAUUSD vs XAUUSDm)
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import pandas as pd
import requests

logger = logging.getLogger(__name__)

# MetaApi market data host (different from trading API)
METAAPI_MARKET_DATA_URL = "https://mt-market-data-client-api-v1.new-york.agiliumtrade.ai"

# MT5 timeframe mapping + MetaApi format (API expects 5m, 15m, 1h, not M5, M15, H1)
TIMEFRAME_TO_METAAPI = {
    "1m": "1m", "2m": "2m", "3m": "3m", "4m": "4m", "5m": "5m",
    "M5": "5m", "M1": "1m", "M15": "15m", "M30": "30m",
    "1h": "1h", "H1": "1h", "2h": "2h", "H2": "2h",
    "3h": "3h", "4h": "4h", "H4": "4h", "6h": "6h", "8h": "8h", "12h": "12h",
    "1d": "1d", "D1": "1d", "1w": "1w", "1mn": "1mn",
}
TIMEFRAME_MINUTES = {
    "1m": 1, "2m": 2, "3m": 3, "4m": 4, "5m": 5, "M5": 5,
    "6m": 6,
    "10m": 10,
    "12m": 12,
    "15m": 15,
    "M15": 15,
    "20m": 20,
    "30m": 30,
    "M30": 30,
    "1h": 60,
    "H1": 60,
    "2h": 120,
    "3h": 180,
    "4h": 240,
    "H4": 240,
    "6h": 360,
    "8h": 480,
    "12h": 720,
    "1d": 1440,
    "D1": 1440,
    "1w": 10080,
    "1mn": 43200,
}


def _resolve_symbol(symbol: str, aliases: dict) -> str:
    """Resolve symbol to canonical form for file paths and API."""
    up = symbol.upper()
    for canonical, alts in (aliases or {}).items():
        if up == canonical.upper():
            return canonical
        if up in [a.upper() for a in alts]:
            return canonical
    return symbol


def _align_bar_time(ts: datetime, timeframe_minutes: int) -> datetime:
    """Align timestamp to bar close boundary (TradingView convention)."""
    epoch_minutes = int(ts.timestamp() / 60)
    aligned_minutes = (epoch_minutes // timeframe_minutes) * timeframe_minutes
    return datetime.fromtimestamp(aligned_minutes * 60, tz=timezone.utc)


def _parse_time(s: str) -> datetime:
    """Parse ISO time and ensure UTC."""
    if isinstance(s, datetime):
        return s.replace(tzinfo=timezone.utc) if s.tzinfo is None else s
    dt = pd.to_datetime(s, utc=True)
    return dt.to_pydatetime() if hasattr(dt, "to_pydatetime") else dt


def load_candles_from_file(path: Path) -> Optional[pd.DataFrame]:
    """Load candles from CSV or Parquet. Returns None if file not found."""
    if not path.exists():
        return None
    try:
        if path.suffix.lower() == ".parquet":
            df = pd.read_parquet(path)
        else:
            df = pd.read_csv(path)
        return _normalize_candles(df)
    except Exception as e:
        logger.warning("Failed to load %s: %s", path, e)
        return None


def _normalize_candles(df: pd.DataFrame) -> pd.DataFrame:
    """Normalize to canonical schema and ensure alignment."""
    required = ["time", "open", "high", "low", "close"]
    for c in required:
        if c not in df.columns:
            raise ValueError(f"Missing column: {c}")

    # Normalize column names
    df = df.rename(columns=str.lower).copy()
    if "volume" not in df.columns:
        df["volume"] = 0

    # Parse time
    df["time"] = pd.to_datetime(df["time"], utc=True)
    df = df.sort_values("time").drop_duplicates(subset=["time"], keep="last").reset_index(drop=True)
    df = df[df["time"].notna()]

    for col in ["open", "high", "low", "close", "volume"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    df = df.dropna(subset=["open", "high", "low", "close"])

    return df[["time", "open", "high", "low", "close", "volume"]]


def fetch_metaapi_candles(
    symbol: str,
    timeframe: str,
    from_date: datetime,
    to_date: datetime,
    token: str,
    account_id: str,
    symbol_aliases: Optional[dict] = None,
) -> pd.DataFrame:
    """
    Fetch candles from MetaApi historical market data API.

    API: GET /users/current/accounts/:accountId/historical-market-data/symbols/:symbol/timeframes/:timeframe/candles
    Candles load backwards from startTime. Max 1000 per request.
    """
    aliases = symbol_aliases or {}
    resolved = _resolve_symbol(symbol, aliases)
    # Try resolved first; if API fails, try raw symbol
    symbols_to_try = [resolved, symbol] if resolved != symbol else [symbol]

    # MetaApi expects: 5m, 15m, 1h, 1d, etc. (not M5, M15, H1)
    tf = TIMEFRAME_TO_METAAPI.get(timeframe.upper(), timeframe.lower())

    all_candles = []
    for sym in symbols_to_try:
        url = (
            f"{METAAPI_MARKET_DATA_URL}/users/current/accounts/"
            f"{account_id}/historical-market-data/symbols/{sym}/timeframes/{tf}/candles"
        )
        headers = {"auth-token": token, "Accept": "application/json"}

        # Load backwards from to_date (API loads in reverse chronological order)
        current = to_date
        limit = 1000

        while current >= from_date:
            params = {"startTime": current.strftime("%Y-%m-%dT%H:%M:%S.000Z"), "limit": limit}
            try:
                resp = requests.get(url, headers=headers, params=params, timeout=120)
                if resp.status_code != 200:
                    logger.warning("MetaApi candles %s: HTTP %s %s", sym, resp.status_code, resp.text[:200])
                    break
                data = resp.json()
            except Exception as e:
                logger.error("MetaApi candles failed: %s", e)
                break

            if not data:
                break

            for c in data:
                t = _parse_time(c.get("time", c.get("brokerTime")))
                if t < from_date:
                    continue
                all_candles.append({
                    "time": t,
                    "open": float(c["open"]),
                    "high": float(c["high"]),
                    "low": float(c["low"]),
                    "close": float(c["close"]),
                    "volume": float(c.get("tickVolume", c.get("volume", 0))),
                })

            if len(data) < limit:
                break
            # Move cursor backwards to fetch older candles
            times = [c.get("time", c.get("brokerTime")) for c in data]
            earliest = min(_parse_time(t) for t in times if t is not None)
            if earliest >= current:
                break
            current = earliest

        if all_candles:
            break

    if not all_candles:
        raise ValueError(f"No candles fetched for {symbol} from MetaApi")

    df = pd.DataFrame(all_candles)
    df = df.sort_values("time").drop_duplicates(subset=["time"], keep="last").reset_index(drop=True)
    df = df[(df["time"] >= from_date) & (df["time"] <= to_date)]
    return _normalize_candles(df)


def get_candles(
    symbol: str,
    from_date: datetime,
    to_date: datetime,
    timeframe: str = "M5",
    data_dir: Optional[Path] = None,
    metaapi_token: Optional[str] = None,
    metaapi_account_id: Optional[str] = None,
    symbol_aliases: Optional[dict] = None,
    persist: bool = True,
) -> pd.DataFrame:
    """
    Load candles: from file if present, else MetaApi. Persist to Parquet when fetching.

    Returns DataFrame with: time, open, high, low, close, volume.
    """
    aliases = symbol_aliases or {}
    resolved = _resolve_symbol(symbol, aliases)
    tf_min = TIMEFRAME_MINUTES.get(timeframe.upper(), TIMEFRAME_MINUTES.get("5m", 5))

    if data_dir is None:
        data_dir = Path("data/backtest_candles")
    data_dir = Path(data_dir)
    data_dir.mkdir(parents=True, exist_ok=True)

    # File path: data/backtest_candles/XAUUSD/M5/2026-01-01_2026-02-10.parquet
    from_str = from_date.strftime("%Y-%m-%d")
    to_str = to_date.strftime("%Y-%m-%d")
    parquet_path = data_dir / resolved / timeframe / f"{from_str}_{to_str}.parquet"
    csv_path = data_dir / resolved / timeframe / f"{from_str}_{to_str}.csv"

    # Try load from file (exact date range match)
    for p in [parquet_path, csv_path]:
        df = load_candles_from_file(p)
        if df is not None and len(df) > 0:
            df = df[(df["time"] >= from_date) & (df["time"] <= to_date)]
            if len(df) > 0:
                logger.info("Loaded %d candles from %s", len(df), p)
                return df.reset_index(drop=True)

    # Fallback: try any file in symbol/timeframe that might contain the range
    base_dir = data_dir / resolved / timeframe
    if base_dir.exists():
        for ext in [".csv", ".parquet"]:
            for p in sorted(base_dir.glob(f"*{ext}")):
                df = load_candles_from_file(p)
                if df is not None and len(df) > 0:
                    df = df[(df["time"] >= from_date) & (df["time"] <= to_date)]
                    if len(df) > 0:
                        logger.info("Loaded %d candles from %s (fallback)", len(df), p)
                        return df.reset_index(drop=True)

    # Fetch from MetaApi
    if not metaapi_token or not metaapi_account_id:
        raise ValueError("metaapi_token and metaapi_account_id required when no local data")

    df = fetch_metaapi_candles(
        symbol=symbol,
        timeframe=timeframe,
        from_date=from_date,
        to_date=to_date,
        token=metaapi_token,
        account_id=metaapi_account_id,
        symbol_aliases=aliases,
    )

    if persist and len(df) > 0:
        parquet_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            df.to_parquet(parquet_path, index=False)
        except ImportError:
            csv_path = parquet_path.with_suffix(".csv")
            df.to_csv(csv_path, index=False)
            parquet_path = csv_path
        logger.info("Persisted %d candles to %s", len(df), parquet_path)

    return df.reset_index(drop=True)
