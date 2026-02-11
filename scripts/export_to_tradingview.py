#!/usr/bin/env python3
"""
Export backtest results to TradingView format.

Creates a CSV file that can be imported into TradingView for visualization.
"""
import sys
from pathlib import Path
import pandas as pd
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent.parent))

def export_trades_for_tradingview(trades_csv: Path, output_path: Path = None):
    """Convert backtest trades to TradingView format."""

    # Read trades
    trades = pd.read_csv(trades_csv)

    if len(trades) == 0:
        print("❌ No trades found in CSV!")
        return

    # Create TradingView format
    # TradingView expects: Time, Open, High, Low, Close, Volume
    tv_data = []

    for _, trade in trades.iterrows():
        entry_time = pd.to_datetime(trade['entry_time'])
        exit_time = pd.to_datetime(trade['exit_time'])
        entry_price = trade['entry_price']
        exit_price = trade['exit_price']
        side = trade['side']
        pnl = trade['pnl']

        # Add entry marker
        tv_data.append({
            'time': entry_time.strftime('%Y-%m-%d %H:%M:%S'),
            'type': 'entry',
            'side': side,
            'price': entry_price,
            'sl': trade.get('stop_price', None),
            'tp': trade.get('limit_price', None),
            'pnl': None,
            'exit_reason': None,
        })

        # Add exit marker
        tv_data.append({
            'time': exit_time.strftime('%Y-%m-%d %H:%M:%S'),
            'type': 'exit',
            'side': side,
            'price': exit_price,
            'sl': None,
            'tp': None,
            'pnl': pnl,
            'exit_reason': trade.get('reason', 'unknown'),
        })

    df = pd.DataFrame(tv_data)

    if output_path is None:
        output_path = trades_csv.parent / "tradingview_export.csv"

    df.to_csv(output_path, index=False)

    print(f"✅ Exported {len(trades)} trades to TradingView format")
    print(f"📁 File: {output_path}")
    print(f"\n📊 Summary:")
    print(f"   Total trades: {len(trades)}")
    print(f"   Net PnL: ${trades['pnl'].sum():.2f}")
    print(f"   Win rate: {(trades['pnl'] > 0).sum() / len(trades) * 100:.1f}%")
    print(f"\n💡 To view in TradingView:")
    print(f"   1. Open TradingView chart")
    print(f"   2. Click 'Indicators' → 'Drawing Tools' → 'Annotation'")
    print(f"   3. Manually mark entry/exit points using the data")
    print(f"\n   OR use the interactive HTML chart:")
    print(f"   python scripts/create_tv_chart.py")

if __name__ == "__main__":
    trades_file = Path("data/backtest/XAUUSD/trades.csv")

    if not trades_file.exists():
        print(f"❌ Trades file not found: {trades_file}")
        print(f"   Run backtest first: python scripts/backtest_tv_settings.py --no-trade-limit --no-htf-flip")
        sys.exit(1)

    export_trades_for_tradingview(trades_file)
