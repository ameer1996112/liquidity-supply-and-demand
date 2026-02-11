#!/usr/bin/env python3
"""
Create TradingView-style interactive HTML chart from backtest results.

Uses Plotly with TradingView-inspired styling.
"""
import sys
from pathlib import Path
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

sys.path.insert(0, str(Path(__file__).parent.parent))

def create_tv_style_chart(candles_csv: Path, trades_csv: Path, output_html: Path = None):
    """Create TradingView-style interactive chart."""

    # Load data
    candles = pd.read_parquet("data/backtest_candles/XAUUSD/M5/2025-01-01_2026-02-10.parquet")
    candles['time'] = pd.to_datetime(candles['time'])

    # Filter to backtest date range
    candles = candles[(candles['time'] >= '2026-01-01') & (candles['time'] <= '2026-01-10')]

    trades = pd.read_csv(trades_csv)
    trades['entry_time'] = pd.to_datetime(trades['entry_time'])
    trades['exit_time'] = pd.to_datetime(trades['exit_time'])

    print(f"📊 Creating chart with {len(candles)} candles and {len(trades)} trades...")

    # Create figure with TradingView dark theme
    fig = make_subplots(
        rows=2, cols=1,
        shared_xaxes=True,
        vertical_spacing=0.03,
        subplot_titles=('Price', 'Equity Curve'),
        row_heights=[0.7, 0.3],
    )

    # Candlestick chart
    fig.add_trace(
        go.Candlestick(
            x=candles['time'],
            open=candles['open'],
            high=candles['high'],
            low=candles['low'],
            close=candles['close'],
            name='XAUUSD',
            increasing_line_color='#089981',  # TradingView green
            decreasing_line_color='#F23645',  # TradingView red
            increasing_fillcolor='#089981',
            decreasing_fillcolor='#F23645',
        ),
        row=1, col=1
    )

    # Add trade markers
    for _, trade in trades.iterrows():
        # Entry marker
        color = '#2962FF' if trade['side'] == 'long' else '#F23645'
        symbol = 'triangle-up' if trade['side'] == 'long' else 'triangle-down'

        fig.add_trace(
            go.Scatter(
                x=[trade['entry_time']],
                y=[trade['entry_price']],
                mode='markers',
                marker=dict(
                    size=15,
                    color=color,
                    symbol=symbol,
                    line=dict(width=2, color='white')
                ),
                name=f"{trade['side'].upper()} Entry",
                showlegend=False,
                hovertemplate=f"<b>ENTRY {trade['side'].upper()}</b><br>" +
                              f"Price: {trade['entry_price']:.2f}<br>" +
                              f"SL: {trade['stop_price']:.2f}<br>" +
                              f"TP: {trade['limit_price']:.2f}<br>" +
                              "<extra></extra>",
            ),
            row=1, col=1
        )

        # Exit marker
        exit_color = '#089981' if trade['pnl'] > 0 else '#F23645'

        fig.add_trace(
            go.Scatter(
                x=[trade['exit_time']],
                y=[trade['exit_price']],
                mode='markers',
                marker=dict(
                    size=12,
                    color=exit_color,
                    symbol='circle',
                    line=dict(width=2, color='white')
                ),
                name=f"Exit ({trade['reason']})",
                showlegend=False,
                hovertemplate=f"<b>EXIT ({trade['reason'].upper()})</b><br>" +
                              f"Price: {trade['exit_price']:.2f}<br>" +
                              f"PnL: ${trade['pnl']:.2f}<br>" +
                              "<extra></extra>",
            ),
            row=1, col=1
        )

        # Connect entry to exit with line
        fig.add_trace(
            go.Scatter(
                x=[trade['entry_time'], trade['exit_time']],
                y=[trade['entry_price'], trade['exit_price']],
                mode='lines',
                line=dict(
                    color=exit_color,
                    width=1,
                    dash='dot'
                ),
                showlegend=False,
                hoverinfo='skip',
            ),
            row=1, col=1
        )

        # SL/TP zones
        if pd.notna(trade['stop_price']):
            fig.add_shape(
                type="line",
                x0=trade['entry_time'],
                x1=trade['exit_time'],
                y0=trade['stop_price'],
                y1=trade['stop_price'],
                line=dict(color='#F23645', width=1, dash='dash'),
                row=1, col=1
            )

        if pd.notna(trade['limit_price']):
            fig.add_shape(
                type="line",
                x0=trade['entry_time'],
                x1=trade['exit_time'],
                y0=trade['limit_price'],
                y1=trade['limit_price'],
                line=dict(color='#089981', width=1, dash='dash'),
                row=1, col=1
            )

    # Equity curve
    if len(trades) > 0:
        trades_sorted = trades.sort_values('exit_time')
        cumulative_pnl = trades_sorted['pnl'].cumsum()

        fig.add_trace(
            go.Scatter(
                x=trades_sorted['exit_time'],
                y=cumulative_pnl,
                mode='lines',
                name='Equity',
                line=dict(color='#2962FF', width=2),
                fill='tozeroy',
                fillcolor='rgba(41, 98, 255, 0.1)',
            ),
            row=2, col=1
        )

    # TradingView-style layout
    fig.update_layout(
        title={
            'text': f'XAUUSD M5 Backtest - {len(trades)} Trades | PnL: ${trades["pnl"].sum():.2f}',
            'font': {'size': 20, 'color': '#D1D4DC'}
        },
        plot_bgcolor='#131722',  # TradingView dark background
        paper_bgcolor='#0D0F14',
        font=dict(color='#D1D4DC', family='Trebuchet MS'),
        xaxis_rangeslider_visible=False,
        hovermode='x unified',
        height=900,
        showlegend=False,
    )

    # Style axes
    fig.update_xaxes(
        gridcolor='#1E222D',
        showgrid=True,
        zeroline=False,
        tickfont=dict(color='#787B86'),
    )

    fig.update_yaxes(
        gridcolor='#1E222D',
        showgrid=True,
        zeroline=False,
        tickfont=dict(color='#787B86'),
        side='right',  # TradingView puts price on right
    )

    # Save
    if output_html is None:
        output_html = Path("data/backtest/XAUUSD/tradingview_chart.html")

    fig.write_html(output_html)

    print(f"✅ Created TradingView-style chart")
    print(f"📁 File: {output_html}")
    print(f"\n🌐 Open in browser:")
    print(f"   open {output_html}")

    return fig

if __name__ == "__main__":
    trades_file = Path("data/backtest/XAUUSD/trades.csv")

    if not trades_file.exists():
        print(f"❌ Trades file not found: {trades_file}")
        print(f"   Run backtest first:")
        print(f"   python scripts/backtest_tv_settings.py --no-trade-limit --no-htf-flip")
        sys.exit(1)

    create_tv_style_chart(None, trades_file)
