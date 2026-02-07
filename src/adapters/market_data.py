"""
Market data adapter for building a simple \"market narrative\".

For v9.1 we keep this intentionally lightweight:
- Uses yfinance to fetch the last N candles (default: 50 x 15m).
- Computes:
    - Trend: price vs SMA50 (Bullish / Bearish / Neutral)
    - Momentum: RSI(14) bucketed into Overbought / Oversold / Neutral
    - Recent price action: Engulfing / Pinbar detection on last candles

Output is a concise natural-language summary that can be fed to the
RAG engine + LLM as part of the ensemble decision process.
"""

from __future__ import annotations

import logging
from typing import Optional

import numpy as np
import pandas as pd
import yfinance as yf

logger = logging.getLogger(__name__)


def _compute_rsi(series: pd.Series, period: int = 14) -> pd.Series:
    """Simple RSI implementation."""
    delta = series.diff()
    gain = (delta.where(delta > 0, 0.0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0.0)).rolling(window=period).mean()
    rs = gain / loss.replace(0, np.nan)
    rsi = 100 - (100 / (1 + rs))
    return rsi


def _detect_engulfing(df: pd.DataFrame) -> Optional[str]:
    """Detect simple bullish/bearish engulfing pattern on last two candles."""
    if len(df) < 2:
        return None
    prev = df.iloc[-2]
    last = df.iloc[-1]

    prev_body = prev["Close"] - prev["Open"]
    last_body = last["Close"] - last["Open"]

    # Bearish engulfing: previous green, last red, body engulfs
    if prev_body > 0 and last_body < 0:
        if last["Open"] >= prev["Close"] and last["Close"] <= prev["Open"]:
            return "Bearish Engulfing"

    # Bullish engulfing: previous red, last green, body engulfs
    if prev_body < 0 and last_body > 0:
        if last["Open"] <= prev["Close"] and last["Close"] >= prev["Open"]:
            return "Bullish Engulfing"

    return None


def _detect_pinbar(candle: pd.Series) -> Optional[str]:
    """Detect a simple pinbar (long wick vs body)."""
    high = candle["High"]
    low = candle["Low"]
    open_ = candle["Open"]
    close = candle["Close"]

    body = abs(close - open_)
    upper_wick = high - max(open_, close)
    lower_wick = min(open_, close) - low

    # Require meaningful range
    if (high - low) == 0:
        return None

    # Wick-to-body ratio heuristic
    if upper_wick > body * 2 and upper_wick > (high - low) * 0.4:
        return "Bearish Pinbar"
    if lower_wick > body * 2 and lower_wick > (high - low) * 0.4:
        return "Bullish Pinbar"
    return None


def get_market_narrative(symbol: str, candles: int = 50) -> str:
    """
    Build a compact natural-language narrative for the given symbol.

    Uses 15m candles for the last `candles` periods via yfinance.
    Maps common trading symbols to Yahoo Finance tickers so that
    indices/FX pairs resolve correctly (e.g. XAUUSD -> GC=F).
    """
    # Map internal symbols to Yahoo Finance tickers
    ticker_map = {
        "XAUUSD": "GC=F",
        "EURUSD": "EURUSD=X",
        "GBPUSD": "GBPUSD=X",
        "USDJPY": "USDJPY=X",
        "BTCUSD": "BTC-USD",
        "NAS100": "NQ=F",
        "US30": "YM=F",
    }
    lookup_symbol = ticker_map.get(symbol.upper(), symbol)

    try:
        ticker = yf.Ticker(lookup_symbol)
        df = ticker.history(period="3d", interval="15m")
        if df.empty:
            raise ValueError("no data returned")
        df = df.tail(candles).copy()
    except Exception as e:
        logger.warning("Failed to fetch market data for %s (lookup=%s): %s", symbol, lookup_symbol, e)
        return f"{symbol} market data unavailable; treat context as neutral."

    df = df.rename(columns=str.capitalize)  # Ensure Open/High/Low/Close

    # Trend: price vs SMA50
    df["SMA50"] = df["Close"].rolling(window=50, min_periods=5).mean()
    last = df.iloc[-1]
    sma = last.get("SMA50")
    close = last["Close"]

    if pd.notnull(sma):
        if close > sma * 1.001:
            trend = "Bullish (price above SMA50)"
        elif close < sma * 0.999:
            trend = "Bearish (price below SMA50)"
        else:
            trend = "Neutral (price near SMA50)"
    else:
        trend = "Unknown (insufficient data for SMA50)"

    # RSI(14)
    df["RSI14"] = _compute_rsi(df["Close"], period=14)
    rsi_val = float(df["RSI14"].iloc[-1]) if pd.notnull(df["RSI14"].iloc[-1]) else 50.0
    if rsi_val > 70:
        rsi_state = "Overbought"
    elif rsi_val < 30:
        rsi_state = "Oversold"
    else:
        rsi_state = "Neutral"

    # Price action pattern
    pattern = _detect_engulfing(df)
    if pattern is None:
        pin = _detect_pinbar(last)
        pattern = pin

    if pattern is None:
        pattern_desc = "Recent candles show no strong pattern."
    else:
        pattern_desc = f"Last candles formed a {pattern} pattern."

    narrative = (
        f"{symbol} trend: {trend}. "
        f"RSI(14) is {rsi_state} ({rsi_val:.1f}). "
        f"{pattern_desc}"
    )

    return narrative


def get_market_snapshot(symbol: str) -> dict:
    """
    Get current market snapshot for TCA tracking.

    Returns:
        dict with:
            - bid: Current bid price
            - ask: Current ask price
            - spread_pips: Bid-ask spread in pips
            - atr: Average True Range (14-period, hourly)
            - timestamp: When data was captured
    """
    from datetime import datetime, timezone

    # Map internal symbols to Yahoo Finance tickers
    ticker_map = {
        "XAUUSD": "GC=F",
        "EURUSD": "EURUSD=X",
        "GBPUSD": "GBPUSD=X",
        "USDJPY": "USDJPY=X",
        "USDCHF": "USDCHF=X",
        "AUDUSD": "AUDUSD=X",
        "NZDUSD": "NZDUSD=X",
        "USDCAD": "USDCAD=X",
        "BTCUSD": "BTC-USD",
        "NAS100": "NQ=F",
        "US30": "YM=F",
    }
    lookup_symbol = ticker_map.get(symbol.upper(), symbol)

    try:
        ticker = yf.Ticker(lookup_symbol)

        # Get current price data
        info = ticker.info
        current_price = info.get("regularMarketPrice") or info.get("currentPrice", 0)

        # For forex, yfinance doesn't provide bid/ask, so we approximate
        # Typical forex spread is 1-3 pips for majors
        spread_pips_estimate = 2.0  # Conservative estimate

        # Get pip size
        from src.services.tca_analyzer import TCAAnalyzer
        pip_size = TCAAnalyzer.PIP_SIZES.get(symbol.upper(), 0.0001)

        # Approximate bid/ask from current price
        spread_value = spread_pips_estimate * pip_size
        bid = current_price - (spread_value / 2)
        ask = current_price + (spread_value / 2)

        # Calculate ATR (14-period on hourly data)
        df = ticker.history(period="7d", interval="1h")
        if not df.empty:
            df = df.rename(columns=str.capitalize)
            atr = _calculate_atr(df, period=14)
        else:
            atr = 0.0

        return {
            "symbol": symbol,
            "bid": bid,
            "ask": ask,
            "spread_pips": spread_pips_estimate,
            "atr": atr,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    except Exception as e:
        logger.warning(f"Failed to get market snapshot for {symbol}: {e}")
        # Return fallback data
        return {
            "symbol": symbol,
            "bid": 0.0,
            "ask": 0.0,
            "spread_pips": 2.0,
            "atr": 0.0,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }


def _calculate_atr(df: pd.DataFrame, period: int = 14) -> float:
    """
    Calculate Average True Range (ATR).

    ATR measures volatility by decomposing the entire range of an asset
    for that period.
    """
    if len(df) < period + 1:
        return 0.0

    high = df["High"]
    low = df["Low"]
    close = df["Close"].shift(1)

    # True Range is the greatest of:
    # 1. Current High - Current Low
    # 2. Abs(Current High - Previous Close)
    # 3. Abs(Current Low - Previous Close)
    tr1 = high - low
    tr2 = (high - close).abs()
    tr3 = (low - close).abs()

    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)

    # ATR is the moving average of True Range
    atr = tr.rolling(window=period).mean().iloc[-1]

    return float(atr) if pd.notnull(atr) else 0.0


def get_current_price(symbol: str) -> float:
    """
    Get current price for a symbol.

    Used for live PnL calculations and quick price checks.

    Returns:
        Current price, or 0.0 if unavailable
    """
    ticker_map = {
        "XAUUSD": "GC=F",
        "EURUSD": "EURUSD=X",
        "GBPUSD": "GBPUSD=X",
        "USDJPY": "USDJPY=X",
        "USDCHF": "USDCHF=X",
        "AUDUSD": "AUDUSD=X",
        "NZDUSD": "NZDUSD=X",
        "USDCAD": "USDCAD=X",
        "BTCUSD": "BTC-USD",
        "NAS100": "NQ=F",
        "US30": "YM=F",
    }
    lookup_symbol = ticker_map.get(symbol.upper(), symbol)

    try:
        ticker = yf.Ticker(lookup_symbol)
        info = ticker.info
        price = info.get("regularMarketPrice") or info.get("currentPrice", 0)
        return float(price)
    except Exception as e:
        logger.warning(f"Failed to get current price for {symbol}: {e}")
        return 0.0


__all__ = ["get_market_narrative", "get_market_snapshot", "get_current_price"]

