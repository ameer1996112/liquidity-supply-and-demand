#!/usr/bin/env python3
"""
Export training data from Supabase trading_signals table.
Creates CSV files compatible with train_ai_guardian.py.

Usage:
    python scripts/export_training_data.py
"""

import os
import sys
from pathlib import Path
import pandas as pd
from datetime import datetime

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.adapters.supabase import init_supabase, supabase


def export_training_data():
    """Export closed trades from Supabase to CSV for ML training."""

    # Initialize Supabase
    init_supabase()
    if not supabase:
        print("❌ Supabase not connected. Check .env credentials.")
        sys.exit(1)

    # Fetch all closed trades with outcome
    print("📥 Fetching closed trades from Supabase...")
    query = (
        supabase.table("trading_signals")
        .select("*")
        .in_("outcome", ["win", "loss"])
        .neq("pnl_r", None)
        .order("created_at", desc=False)
    )

    result = query.execute()

    if not result.data:
        print("❌ No closed trades found in database.")
        print("   Trade some signals first, then export data for training.")
        sys.exit(1)

    print(f"✅ Found {len(result.data)} closed trades")

    # Convert to DataFrame
    df = pd.DataFrame(result.data)

    # Map to training format (TradingView-like columns)
    training_data = pd.DataFrame({
        'symbol': df['symbol'],
        'type': df['side'].str.lower(),  # buy/sell
        'signal': df.get('signal', ''),
        'close_time': df['exit_time'],
        'profit_pct': df['pnl_r'],  # R multiples (for win/loss classification)

        # Additional features (if available)
        'entry_model': df.get('entry_model', ''),
        'zone_type': df.get('zone_type', ''),
        'session': df.get('session', ''),
        'score': df.get('score', 0),
        'freshness': df.get('freshness', 0),
        'atr_ratio': df.get('atr_ratio', 0),
        'trend': df.get('trend', 0),
        'htf_trend': df.get('htf_trend', 0),
        'rsi': df.get('rsi', 0),
        'rvol': df.get('rvol', 0),
        'adx': df.get('adx', 0),
        'touch_count': df.get('touch_count', 0),
        'base_quality': df.get('base_quality', 0),
        'departure_strength': df.get('departure_strength', 0),
        'liquidity_distance': df.get('liquidity_distance', 0),
        'return_strength': df.get('return_strength', 0),
        '_source': 'database',
    })

    # Create backtest_data directory
    output_dir = project_root / 'backtest_data'
    output_dir.mkdir(exist_ok=True)

    # Group by symbol and save separate CSVs
    symbols = training_data['symbol'].unique()

    for symbol in symbols:
        symbol_df = training_data[training_data['symbol'] == symbol]

        if len(symbol_df) < 10:
            print(f"⚠️  Skipping {symbol}: only {len(symbol_df)} trades (need 10+ for training)")
            continue

        filename = f"trades_{symbol}_{datetime.now().strftime('%Y%m%d')}.csv"
        filepath = output_dir / filename

        symbol_df.to_csv(filepath, index=False)
        print(f"✅ Exported {len(symbol_df)} trades for {symbol} → {filename}")

    # Save combined file
    combined_file = output_dir / f"all_trades_{datetime.now().strftime('%Y%m%d')}.csv"
    training_data.to_csv(combined_file, index=False)
    print(f"\n✅ Combined file: {combined_file}")

    print(f"\n📊 Summary:")
    print(f"   Total trades: {len(training_data)}")
    print(f"   Symbols: {len(symbols)}")
    print(f"   Win rate: {(training_data['profit_pct'] > 0).mean():.1%}")

    print(f"\n🚀 Next step: Train the model")
    print(f"   python ml/train_ai_guardian.py --data backtest_data")


if __name__ == "__main__":
    export_training_data()
