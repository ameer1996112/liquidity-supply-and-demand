"""
TradingView Backtest Importer
==============================
Imports TradingView strategy backtest results into Supabase for optimization.

Usage:
    python import_tradingview_backtest.py backtest.csv
"""

import os
import sys
import pandas as pd
import numpy as np
from supabase import create_client
from dotenv import load_dotenv
from datetime import datetime

# Load environment variables
load_dotenv()
load_dotenv('tests/.env')


def parse_tradingview_csv(csv_path: str) -> pd.DataFrame:
    """
    Parse TradingView backtest CSV export.

    TradingView typically exports columns like:
    - Trade #, Signal, Date/Time, Price, Contracts, P&L, Cum. Profit, Run-up, Drawdown

    Args:
        csv_path: Path to TradingView CSV file

    Returns:
        DataFrame ready for Supabase import
    """
    print(f"📂 Reading CSV from: {csv_path}")

    # Read CSV (TradingView uses various formats, try to be flexible)
    try:
        df = pd.read_csv(csv_path)
    except Exception as e:
        print(f"❌ Error reading CSV: {e}")
        sys.exit(1)

    print(f"✓ Loaded {len(df)} rows")
    print(f"📋 Columns found: {list(df.columns)}")

    # TradingView exports trades in pairs (entry + exit)
    # We need to group them into complete trades
    parsed_trades = []

    # Common TradingView column name variations
    signal_col = next((c for c in df.columns if 'signal' in c.lower() or 'type' in c.lower()), None)
    datetime_col = next((c for c in df.columns if 'date' in c.lower() or 'time' in c.lower()), None)
    price_col = next((c for c in df.columns if 'price' in c.lower()), None)
    pnl_col = next((c for c in df.columns if 'p&l' in c.lower() or 'pnl' in c.lower() or 'profit' in c.lower()), None)

    if not all([signal_col, datetime_col, price_col]):
        print("❌ Could not identify required columns. Please check CSV format.")
        print(f"\nExpected columns like: Signal/Type, Date/Time, Price, P&L")
        print(f"Found: {list(df.columns)}")
        return None

    print(f"\n✓ Mapped columns:")
    print(f"  Signal: {signal_col}")
    print(f"  DateTime: {datetime_col}")
    print(f"  Price: {price_col}")
    print(f"  P&L: {pnl_col}")

    # Group trades by pairs (Entry + Exit)
    i = 0
    while i < len(df) - 1:
        entry_row = df.iloc[i]
        exit_row = df.iloc[i + 1]

        # Check if this is an entry-exit pair
        entry_signal = str(entry_row[signal_col]).lower()
        exit_signal = str(exit_row[signal_col]).lower()

        # Detect trade direction
        if 'buy' in entry_signal or 'long' in entry_signal:
            side = 'BUY'
        elif 'sell' in entry_signal or 'short' in entry_signal:
            side = 'SELL'
        else:
            i += 1
            continue

        # Calculate P&L
        if pnl_col and not pd.isna(exit_row[pnl_col]):
            # Use TradingView's calculated P&L
            pnl = float(exit_row[pnl_col])
        else:
            # Calculate P&L from price difference
            entry_price = float(entry_row[price_col])
            exit_price = float(exit_row[price_col])

            if side == 'BUY':
                pnl = ((exit_price - entry_price) / entry_price) * 100
            else:
                pnl = ((entry_price - exit_price) / entry_price) * 100

        # Determine if Win or Loss
        exit_type = 'Win' if pnl > 0 else 'Loss'

        # Calculate placeholder SL and TP (since TradingView doesn't export them)
        entry_price = float(entry_row[price_col])
        exit_price = float(exit_row[price_col])

        if side == 'BUY':
            # For BUY: SL below entry, TP above entry
            sl = entry_price * 0.995  # 0.5% below entry
            tp = entry_price * 1.015  # 1.5% above entry
        else:  # SELL
            # For SELL: SL above entry, TP below entry
            sl = entry_price * 1.005  # 0.5% above entry
            tp = entry_price * 0.985  # 1.5% below entry

        trade = {
            'symbol': 'EURUSD',  # Default, can be changed
            'side': side,
            'entry': entry_price,
            'sl': round(sl, 5),
            'tp': round(tp, 5),
            'size': 0.01,  # Placeholder lot size
            'close_price': exit_price,
            'pnl': pnl,
            'exit_type': exit_type,
            'created_at': str(entry_row[datetime_col]),
            'close_time': str(exit_row[datetime_col]),
            'status': 'closed',
            # Placeholder values for indicators (to be filled)
            'rsi': np.nan,
            'adx': np.nan,
            'freshness': np.nan,
            'base_quality': np.nan,
            'liq_swept': False,
        }

        parsed_trades.append(trade)
        i += 2  # Skip to next pair

    trades_df = pd.DataFrame(parsed_trades)
    print(f"\n✓ Parsed {len(trades_df)} complete trades")
    print(f"  Winning trades: {len(trades_df[trades_df['exit_type'] == 'Win'])}")
    print(f"  Losing trades:  {len(trades_df[trades_df['exit_type'] == 'Loss'])}")
    print(f"  Total P&L:      {trades_df['pnl'].sum():.2f}%")

    return trades_df


def add_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """
    Add indicator values to trades.

    For now, generates random indicator values for demonstration.
    In production, you should calculate actual indicator values at entry time.

    Args:
        df: DataFrame with trades

    Returns:
        DataFrame with indicator columns filled
    """
    print("\n📊 Adding indicator values...")
    print("⚠️  WARNING: Using randomized indicator values for demonstration.")
    print("   In production, calculate actual RSI, ADX, etc. at entry time.")

    # Generate realistic-looking indicator values
    np.random.seed(42)
    n = len(df)

    df['rsi'] = np.random.uniform(20, 80, n)
    df['adx'] = np.random.uniform(10, 50, n)
    df['freshness'] = np.random.randint(1, 11, n)
    df['base_quality'] = np.random.uniform(0.1, 1.0, n)
    df['liq_swept'] = np.random.choice([True, False], n)

    print("✓ Added indicators: RSI, ADX, Freshness, Quality, Liquidity Swept")

    return df


def upload_to_supabase(df: pd.DataFrame, batch_size: int = 100) -> bool:
    """
    Upload trades to Supabase in batches.

    Args:
        df: DataFrame with trades
        batch_size: Number of records per batch

    Returns:
        True if successful
    """
    supabase_url = os.getenv('SUPABASE_URL')
    supabase_key = os.getenv('SUPABASE_KEY') or os.getenv('SUPABASE_ANON_KEY')

    if not supabase_url or not supabase_key:
        print("❌ Supabase credentials not found in environment variables")
        return False

    print(f"\n📤 Uploading {len(df)} trades to Supabase...")

    supabase = create_client(supabase_url, supabase_key)

    # Convert DataFrame to list of dicts
    records = df.to_dict('records')

    # Upload in batches
    total_batches = (len(records) + batch_size - 1) // batch_size

    for i in range(0, len(records), batch_size):
        batch = records[i:i + batch_size]
        batch_num = (i // batch_size) + 1

        try:
            response = supabase.table('trading_signals').insert(batch).execute()
            print(f"  ✓ Batch {batch_num}/{total_batches}: Uploaded {len(batch)} trades")
        except Exception as e:
            print(f"  ❌ Batch {batch_num}/{total_batches} failed: {e}")
            return False

    print(f"\n✅ Successfully uploaded {len(records)} trades to Supabase!")
    return True


def main():
    if len(sys.argv) < 2:
        print("Usage: python import_tradingview_backtest.py <path_to_csv> [--yes]")
        print("\nExample:")
        print("  python import_tradingview_backtest.py tradingview_backtest.csv")
        print("  python import_tradingview_backtest.py tradingview_backtest.csv --yes")
        sys.exit(1)

    csv_path = sys.argv[1]
    auto_confirm = '--yes' in sys.argv or '-y' in sys.argv

    if not os.path.exists(csv_path):
        print(f"❌ File not found: {csv_path}")
        sys.exit(1)

    print("=" * 70)
    print("📊 TRADINGVIEW BACKTEST IMPORTER")
    print("=" * 70)

    # Step 1: Parse CSV
    df = parse_tradingview_csv(csv_path)

    if df is None or len(df) == 0:
        print("❌ No trades to import")
        sys.exit(1)

    # Step 2: Add indicators (placeholder - you should calculate real values)
    df = add_indicators(df)

    # Step 3: Preview data
    print("\n" + "=" * 70)
    print("📋 PREVIEW OF TRADES TO IMPORT")
    print("=" * 70)
    print(df.head(5).to_string())

    # Step 4: Confirm upload
    print("\n" + "=" * 70)

    if not auto_confirm:
        response = input(f"\n⚠️  Upload {len(df)} trades to Supabase? (yes/no): ")
        if response.lower() not in ['yes', 'y']:
            print("❌ Upload cancelled")
            sys.exit(0)
    else:
        print(f"\n✅ Auto-confirm enabled. Uploading {len(df)} trades...")

    # Step 5: Upload
    success = upload_to_supabase(df)

    if success:
        print("\n" + "=" * 70)
        print("🎉 IMPORT COMPLETE!")
        print("=" * 70)
        print("\nNext steps:")
        print("  1. Run the optimizer: python optimize_filters.py")
        print("  2. Review the optimal filters")
        print("  3. Apply filters to your live trading strategy")
    else:
        print("\n❌ Import failed. Please check errors above.")
        sys.exit(1)


if __name__ == "__main__":
    main()
