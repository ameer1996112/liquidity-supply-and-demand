"""
TradingView Strategy Export Ingestor — Real Signal Data Pipeline

Reads the 'List of Trades' CSV exported from TradingView Strategy Tester,
enriches each closed trade with market-DNA features via yFinance, and
inserts labelled records into the Railway PostgreSQL database so that
train_v1.py has ground-truth data instead of synthetic data.

─────────────────────────────────────────────────────────────────────────────
HOW FEATURES ARE SOURCED (two tiers, best available wins)

  TIER 1 — F: tags in the Signal/Comment column (most accurate)
           These are written by the Pine Script when 'Show AI Debug Text'
           is enabled in the S&D Algo settings.  Example:
             "🟢 LONG | F:score=72.5 | F:session=2 | F:rvol=1.23 ..."

  TIER 2 — yFinance OHLCV recalculation (fallback / gap-fill)
           Fetches the full bar history for the symbol, then recomputes
           RVOL, ATR ratio, RSI, ADX, EMA trend, and session from scratch
           at the exact entry timestamp.

  Session is always overridden from the entry timestamp (always available).
─────────────────────────────────────────────────────────────────────────────
EXPECTED CSV FORMAT  (TradingView → Strategy Tester → List of Trades → Export)

  Trade # │ Type          │ Signal   │ Date/Time          │ Price  │ Profit
  ────────┼───────────────┼──────────┼────────────────────┼────────┼───────
  1       │ Entry Long    │ 🟢 LONG  │ 2024-01-15 09:15   │ 2024.5 │
  1       │ Exit Long     │          │ 2024-01-15 11:30   │ 2028.3 │ $485
  2       │ Entry Short   │ 🔴 SHORT │ 2024-01-16 14:00   │ 2031.0 │
  2       │ Exit Short    │          │ 2024-01-16 15:45   │ 2040.1 │ -$228

  Also handles single-row-per-trade exports where Profit appears on entry row.

─────────────────────────────────────────────────────────────────────────────
EFFECTS OF INGESTING HISTORY

  • Historian:  After ingest, run embed_history.py so trade_embeddings is
                populated — then the Historian can say "Found N similar trades".
  • Analytics:  Ingested trades appear in /api/v1/analytics/trades and any
                dashboards (win rate, PnL reflect full history).
  • ML model:   Live inference (galil_v1.json) is unchanged. Future retraining
                (train_v1.py) will use this data as ground truth.
  • Duplicates: Running the same CSV twice inserts duplicate rows — ingest
                each file once. Rows are tagged run_mode='BACKTEST'.

─────────────────────────────────────────────────────────────────────────────
USAGE  (from repo root; set DATABASE_URL for Railway Postgres)

    DATABASE_URL="postgresql://..." python apps/ml/ingest_tv_export.py --csv trades.csv --symbol XAUUSD
    DATABASE_URL="postgresql://..." python apps/ml/ingest_tv_export.py --csv trades.csv --symbol NQ --tf 1h
    python apps/ml/ingest_tv_export.py --csv trades.csv --symbol EURUSD --dry-run
"""

import json
import math
import os
import re
import sys
import argparse
import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
)
log = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# SYMBOL MAPPING: TradingView → yFinance
# ─────────────────────────────────────────────────────────────────────────────

YF_TICKER: dict[str, str] = {
    # Metals
    "XAUUSD": "GC=F",   "GOLD": "GC=F",
    "XAGUSD": "SI=F",   "SILVER": "SI=F",
    "XPTUSD": "PL=F",
    # Forex majors
    "EURUSD": "EURUSD=X", "GBPUSD": "GBPUSD=X",
    "USDJPY": "JPY=X",    "USDCHF": "CHF=X",
    "USDCAD": "CAD=X",    "AUDUSD": "AUDUSD=X",
    "NZDUSD": "NZDUSD=X",
    # Forex crosses
    "EURJPY": "EURJPY=X", "GBPJPY": "GBPJPY=X",
    "EURGBP": "EURGBP=X", "EURAUD": "EURAUD=X",
    "GBPAUD": "GBPAUD=X", "CADJPY": "CADJPY=X",
    "AUDCAD": "AUDCAD=X", "AUDNZD": "AUDNZD=X",
    "GBPCAD": "GBPCAD=X", "NZDJPY": "NZDJPY=X",
    "GBPNZD": "GBPNZD=X", "EURCAD": "EURCAD=X",
    # Indices
    "NQ": "NQ=F",    "US100": "NQ=F",  "NAS100": "NQ=F", "NDX": "NQ=F",
    "SPX": "ES=F",   "US500": "ES=F",
    "US30": "YM=F",  "DJI": "YM=F",
    "DAX": "DAX=F",  "FTSE": "^FTSE",
    # Crypto
    "BTCUSD": "BTC-USD", "ETHUSD": "ETH-USD",
    # Oil
    "USOIL": "CL=F", "WTI": "CL=F",
}

# ─────────────────────────────────────────────────────────────────────────────
# CSV COLUMN DETECTION
# ─────────────────────────────────────────────────────────────────────────────

_COL_CANDIDATES: dict[str, list[str]] = {
    "trade_num": ["Trade #", "Trade#", "Trade No", "Trade", "#"],
    "type":      ["Type"],
    "signal":    ["Signal", "Comment", "Description", "Alert"],
    "dt":        ["Date/Time", "DateTime", "Date and time", "Date", "Time", "Entry Time", "Open time"],
    "price":     ["Price", "Price USD", "Entry Price", "Open"],
    "profit":    ["Profit", "Net P&L USD", "Net P&L", "Net Profit", "P&L", "PnL", "Gain/Loss"],
    "run_up":    ["Favorable excursion USD", "Favorable excursion", "Run-up", "Run Up", "MFE", "Max Profit", "Max Run-up"],
    "drawdown":  ["Adverse excursion USD", "Adverse excursion", "Drawdown", "MAE", "Max Loss", "Max Drawdown"],
}


def _find_col(df: pd.DataFrame, key: str) -> Optional[str]:
    """Return the first matching column name for a semantic key, or None."""
    cols_lower = {c: c.strip().lower() for c in df.columns}

    # Exact-match pass
    for candidate in _COL_CANDIDATES[key]:
        for col, cl in cols_lower.items():
            if cl == candidate.lower():
                return col

    # Prefix-match fallback for price (handles "Price USD", "Price CAD", etc.)
    if key == "price":
        for col, cl in cols_lower.items():
            if cl.startswith("price"):
                return col

    return None


def _parse_money(val) -> Optional[float]:
    """Parse '$1,234.56', '-1 234,56', '(123)' etc. → float. None if invalid."""
    if val is None or (isinstance(val, float) and math.isnan(val)):
        return None
    s = str(val).strip()
    if s in ("", "-", "—", "N/A"):
        return None
    s = re.sub(r"[€£¥₽$\s]", "", s)    # strip currency & spaces
    s = s.replace(",", ".")             # EU locale: 1.234,56 → 1.234.56
    # Keep only the last decimal point
    parts = s.split(".")
    if len(parts) > 2:
        s = "".join(parts[:-1]) + "." + parts[-1]
    s = s.replace("(", "-").replace(")", "")   # (123) → -123
    try:
        return float(s)
    except ValueError:
        return None


def _parse_dt(val) -> Optional[datetime]:
    """Try several datetime formats used by TradingView exports."""
    if val is None or (isinstance(val, float) and math.isnan(val)):
        return None
    s = str(val).strip()
    formats = [
        "%Y-%m-%d %H:%M:%S %z",
        "%Y-%m-%d %H:%M %z",
        "%Y-%m-%dT%H:%M:%S%z",
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d %H:%M",
        "%m/%d/%Y %H:%M",
        "%d/%m/%Y %H:%M",
        "%Y-%m-%d",
    ]
    for fmt in formats:
        try:
            dt = datetime.strptime(s, fmt)
            return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    log.warning(f"Could not parse datetime: {val!r}")
    return None


# ─────────────────────────────────────────────────────────────────────────────
# 1. CSV PARSING
# ─────────────────────────────────────────────────────────────────────────────

def parse_tv_csv(csv_path: str) -> list[dict]:
    """
    Parse a TradingView 'List of Trades' CSV into a list of trade dicts.

    Handles two export formats:
      • PAIRED   — separate Entry / Exit rows per trade (most common)
      • SUMMARY  — one row per completed trade with Profit on same row

    Each returned dict contains:
        side            'buy' | 'sell'
        entry_time      datetime (UTC)
        entry_price     float
        exit_time       datetime | None
        exit_price      float | None
        profit          float  (positive = win, negative = loss)
        run_up          float | None  (MFE in account currency)
        drawdown        float | None  (MAE in account currency, absolute)
        signal_comment  str
    """
    df = pd.read_csv(csv_path, dtype=str)
    df.columns = [c.strip() for c in df.columns]

    c_num    = _find_col(df, "trade_num")
    c_type   = _find_col(df, "type")
    c_signal = _find_col(df, "signal")
    c_dt     = _find_col(df, "dt")
    c_price  = _find_col(df, "price")
    c_profit = _find_col(df, "profit")
    c_runup  = _find_col(df, "run_up")
    c_dd     = _find_col(df, "drawdown")

    if not c_type or not c_dt or not c_price:
        raise ValueError(
            f"Required columns (Type, Date/Time, Price) not found.\n"
            f"Available columns: {list(df.columns)}"
        )

    type_vals = df[c_type].dropna().str.lower().tolist()
    is_paired = any("entry" in v for v in type_vals)

    trades: list[dict] = []

    if is_paired:
        # ── PAIRED FORMAT ────────────────────────────────────────────────────
        # Collect entry and exit rows separately (TradingView can export either
        # order: entry-first or exit-first within the same trade number).
        entry_rows: dict[str, dict] = {}
        exit_rows:  dict[str, dict] = {}

        for _, row in df.iterrows():
            raw_type = str(row.get(c_type, "")).strip().lower()
            trade_id = str(row[c_num]).strip() if c_num else str(_)

            if "entry" in raw_type:
                entry_rows[trade_id] = {
                    "side":           "buy" if "long" in raw_type else "sell",
                    "entry_time":     _parse_dt(row[c_dt]),
                    "entry_price":    _parse_money(row[c_price]),
                    "signal_comment": str(row[c_signal]).strip() if c_signal else "",
                    # P&L sometimes duplicated on entry row — store as fallback
                    "_profit_fb":     _parse_money(row[c_profit]) if c_profit else None,
                    "_runup_fb":      _parse_money(row[c_runup])  if c_runup  else None,
                    "_dd_fb":         _parse_money(row[c_dd])     if c_dd     else None,
                }
            elif "exit" in raw_type:
                exit_rows[trade_id] = {
                    "exit_time":  _parse_dt(row[c_dt]),
                    "exit_price": _parse_money(row[c_price]),
                    "profit":     _parse_money(row[c_profit]) if c_profit else None,
                    "run_up":     _parse_money(row[c_runup])  if c_runup  else None,
                    "drawdown":   _parse_money(row[c_dd])     if c_dd     else None,
                }

        # Merge pairs
        for trade_id, e in entry_rows.items():
            ex = exit_rows.get(trade_id, {})
            profit  = ex.get("profit")  or e.get("_profit_fb")
            run_up  = ex.get("run_up")  or e.get("_runup_fb")
            dd      = ex.get("drawdown") or e.get("_dd_fb")
            trades.append({
                "side":           e["side"],
                "entry_time":     e["entry_time"],
                "entry_price":    e["entry_price"],
                "signal_comment": e["signal_comment"],
                "exit_time":      ex.get("exit_time"),
                "exit_price":     ex.get("exit_price"),
                "profit":         profit,
                "run_up":         abs(run_up) if run_up is not None else None,
                "drawdown":       abs(dd)     if dd     is not None else None,
            })
    else:
        # ── SUMMARY FORMAT ───────────────────────────────────────────────────
        for _, row in df.iterrows():
            raw_type = str(row.get(c_type, "")).strip().lower()
            profit   = _parse_money(row[c_profit]) if c_profit else None
            if profit is None:
                continue
            run_up = _parse_money(row[c_runup]) if c_runup else None
            dd     = _parse_money(row[c_dd])    if c_dd    else None
            trades.append({
                "side":           "buy" if "long" in raw_type else "sell",
                "entry_time":     _parse_dt(row[c_dt]),
                "entry_price":    _parse_money(row[c_price]),
                "exit_time":      None,
                "exit_price":     None,
                "profit":         profit,
                "run_up":         abs(run_up) if run_up is not None else None,
                "drawdown":       abs(dd)     if dd     is not None else None,
                "signal_comment": str(row[c_signal]).strip() if c_signal else "",
            })

    # ── Drop incomplete rows ──────────────────────────────────────────────────
    before = len(trades)
    trades = [
        t for t in trades
        if t["entry_time"] is not None
        and t["entry_price"] is not None
        and t["profit"] is not None
    ]
    if before - len(trades):
        log.warning(f"Dropped {before - len(trades)} rows with missing required fields")

    log.info(f"Parsed {len(trades)} valid closed trades from {csv_path}")
    return trades


# ─────────────────────────────────────────────────────────────────────────────
# 2. PINE SCRIPT F: FEATURE EXTRACTION
# ─────────────────────────────────────────────────────────────────────────────

_F_RE = re.compile(r"F:([\w_]+)=([-\d.]+)")


def extract_f_features(comment: str) -> dict:
    """
    Parse 'F:key=value' tags from the TradingView Signal/Comment field.

    Returns a dict mapping tag names → float values.
    Empty dict if no tags found.

    Example input:
        '🟢 LONG | F:score=72.5 | F:session=2 | F:rvol=1.23 | F:adx=28.45 ...'
    """
    return {k: float(v) for k, v in _F_RE.findall(comment or "")}


# ─────────────────────────────────────────────────────────────────────────────
# 3. YFINANCE MARKET DATA
# ─────────────────────────────────────────────────────────────────────────────

def get_yf_ticker(symbol: str) -> str:
    """Map a TradingView symbol (e.g. 'OANDA:XAUUSD') to a yFinance ticker."""
    sym = symbol.split(":")[-1].upper()
    return YF_TICKER.get(sym, sym)


def fetch_market_data(
    symbol: str,
    start: datetime,
    end: datetime,
    interval: str = "1h",
) -> Optional[pd.DataFrame]:
    """
    Bulk-download OHLCV bars from yFinance for the full date range of all trades.

    The returned DataFrame is indexed by UTC timestamp and has lower-case
    columns: open, high, low, close, volume.

    yFinance interval limits:
        5m / 15m / 30m  → max 60 days history
        1h              → max ~730 days history
        1d              → unlimited
    """
    try:
        import yfinance as yf
    except ImportError:
        log.error("yfinance not installed — run: pip install yfinance")
        return None

    ticker    = get_yf_ticker(symbol)
    days_span = (end - start).days

    # Auto-downgrade interval when range exceeds yFinance limits
    if interval in ("5m", "15m", "30m") and days_span > 59:
        log.warning(
            f"Date range is {days_span} days — downgrading {interval} → 1h "
            f"(yFinance free-tier limit for sub-hour data is 60 days)"
        )
        interval = "1h"
    if interval == "1h" and days_span > 729:
        log.warning(f"Date range is {days_span} days — downgrading 1h → 1d")
        interval = "1d"

    # Pad the start by enough bars for EMA-200 calculation
    extra = {"5m": 2, "15m": 5, "30m": 7, "1h": 15, "1d": 300}
    padded_start = start - timedelta(days=extra.get(interval, 15))

    log.info(f"yFinance: {ticker} [{interval}]  {padded_start.date()} → {end.date()}")
    try:
        df = yf.download(
            ticker,
            start=padded_start,
            end=end + timedelta(days=1),
            interval=interval,
            auto_adjust=True,
            progress=False,
            multi_level_index=False,  # yfinance ≥0.2.x returns MultiIndex by default
        )
    except TypeError:
        # Older yfinance version without multi_level_index parameter
        df = yf.download(
            ticker,
            start=padded_start,
            end=end + timedelta(days=1),
            interval=interval,
            auto_adjust=True,
            progress=False,
        )

    if df is None or df.empty:
        log.warning(f"yFinance returned no data for {ticker}")
        return None

    # Flatten MultiIndex if present (yfinance 0.2.x)
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)

    df.columns = [c.lower() for c in df.columns]
    df.index   = pd.to_datetime(df.index, utc=True)
    df.sort_index(inplace=True)

    log.info(f"  → {len(df)} bars fetched")
    return df


# ─────────────────────────────────────────────────────────────────────────────
# 4. FEATURE CALCULATION FROM OHLCV WINDOW
# ─────────────────────────────────────────────────────────────────────────────

def _session_id(dt: datetime) -> int:
    """0=Asia, 1=London, 2=NY, 3=Off-hours  (mirrors Pine Script logic)."""
    h = dt.astimezone(timezone.utc).hour
    if h < 8:   return 0   # Asian session
    if h < 13:  return 1   # London session
    if h < 21:  return 2   # New York session
    return 3                # Off-hours


def calculate_bar_features(
    ohlcv: pd.DataFrame,
    at: datetime,
    entry_dt: datetime,
) -> dict:
    """
    Compute the 7 market-DNA features that cannot be read from the Pine comment.

    Uses the 250 bars immediately preceding `at` from the cached OHLCV frame.
    Returns an empty dict if insufficient history is available.

    Features returned: rvol, atr_ratio, rsi, adx, trend, htf_trend, session
    """
    at_ts = (
        pd.Timestamp(at, tz=timezone.utc)
        if at.tzinfo is None
        else pd.Timestamp(at).tz_convert("UTC")
    )
    idx    = ohlcv.index.searchsorted(at_ts, side="right")
    window = ohlcv.iloc[max(0, idx - 250):idx].copy()

    if len(window) < 20:
        return {}

    c   = window["close"]
    h   = window["high"]
    lo  = window["low"]
    vol = window.get("volume", pd.Series(1.0, index=window.index))

    # ── RVOL ─────────────────────────────────────────────────────────────────
    vol_sma  = vol.rolling(20).mean()
    last_vol = vol.iloc[-1]
    last_sma = vol_sma.iloc[-1]
    rvol = float(np.clip(last_vol / last_sma, 0.1, 10.0)) if last_sma > 0 else 1.0

    # ── ATR (14) ─────────────────────────────────────────────────────────────
    hl   = h - lo
    hpc  = (h - c.shift(1)).abs()
    lpc  = (lo - c.shift(1)).abs()
    tr   = pd.concat([hl, hpc, lpc], axis=1).max(axis=1)
    atr  = tr.rolling(14).mean()
    last_atr   = float(atr.iloc[-1]) if not math.isnan(atr.iloc[-1]) else float(tr.mean())
    atr_ratio  = float(np.clip(float(hl.iloc[-1]) / max(last_atr, 1e-9), 0.1, 5.0))

    # ── RSI (14) ─────────────────────────────────────────────────────────────
    delta = c.diff()
    gain  = delta.clip(lower=0).rolling(14).mean()
    loss  = (-delta.clip(upper=0)).rolling(14).mean()
    rs    = gain / loss.clip(1e-9)
    rsi_v = float((100 - 100 / (1 + rs)).iloc[-1])
    rsi   = float(np.clip(rsi_v, 0.0, 100.0)) if not math.isnan(rsi_v) else 50.0

    # ── ADX (14, simplified) ─────────────────────────────────────────────────
    pdm      = h.diff().clip(lower=0)
    ndm      = (-lo.diff()).clip(lower=0)
    plus_di  = 100 * pdm.rolling(14).mean() / atr.clip(1e-9)
    minus_di = 100 * ndm.rolling(14).mean() / atr.clip(1e-9)
    dx       = 100 * (plus_di - minus_di).abs() / (plus_di + minus_di).clip(1e-9)
    adx_v    = float(dx.rolling(14).mean().iloc[-1])
    adx      = float(np.clip(adx_v, 0.0, 100.0)) if not math.isnan(adx_v) else 20.0

    # ── Trend: EMA50 vs EMA200 ────────────────────────────────────────────────
    ema50  = c.ewm(span=50,  adjust=False).mean()
    ema200 = c.ewm(span=200, adjust=False).mean()
    trend  = 1 if ema50.iloc[-1] > ema200.iloc[-1] else (
             -1 if ema50.iloc[-1] < ema200.iloc[-1] else 0)

    # ── HTF trend: EMA100 vs EMA200 ──────────────────────────────────────────
    ema100    = c.ewm(span=100, adjust=False).mean()
    htf_trend = 1 if ema100.iloc[-1] > ema200.iloc[-1] else (
                -1 if ema100.iloc[-1] < ema200.iloc[-1] else 0)

    return {
        "rvol":      rvol,
        "atr_ratio": atr_ratio,
        "rsi":       rsi,
        "adx":       adx,
        "trend":     trend,
        "htf_trend": htf_trend,
        "session":   _session_id(entry_dt),
    }


# ─────────────────────────────────────────────────────────────────────────────
# 5. TRADE ENRICHMENT (TIER 1 + TIER 2 merge)
# ─────────────────────────────────────────────────────────────────────────────

# Pine F: tag name  →  internal feature key
_F_TAG_MAP: dict[str, str] = {
    "rvol":                     "rvol",
    "session":                  "session",
    "atr_ratio":                "atr_ratio",
    "trend":                    "trend",
    "rsi":                      "rsi",
    "htf_trend":                "htf_trend",
    "adx":                      "adx",
    "touch_count":              "touch_count",
    "base_quality":             "base_quality",
    "departure_strength":       "departure_strength",
    "liquidity_distance_score": "liquidity_distance",   # 0-100 score (not raw pips)
    "liquidity_spread_score":   "liquidity_spread",     # 0-100 score (not raw pips)
    "return_strength":          "return_strength",
    "score":                    "score",
    "fresh":                    "freshness",
    "is_accuracy":              "is_accuracy",
    "zone_type":                "zone_type",
}


def enrich_trade(trade: dict, ohlcv: Optional[pd.DataFrame]) -> dict:
    """
    Build the full feature dict for one trade by merging both tiers:

      • Tier 2 (yFinance) provides the base OHLCV-derived features.
      • Tier 1 (Pine F: tags) overrides with the exact values the strategy used.
      • Session is always recomputed from entry_time (authoritative).
      • Defaults fill any remaining gaps.
    """
    # ── Tier 2: market DNA from yFinance ─────────────────────────────────────
    features: dict = {}
    if ohlcv is not None and trade["entry_time"] is not None:
        features = calculate_bar_features(ohlcv, trade["entry_time"], trade["entry_time"])

    # ── Tier 1: Pine F: tags override yFinance values ─────────────────────────
    f_raw = extract_f_features(trade.get("signal_comment", ""))
    for pine_key, feat_key in _F_TAG_MAP.items():
        if pine_key in f_raw:
            features[feat_key] = f_raw[pine_key]

    # ── Session always from entry timestamp (ground truth) ───────────────────
    if trade["entry_time"] is not None:
        features["session"] = _session_id(trade["entry_time"])

    # ── Zone type from trade direction if not in F: tags ────────────────────
    features.setdefault("zone_type", 0 if trade["side"] == "buy" else 1)

    # ── Defaults for any remaining missing values ─────────────────────────────
    defaults: dict = {
        "rvol":               1.0,
        "atr_ratio":          1.0,
        "trend":              0,
        "rsi":                50.0,
        "htf_trend":          0,
        "adx":                20.0,
        "touch_count":        1,
        "base_quality":       50.0,
        "departure_strength": 50.0,
        "liquidity_distance": 50.0,
        "liquidity_spread":   50.0,
        "return_strength":    50.0,
        "score":              50.0,
        "freshness":          1,
        "is_accuracy":        0,
    }
    for k, v in defaults.items():
        features.setdefault(k, v)

    trade["features"] = features
    return trade


# ─────────────────────────────────────────────────────────────────────────────
# 6. DATABASE INSERTION
# ─────────────────────────────────────────────────────────────────────────────

def _ingest_key(symbol: str, side: str, dt) -> tuple:
    """Hashable key for (symbol, side, entry time) to detect duplicates."""
    if dt is None:
        return (symbol, side, "")
    # Normalise to naive datetime string for comparison (DB may return aware)
    t = dt.replace(tzinfo=None) if getattr(dt, "tzinfo", None) else dt
    return (symbol, side, t.isoformat()[:19] if hasattr(t, "isoformat") else str(t)[:19])


def save_to_database(
    trades: list[dict],
    symbol: str,
    dry_run: bool = False,
    skip_existing: bool = True,
    batch_commit_every: int = 200,
) -> int:
    """
    Insert enriched trades as (snd_signals + snd_trades) pairs.

    Each trade becomes:
      • 1 row in snd_signals  — all 15 AI features + metadata
      • 1 row in snd_trades   — outcome, P&L, timing

    run_mode = 'BACKTEST' tags these rows. If skip_existing is True (default),
    trades already in the DB (same symbol, side, entry time) are skipped so you
    can resume after a disconnect. Commits every batch_commit_every rows.
    """
    if dry_run:
        log.info("DRY RUN — skipping database write")
        return 0

    try:
        from dotenv import load_dotenv
        backend_env = Path(__file__).parent.parent / ".env"
        if backend_env.exists():
            load_dotenv(backend_env)
            log.info(f"Loaded env from {backend_env}")

        db_url = os.environ.get("DATABASE_URL", "sqlite:///./data/trading_bot.db")
        log.info(f"Database: {db_url[:70]}...")

        from sqlalchemy import create_engine, text
        ck     = {"check_same_thread": False} if db_url.startswith("sqlite") else {}
        engine = create_engine(db_url, connect_args=ck)
        is_pg  = not db_url.startswith("sqlite")

        existing = set()
        if skip_existing:
            with engine.connect() as conn:
                rows = conn.execute(
                    text("SELECT symbol, side, signal_time FROM snd_signals WHERE run_mode = 'BACKTEST'")
                ).fetchall()
                for row in rows:
                    existing.add(_ingest_key(str(row[0]), str(row[1]), row[2]))
            if existing:
                log.info("Resume mode: skipping %d trade(s) already in DB", len(existing))

        inserted = errors = skipped = 0

        with engine.connect() as conn:
            for trade in trades:
                try:
                    f       = trade["features"]
                    outcome = "win" if trade["profit"] > 0 else "loss"
                    side    = trade["side"]
                    entry_p = float(trade["entry_price"])
                    exit_p  = float(trade["exit_price"]) if trade.get("exit_price") else entry_p
                    entry_t = trade["entry_time"]
                    exit_t  = trade.get("exit_time") or (entry_t + timedelta(hours=4))

                    key = _ingest_key(symbol, side, entry_t)
                    if skip_existing and key in existing:
                        skipped += 1
                        continue

                    # ── Approximate SL/TP from drawdown/run-up (P&L in account currency) ──
                    # We derive price-distance proxies using the position size implied by
                    # the S&D Algo's fixed-risk formula.  These are approximate — they
                    # are stored for completeness but are NOT used in ML training.
                    dd_raw = trade.get("drawdown") or 0.0
                    ru_raw = trade.get("run_up")   or 0.0
                    # Fallback: 0.5% for SL and 1.5% for TP of entry price
                    sl_delta = abs(float(dd_raw)) if dd_raw else entry_p * 0.005
                    tp_delta = abs(float(ru_raw)) if ru_raw else entry_p * 0.015
                    # Cap deltas to avoid absurd values (e.g. currency-formatted P&L misread)
                    sl_delta = min(sl_delta, entry_p * 0.05)
                    tp_delta = min(tp_delta, entry_p * 0.20)
                    sl = (entry_p - sl_delta) if side == "buy" else (entry_p + sl_delta)
                    tp = (entry_p + tp_delta) if side == "buy" else (entry_p - tp_delta)

                    bars_held = max(1, int((exit_t - entry_t).total_seconds() / 300))
                    pnl_usd   = float(trade["profit"])
                    # R = profit / risk (approximate: risk ≈ |drawdown|)
                    pnl_r = float(np.clip(
                        pnl_usd / max(abs(float(dd_raw or sl_delta)), 1e-6),
                        -5.0, 10.0,
                    ))

                    # ── Insert signal ──────────────────────────────────────────────────
                    result = conn.execute(text("""
                        INSERT INTO snd_signals (
                            symbol, side,
                            entry_price, stop_loss, take_profit, rr_ratio,
                            entry_model, run_mode,
                            feature_score, feature_freshness, feature_session,
                            feature_atr_ratio, feature_trend, feature_rsi,
                            feature_htf_trend, feature_rvol, feature_adx,
                            feature_touch_count, feature_base_quality,
                            feature_departure_strength, feature_liquidity_distance,
                            feature_liquidity_spread, feature_return_strength,
                            ml_decision, ml_confidence, ml_reasoning,
                            ml_model_version, ml_processed,
                            signal_time, received_at
                        ) VALUES (
                            :symbol, :side,
                            :entry, :sl, :tp, :rr,
                            'TV_EXPORT', 'BACKTEST',
                            :score, :freshness, :session,
                            :atr_ratio, :trend, :rsi,
                            :htf_trend, :rvol, :adx,
                            :touch_count, :base_quality,
                            :departure_strength, :liquidity_distance,
                            :liquidity_spread, :return_strength,
                            'ALLOW', 0.5, 'TradingView export import',
                            'tv_ingest_v1', true,
                            :signal_time, :signal_time
                        )
                    """), {
                        "symbol":               symbol,
                        "side":                 side,
                        "entry":                entry_p,
                        "sl":                   sl,
                        "tp":                   tp,
                        "rr":                   round(abs(pnl_r), 2),
                        "score":                float(f["score"]),
                        "freshness":            int(f["freshness"]),
                        "session":              int(f["session"]),
                        "atr_ratio":            float(f["atr_ratio"]),
                        "trend":                int(f["trend"]),
                        "rsi":                  float(f["rsi"]),
                        "htf_trend":            int(f["htf_trend"]),
                        "rvol":                 float(f["rvol"]),
                        "adx":                  float(f["adx"]),
                        "touch_count":          int(f["touch_count"]),
                        "base_quality":         float(f["base_quality"]),
                        "departure_strength":   float(f["departure_strength"]),
                        "liquidity_distance":   float(f["liquidity_distance"]),
                        "liquidity_spread":     float(f["liquidity_spread"]),
                        "return_strength":      float(f["return_strength"]),
                        "signal_time":          entry_t,
                    })

                    # ── Get new signal ID ─────────────────────────────────────────────
                    sig_id = (
                        conn.execute(text("SELECT lastval()")).scalar()
                        if is_pg
                        else result.lastrowid
                    )

                    if sig_id:
                        conn.execute(text("""
                            INSERT INTO snd_trades (
                                signal_id, symbol, side,
                                entry_price, exit_price, entry_time, exit_time,
                                pnl_r, pnl_usd, outcome, status, bars_held,
                                created_at, closed_at
                            ) VALUES (
                                :sig_id, :symbol, :side,
                                :entry, :exit_p, :entry_t, :exit_t,
                                :pnl_r, :pnl_usd, :outcome, 'CLOSED', :bars,
                                :entry_t, :exit_t
                            )
                        """), {
                            "sig_id":  sig_id,
                            "symbol":  symbol,
                            "side":    side,
                            "entry":   entry_p,
                            "exit_p":  exit_p,
                            "entry_t": entry_t,
                            "exit_t":  exit_t,
                            "pnl_r":   pnl_r,
                            "pnl_usd": pnl_usd,
                            "outcome": outcome,
                            "bars":    bars_held,
                        })

                    existing.add(key)
                    inserted += 1
                    if inserted % batch_commit_every == 0:
                        conn.commit()
                        log.info(f"  Committed batch: {inserted} inserted, {skipped} skipped…")
                    elif inserted % 50 == 0:
                        log.info(f"  Inserted {inserted} / {len(trades)} records…")

                except Exception as exc:
                    errors += 1
                    log.debug(f"Row error: {exc}")

            conn.commit()
        log.info(f"Done: {inserted} inserted, {skipped} skipped (already in DB), {errors} errors")
        return inserted

    except Exception as exc:
        log.error(f"Database error: {exc}", exc_info=True)
        raise


# ─────────────────────────────────────────────────────────────────────────────
# 7. MAIN
# ─────────────────────────────────────────────────────────────────────────────

def _print_loss_preview(trades: list[dict]) -> None:
    """Print a quick loss-pattern breakdown before writing to the database."""
    losses = [t for t in trades if t["profit"] <= 0]
    if not losses:
        return

    log.info("\n── Loss Pattern Preview (from enriched features) ─────────────")

    # Session breakdown
    sess_label = {0: "Asia", 1: "London", 2: "NY", 3: "Off"}
    counts: dict[str, int] = {}
    for t in losses:
        s = int(t["features"].get("session", 2))
        counts[sess_label.get(s, "?")] = counts.get(sess_label.get(s, "?"), 0) + 1
    log.info("  By session:")
    for name, cnt in sorted(counts.items(), key=lambda x: -x[1]):
        log.info(f"    {name:<8}  {cnt:3d} losses  ({cnt / len(losses):.0%})")

    # RVOL breakdown
    low_rvol  = sum(1 for t in losses if float(t["features"].get("rvol", 1)) < 1.0)
    high_rvol = len(losses) - low_rvol
    log.info(f"  By RVOL:   low (<1.0)={low_rvol} ({low_rvol/len(losses):.0%})   "
             f"high (≥1.0)={high_rvol} ({high_rvol/len(losses):.0%})")

    # Trend breakdown
    counter  = sum(1 for t in losses if int(t["features"].get("trend", 0)) == 0)
    aligned  = len(losses) - counter
    log.info(f"  By trend:  counter/flat={counter} ({counter/len(losses):.0%})   "
             f"aligned={aligned} ({aligned/len(losses):.0%})")
    log.info("─" * 62)


def _symbol_from_filename(path: Path) -> Optional[str]:
    """Extract symbol from filename like 'XAUUSD_2026-02-28.csv' or
    'S&D_Algo_[Pro]_FX_NAS100_2026-02-28 (1).csv'."""
    stem = path.stem  # filename without extension
    # Pattern: symbol is the segment immediately before a date (YYYY-MM-DD)
    m = re.search(r"_([A-Z0-9]{3,8})_\d{4}-\d{2}-\d{2}", stem, re.IGNORECASE)
    if m:
        return m.group(1).upper()
    # Fallback: if filename IS the symbol (e.g. "XAUUSD_2026-02-28")
    parts = stem.split("_")
    if parts and re.match(r"^[A-Z]{3,8}[0-9]{0,3}$", parts[0], re.IGNORECASE):
        return parts[0].upper()
    return None


def _ingest_one(
    csv_path: str,
    symbol: str,
    tf: str,
    dry_run: bool,
    skip_existing: bool = True,
    batch_commit_every: int = 200,
    tier1_only: bool = False,
) -> int:
    """Parse, enrich, and insert one CSV. Returns number of records inserted."""
    log.info("=" * 62)
    log.info(f"Processing: {Path(csv_path).name}  →  symbol={symbol}")
    log.info("=" * 62)

    trades = parse_tv_csv(csv_path)
    if not trades:
        log.error("No valid trades — skipping")
        return 0

    wins   = sum(1 for t in trades if t["profit"] > 0)
    losses = len(trades) - wins
    log.info(
        f"📊 {len(trades)} trades  │  "
        f"{wins} wins ({wins / len(trades):.0%})  │  "
        f"{losses} losses ({losses / len(trades):.0%})"
    )

    tier1_count = sum(1 for t in trades if extract_f_features(t.get("signal_comment", "")))
    if tier1_count:
        log.info(f"✅ Tier 1 (F: tags): {tier1_count}/{len(trades)} trades")
    else:
        log.info("ℹ️  No F: tags — enriching from yFinance only")

    ohlcv: Optional[pd.DataFrame] = None
    if not tier1_only:
        valid_times = [t["entry_time"] for t in trades if t["entry_time"]]
        if valid_times:
            ohlcv = fetch_market_data(
                symbol,
                start=min(valid_times),
                end=max(valid_times) + timedelta(hours=1),
                interval=tf,
            )
    else:
        log.info("Tier 1 only — skipping yFinance (faster, no network)")

    enriched = [enrich_trade(t, ohlcv) for t in trades]
    _print_loss_preview(enriched)

    if dry_run:
        log.info("🔸 DRY RUN — database NOT modified")
        if enriched:
            t = enriched[0]
            log.info(
                f"Sample: side={t['side']} profit={t['profit']:.2f}\n"
                f"  features={json.dumps({k: round(float(v), 3) for k, v in t['features'].items()}, indent=4)}"
            )
        return 0

    return save_to_database(
        enriched, symbol, dry_run=False,
        skip_existing=skip_existing,
        batch_commit_every=batch_commit_every,
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Ingest TradingView 'List of Trades' CSV into the ML database"
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--csv",  help="Path to a single TradingView CSV file")
    group.add_argument("--dir",  help="Directory containing multiple CSV files "
                                      "(symbol inferred from each filename)")
    parser.add_argument("--symbol",  default=None,
                        help="Symbol override for --csv mode (e.g. XAUUSD, NQ)")
    parser.add_argument("--tf",      default="1h",
                        help="yFinance interval (5m / 15m / 1h / 1d, default: 1h)")
    parser.add_argument("--dry-run", action="store_true",
                        help="Parse and preview — do NOT write to the database")
    parser.add_argument("--no-skip-existing", action="store_true",
                        help="Insert all rows even if already in DB (default: skip duplicates for resume)")
    parser.add_argument("--batch-size", type=int, default=200,
                        help="Commit every N rows (default 200). Larger = faster, resume-friendly.")
    parser.add_argument("--tier1-only", action="store_true",
                        help="Use only F: tags from CSV; skip yFinance (faster, no network, use when CSV has F: tags).")
    args = parser.parse_args()

    log.info("=" * 62)
    log.info("TradingView Export Ingestor — Real Signal Pipeline")
    log.info("=" * 62)

    total_inserted = 0
    skip_existing = not args.no_skip_existing
    batch_commit = args.batch_size
    tier1_only = args.tier1_only

    if args.dir:
        # ── DIRECTORY MODE: process every CSV in the folder ─────────────────
        csv_files = sorted(Path(args.dir).glob("*.csv"))
        if not csv_files:
            log.error(f"No CSV files found in {args.dir}")
            sys.exit(1)
        log.info(f"Found {len(csv_files)} CSV files in {args.dir}")

        for csv_path in csv_files:
            symbol = _symbol_from_filename(csv_path)
            if not symbol:
                log.warning(f"Cannot infer symbol from {csv_path.name} — skipping")
                continue
            n = _ingest_one(str(csv_path), symbol, args.tf, args.dry_run, skip_existing, batch_commit, tier1_only)
            total_inserted += n

    else:
        # ── SINGLE FILE MODE ─────────────────────────────────────────────────
        symbol = args.symbol
        if not symbol:
            symbol = _symbol_from_filename(Path(args.csv))
        if not symbol:
            log.error("Cannot infer symbol from filename — please pass --symbol")
            sys.exit(1)
        total_inserted = _ingest_one(args.csv, symbol, args.tf, args.dry_run, skip_existing, batch_commit, tier1_only)

    if not args.dry_run and total_inserted:
        log.info("\n" + "=" * 62)
        log.info(f"✅ Total inserted: {total_inserted} signal+trade pairs")
        log.info("Next steps:")
        log.info("  • Populate Historian memory:  DATABASE_URL=... python apps/ml/embed_history.py")
        log.info("  • Retrain ML model (optional):  python apps/ml/train_v1.py")
        log.info("=" * 62)


if __name__ == "__main__":
    main()
