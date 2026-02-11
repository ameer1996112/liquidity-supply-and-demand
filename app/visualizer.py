"""
TradingView-quality backtest visualizer using Streamlit + lightweight-charts.

Features:
- Interactive candlestick charts with zoom/pan
- Trade markers (entry/exit) with color-coded PnL
- Zone visualization (demand/supply rectangles)
- SL/TP shaded boxes
- Performance metrics dashboard
- Multi-tab layout (Chart, Analytics, Optimization)

Usage:
    cd /path/to/trading && streamlit run app/visualizer.py
"""

from __future__ import annotations

import sys
from pathlib import Path

# Ensure project root is on path when run via streamlit run app/visualizer.py
_root = Path(__file__).resolve().parent.parent
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))

import time
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import List, Optional
import logging

import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from app.config import BacktestConfig
from app.data import get_candles

# FastBacktestEngine requires numba; numba can fail with coverage<7.6.1
# Fall back to standard engine when FastBacktestEngine is unavailable
try:
    from app.engine_core import FastBacktestEngine
    _FAST_ENGINE_AVAILABLE = True
except (ImportError, AttributeError) as e:
    _FAST_ENGINE_AVAILABLE = False
    _FAST_ENGINE_ERROR = str(e)  # e.g. numba/coverage incompatibility

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# ========== Page Configuration ==========

st.set_page_config(
    page_title="SND Backtester Pro",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)


# ========== Helper Functions ==========

def generate_sample_candles(n_bars: int = 1000, symbol: str = "XAUUSD") -> pd.DataFrame:
    """Generate synthetic candle data for quick testing."""
    start_time = datetime(2026, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
    base_price = 2000.0 if "XAU" in symbol else 1.1000
    volatility = 10.0 if "XAU" in symbol else 0.0010

    times, opens, highs, lows, closes = [], [], [], [], []
    current_price = base_price
    current_time = start_time

    for i in range(n_bars):
        change = np.random.randn() * volatility
        open_price = current_price
        close_price = current_price + change
        high_price = max(open_price, close_price) + abs(np.random.randn() * volatility * 0.3)
        low_price = min(open_price, close_price) - abs(np.random.randn() * volatility * 0.3)

        times.append(current_time)
        opens.append(open_price)
        highs.append(high_price)
        lows.append(low_price)
        closes.append(close_price)

        current_price = close_price
        current_time += timedelta(minutes=5)

    return pd.DataFrame({
        'time': times,
        'open': opens,
        'high': highs,
        'low': lows,
        'close': closes,
        'volume': [100] * n_bars,
    })


def compute_metrics(trades: list) -> dict:
    """Calculate performance metrics from trades."""
    if not trades:
        return {
            'net_profit': 0.0,
            'gross_profit': 0.0,
            'gross_loss': 0.0,
            'win_count': 0,
            'loss_count': 0,
            'total_trades': 0,
            'win_rate': 0.0,
            'profit_factor': 0.0,
            'avg_trade': 0.0,
            'avg_win': 0.0,
            'avg_loss': 0.0,
            'sharpe_ratio': 0.0,
            'max_drawdown': 0.0,
            'max_drawdown_pct': 0.0,
        }

    wins = [t for t in trades if t.pnl > 0]
    losses = [t for t in trades if t.pnl < 0]

    gross_profit = sum(t.pnl for t in wins)
    gross_loss = abs(sum(t.pnl for t in losses))
    net_profit = gross_profit - gross_loss

    profit_factor = gross_profit / gross_loss if gross_loss > 0 else (float('inf') if gross_profit > 0 else 0.0)

    # Sharpe ratio (simplified: returns / std)
    returns = [t.pnl for t in trades]
    sharpe = (np.mean(returns) / np.std(returns) * np.sqrt(252)) if len(returns) > 1 and np.std(returns) > 0 else 0.0

    # Max drawdown
    equity_curve = np.cumsum([t.pnl for t in trades])
    running_max = np.maximum.accumulate(equity_curve)
    drawdown = running_max - equity_curve
    max_drawdown = np.max(drawdown) if len(drawdown) > 0 else 0.0
    max_drawdown_pct = (max_drawdown / running_max[np.argmax(drawdown)]) * 100 if np.argmax(drawdown) < len(running_max) and running_max[np.argmax(drawdown)] > 0 else 0.0

    return {
        'net_profit': net_profit,
        'gross_profit': gross_profit,
        'gross_loss': gross_loss,
        'win_count': len(wins),
        'loss_count': len(losses),
        'total_trades': len(trades),
        'win_rate': (len(wins) / len(trades) * 100) if trades else 0.0,
        'profit_factor': profit_factor,
        'avg_trade': net_profit / len(trades) if trades else 0.0,
        'avg_win': gross_profit / len(wins) if wins else 0.0,
        'avg_loss': -gross_loss / len(losses) if losses else 0.0,
        'sharpe_ratio': sharpe,
        'max_drawdown': max_drawdown,
        'max_drawdown_pct': max_drawdown_pct,
    }


def create_candlestick_chart(candles_df: pd.DataFrame, trades: list) -> go.Figure:
    """
    Create interactive candlestick chart with trade markers.

    Uses Plotly for rich interactivity (lightweight-charts-python requires more setup).
    """
    fig = go.Figure()

    # Candlestick
    fig.add_trace(go.Candlestick(
        x=candles_df['time'],
        open=candles_df['open'],
        high=candles_df['high'],
        low=candles_df['low'],
        close=candles_df['close'],
        name='Price',
        increasing_line_color='#26a69a',
        decreasing_line_color='#ef5350',
    ))

    # Trade entry markers
    if trades:
        entry_times = [t.entry_time for t in trades]
        entry_prices = [t.entry_price for t in trades]
        entry_colors = ['green' if t.side.value == 'long' else 'red' for t in trades]
        entry_symbols = ['triangle-up' if t.side.value == 'long' else 'triangle-down' for t in trades]
        entry_labels = [f"{t.side.value.upper()} {t.entry_comment}<br>Entry: ${t.entry_price:.2f}" for t in trades]

        fig.add_trace(go.Scatter(
            x=entry_times,
            y=entry_prices,
            mode='markers',
            marker=dict(size=12, color=entry_colors, symbol=entry_symbols, line=dict(width=1, color='white')),
            text=entry_labels,
            hoverinfo='text',
            name='Entries',
        ))

        # Trade exit markers
        exit_times = [t.exit_time for t in trades]
        exit_prices = [t.exit_price for t in trades]
        exit_colors = ['green' if t.pnl > 0 else 'red' for t in trades]
        exit_labels = [f"Exit: ${t.exit_price:.2f}<br>PnL: ${t.pnl:.2f} ({t.pnl_pct:.1f}%)<br>{t.reason.upper()}" for t in trades]

        fig.add_trace(go.Scatter(
            x=exit_times,
            y=exit_prices,
            mode='markers',
            marker=dict(size=10, color=exit_colors, symbol='circle', line=dict(width=1, color='white')),
            text=exit_labels,
            hoverinfo='text',
            name='Exits',
        ))

        # SL/TP lines for each trade (shaded rectangles)
        for t in trades:
            # SL box (red shaded)
            if t.stop_price > 0:
                fig.add_shape(
                    type="rect",
                    x0=t.entry_time,
                    x1=t.exit_time,
                    y0=t.stop_price,
                    y1=t.entry_price if t.side.value == 'long' else t.stop_price,
                    fillcolor="red",
                    opacity=0.1,
                    line=dict(width=0),
                    layer="below",
                )

            # TP box (green shaded)
            if t.limit_price is not None and t.limit_price > 0:
                fig.add_shape(
                    type="rect",
                    x0=t.entry_time,
                    x1=t.exit_time,
                    y0=t.entry_price if t.side.value == 'long' else t.limit_price,
                    y1=t.limit_price if t.side.value == 'long' else t.entry_price,
                    fillcolor="green",
                    opacity=0.1,
                    line=dict(width=0),
                    layer="below",
                )

    # Layout: 5m candles need readable bar spacing
    n_bars = len(candles_df)
    # Show last ~500 bars by default (c. 3.5 days of 5m data) so bars are distinct
    max_bars_visible = 500
    if n_bars > max_bars_visible:
        x_start = candles_df['time'].iloc[-max_bars_visible]
        x_end = candles_df['time'].iloc[-1]
    else:
        x_start = candles_df['time'].iloc[0]
        x_end = candles_df['time'].iloc[-1]

    fig.update_layout(
        title="Price Chart with Trades (5m)",
        xaxis_title="Time",
        yaxis_title="Price",
        height=600,
        hovermode='x unified',
        xaxis_rangeslider_visible=True,
        xaxis_range=[x_start, x_end],
        template="plotly_dark",
    )

    return fig


def create_equity_curve(trades: list, initial_equity: float = 50000) -> go.Figure:
    """Create equity curve chart."""
    if not trades:
        return go.Figure()

    times = [t.exit_time for t in trades]
    pnls = [t.pnl for t in trades]
    equity = [initial_equity + sum(pnls[:i+1]) for i in range(len(pnls))]

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=times,
        y=equity,
        mode='lines',
        name='Equity',
        line=dict(color='#26a69a', width=2),
        fill='tozeroy',
        fillcolor='rgba(38, 166, 154, 0.2)',
    ))

    fig.update_layout(
        title="Equity Curve",
        xaxis_title="Time",
        yaxis_title="Equity ($)",
        height=400,
        template="plotly_dark",
    )

    return fig


def create_drawdown_chart(trades: list) -> go.Figure:
    """Create drawdown chart."""
    if not trades:
        return go.Figure()

    pnls = [t.pnl for t in trades]
    equity_curve = np.cumsum(pnls)
    running_max = np.maximum.accumulate(equity_curve)
    drawdown = running_max - equity_curve
    drawdown_pct = (drawdown / running_max) * 100

    times = [t.exit_time for t in trades]

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=times,
        y=drawdown_pct,
        mode='lines',
        name='Drawdown %',
        line=dict(color='#ef5350', width=2),
        fill='tozeroy',
        fillcolor='rgba(239, 83, 80, 0.2)',
    ))

    fig.update_layout(
        title="Drawdown %",
        xaxis_title="Time",
        yaxis_title="Drawdown (%)",
        height=400,
        template="plotly_dark",
    )

    return fig


# ========== Main Application ==========

def main():
    st.title("📊 SND Backtester Pro")
    st.caption("High-Performance Backtesting with TradingView-Quality Visualization")

    # ========== Sidebar: Configuration ==========
    with st.sidebar:
        st.header("⚙️ Configuration")

        # Symbol & Timeframe
        symbol = st.selectbox("Symbol", ["XAUUSD", "EURUSD", "GBPUSD", "BTCUSD"], index=0)
        timeframe = st.selectbox("Timeframe", ["M5", "M15", "H1", "H4", "D1"], index=0)

        # Date range
        st.subheader("Date Range")
        from_date = st.date_input("From", datetime(2026, 1, 1))
        to_date = st.date_input("To", datetime(2026, 1, 10))

        # Risk settings
        st.subheader("Risk Settings")
        risk_pct = st.slider("Risk per Trade (%)", 0.1, 2.0, 0.5, 0.1)
        sl_buffer = st.slider("SL Buffer (pips)", 0.5, 5.0, 1.0, 0.5)
        tp_ratio = st.slider("TP Ratio (R:R)", 1.0, 5.0, 2.0, 0.5)

        # Filters
        st.subheader("Filters")
        quality_threshold = st.slider("AI Quality Threshold", 0, 100, 70, 5)
        require_htf_flip = st.checkbox("Require HTF FLIP", value=False)
        enable_trade_limit = st.checkbox("Enable Daily Trade Limit", value=False)
        max_trades_per_day = st.number_input("Max Trades Per Day", min_value=1, max_value=20, value=2) if enable_trade_limit else 100

        st.subheader("Entry Models")
        enable_flip = st.checkbox("FLIP", value=True)
        enable_break = st.checkbox("BREAK_CANDLE", value=True)
        enable_dir = st.checkbox("DIR_CLOSE", value=True)

        # Data source
        st.subheader("Data Source")
        use_sample_data = st.checkbox("Use Sample Data (for testing)", value=True)

        # Run button
        run_backtest = st.button("🚀 Run Backtest", type="primary", use_container_width=True)

    # ========== Main Content ==========
    if run_backtest:
        # Progress bar
        progress_bar = st.progress(0, text="Loading data...")

        # Create config
        config = BacktestConfig(
            symbol=symbol,
            timeframe=timeframe,
            tick_size=0.01 if "XAU" in symbol else 0.00001,
            pip_size=0.01 if "XAU" in symbol else 0.0001,
            risk_per_trade_pct=risk_pct,
            stop_loss_buffer_pips=sl_buffer,
            risk_reward_ratio=tp_ratio,
            use_custom_rr=True,
            ai_quality_threshold=quality_threshold,
            require_htf_flip=require_htf_flip,
            enable_trade_limit=enable_trade_limit,
            max_trades_per_day=max_trades_per_day,
            account_size_usd=50000.0,
            start_date=datetime.combine(from_date, datetime.min.time()).replace(tzinfo=timezone.utc),
            end_date=datetime.combine(to_date, datetime.min.time()).replace(tzinfo=timezone.utc),
        )

        # Load data
        progress_bar.progress(20, text="Loading candle data...")
        if use_sample_data:
            candles_df = generate_sample_candles(n_bars=1000, symbol=symbol)
            st.info(f"📊 Using sample data: {len(candles_df)} bars")
        else:
            try:
                candles_df = get_candles(
                    symbol=symbol,
                    from_date=config.start_date,
                    to_date=config.end_date,
                    timeframe=timeframe,
                    data_dir=Path("data/backtest_candles"),
                    metaapi_token=None,  # Use local only for now
                    metaapi_account_id=None,
                    symbol_aliases={},
                    persist=False,
                )
                st.success(f"✅ Loaded {len(candles_df)} bars from local file")
            except Exception as e:
                st.error(f"Failed to load data: {e}")
                st.info("💡 Try enabling 'Use Sample Data' for testing")
                return

        # Run backtest
        progress_bar.progress(50, text="Running backtest...")

        start_time = time.time()
        if _FAST_ENGINE_AVAILABLE:
            engine = FastBacktestEngine(config=config)
            trades = engine.run(candles_df)
            perf = engine.get_performance_summary()
        else:
            from app.engine import BacktestEngine
            from app.snd_strategy import SNDStrategy

            engine = BacktestEngine(
                tick_size=config.tick_size,
                slippage_ticks=3,
                initial_equity=config.account_size_usd,
                max_bars_held=config.max_bars_held,
            )
            strategy = SNDStrategy(config=config)

            def on_bar(bar_idx: int, bar, history, has_position: bool):
                return strategy.on_bar(bar_idx, bar, history, has_position)

            trades = engine.run(candles_df, on_bar)
            runtime_sec = time.time() - start_time
            perf = {"bars_per_second": len(candles_df) / runtime_sec if runtime_sec > 0 else 0, "speedup_estimate": 1.0}

        runtime = time.time() - start_time

        progress_bar.progress(100, text="Complete!")
        st.success(f"✅ Backtest complete in **{runtime:.2f}s** ({len(trades)} trades)")
        if not _FAST_ENGINE_AVAILABLE:
            st.warning("⚠️ Using standard engine (Numba unavailable). For faster runs: `pip install coverage>=7.6.1`")

        # Performance metrics
        st.metric(
            label="🚀 Performance",
            value=f"{perf['bars_per_second']:.0f} bars/sec",
            delta=f"{perf['speedup_estimate']:.1f}x faster than legacy" if _FAST_ENGINE_AVAILABLE else "standard engine"
        )

        # ========== Tabs ==========
        tab1, tab2, tab3 = st.tabs(["📈 Chart & Trades", "📊 Analytics", "🔧 Optimization"])

        with tab1:
            st.subheader("Performance Summary")

            # Metrics
            metrics = compute_metrics(trades)
            col1, col2, col3, col4, col5 = st.columns(5)

            col1.metric("Net Profit", f"${metrics['net_profit']:,.0f}")
            col2.metric("Win Rate", f"{metrics['win_rate']:.1f}%")
            col3.metric("Profit Factor", f"{metrics['profit_factor']:.2f}" if metrics['profit_factor'] < 999 else "∞")
            col4.metric("Total Trades", metrics['total_trades'])
            col5.metric("Sharpe Ratio", f"{metrics['sharpe_ratio']:.2f}")

            col6, col7, col8, col9, col10 = st.columns(5)
            col6.metric("Gross Profit", f"${metrics['gross_profit']:,.0f}")
            col7.metric("Gross Loss", f"${metrics['gross_loss']:,.0f}")
            col8.metric("Avg Win", f"${metrics['avg_win']:,.0f}")
            col9.metric("Avg Loss", f"${metrics['avg_loss']:,.0f}")
            col10.metric("Max DD %", f"{metrics['max_drawdown_pct']:.1f}%")

            # Chart
            st.subheader("Price Chart with Trades")
            fig = create_candlestick_chart(candles_df, trades)
            st.plotly_chart(fig, use_container_width=True)

            # Trade list
            st.subheader("Trade List")
            if trades:
                trades_df = pd.DataFrame([{
                    'Entry Time': t.entry_time,
                    'Exit Time': t.exit_time,
                    'Side': t.side.value.upper(),
                    'Entry Model': t.entry_comment,
                    'Entry Price': f"${t.entry_price:.2f}",
                    'Exit Price': f"${t.exit_price:.2f}",
                    'PnL': f"${t.pnl:.2f}",
                    'PnL %': f"{t.pnl_pct:.2f}%",
                    'Bars Held': t.bars_held,
                    'Exit': t.reason.upper(),
                } for t in trades])

                st.dataframe(trades_df, use_container_width=True, height=400)
            else:
                st.info("No trades generated. Try adjusting filters or date range.")

        with tab2:
            st.subheader("Performance Analytics")

            if trades:
                # Equity curve
                fig_equity = create_equity_curve(trades, initial_equity=config.account_size_usd)
                st.plotly_chart(fig_equity, use_container_width=True)

                # Drawdown
                fig_dd = create_drawdown_chart(trades)
                st.plotly_chart(fig_dd, use_container_width=True)

                # Win/Loss distribution
                st.subheader("Trade Distribution")
                col1, col2 = st.columns(2)

                with col1:
                    pnls = [t.pnl for t in trades]
                    fig_hist = go.Figure(data=[go.Histogram(x=pnls, nbinsx=20)])
                    fig_hist.update_layout(
                        title="PnL Distribution",
                        xaxis_title="PnL ($)",
                        yaxis_title="Count",
                        height=350,
                        template="plotly_dark"
                    )
                    st.plotly_chart(fig_hist, use_container_width=True)

                with col2:
                    # Entry model breakdown
                    entry_models = [t.entry_comment for t in trades if t.entry_comment]
                    if entry_models:
                        model_counts = pd.Series(entry_models).value_counts()
                        fig_pie = go.Figure(data=[go.Pie(labels=model_counts.index, values=model_counts.values)])
                        fig_pie.update_layout(
                            title="Entry Models",
                            height=350,
                            template="plotly_dark"
                        )
                        st.plotly_chart(fig_pie, use_container_width=True)
            else:
                st.info("No trades to analyze.")

        with tab3:
            st.subheader("🔧 Optimization (Coming Soon)")
            st.info("Walk-forward analysis and Bayesian optimization will be available in this tab.")

            st.markdown("""
            **Planned Features:**
            - Walk-Forward Analysis (rolling window optimization)
            - Bayesian Optimization with Optuna (find best parameters)
            - Parameter heatmaps (2D sensitivity analysis)
            - Robustness testing (Monte Carlo)
            """)


if __name__ == "__main__":
    main()
