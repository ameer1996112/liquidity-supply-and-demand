"""
Chart Generator Service -- Professional candlestick charts for trade notifications.

Generates annotated candlestick charts with entry/SL/TP levels and zone shading,
returns PNG bytes for direct upload to Discord/Telegram.

Data source priority:
  1. MetaAPI (broker candles -- most accurate, same data trades execute on)
  2. yfinance (fallback -- free, covers all symbols)

Non-blocking: uses ThreadPoolExecutor with hard timeout. Returns None on any failure.
Trade execution is NEVER delayed -- chart generation happens after notification dispatch.
"""

import io
import logging
import time
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError
from typing import Optional

import matplotlib
matplotlib.use("Agg")  # Headless backend -- no GUI required

import matplotlib.pyplot as plt  # noqa: E402
import mplfinance as mpf  # noqa: E402
import pandas as pd  # noqa: E402
import requests as http_requests  # noqa: E402
import yfinance as yf  # noqa: E402

logger = logging.getLogger(__name__)

_chart_executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="ChartGen")

# Circuit breaker: disable chart gen after N consecutive failures
_consecutive_failures = 0
_CIRCUIT_BREAKER_THRESHOLD = 3
_circuit_open_until = 0.0  # epoch timestamp
_CIRCUIT_OPEN_DURATION = 900  # 15 minutes

CHART_TIMEOUT_SEC = 10

# Yahoo Finance ticker map (fallback only)
YAHOO_TICKER_MAP = {
    "XAUUSD": "GC=F",
    "XAGUSD": "SI=F",
    "EURUSD": "EURUSD=X",
    "GBPUSD": "GBPUSD=X",
    "GBPJPY": "GBPJPY=X",
    "GBPCAD": "GBPCAD=X",
    "GBPAUD": "GBPAUD=X",
    "USDJPY": "USDJPY=X",
    "USDCHF": "USDCHF=X",
    "USDCAD": "USDCAD=X",
    "AUDUSD": "AUDUSD=X",
    "NZDUSD": "NZDUSD=X",
    "NZDJPY": "NZDJPY=X",
    "CHFJPY": "CHFJPY=X",
    "EURJPY": "EURJPY=X",
    "EURGBP": "EURGBP=X",
    "CADJPY": "CADJPY=X",
    "BTCUSD": "BTC-USD",
    "ETHUSD": "ETH-USD",
    "NAS100": "NQ=F",
    "US30": "YM=F",
    "SPX500": "ES=F",
    "US500": "ES=F",
    "GER40": "GC=F",
}

# TradingView-like dark theme
CHART_STYLE = mpf.make_mpf_style(
    base_mpf_style="nightclouds",
    marketcolors=mpf.make_marketcolors(
        up="#26a69a", down="#ef5350",
        edge="inherit", wick="inherit",
        volume={"up": "#26a69a80", "down": "#ef535080"},
    ),
    figcolor="#131722",
    facecolor="#131722",
    gridcolor="#1e222d",
    rc={
        "font.size": 9,
        "axes.labelcolor": "#d1d4dc",
        "xtick.color": "#787b86",
        "ytick.color": "#787b86",
    },
)


def generate_chart_async(
    symbol: str,
    side: str,
    entry: float,
    sl: float,
    tp: float,
    signal_id: int,
    zone_type: Optional[str] = None,
    zone_body_low: Optional[float] = None,
    zone_body_high: Optional[float] = None,
) -> Optional[bytes]:
    """
    Generate chart PNG bytes. Non-blocking with timeout.
    Returns PNG bytes or None on failure.
    """
    global _consecutive_failures, _circuit_open_until

    # Circuit breaker check
    if _consecutive_failures >= _CIRCUIT_BREAKER_THRESHOLD:
        if time.time() < _circuit_open_until:
            logger.info("Chart circuit breaker open, skipping for %s #%s", symbol, signal_id)
            return None
        # Reset after cooldown
        _consecutive_failures = 0

    try:
        future = _chart_executor.submit(
            _generate_chart,
            symbol, side, entry, sl, tp, signal_id,
            zone_type, zone_body_low, zone_body_high,
        )
        result = future.result(timeout=CHART_TIMEOUT_SEC)
        if result:
            _consecutive_failures = 0
        return result
    except FuturesTimeoutError:
        logger.warning("Chart generation timed out for %s signal #%s", symbol, signal_id)
        _consecutive_failures += 1
        if _consecutive_failures >= _CIRCUIT_BREAKER_THRESHOLD:
            _circuit_open_until = time.time() + _CIRCUIT_OPEN_DURATION
            logger.warning("Chart circuit breaker OPEN for %d seconds", _CIRCUIT_OPEN_DURATION)
        return None
    except Exception:
        logger.warning("Chart generation failed for %s signal #%s", symbol, signal_id, exc_info=True)
        _consecutive_failures += 1
        if _consecutive_failures >= _CIRCUIT_BREAKER_THRESHOLD:
            _circuit_open_until = time.time() + _CIRCUIT_OPEN_DURATION
        return None


def _generate_chart(
    symbol: str,
    side: str,
    entry: float,
    sl: float,
    tp: float,
    signal_id: int,
    zone_type: Optional[str] = None,
    zone_body_low: Optional[float] = None,
    zone_body_high: Optional[float] = None,
) -> Optional[bytes]:
    """Synchronous: fetch candles -> render -> return PNG bytes."""

    # 1. Fetch candle data: MetaAPI (broker) first, yfinance fallback
    df = _fetch_candles_metaapi(symbol, count=50)
    if df is None or df.empty:
        logger.info("MetaAPI candles unavailable for %s, falling back to yfinance", symbol)
        df = _fetch_candles_yfinance(symbol, count=50)
    if df is None or df.empty:
        logger.warning("No candle data for chart from any source: %s", symbol)
        return None

    # 2. Render to bytes
    return _render_chart(
        df, symbol, side, entry, sl, tp, signal_id,
        zone_type, zone_body_low, zone_body_high,
    )


# ═══════════════════════════════════════════════════════════════════════════
# Data source 1: MetaAPI (broker candles -- most accurate)
# ═══════════════════════════════════════════════════════════════════════════

def _fetch_candles_metaapi(symbol: str, count: int = 50) -> Optional[pd.DataFrame]:
    """
    Fetch candles from MetaAPI market data REST endpoint.
    Uses the same broker connection that executes trades -- most accurate data.
    """
    try:
        from src.core.metaapi_credentials import get_primary_credentials
        from src.services.symbol_mapper import SymbolMapper
    except ImportError:
        logger.debug("MetaAPI modules not available for chart candles")
        return None

    try:
        token, account_id, region = get_primary_credentials()
        if not token or not account_id:
            return None

        # Translate symbol to broker format (e.g., GBPUSD -> GBPUSD.raw)
        broker_symbol = symbol
        try:
            broker_symbol = SymbolMapper.to_broker_symbol(symbol) or symbol
        except Exception:
            pass

        region = (region or "new-york").strip()
        base_url = f"https://mt-client-api-v1.{region}.agiliumtrade.ai"
        headers = {"auth-token": token.strip(), "Content-Type": "application/json"}

        # MetaAPI historical candles endpoint: GET /users/current/accounts/{id}/historical-market-data/symbols/{symbol}/timeframes/15m/candles
        # Fetch enough candles (request more than needed, trim to count)
        url = (
            f"{base_url}/users/current/accounts/{account_id.strip()}"
            f"/historical-market-data/symbols/{broker_symbol}"
            f"/timeframes/15m/candles"
            f"?limit={count}"
        )

        resp = http_requests.get(url, headers=headers, timeout=8)

        if resp.status_code != 200:
            logger.debug("MetaAPI candles HTTP %s for %s", resp.status_code, symbol)
            return None

        candles = resp.json()
        if not candles or not isinstance(candles, list) or len(candles) < 5:
            return None

        # Convert MetaAPI candle format to DataFrame
        # MetaAPI returns: [{time, open, high, low, close, tickVolume, ...}]
        rows = []
        for c in candles:
            rows.append({
                "Date": pd.to_datetime(c.get("time")),
                "Open": float(c.get("open", 0)),
                "High": float(c.get("high", 0)),
                "Low": float(c.get("low", 0)),
                "Close": float(c.get("close", 0)),
                "Volume": float(c.get("tickVolume", 0) or c.get("volume", 0) or 0),
            })

        df = pd.DataFrame(rows)
        df.set_index("Date", inplace=True)
        df.sort_index(inplace=True)
        df = df.tail(count)
        df.index.name = "Date"

        logger.info("MetaAPI candles fetched for chart: %s (%d candles)", symbol, len(df))
        return df

    except Exception as e:
        logger.debug("MetaAPI candle fetch failed for %s: %s", symbol, e)
        return None


# ═══════════════════════════════════════════════════════════════════════════
# Data source 2: yfinance (fallback -- free, delayed)
# ═══════════════════════════════════════════════════════════════════════════

def _fetch_candles_yfinance(symbol: str, count: int = 50) -> Optional[pd.DataFrame]:
    """Fetch 15m candles from yfinance (fallback when MetaAPI unavailable)."""
    ticker_str = YAHOO_TICKER_MAP.get(symbol.upper())
    if not ticker_str:
        s = symbol.upper()
        # Strip broker suffixes like .raw, .ecn
        for suffix in (".raw", ".ecn", ".std", ".pro"):
            if s.endswith(suffix.upper()):
                s = s[: -len(suffix)]
        if s in YAHOO_TICKER_MAP:
            ticker_str = YAHOO_TICKER_MAP[s]
        elif len(s) == 6 and s[:3].isalpha() and s[3:].isalpha():
            ticker_str = f"{s}=X"
        else:
            logger.warning("No Yahoo ticker mapping for %s", symbol)
            return None

    try:
        ticker = yf.Ticker(ticker_str)
        df = ticker.history(period="5d", interval="15m")
        if df.empty:
            return None
        df = df.tail(count).copy()
        df.index.name = "Date"
        for col in ["Open", "High", "Low", "Close", "Volume"]:
            if col not in df.columns:
                cap = col.capitalize()
                if cap in df.columns:
                    df.rename(columns={cap: col}, inplace=True)
        logger.info("yfinance candles fetched for chart: %s (%d candles)", symbol, len(df))
        return df[["Open", "High", "Low", "Close", "Volume"]]
    except Exception as e:
        logger.warning("yfinance fetch failed for chart %s (%s): %s", symbol, ticker_str, e)
        return None


def _render_chart(
    df: pd.DataFrame,
    symbol: str,
    side: str,
    entry: float,
    sl: float,
    tp: float,
    signal_id: int,
    zone_type: Optional[str] = None,
    zone_body_low: Optional[float] = None,
    zone_body_high: Optional[float] = None,
) -> Optional[bytes]:
    """Render candlestick chart to PNG bytes buffer."""
    try:
        # Calculate R:R for title
        risk = abs(entry - sl) if sl and entry else 0
        rr = abs(tp - entry) / risk if risk > 0 and tp else 0
        title = f"{symbol}  {side.upper()}  |  R:R 1:{rr:.1f}  |  15m  |  #{signal_id}"

        kwargs = dict(
            type="candle",
            style=CHART_STYLE,
            title=title,
            volume=False,
            figsize=(10, 5.625),  # 16:9
            tight_layout=True,
            returnfig=True,
            scale_padding=dict(left=0.05, right=0.15, top=0.2, bottom=0.2),
            warn_too_much_data=200,
        )

        # Do NOT pass hlines to mplfinance -- it stretches y-axis to include
        # distant prices. Draw lines manually after plotting.
        fig, axes = mpf.plot(df, **kwargs)
        ax = axes[0]

        # Compute y-axis range from candle data + trade levels
        data_low = df["Low"].min()
        data_high = df["High"].max()
        all_prices = [data_low, data_high]
        if entry and entry > 0:
            all_prices.append(entry)
        if sl and sl > 0:
            all_prices.append(sl)
        if tp and tp > 0:
            all_prices.append(tp)
        if zone_body_low and zone_body_low > 0:
            all_prices.append(zone_body_low)
        if zone_body_high and zone_body_high > 0:
            all_prices.append(zone_body_high)

        y_min = min(all_prices)
        y_max = max(all_prices)
        y_pad = (y_max - y_min) * 0.08  # 8% padding
        ax.set_ylim(y_min - y_pad, y_max + y_pad)

        n = len(df)

        # Draw entry/SL/TP as manual horizontal lines (clipped to y-range)
        line_levels = []
        if entry and entry > 0:
            line_levels.append((entry, "#2962ff", f"ENTRY {entry:.5g}"))
        if sl and sl > 0:
            line_levels.append((sl, "#ef5350", f"SL {sl:.5g}"))
        if tp and tp > 0:
            line_levels.append((tp, "#26a69a", f"TP {tp:.5g}"))

        label_props = dict(fontsize=9, va="center", fontweight="bold", fontfamily="monospace")
        for price, color, label in line_levels:
            ax.axhline(y=price, color=color, linestyle="--", linewidth=1.5, alpha=0.8, zorder=3)
            ax.text(n + 0.5, price, f"  {label}", color=color, **label_props)

        # Zone shading
        if zone_type and zone_body_low and zone_body_high:
            zone_color = "#26a69a" if zone_type.lower() == "demand" else "#ef5350"
            ax.axhspan(
                zone_body_low, zone_body_high,
                alpha=0.12, color=zone_color, zorder=0,
            )
            zone_mid = (zone_body_low + zone_body_high) / 2
            ax.text(
                1, zone_mid, f"  {zone_type.upper()} ZONE",
                color=zone_color, fontsize=8, va="center", alpha=0.7,
            )

        # Side arrow marker on last candle
        last_close = df["Close"].iloc[-1]
        arrow_y = entry if (entry and entry > 0) else last_close
        arrow_color = "#26a69a" if side.upper() == "BUY" else "#ef5350"
        arrow_marker = "^" if side.upper() == "BUY" else "v"
        ax.scatter(n - 1, arrow_y, marker=arrow_marker, color=arrow_color, s=120, zorder=5)

        # Render to bytes
        buf = io.BytesIO()
        fig.savefig(
            buf, format="png", dpi=120, bbox_inches="tight",
            facecolor=fig.get_facecolor(), edgecolor="none",
        )
        plt.close(fig)
        buf.seek(0)
        return buf.getvalue()

    except Exception as e:
        logger.warning("Chart render failed for %s: %s", symbol, e)
        plt.close("all")
        return None
