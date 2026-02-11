"""
Generate TradingView-style chart with price data and trade markers.

Creates an interactive HTML chart (candlesticks + buy/sell markers) like TradingView Strategy Tester.

Usage:
  python -m app.backtest_chart --symbol XAUUSD --from 2026-01-01 --to 2026-02-10
  # Opens chart.html in browser, or outputs path

Requires: run backtest first to have trades.csv
"""

from __future__ import annotations

import argparse
import json
import webbrowser
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

# Template uses TradingView Lightweight Charts from CDN
# Use {{ and }} for literal braces in .format()
CHART_HTML_TEMPLATE = """<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <title>Strategy Tester - {symbol}</title>
  <script src="https://unpkg.com/lightweight-charts@4.1.0/dist/lightweight-charts.standalone.production.js"></script>
  <style>
    body {{ margin: 0; background: #131722; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; }}
    #chart {{ width: 100vw; height: 100vh; }}
    .info {{ position: fixed; top: 10px; left: 10px; color: #787b86; font-size: 12px; z-index: 10; }}
  </style>
</head>
<body>
  <div class="info">{symbol} | {from_date} – {to_date} | {trade_count} trades</div>
  <div id="chart"></div>
  <script>
    const chart = LightweightCharts.createChart(document.getElementById('chart'), {{
      layout: {{ background: {{ type: 'solid', color: '#131722' }}, textColor: '#d1d4dc' }},
      grid: {{ vertLines: {{ color: '#1e222d' }}, horzLines: {{ color: '#1e222d' }} }},
      crosshair: {{ mode: 1 }},
      rightPriceScale: {{ borderColor: '#2a2e39', scaleMargins: {{ top: 0.1, bottom: 0.2 }} }},
      timeScale: {{ borderColor: '#2a2e39', timeVisible: true, secondsVisible: false }}
    }});

    const candleSeries = chart.addCandlestickSeries({{
      upColor: '#26a69a', downColor: '#ef5350', borderDownColor: '#ef5350', borderUpColor: '#26a69a',
      wickDownColor: '#ef5350', wickUpColor: '#26a69a'
    }});
    candleSeries.setData({candle_data});

    const markers = {marker_data};
    candleSeries.setMarkers(markers);

    // SL/TP price lines (dashed, like TradingView)
    const priceLines = {price_lines};
    priceLines.forEach(function(pl) {{
      candleSeries.createPriceLine({{
        price: pl.price,
        color: pl.color,
        lineWidth: 1,
        lineStyle: pl.lineStyle !== undefined ? pl.lineStyle : 2,
        axisLabelVisible: false,
        title: pl.title
      }});
    }});

    chart.timeScale().fitContent();
  </script>
</body>
</html>
"""


def load_candles(symbol: str, from_date: datetime, to_date: datetime, data_dir: Path, timeframe: str = "M5") -> pd.DataFrame:
    """Load candles from local file (same path as backtest)."""
    from_str = from_date.strftime("%Y-%m-%d")
    to_str = to_date.strftime("%Y-%m-%d")
    for ext in [".csv", ".parquet"]:
        path = data_dir / symbol / timeframe / f"{from_str}_{to_str}{ext}"
        if path.exists():
            df = pd.read_csv(path) if ext == ".csv" else pd.read_parquet(path)
            df["time"] = pd.to_datetime(df["time"], utc=True)
            df = df[(df["time"] >= from_date) & (df["time"] <= to_date)].sort_values("time")
            return df
    raise FileNotFoundError(f"No candle data at {data_dir / symbol / timeframe / f'{from_str}_{to_str}.csv'}")


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
    parser = argparse.ArgumentParser(description="Generate TradingView-style chart with trades")
    parser.add_argument("--symbol", default="XAUUSD")
    parser.add_argument("--from", dest="from_date", required=True, help="Start date YYYY-MM-DD")
    parser.add_argument("--to", dest="to_date", required=True, help="End date YYYY-MM-DD")
    parser.add_argument("--timeframe", default="M5")
    parser.add_argument("--data-dir", type=Path, default=Path("data/backtest_candles"))
    parser.add_argument("--output-dir", type=Path, default=Path("data/backtest"))
    parser.add_argument("--no-open", action="store_true", help="Do not open chart in browser")
    args = parser.parse_args()

    from_date = datetime.strptime(args.from_date, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    to_date = datetime.strptime(args.to_date, "%Y-%m-%d").replace(hour=23, minute=59, second=59, tzinfo=timezone.utc)

    candles = load_candles(args.symbol, from_date, to_date, args.data_dir, args.timeframe)
    trades = load_trades(args.output_dir, args.symbol)

    # Filter trades to chart date range
    trades = trades[(trades["entry_time"] >= from_date) & (trades["entry_time"] <= to_date)]

    # Candlestick data for Lightweight Charts (Unix timestamp in seconds)
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

    # Markers: entry only (cleaner; exit adds clutter)
    marker_data = []
    for _, t in trades.iterrows():
        is_long = str(t["side"]).lower() == "long"
        ent_model = t.get("entry_model", "")
        marker_data.append({
            "time": int(t["entry_time"].timestamp()),
            "position": "belowBar" if is_long else "aboveBar",
            "shape": "arrowUp" if is_long else "arrowDown",
            "color": "#26a69a" if is_long else "#ef5350",
            "text": f"{'L' if is_long else 'S'} {ent_model}",
        })

    marker_data.sort(key=lambda m: m["time"])

    # SL/TP only for last 3 trades (avoids clutter)
    price_lines: list = []
    if "stop_price" in trades.columns and "limit_price" in trades.columns:
        for _, t in trades.tail(3).iterrows():
            sp, lp = t.get("stop_price"), t.get("limit_price")
            if pd.notna(sp) and float(sp) > 0:
                price_lines.append({"price": round(float(sp), 2), "color": "#ef5350", "title": "SL", "lineStyle": 2})
            if pd.notna(lp) and float(lp) > 0:
                price_lines.append({"price": round(float(lp), 2), "color": "#26a69a", "title": "TP", "lineStyle": 2})

    html = CHART_HTML_TEMPLATE.format(
        symbol=args.symbol,
        from_date=args.from_date,
        to_date=args.to_date,
        trade_count=len(trades),
        candle_data=json.dumps(candle_data),
        marker_data=json.dumps(marker_data),
        price_lines=json.dumps(price_lines),
    )

    out_path = args.output_dir / args.symbol / "chart.html"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(html, encoding="utf-8")

    print(f"Chart saved to {out_path}")
    if not args.no_open:
        webbrowser.open(f"file://{out_path.absolute()}")


if __name__ == "__main__":
    main()
