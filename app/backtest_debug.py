"""
Enhanced Backtest Debugger - Visual verification tool like TradingView Strategy Tester.

Creates a detailed HTML chart showing:
- All candles with zones overlaid
- Entry/exit markers with full details
- Stop loss and take profit lines for EACH trade
- Zone boundaries (demand=green, supply=red)
- Entry model labels (FLIP, BREAK_CANDLE, DIR_CLOSE)
- Hover tooltips with trade metrics

Usage:
  python -m app.backtest_debug --symbol XAUUSD --from 2026-01-01 --to 2026-02-10
"""

from __future__ import annotations

import argparse
import json
import webbrowser
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

# Enhanced template with zones, detailed tooltips, and trade metrics
ENHANCED_CHART_TEMPLATE = """<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <title>Backtest Debugger - {symbol}</title>
  <script src="https://unpkg.com/lightweight-charts@4.1.0/dist/lightweight-charts.standalone.production.js"></script>
  <style>
    body {{
      margin: 0;
      background: #131722;
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
      color: #d1d4dc;
    }}
    #chart {{ width: 100%; height: 70vh; }}
    .header {{
      padding: 15px;
      background: #1e222d;
      border-bottom: 1px solid #2a2e39;
    }}
    .header h1 {{ margin: 0 0 10px 0; font-size: 20px; }}
    .stats {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
      gap: 10px;
      margin-top: 10px;
    }}
    .stat {{
      background: #2a2e39;
      padding: 10px;
      border-radius: 4px;
    }}
    .stat-label {{ font-size: 11px; color: #787b86; }}
    .stat-value {{ font-size: 18px; font-weight: 600; margin-top: 4px; }}
    .stat-value.positive {{ color: #26a69a; }}
    .stat-value.negative {{ color: #ef5350; }}
    .controls {{
      padding: 15px;
      background: #1e222d;
      border-top: 1px solid #2a2e39;
    }}
    .trade-list {{
      max-height: 200px;
      overflow-y: auto;
      font-size: 12px;
    }}
    .trade-item {{
      padding: 8px;
      border-bottom: 1px solid #2a2e39;
      cursor: pointer;
    }}
    .trade-item:hover {{
      background: #2a2e39;
    }}
    .trade-item.win {{ border-left: 3px solid #26a69a; }}
    .trade-item.loss {{ border-left: 3px solid #ef5350; }}
  </style>
</head>
<body>
  <div class="header">
    <h1>📊 Backtest Debugger - {symbol}</h1>
    <div style="color: #787b86; font-size: 12px;">
      {from_date} to {to_date} | {trade_count} trades | Timeframe: {timeframe}
    </div>
    <div class="stats">
      <div class="stat">
        <div class="stat-label">Net P&L</div>
        <div class="stat-value {net_pnl_class}">${net_pnl}</div>
      </div>
      <div class="stat">
        <div class="stat-label">Win Rate</div>
        <div class="stat-value">{win_rate}%</div>
      </div>
      <div class="stat">
        <div class="stat-label">Profit Factor</div>
        <div class="stat-value">{profit_factor}</div>
      </div>
      <div class="stat">
        <div class="stat-label">Avg Bars Held</div>
        <div class="stat-value">{avg_bars}</div>
      </div>
      <div class="stat">
        <div class="stat-label">Wins/Losses</div>
        <div class="stat-value">{wins}/{losses}</div>
      </div>
    </div>
  </div>

  <div id="chart"></div>

  <div class="controls">
    <h3 style="margin: 0 0 10px 0;">Trade List (click to zoom)</h3>
    <div class="trade-list" id="tradeList"></div>
  </div>

  <script>
    const chart = LightweightCharts.createChart(document.getElementById('chart'), {{
      layout: {{ background: {{ type: 'solid', color: '#131722' }}, textColor: '#d1d4dc' }},
      grid: {{ vertLines: {{ color: '#1e222d' }}, horzLines: {{ color: '#1e222d' }} }},
      crosshair: {{ mode: 1 }},
      rightPriceScale: {{ borderColor: '#2a2e39', scaleMargins: {{ top: 0.1, bottom: 0.2 }} }},
      timeScale: {{ borderColor: '#2a2e39', timeVisible: true, secondsVisible: false }}
    }});

    // Candlesticks
    const candleSeries = chart.addCandlestickSeries({{
      upColor: '#26a69a', downColor: '#ef5350',
      borderDownColor: '#ef5350', borderUpColor: '#26a69a',
      wickDownColor: '#ef5350', wickUpColor: '#26a69a'
    }});
    candleSeries.setData({candle_data});

    // Entry/Exit markers
    const markers = {marker_data};
    candleSeries.setMarkers(markers);

    // Zone boundaries (demand=green box, supply=red box)
    const zones = {zone_data};
    zones.forEach(function(zone) {{
      // Top line
      candleSeries.createPriceLine({{
        price: zone.top,
        color: zone.color,
        lineWidth: 2,
        lineStyle: 1,
        axisLabelVisible: true,
        title: zone.type + ' Zone'
      }});
      // Bottom line
      candleSeries.createPriceLine({{
        price: zone.bottom,
        color: zone.color,
        lineWidth: 2,
        lineStyle: 1,
        axisLabelVisible: true,
        title: ''
      }});
    }});

    // SL/TP lines for ALL trades (not just last 3)
    const priceLines = {price_lines};
    priceLines.forEach(function(pl) {{
      candleSeries.createPriceLine({{
        price: pl.price,
        color: pl.color,
        lineWidth: 1,
        lineStyle: 2,
        axisLabelVisible: false,
        title: pl.title
      }});
    }});

    // Trade list with click-to-zoom
    const trades = {trades_json};
    const tradeList = document.getElementById('tradeList');
    trades.forEach(function(trade, idx) {{
      const div = document.createElement('div');
      div.className = 'trade-item ' + (trade.pnl > 0 ? 'win' : 'loss');
      div.innerHTML = `
        <strong>#${{idx + 1}}</strong>
        ${{trade.side.toUpperCase()}} ${{trade.entry_model}}
        @ ${{trade.entry_price.toFixed(2)}} → ${{trade.exit_price.toFixed(2)}}
        | P&L: $${{trade.pnl.toFixed(2)}}
        | Bars: ${{trade.bars_held}}
        | Exit: ${{trade.reason}}
      `;
      div.onclick = function() {{
        chart.timeScale().setVisibleRange({{
          from: trade.entry_time - 3600 * 2,
          to: trade.exit_time + 3600 * 2
        }});
      }};
      tradeList.appendChild(div);
    }});

    chart.timeScale().fitContent();
  </script>
</body>
</html>
"""


def load_candles(symbol: str, from_date: datetime, to_date: datetime, data_dir: Path, timeframe: str = "M5") -> pd.DataFrame:
    """Load candles from local file."""
    # Try exact match first
    from_str = from_date.strftime("%Y-%m-%d")
    to_str = to_date.strftime("%Y-%m-%d")
    for ext in [".csv", ".parquet"]:
        path = data_dir / symbol / timeframe / f"{from_str}_{to_str}{ext}"
        if path.exists():
            df = pd.read_csv(path) if ext == ".csv" else pd.read_parquet(path)
            df["time"] = pd.to_datetime(df["time"], utc=True)
            df = df[(df["time"] >= from_date) & (df["time"] <= to_date)].sort_values("time")
            return df

    # Try any file in the directory that might contain the range
    candle_dir = data_dir / symbol / timeframe
    if candle_dir.exists():
        for file in candle_dir.glob("*.csv"):
            df = pd.read_csv(file)
            df["time"] = pd.to_datetime(df["time"], utc=True)
            df = df[(df["time"] >= from_date) & (df["time"] <= to_date)].sort_values("time")
            if len(df) > 0:
                return df
        for file in candle_dir.glob("*.parquet"):
            df = pd.read_parquet(file)
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
    parser = argparse.ArgumentParser(description="Enhanced backtest debugger with zones")
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

    # Enhanced markers with exit markers
    marker_data = []
    for _, t in trades.iterrows():
        is_long = str(t["side"]).lower() == "long"
        ent_model = t.get("entry_model", "")

        # Entry marker
        marker_data.append({
            "time": int(t["entry_time"].timestamp()),
            "position": "belowBar" if is_long else "aboveBar",
            "shape": "arrowUp" if is_long else "arrowDown",
            "color": "#26a69a" if is_long else "#ef5350",
            "text": f"{'L' if is_long else 'S'} {ent_model}",
        })

        # Exit marker
        exit_color = "#26a69a" if t["pnl"] > 0 else "#ef5350"
        marker_data.append({
            "time": int(t["exit_time"].timestamp()),
            "position": "aboveBar" if is_long else "belowBar",
            "shape": "circle",
            "color": exit_color,
            "text": f"${t['pnl']:.0f} ({t['reason']})",
        })

    marker_data.sort(key=lambda m: m["time"])

    # SL/TP lines for ALL trades
    price_lines = []
    for _, t in trades.iterrows():
        sp, lp = t.get("stop_price"), t.get("limit_price")
        if pd.notna(sp) and float(sp) > 0:
            price_lines.append({
                "price": round(float(sp), 2),
                "color": "#ef5350",
                "title": f"SL {t['entry_time'].strftime('%H:%M')}"
            })
        if pd.notna(lp) and float(lp) > 0:
            price_lines.append({
                "price": round(float(lp), 2),
                "color": "#26a69a",
                "title": f"TP {t['entry_time'].strftime('%H:%M')}"
            })

    # Zone boundaries
    zone_data = []
    for _, t in trades.iterrows():
        zb, zt = t.get("zone_bottom"), t.get("zone_top")
        if pd.notna(zb) and pd.notna(zt):
            is_demand = str(t["side"]).lower() == "long"
            zone_data.append({
                "bottom": round(float(zb), 2),
                "top": round(float(zt), 2),
                "color": "#26a69a" if is_demand else "#ef5350",
                "type": "Demand" if is_demand else "Supply"
            })

    # Summary stats
    wins = trades[trades["pnl"] > 0]
    losses = trades[trades["pnl"] <= 0]
    net_pnl = trades["pnl"].sum()
    gross_profit = wins["pnl"].sum() if len(wins) > 0 else 0
    gross_loss = abs(losses["pnl"].sum()) if len(losses) > 0 else 0
    profit_factor = round(gross_profit / gross_loss, 2) if gross_loss > 0 else 0
    win_rate = round(len(wins) / len(trades) * 100, 1) if len(trades) > 0 else 0
    avg_bars = round(trades["bars_held"].mean(), 1) if len(trades) > 0 else 0

    # Trades JSON for interactive list
    trades_json = []
    for _, t in trades.iterrows():
        trades_json.append({
            "side": t["side"],
            "entry_model": t.get("entry_model", ""),
            "entry_price": float(t["entry_price"]),
            "exit_price": float(t["exit_price"]),
            "pnl": float(t["pnl"]),
            "bars_held": int(t["bars_held"]),
            "reason": t["reason"],
            "entry_time": int(t["entry_time"].timestamp()),
            "exit_time": int(t["exit_time"].timestamp())
        })

    html = ENHANCED_CHART_TEMPLATE.format(
        symbol=args.symbol,
        from_date=args.from_date,
        to_date=args.to_date,
        timeframe=args.timeframe,
        trade_count=len(trades),
        net_pnl=f"{net_pnl:,.2f}",
        net_pnl_class="positive" if net_pnl > 0 else "negative",
        win_rate=win_rate,
        profit_factor=profit_factor,
        avg_bars=avg_bars,
        wins=len(wins),
        losses=len(losses),
        candle_data=json.dumps(candle_data),
        marker_data=json.dumps(marker_data),
        zone_data=json.dumps(zone_data),
        price_lines=json.dumps(price_lines),
        trades_json=json.dumps(trades_json)
    )

    out_path = args.output_dir / args.symbol / "chart_debug.html"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(html, encoding="utf-8")

    print(f"✅ Enhanced debug chart saved to {out_path}")
    print(f"📊 Summary: {len(trades)} trades | Win rate: {win_rate}% | Net P&L: ${net_pnl:,.2f}")

    if not args.no_open:
        webbrowser.open(f"file://{out_path.absolute()}")


if __name__ == "__main__":
    main()
