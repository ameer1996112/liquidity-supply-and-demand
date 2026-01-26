"""
Sample Trading Data Generator
==============================
Generates realistic sample trading data for testing the optimizer.

Usage:
    python generate_sample_data.py --trades 200
    python generate_sample_data.py --trades 500 --upload
"""

import os
import sys
import argparse
import pandas as pd
import numpy as np
from supabase import create_client
from dotenv import load_dotenv
from datetime import datetime, timedelta

# Load environment variables
load_dotenv()
load_dotenv('tests/.env')


def generate_sample_trades(n_trades: int = 200, win_rate: float = 0.55) -> pd.DataFrame:
    """
    Generate realistic sample trading data.

    The generated data includes:
    - Winning and losing trades based on win_rate
    - Realistic indicator values that correlate with outcomes
    - Various trade characteristics

    Args:
        n_trades: Number of trades to generate
        win_rate: Target win rate (0.0 to 1.0)

    Returns:
        DataFrame with sample trades
    """
    print(f"🎲 Generating {n_trades} sample trades with {win_rate*100:.1f}% win rate...")

    np.random.seed(42)

    trades = []
    base_date = datetime(2023, 1, 1)

    for i in range(n_trades):
        # Determine if this is a winning trade
        is_win = np.random.random() < win_rate

        # Generate correlated indicator values
        # Winners tend to have:
        # - Lower RSI (oversold = better buy opportunities)
        # - Higher ADX (stronger trends)
        # - Higher freshness and quality
        # - More likely to have liquidity swept

        if is_win:
            rsi = np.random.uniform(25, 65)  # Slightly oversold to neutral
            adx = np.random.uniform(25, 50)  # Strong trend
            freshness = np.random.randint(5, 11)  # Fresh zones
            base_quality = np.random.uniform(0.5, 1.0)  # High quality
            liq_swept = np.random.choice([True, False], p=[0.7, 0.3])  # More likely
            pnl_base = np.random.uniform(1.5, 4.5)  # Positive P&L
        else:
            rsi = np.random.uniform(40, 80)  # Overbought or neutral
            adx = np.random.uniform(10, 30)  # Weak trend
            freshness = np.random.randint(1, 6)  # Older zones
            base_quality = np.random.uniform(0.1, 0.6)  # Lower quality
            liq_swept = np.random.choice([True, False], p=[0.3, 0.7])  # Less likely
            pnl_base = np.random.uniform(-3.0, -0.5)  # Negative P&L

        # Add some noise to make it realistic (not perfectly correlated)
        pnl = pnl_base + np.random.normal(0, 0.5)

        # Random trade details
        side = np.random.choice(['BUY', 'SELL'])
        symbol = 'EURUSD'

        # Base price around 1.08 for EURUSD
        entry_price = 1.08 + np.random.uniform(-0.02, 0.02)

        # Calculate exit price from P&L
        if side == 'BUY':
            exit_price = entry_price * (1 + pnl / 100)
        else:
            exit_price = entry_price * (1 - pnl / 100)

        # SL and TP
        if side == 'BUY':
            sl = entry_price * 0.995  # 0.5% stop loss
            tp = entry_price * 1.015  # 1.5% take profit
        else:
            sl = entry_price * 1.005
            tp = entry_price * 0.985

        # Trade timestamps
        entry_time = base_date + timedelta(hours=i * 6)
        exit_time = entry_time + timedelta(hours=np.random.randint(2, 48))

        trade = {
            'symbol': symbol,
            'side': side,
            'entry': round(entry_price, 5),
            'sl': round(sl, 5),
            'tp': round(tp, 5),
            'close_price': round(exit_price, 5),
            'pnl': round(pnl, 2),
            'exit_type': 'Win' if is_win else 'Loss',
            'rsi': round(rsi, 2),
            'adx': round(adx, 2),
            'freshness': int(freshness),
            'base_quality': round(base_quality, 2),
            'liq_swept': liq_swept,
            'created_at': entry_time.isoformat(),
            'close_time': exit_time.isoformat(),
            'status': 'closed',
            'outcome': 'Win' if is_win else 'Loss',
        }

        trades.append(trade)

    df = pd.DataFrame(trades)

    # Calculate statistics
    wins = df[df['exit_type'] == 'Win']
    losses = df[df['exit_type'] == 'Loss']

    print("\n" + "="*70)
    print("📊 GENERATED SAMPLE DATA STATISTICS")
    print("="*70)
    print(f"Total Trades:      {len(df)}")
    print(f"Winning Trades:    {len(wins)} ({len(wins)/len(df)*100:.1f}%)")
    print(f"Losing Trades:     {len(losses)} ({len(losses)/len(df)*100:.1f}%)")
    print(f"Total P&L:         {df['pnl'].sum():.2f}%")
    print(f"Avg P&L/Trade:     {df['pnl'].mean():.2f}%")
    print(f"Avg Win:           {wins['pnl'].mean():.2f}%")
    print(f"Avg Loss:          {losses['pnl'].mean():.2f}%")
    print(f"\nAvg RSI (Wins):    {wins['rsi'].mean():.1f}")
    print(f"Avg RSI (Losses):  {losses['rsi'].mean():.1f}")
    print(f"Avg ADX (Wins):    {wins['adx'].mean():.1f}")
    print(f"Avg ADX (Losses):  {losses['adx'].mean():.1f}")
    print("="*70 + "\n")

    return df


def upload_to_supabase(df: pd.DataFrame, batch_size: int = 100) -> bool:
    """Upload trades to Supabase."""
    supabase_url = os.getenv('SUPABASE_URL')
    supabase_key = os.getenv('SUPABASE_KEY') or os.getenv('SUPABASE_ANON_KEY')

    if not supabase_url or not supabase_key:
        print("❌ Supabase credentials not found")
        return False

    print(f"📤 Uploading {len(df)} trades to Supabase...")

    supabase = create_client(supabase_url, supabase_key)
    records = df.to_dict('records')

    total_batches = (len(records) + batch_size - 1) // batch_size

    for i in range(0, len(records), batch_size):
        batch = records[i:i + batch_size]
        batch_num = (i // batch_size) + 1

        try:
            supabase.table('trading_signals').insert(batch).execute()
            print(f"  ✓ Batch {batch_num}/{total_batches}: Uploaded {len(batch)} trades")
        except Exception as e:
            print(f"  ❌ Batch {batch_num} failed: {e}")
            return False

    print(f"\n✅ Uploaded {len(records)} trades!")
    return True


def save_to_csv(df: pd.DataFrame, filename: str = 'sample_trades.csv'):
    """Save trades to CSV file."""
    df.to_csv(filename, index=False)
    print(f"💾 Saved to {filename}")


def main():
    parser = argparse.ArgumentParser(description='Generate sample trading data')
    parser.add_argument('--trades', type=int, default=200,
                        help='Number of trades to generate (default: 200)')
    parser.add_argument('--win-rate', type=float, default=0.55,
                        help='Target win rate 0.0-1.0 (default: 0.55)')
    parser.add_argument('--upload', action='store_true',
                        help='Upload to Supabase after generating')
    parser.add_argument('--csv', type=str, default='sample_trades.csv',
                        help='CSV filename to save (default: sample_trades.csv)')

    args = parser.parse_args()

    print("=" * 70)
    print("🎲 SAMPLE TRADING DATA GENERATOR")
    print("=" * 70)

    # Generate data
    df = generate_sample_trades(n_trades=args.trades, win_rate=args.win_rate)

    # Save to CSV
    save_to_csv(df, args.csv)

    # Upload if requested
    if args.upload:
        print("\n" + "="*70)
        response = input(f"⚠️  Upload {len(df)} trades to Supabase? (yes/no): ")

        if response.lower() in ['yes', 'y']:
            success = upload_to_supabase(df)

            if success:
                print("\n" + "="*70)
                print("🎉 DONE!")
                print("="*70)
                print("\nNext step: Run the optimizer")
                print("  python optimize_filters.py")
            else:
                print("\n❌ Upload failed")
        else:
            print("❌ Upload cancelled")
    else:
        print("\n💡 Tip: Use --upload flag to upload directly to Supabase")
        print("   Or use import script: python import_tradingview_backtest.py sample_trades.csv")


if __name__ == "__main__":
    main()
