"""
Ultra-Clean TradingView-Style Chart using Plotly.

Creates professional charts with:
- Proper filled zone rectangles (like TradingView)
- Clean candlesticks
- Entry/exit annotations
- Minimal clutter

Usage:
  python -m app.backtest_chart_clean --from 2026-01-01 --to 2026-02-10
"""

from __future__ import annotations

import argparse
import webbrowser
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots


def load_candles(symbol: str, from_date: datetime, to_date: datetime, data_dir: Path, timeframe: str = "M5") -> pd.DataFrame:
    """Load candles from local file."""
    from_str = from_date.strftime("%Y-%m-%d")
    to_str = to_date.strftime("%Y-%m-%d")

    # Try exact match first
    for ext in [".csv", ".parquet"]:
        path = data_dir / symbol / timeframe / f"{from_str}_{to_str}{ext}"
        if path.exists():
            df = pd.read_csv(path) if ext == ".csv" else pd.read_parquet(path)
            df["time"] = pd.to_datetime(df["time"], utc=True)
            df = df[(df["time"] >= from_date) & (df["time"] <= to_date)].sort_values("time")
            return df

    # Try any file that contains the range
    candle_dir = data_dir / symbol / timeframe
    if candle_dir.exists():
        for file in list(candle_dir.glob("*.csv")) + list(candle_dir.glob("*.parquet")):
            df = pd.read_csv(file) if file.suffix == ".csv" else pd.read_parquet(file)
            df["time"] = pd.to_datetime(df["time"], utc=True)
            df = df[(df["time"] >= from_date) & (df["time"] <= to_date)].sort_values("time")
            if len(df) > 0:
                return df

    raise FileNotFoundError(f"No candle data found for {symbol} {timeframe}")


def load_trades(out_dir: Path, symbol: str) -> pd.DataFrame:
    """Load trades from backtest output."""
    path = out_dir / symbol / "trades.csv"
    if not path.exists():
        raise FileNotFoundError(f"No trades at {path}. Run backtest first.")
    df = pd.read_csv(path)
    df["entry_time"] = pd.to_datetime(df["entry_time"], utc=True)
    df["exit_time"] = pd.to_datetime(df["exit_time"], utc=True)
    return df


def main() -> None:
    parser = argparse.ArgumentParser(description="Ultra-clean TradingView-style chart")
    parser.add_argument("--symbol", default="XAUUSD")
    parser.add_argument("--from", dest="from_date", required=True, help="Start date YYYY-MM-DD")
    parser.add_argument("--to", dest="to_date", required=True, help="End date YYYY-MM-DD")
    parser.add_argument("--timeframe", default="M5")
    parser.add_argument("--data-dir", type=Path, default=Path("data/backtest_candles"))
    parser.add_argument("--output-dir", type=Path, default=Path("data/backtest"))
    parser.add_argument("--no-open", action="store_true", help="Do not open chart in browser")
    parser.add_argument("--max-zones", type=int, default=6, help="Max zones to display (default: 6)")
    args = parser.parse_args()

    from_date = datetime.strptime(args.from_date, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    to_date = datetime.strptime(args.to_date, "%Y-%m-%d").replace(hour=23, minute=59, second=59, tzinfo=timezone.utc)

    candles = load_candles(args.symbol, from_date, to_date, args.data_dir, args.timeframe)
    trades = load_trades(args.output_dir, args.symbol)
    trades = trades[(trades["entry_time"] >= from_date) & (trades["entry_time"] <= to_date)]

    # Create figure
    fig = go.Figure()

    # 1. Candlestick chart
    fig.add_trace(go.Candlestick(
        x=candles["time"],
        open=candles["open"],
        high=candles["high"],
        low=candles["low"],
        close=candles["close"],
        name="XAUUSD",
        increasing_line_color='#26a69a',
        decreasing_line_color='#ef5350',
        increasing_fillcolor='#26a69a',
        decreasing_fillcolor='#ef5350'
    ))

    # 2. Zone rectangles (ONLY from trades, limited)
    unique_zones = []
    for _, t in trades.iterrows():
        zb, zt = t.get("zone_bottom"), t.get("zone_top")
        if pd.notna(zb) and pd.notna(zt):
            zone_key = (round(float(zb), 2), round(float(zt), 2), str(t["side"]))
            if zone_key not in unique_zones:
                unique_zones.append((float(zb), float(zt), str(t["side"]), t["entry_time"]))

    # Limit to most recent zones
    unique_zones = sorted(unique_zones, key=lambda x: x[3])[-args.max_zones:]

    for zb, zt, side, _ in unique_zones:
        is_demand = side.lower() == "long"
        color = "rgba(76, 175, 80, 0.2)" if is_demand else "rgba(244, 67, 54, 0.2)"
        line_color = "rgb(76, 175, 80)" if is_demand else "rgb(244, 67, 54)"

        # Add filled rectangle shape
        fig.add_shape(
            type="rect",
            x0=candles["time"].min(),
            x1=candles["time"].max(),
            y0=zb,
            y1=zt,
            fillcolor=color,
            line=dict(color=line_color, width=1),
            layer="below",
            opacity=0.3
        )

    # 3. Entry markers
    long_entries = trades[trades["side"] == "long"]
    short_entries = trades[trades["side"] == "short"]

    if len(long_entries) > 0:
        fig.add_trace(go.Scatter(
            x=long_entries["entry_time"],
            y=long_entries["entry_price"],
            mode='markers+text',
            marker=dict(
                symbol='triangle-up',
                size=12,
                color='#26a69a',
                line=dict(color='white', width=1)
            ),
            text=[f"{m}" for m in long_entries["entry_model"]],
            textposition="bottom center",
            textfont=dict(size=9, color='#26a69a'),
            name='Long Entry',
            hovertemplate='<b>Long Entry</b><br>Price: %{y}<br>Model: %{text}<extra></extra>'
        ))

    if len(short_entries) > 0:
        fig.add_trace(go.Scatter(
            x=short_entries["entry_time"],
            y=short_entries["entry_price"],
            mode='markers+text',
            marker=dict(
                symbol='triangle-down',
                size=12,
                color='#ef5350',
                line=dict(color='white', width=1)
            ),
            text=[f"{m}" for m in short_entries["entry_model"]],
            textposition="top center",
            textfont=dict(size=9, color='#ef5350'),
            name='Short Entry',
            hovertemplate='<b>Short Entry</b><br>Price: %{y}<br>Model: %{text}<extra></extra>'
        ))

    # 4. Exit markers (small circles)
    wins = trades[trades["pnl"] > 0]
    losses = trades[trades["pnl"] <= 0]

    if len(wins) > 0:
        fig.add_trace(go.Scatter(
            x=wins["exit_time"],
            y=wins["exit_price"],
            mode='markers',
            marker=dict(
                symbol='circle',
                size=8,
                color='#4caf50',
                line=dict(color='white', width=1)
            ),
            name='Win',
            hovertemplate='<b>Exit (Win)</b><br>Price: %{y}<br>P&L: $%{customdata}<extra></extra>',
            customdata=wins["pnl"].round(2)
        ))

    if len(losses) > 0:
        fig.add_trace(go.Scatter(
            x=losses["exit_time"],
            y=losses["exit_price"],
            mode='markers',
            marker=dict(
                symbol='circle',
                size=8,
                color='#f44336',
                line=dict(color='white', width=1)
            ),
            name='Loss',
            hovertemplate='<b>Exit (Loss)</b><br>Price: %{y}<br>P&L: $%{customdata}<extra></extra>',
            customdata=losses["pnl"].round(2)
        ))

    # Summary stats
    net_pnl = trades["pnl"].sum()
    win_rate = round(len(wins) / len(trades) * 100, 1) if len(trades) > 0 else 0

    # Layout
    fig.update_layout(
        title=dict(
            text=f"{args.symbol} · {args.timeframe} · {args.from_date} to {args.to_date}<br>" +
                 f"<sub>Trades: {len(trades)} | Win Rate: {win_rate}% | Net P&L: ${net_pnl:,.2f}</sub>",
            x=0.5,
            xanchor='center',
            font=dict(size=18)
        ),
        xaxis=dict(
            title="Time",
            rangeslider=dict(visible=False),
            gridcolor='rgba(128, 128, 128, 0.2)',
            showgrid=True
        ),
        yaxis=dict(
            title="Price (USD)",
            gridcolor='rgba(128, 128, 128, 0.2)',
            showgrid=True
        ),
        template="plotly_dark",
        hovermode='x unified',
        height=800,
        showlegend=True,
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="right",
            x=1
        )
    )

    # Save
    out_path = args.output_dir / args.symbol / "chart_clean.html"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.write_html(str(out_path))

    print(f"✅ Clean chart saved to {out_path}")
    print(f"📊 {len(trades)} trades | {len(unique_zones)} zones | Win rate: {win_rate}% | P&L: ${net_pnl:,.2f}")

    if not args.no_open:
        webbrowser.open(f"file://{out_path.absolute()}")


if __name__ == "__main__":
    main()
