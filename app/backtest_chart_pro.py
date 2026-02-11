"""
Professional TradingView-Style Chart - Clean and Readable.

Features:
- Only shows zones that had actual trades (no clutter)
- Transparent zone boxes with borders
- Clean price lines (SL/TP only for visible trades)
- Entry/exit markers with hover info
- Minimal visual noise

Usage:
  python -m app.backtest_chart_pro --from 2026-01-01 --to 2026-02-10
"""

from __future__ import annotations

import argparse
import json
import webbrowser
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

# Professional chart template (TradingView-like)
CHART_TEMPLATE = """<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <title>Strategy Tester - {symbol}</title>
  <script src="https://unpkg.com/lightweight-charts@4.1.0/dist/lightweight-charts.standalone.production.js"></script>
  <style>
    * {{ margin: 0; padding: 0; box-sizing: border-box; }}
    body {{
      background: #0d1117;
      font-family: -apple-system, BlinkMacSystemFont, "Trebuchet MS", Roboto, Ubuntu, sans-serif;
      color: #c9d1d9;
      overflow: hidden;
    }}
    .header {{
      display: flex;
      align-items: center;
      justify-content: space-between;
      padding: 12px 20px;
      background: #161b22;
      border-bottom: 1px solid #21262d;
    }}
    .title {{
      font-size: 16px;
      font-weight: 600;
      color: #58a6ff;
    }}
    .stats {{
      display: flex;
      gap: 24px;
      font-size: 13px;
    }}
    .stat {{
      display: flex;
      flex-direction: column;
      align-items: flex-end;
    }}
    .stat-label {{ color: #8b949e; font-size: 11px; margin-bottom: 2px; }}
    .stat-value {{ font-weight: 600; }}
    .stat-value.positive {{ color: #3fb950; }}
    .stat-value.negative {{ color: #f85149; }}
    #chart {{ width: 100vw; height: calc(100vh - 120px); }}
    .footer {{
      padding: 8px 20px;
      background: #161b22;
      border-top: 1px solid #21262d;
      font-size: 11px;
      color: #8b949e;
      display: flex;
      gap: 20px;
    }}
    .legend-item {{
      display: flex;
      align-items: center;
      gap: 6px;
    }}
    .legend-box {{
      width: 14px;
      height: 14px;
      border-radius: 2px;
    }}
  </style>
</head>
<body>
  <div class="header">
    <div class="title">{symbol} · {timeframe} · {from_date} – {to_date}</div>
    <div class="stats">
      <div class="stat">
        <div class="stat-label">Net P&L</div>
        <div class="stat-value {net_pnl_class}">{net_pnl}</div>
      </div>
      <div class="stat">
        <div class="stat-label">Trades</div>
        <div class="stat-value">{trade_count}</div>
      </div>
      <div class="stat">
        <div class="stat-label">Win Rate</div>
        <div class="stat-value">{win_rate}%</div>
      </div>
      <div class="stat">
        <div class="stat-label">Profit Factor</div>
        <div class="stat-value">{profit_factor}</div>
      </div>
    </div>
  </div>

  <div id="chart"></div>

  <div class="footer">
    <div class="legend-item">
      <div class="legend-box" style="background: rgba(56, 142, 60, 0.2); border: 1px solid #388e3c;"></div>
      <span>Demand Zone</span>
    </div>
    <div class="legend-item">
      <div class="legend-box" style="background: rgba(211, 47, 47, 0.2); border: 1px solid #d32f2f;"></div>
      <span>Supply Zone</span>
    </div>
    <div class="legend-item">
      <span>↑ Long Entry</span>
    </div>
    <div class="legend-item">
      <span>↓ Short Entry</span>
    </div>
  </div>

  <script>
    const chart = LightweightCharts.createChart(document.getElementById('chart'), {{
      layout: {{
        background: {{ type: 'solid', color: '#0d1117' }},
        textColor: '#8b949e',
        fontSize: 12
      }},
      grid: {{
        vertLines: {{ color: 'rgba(33, 38, 45, 0.5)' }},
        horzLines: {{ color: 'rgba(33, 38, 45, 0.5)' }}
      }},
      crosshair: {{
        mode: LightweightCharts.CrosshairMode.Normal,
        vertLine: {{
          color: '#6e7681',
          width: 1,
          style: LightweightCharts.LineStyle.Dashed
        }},
        horzLine: {{
          color: '#6e7681',
          width: 1,
          style: LightweightCharts.LineStyle.Dashed
        }}
      }},
      rightPriceScale: {{
        borderColor: '#21262d',
        scaleMargins: {{ top: 0.1, bottom: 0.15 }}
      }},
      timeScale: {{
        borderColor: '#21262d',
        timeVisible: true,
        secondsVisible: false
      }}
    }});

    // Candlestick series
    const candleSeries = chart.addCandlestickSeries({{
      upColor: '#26a69a',
      downColor: '#ef5350',
      borderUpColor: '#26a69a',
      borderDownColor: '#ef5350',
      wickUpColor: '#26a69a',
      wickDownColor: '#ef5350'
    }});
    candleSeries.setData({candle_data});

    // Zone rectangles (semi-transparent boxes)
    {zone_series_code}

    // Entry/exit markers
    const markers = {marker_data};
    candleSeries.setMarkers(markers);

    // Stop loss and take profit lines (only for recent trades)
    {price_lines_code}

    chart.timeScale().fitContent();

    // Responsive resize
    window.addEventListener('resize', () => {{
      chart.applyOptions({{ width: window.innerWidth, height: window.innerHeight - 120 }});
    }});
  </script>
</body>
</html>
"""


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
    parser = argparse.ArgumentParser(description="Professional TradingView-style chart")
    parser.add_argument("--symbol", default="XAUUSD")
    parser.add_argument("--from", dest="from_date", required=True, help="Start date YYYY-MM-DD")
    parser.add_argument("--to", dest="to_date", required=True, help="End date YYYY-MM-DD")
    parser.add_argument("--timeframe", default="M5")
    parser.add_argument("--data-dir", type=Path, default=Path("data/backtest_candles"))
    parser.add_argument("--output-dir", type=Path, default=Path("data/backtest"))
    parser.add_argument("--no-open", action="store_true", help="Do not open chart in browser")
    parser.add_argument("--max-zones", type=int, default=10, help="Max zones to display (default: 10)")
    args = parser.parse_args()

    from_date = datetime.strptime(args.from_date, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    to_date = datetime.strptime(args.to_date, "%Y-%m-%d").replace(hour=23, minute=59, second=59, tzinfo=timezone.utc)

    candles = load_candles(args.symbol, from_date, to_date, args.data_dir, args.timeframe)
    trades = load_trades(args.output_dir, args.symbol)
    trades = trades[(trades["entry_time"] >= from_date) & (trades["entry_time"] <= to_date)]

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

    # Entry/exit markers (clean, minimal)
    marker_data = []
    for idx, t in trades.iterrows():
        is_long = str(t["side"]).lower() == "long"
        model = t.get("entry_model", "")

        # Entry marker
        marker_data.append({
            "time": int(t["entry_time"].timestamp()),
            "position": "belowBar" if is_long else "aboveBar",
            "shape": "arrowUp" if is_long else "arrowDown",
            "color": "#26a69a" if is_long else "#ef5350",
            "text": f"{model[:4]}"  # Shortened (FLIP, BOC, DIR)
        })

        # Exit marker (small dot)
        exit_color = "#3fb950" if t["pnl"] > 0 else "#f85149"
        marker_data.append({
            "time": int(t["exit_time"].timestamp()),
            "position": "aboveBar" if is_long else "belowBar",
            "shape": "circle",
            "color": exit_color,
            "text": f"${int(t['pnl'])}"
        })

    # Zone rectangles (ONLY for trades, limited to max_zones)
    unique_zones = []
    for _, t in trades.iterrows():
        zb, zt = t.get("zone_bottom"), t.get("zone_top")
        if pd.notna(zb) and pd.notna(zt):
            zone_key = (round(float(zb), 2), round(float(zt), 2))
            if zone_key not in unique_zones:
                unique_zones.append(zone_key)

    # Limit to most recent zones
    unique_zones = unique_zones[-args.max_zones:]

    zone_series_code = ""
    for idx, (zb, zt) in enumerate(unique_zones):
        # Determine if demand or supply based on which trades used it
        is_demand = any(
            (abs(float(t.get("zone_bottom", 0)) - zb) < 0.1 and str(t["side"]).lower() == "long")
            for _, t in trades.iterrows()
        )

        color = "rgba(56, 142, 60, 0.15)" if is_demand else "rgba(211, 47, 47, 0.15)"
        border_color = "#388e3c" if is_demand else "#d32f2f"

        # Use rectangle series for zones
        zone_series_code += f"""
    const zoneSeries{idx} = chart.addLineSeries({{
      color: '{border_color}',
      lineWidth: 1,
      lineStyle: LightweightCharts.LineStyle.Dashed,
      priceLineVisible: false,
      lastValueVisible: false
    }});
    zoneSeries{idx}.createPriceLine({{
      price: {zt},
      color: '{border_color}',
      lineWidth: 1,
      lineStyle: LightweightCharts.LineStyle.Solid,
      axisLabelVisible: false
    }});
    zoneSeries{idx}.createPriceLine({{
      price: {zb},
      color: '{border_color}',
      lineWidth: 1,
      lineStyle: LightweightCharts.LineStyle.Solid,
      axisLabelVisible: false
    }});
    """

    # Price lines (SL/TP) - only for last 5 trades to avoid clutter
    price_lines_code = ""
    for _, t in trades.tail(5).iterrows():
        sp, lp = t.get("stop_price"), t.get("limit_price")
        entry_ts = int(t["entry_time"].timestamp())

        if pd.notna(sp) and float(sp) > 0:
            price_lines_code += f"""
    candleSeries.createPriceLine({{
      price: {round(float(sp), 2)},
      color: '#f85149',
      lineWidth: 1,
      lineStyle: LightweightCharts.LineStyle.Dashed,
      axisLabelVisible: false,
      title: 'SL'
    }});
    """

        if pd.notna(lp) and float(lp) > 0:
            price_lines_code += f"""
    candleSeries.createPriceLine({{
      price: {round(float(lp), 2)},
      color: '#3fb950',
      lineWidth: 1,
      lineStyle: LightweightCharts.LineStyle.Dashed,
      axisLabelVisible: false,
      title: 'TP'
    }});
    """

    # Summary stats
    wins = trades[trades["pnl"] > 0]
    losses = trades[trades["pnl"] <= 0]
    net_pnl = trades["pnl"].sum()
    gross_profit = wins["pnl"].sum() if len(wins) > 0 else 0
    gross_loss = abs(losses["pnl"].sum()) if len(losses) > 0 else 0
    profit_factor = round(gross_profit / gross_loss, 2) if gross_loss > 0 else 0
    win_rate = round(len(wins) / len(trades) * 100, 1) if len(trades) > 0 else 0

    html = CHART_TEMPLATE.format(
        symbol=args.symbol,
        timeframe=args.timeframe,
        from_date=args.from_date,
        to_date=args.to_date,
        trade_count=len(trades),
        net_pnl=f"${net_pnl:,.2f}",
        net_pnl_class="positive" if net_pnl > 0 else "negative",
        win_rate=win_rate,
        profit_factor=profit_factor,
        candle_data=json.dumps(candle_data),
        marker_data=json.dumps(marker_data),
        zone_series_code=zone_series_code,
        price_lines_code=price_lines_code
    )

    out_path = args.output_dir / args.symbol / "chart_pro.html"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(html, encoding="utf-8")

    print(f"✅ Professional chart saved to {out_path}")
    print(f"📊 {len(trades)} trades | {len(unique_zones)} zones | Win rate: {win_rate}%")

    if not args.no_open:
        webbrowser.open(f"file://{out_path.absolute()}")


if __name__ == "__main__":
    main()
