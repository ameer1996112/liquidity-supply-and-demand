#!/usr/bin/env python3
"""
Create professional FX Replay / TradingView style chart.

Clean, minimal design with:
- Pure candlestick chart (no clutter)
- Trade markers on separate axis
- Clean equity curve
- Professional dark theme
"""
import sys
from pathlib import Path
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

sys.path.insert(0, str(Path(__file__).parent.parent))

def create_professional_chart(trades_csv: Path, output_html: Path = None):
    """Create clean professional chart like FX Replay."""

    # Load data
    candles = pd.read_parquet("data/backtest_candles/XAUUSD/M5/2025-01-01_2026-02-10.parquet")
    candles['time'] = pd.to_datetime(candles['time'])
    candles = candles[(candles['time'] >= '2026-01-01') & (candles['time'] <= '2026-01-10')]

    trades = pd.read_csv(trades_csv)
    trades['entry_time'] = pd.to_datetime(trades['entry_time'])
    trades['exit_time'] = pd.to_datetime(trades['exit_time'])

    wins = trades[trades['pnl'] > 0]
    losses = trades[trades['pnl'] <= 0]

    print(f"📊 Creating professional chart...")
    print(f"   {len(candles)} candles | {len(trades)} trades ({len(wins)}W {len(losses)}L)")

    # Create figure with 3 rows: Price, Trades Timeline, Equity
    fig = make_subplots(
        rows=3, cols=1,
        shared_xaxes=True,
        vertical_spacing=0.02,
        row_heights=[0.6, 0.15, 0.25],
        subplot_titles=('', '', ''),
    )

    # ========== ROW 1: CLEAN CANDLESTICK CHART ==========
    fig.add_trace(
        go.Candlestick(
            x=candles['time'],
            open=candles['open'],
            high=candles['high'],
            low=candles['low'],
            close=candles['close'],
            name='',
            increasing_line_color='#26a69a',  # Professional green
            decreasing_line_color='#ef5350',  # Professional red
            increasing_fillcolor='#26a69a',
            decreasing_fillcolor='#ef5350',
            line=dict(width=1),
        ),
        row=1, col=1
    )

    # Add MINIMAL trade markers (only entry points, small and subtle)
    if len(trades) > 0:
        # Long entries (subtle green triangles)
        long_entries = trades[trades['side'] == 'long']
        if len(long_entries) > 0:
            fig.add_trace(
                go.Scatter(
                    x=long_entries['entry_time'],
                    y=long_entries['entry_price'],
                    mode='markers',
                    marker=dict(
                        size=8,
                        color='rgba(38, 166, 154, 0.7)',
                        symbol='triangle-up',
                        line=dict(width=1, color='white')
                    ),
                    name='Long',
                    hovertemplate='Long Entry<br>%{y:.2f}<extra></extra>',
                ),
                row=1, col=1
            )

        # Short entries (subtle red triangles)
        short_entries = trades[trades['side'] == 'short']
        if len(short_entries) > 0:
            fig.add_trace(
                go.Scatter(
                    x=short_entries['entry_time'],
                    y=short_entries['entry_price'],
                    mode='markers',
                    marker=dict(
                        size=8,
                        color='rgba(239, 83, 80, 0.7)',
                        symbol='triangle-down',
                        line=dict(width=1, color='white')
                    ),
                    name='Short',
                    hovertemplate='Short Entry<br>%{y:.2f}<extra></extra>',
                ),
                row=1, col=1
            )

    # ========== ROW 2: TRADE PERFORMANCE BARS ==========
    # Show each trade as a colored bar (green=win, red=loss)
    if len(trades) > 0:
        colors = ['#26a69a' if pnl > 0 else '#ef5350' for pnl in trades['pnl']]

        fig.add_trace(
            go.Bar(
                x=trades['exit_time'],
                y=trades['pnl'],
                marker_color=colors,
                name='Trade PnL',
                hovertemplate='PnL: $%{y:.2f}<br>%{x}<extra></extra>',
            ),
            row=2, col=1
        )

    # ========== ROW 3: CLEAN EQUITY CURVE ==========
    if len(trades) > 0:
        trades_sorted = trades.sort_values('exit_time')
        cumulative_pnl = trades_sorted['pnl'].cumsum()

        # Equity line
        fig.add_trace(
            go.Scatter(
                x=trades_sorted['exit_time'],
                y=cumulative_pnl,
                mode='lines',
                name='Equity',
                line=dict(color='#2962FF', width=2),
                fill='tozeroy',
                fillcolor='rgba(41, 98, 255, 0.1)',
                hovertemplate='Equity: $%{y:.2f}<extra></extra>',
            ),
            row=3, col=1
        )

        # Add zero line
        fig.add_hline(y=0, line_dash="dash", line_color="gray", opacity=0.5, row=3, col=1)

    # ========== PROFESSIONAL STYLING ==========
    net_pnl = trades['pnl'].sum() if len(trades) > 0 else 0
    win_rate = (len(wins) / len(trades) * 100) if len(trades) > 0 else 0

    fig.update_layout(
        title={
            'text': f'<b>XAUUSD M5 Backtest</b><br>' +
                    f'<span style="font-size:14px">Trades: {len(trades)} ({len(wins)}W-{len(losses)}L) | ' +
                    f'Win Rate: {win_rate:.1f}% | ' +
                    f'PnL: <span style="color:{"#26a69a" if net_pnl > 0 else "#ef5350"}">${net_pnl:.2f}</span></span>',
            'x': 0.5,
            'xanchor': 'center',
            'font': {'size': 18, 'color': '#e0e3eb'}
        },

        # TradingView dark theme
        plot_bgcolor='#1e222d',
        paper_bgcolor='#131722',
        font=dict(color='#d1d4dc', family='Trebuchet MS, sans-serif', size=11),

        # Remove clutter
        showlegend=False,
        hovermode='x unified',
        height=1000,

        # Clean margins
        margin=dict(l=10, r=10, t=80, b=10),
    )

    # Style all axes uniformly
    for i in range(1, 4):
        fig.update_xaxes(
            gridcolor='#2a2e39',
            showgrid=True,
            zeroline=False,
            tickfont=dict(color='#787b86', size=10),
            row=i, col=1
        )

        fig.update_yaxes(
            gridcolor='#2a2e39',
            showgrid=True,
            zeroline=False,
            tickfont=dict(color='#787b86', size=10),
            side='right',  # Price on right like TradingView
            row=i, col=1
        )

    # Remove range slider (cleaner)
    fig.update_xaxes(rangeslider_visible=False, row=1, col=1)

    # Row labels
    fig.update_yaxes(title_text="Price", title_font=dict(size=12), row=1, col=1)
    fig.update_yaxes(title_text="PnL", title_font=dict(size=12), row=2, col=1)
    fig.update_yaxes(title_text="Equity", title_font=dict(size=12), row=3, col=1)

    # Save
    if output_html is None:
        output_html = Path("data/backtest/XAUUSD/professional_chart.html")

    fig.write_html(
        output_html,
        config={
            'displayModeBar': True,
            'modeBarButtonsToRemove': ['lasso2d', 'select2d'],
            'displaylogo': False,
        }
    )

    print(f"✅ Created professional chart")
    print(f"📁 {output_html}")
    print(f"\n🌐 Open in browser:")
    print(f"   open {output_html}")

    return fig

if __name__ == "__main__":
    trades_file = Path("data/backtest/XAUUSD/trades.csv")

    if not trades_file.exists():
        print(f"❌ No trades found. Run backtest first:")
        print(f"   python scripts/backtest_tv_settings.py --no-trade-limit --no-htf-flip")
        sys.exit(1)

    create_professional_chart(trades_file)
