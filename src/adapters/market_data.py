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


__all__ = ["get_market_narrative"]

