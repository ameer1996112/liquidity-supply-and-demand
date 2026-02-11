"""
FX Replay-style Backtest Dashboard

Professional interactive backtesting interface using Streamlit + Lightweight Charts v5.

Features:
- Dark mode (#131722) matching TradingView aesthetics
- Interactive candlestick charts with entry/exit markers
- Shaded trade boxes (green=win, red=loss)
- Real-time performance metrics
- Trade table with drill-down

Usage:
    streamlit run app/app.py -- --symbol XAUUSD --from 2026-01-01 --to 2026-02-10
"""

from __future__ import annotations

import argparse
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path

# Add project root to Python path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pandas as pd
import streamlit as st
from streamlit_lightweight_charts import renderLightweightCharts

from app.config import BacktestConfig
from app.data_loader_fxcm import get_candles_auto  # FXCM primary, MetaApi fallback
from app.engine_core import FastBacktestEngine
from app.outputs import compute_summary

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ========== Page Config ==========
st.set_page_config(
    page_title="FX Replay - Backtest Dashboard",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ========== Dark Mode CSS ==========
DARK_MODE_CSS = """
<style>
    /* TradingView Dark Theme */
    .stApp {
        background-color: #131722;
        color: #d1d4dc;
    }

    .main {
        background-color: #131722;
    }

    /* Metrics Cards */
    [data-testid="stMetricValue"] {
        color: #26a69a;
        font-size: 28px;
        font-weight: 600;
    }

    [data-testid="stMetricLabel"] {
        color: #787b86;
        font-size: 14px;
        text-transform: uppercase;
        letter-spacing: 0.5px;
    }

    /* Headers */
    h1, h2, h3 {
        color: #d1d4dc !important;
        font-weight: 600;
    }

    /* Sidebar */
    [data-testid="stSidebar"] {
        background-color: #1e222d;
    }

    /* Tables */
    .dataframe {
        background-color: #1e222d !important;
        color: #d1d4dc !important;
    }

    .dataframe thead tr th {
        background-color: #2a2e39 !important;
        color: #787b86 !important;
    }

    /* Buttons */
    .stButton>button {
        background-color: #2962ff;
        color: white;
        border: none;
        border-radius: 4px;
        padding: 0.5rem 1rem;
        font-weight: 500;
    }

    .stButton>button:hover {
        background-color: #1e4db7;
    }
</style>
"""

st.markdown(DARK_MODE_CSS, unsafe_allow_html=True)


# ========== Data Loading ==========
@st.cache_data(ttl=3600)
def load_backtest_data(
    symbol: str,
    from_date: datetime,
    to_date: datetime,
    timeframe: str,
    config: BacktestConfig
):
    """Load candles and run backtest (cached for 1 hour)."""
    try:
        # Use FXCM as primary source (auto-falls back to MetaApi)
        candles = get_candles_auto(
            symbol=symbol,
            from_date=from_date,
            to_date=to_date,
            timeframe=timeframe
        )

        logger.info(f"Loaded {len(candles)} candles")

        # Run fast backtest
        engine = FastBacktestEngine(config=config)
        trades = engine.run(candles)

        summary = compute_summary(trades, engine.equity_curve)

        return candles, trades, summary, engine

    except Exception as e:
        logger.error(f"Backtest failed: {e}")
        st.error(f"Failed to load data: {e}")
        return None, None, None, None


def prepare_chart_data(candles: pd.DataFrame, trades: list) -> dict:
    """
    Prepare chart data for Lightweight Charts v5.

    Returns dict with:
    - candlestick_data: OHLC candles
    - markers: Entry/exit arrows
    - trade_boxes: Shaded rectangles for each trade
    """
    # Candlestick data
    candle_data = []
    for _, row in candles.iterrows():
        ts = int(row["time"].timestamp())
        candle_data.append({
            "time": ts,
            "open": round(float(row["open"]), 2),
            "high": round(float(row["high"]), 2),
            "low": round(float(row["low"]), 2),
            "close": round(float(row["close"]), 2),
        })

    # Markers (entry/exit arrows)
    markers = []
    for t in trades:
        is_long = str(t.side).lower() == "long"

        # Entry marker
        markers.append({
            "time": int(t.entry_time.timestamp()),
            "position": "belowBar" if is_long else "aboveBar",
            "color": "#26a69a" if is_long else "#ef5350",
            "shape": "arrowUp" if is_long else "arrowDown",
            "text": f"{'L' if is_long else 'S'} {t.entry_comment or 'ENTRY'}"
        })

        # Exit marker
        exit_color = "#26a69a" if t.pnl > 0 else "#ef5350"
        markers.append({
            "time": int(t.exit_time.timestamp()),
            "position": "aboveBar" if is_long else "belowBar",
            "color": exit_color,
            "shape": "circle",
            "text": f"Exit: {t.reason.upper()}"
        })

    # Trade boxes (shaded rectangles)
    trade_boxes = []
    for t in trades:
        is_win = t.pnl > 0
        box_color = "rgba(38, 166, 154, 0.2)" if is_win else "rgba(239, 83, 80, 0.2)"

        trade_boxes.append({
            "time_start": int(t.entry_time.timestamp()),
            "time_end": int(t.exit_time.timestamp()),
            "price_top": max(t.entry_price, t.exit_price),
            "price_bottom": min(t.entry_price, t.exit_price),
            "color": box_color,
            "borderColor": "#26a69a" if is_win else "#ef5350",
            "text": f"${t.pnl:,.0f}"
        })

    return {
        "candlestick_data": candle_data,
        "markers": markers,
        "trade_boxes": trade_boxes
    }


def render_chart(chart_data: dict, symbol: str):
    """Render interactive chart with Lightweight Charts v5."""

    # Chart config (TradingView dark theme)
    chart_options = {
        "layout": {
            "background": {"type": "solid", "color": "#131722"},
            "textColor": "#d1d4dc"
        },
        "grid": {
            "vertLines": {"color": "#1e222d"},
            "horzLines": {"color": "#1e222d"}
        },
        "crosshair": {
            "mode": 1
        },
        "rightPriceScale": {
            "borderColor": "#2a2e39",
            "scaleMargins": {"top": 0.1, "bottom": 0.2}
        },
        "timeScale": {
            "borderColor": "#2a2e39",
            "timeVisible": True,
            "secondsVisible": False
        },
        "height": 600
    }

    # Candlestick series
    candlestick_series = {
        "type": "Candlestick",
        "data": chart_data["candlestick_data"],
        "options": {
            "upColor": "#26a69a",
            "downColor": "#ef5350",
            "borderUpColor": "#26a69a",
            "borderDownColor": "#ef5350",
            "wickUpColor": "#26a69a",
            "wickDownColor": "#ef5350"
        }
    }

    # Markers
    if chart_data["markers"]:
        candlestick_series["markers"] = chart_data["markers"]

    # Render chart
    renderLightweightCharts([
        {
            "chart": chart_options,
            "series": [candlestick_series]
        }
    ], f"chart_{symbol}")

    # Note: Trade boxes (shaded rectangles) require custom series implementation
    # in streamlit-lightweight-charts-v5. For now, we use markers only.
    # TODO: Implement custom Rectangle series for trade boxes


def render_metrics(summary: dict):
    """Render performance metrics cards."""
    col1, col2, col3, col4, col5 = st.columns(5)

    with col1:
        net_profit = summary.get("net_profit", 0)
        st.metric("Net Profit", f"${net_profit:,.2f}")

    with col2:
        win_rate = summary.get("win_rate", 0)
        st.metric("Win Rate", f"{win_rate:.1f}%")

    with col3:
        total_trades = summary.get("total_trades", 0)
        st.metric("Total Trades", total_trades)

    with col4:
        max_dd = summary.get("max_drawdown_pct", 0)
        st.metric("Max Drawdown", f"{max_dd:.2f}%")

    with col5:
        profit_factor = summary.get("profit_factor", 0)
        st.metric("Profit Factor", f"{profit_factor:.2f}")


def render_trades_table(trades: list):
    """Render trades table with styling."""
    if not trades:
        st.warning("No trades executed")
        return

    # Convert to DataFrame
    trades_data = []
    for t in trades:
        trades_data.append({
            "Entry Time": t.entry_time.strftime("%Y-%m-%d %H:%M"),
            "Exit Time": t.exit_time.strftime("%Y-%m-%d %H:%M"),
            "Side": str(t.side).upper(),
            "Entry": f"${t.entry_price:.2f}",
            "Exit": f"${t.exit_price:.2f}",
            "P&L": f"${t.pnl:.2f}",
            "P&L %": f"{t.pnl_pct:.2f}%",
            "Bars": t.bars_held,
            "Model": t.entry_comment or "N/A",
            "Exit": t.reason.upper()
        })

    df = pd.DataFrame(trades_data)

    # Color-code P&L
    def color_pnl(val):
        if isinstance(val, str) and '$' in val:
            num = float(val.replace('$', '').replace(',', ''))
            color = 'color: #26a69a' if num > 0 else 'color: #ef5350'
            return color
        return ''

    styled_df = df.style.applymap(color_pnl, subset=['P&L', 'P&L %'])

    st.dataframe(styled_df, use_container_width=True, height=400)


# ========== Main App ==========
def main():
    st.title("📈 FX Replay - Backtest Dashboard")
    st.caption("Professional backtesting interface powered by Numba-accelerated engine")

    # Sidebar - Controls
    with st.sidebar:
        st.header("⚙️ Backtest Settings")

        symbol = st.selectbox("Symbol", ["XAUUSD", "EURUSD", "GBPUSD", "USDJPY"], index=0)

        timeframe = st.selectbox("Timeframe", ["M5", "M15", "M30", "H1", "H4"], index=0)

        from_date = st.date_input("From Date", value=datetime(2026, 1, 1))
        to_date = st.date_input("To Date", value=datetime(2026, 2, 10))

        st.divider()

        st.subheader("Risk Settings")
        risk_pct = st.slider("Risk per Trade (%)", 0.1, 2.0, 0.5, 0.1)
        account_size = st.number_input("Account Size ($)", 10000, 1000000, 50000, 10000)

        st.divider()

        run_backtest = st.button("🚀 Run Backtest", type="primary", use_container_width=True)

    # Convert dates to UTC datetime
    from_dt = datetime.combine(from_date, datetime.min.time()).replace(tzinfo=timezone.utc)
    to_dt = datetime.combine(to_date, datetime.max.time()).replace(tzinfo=timezone.utc)

    # Config
    config = BacktestConfig(
        symbol=symbol,
        timeframe=timeframe,
        tick_size=0.01 if "XAU" in symbol else 0.00001,
        pip_size=0.01 if "XAU" in symbol else 0.0001,
        start_date=from_dt,
        end_date=to_dt,
        account_size_usd=float(account_size),
        risk_per_trade_pct=float(risk_pct),
    )

    # Run backtest
    if run_backtest or "backtest_results" not in st.session_state:
        with st.spinner("Running backtest... This may take a moment."):
            candles, trades, summary, engine = load_backtest_data(
                symbol, from_dt, to_dt, timeframe, config
            )

            if candles is not None:
                st.session_state["backtest_results"] = {
                    "candles": candles,
                    "trades": trades,
                    "summary": summary,
                    "engine": engine
                }

    # Display results
    if "backtest_results" in st.session_state:
        results = st.session_state["backtest_results"]
        candles = results["candles"]
        trades = results["trades"]
        summary = results["summary"]

        # Metrics
        st.subheader("📊 Performance Metrics")
        render_metrics(summary)

        st.divider()

        # Chart
        st.subheader(f"📈 {symbol} Chart - {timeframe}")
        chart_data = prepare_chart_data(candles, trades)
        render_chart(chart_data, symbol)

        st.divider()

        # Trades Table
        st.subheader("📋 Trade History")
        render_trades_table(trades)

        # Performance details
        with st.expander("🔍 Detailed Statistics"):
            col1, col2 = st.columns(2)

            with col1:
                st.write("**Returns**")
                st.write(f"Net Profit: ${summary.get('net_profit', 0):,.2f}")
                st.write(f"ROI: {summary.get('roi_pct', 0):.2f}%")
                st.write(f"Sharpe Ratio: {summary.get('sharpe_ratio', 0):.2f}")

            with col2:
                st.write("**Risk Metrics**")
                st.write(f"Max Drawdown: {summary.get('max_drawdown_pct', 0):.2f}%")
                st.write(f"Avg Win: ${summary.get('avg_win', 0):,.2f}")
                st.write(f"Avg Loss: ${summary.get('avg_loss', 0):,.2f}")


if __name__ == "__main__":
    main()
