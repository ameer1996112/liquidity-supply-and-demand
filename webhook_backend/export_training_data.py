#!/usr/bin/env python3
"""
Training Data Exporter
======================
Exports closed trades from Supabase to CSV format for model retraining.

Usage:
    python export_training_data.py

Output:
    backtest_data/live/training_live_YYYY_MM_DD.csv
"""

import supabase_db
from datetime import datetime
import pandas as pd
from pathlib import Path

def export_training_data():
    """Export closed trades from Supabase to CSV"""
    print("="*60)
    print("📦 TRAINING DATA EXPORT")
    print("="*60)

    # Initialize Supabase
    supabase_db.init_supabase()

    # Get all closed trades with outcomes
    all_trades = supabase_db.supabase.table('trading_signals').select('*').execute().data

    # Filter for closed trades with win/loss outcome
    closed_trades = [
        t for t in all_trades
        if t.get('status') == 'closed' and t.get('outcome') in ['win', 'loss']
    ]

    print(f"✅ Found {len(closed_trades)} closed trades")

    if len(closed_trades) == 0:
        print("⚠️  No closed trades to export. Continue trading!")
        return

    # Convert to training format (V7.1 - 17 features)
    training_rows = []

    for trade in closed_trades:
        # Extract features (same as in trading_bot.py predict_win_probability)
        row = {
            # V7.1 Features (17 total)
            'Score': trade.get('score', 50),
            'Freshness': trade.get('freshness', 10),
            'Session': trade.get('session', 1),
            'ZoneType': 0 if trade.get('side', '').lower() == 'buy' else 1,
            'ATR_Ratio': trade.get('atr_ratio', 0.5),
            'isAccuracy': int(trade.get('is_accuracy', 0)),
            'Trend': trade.get('trend', 1),
            'RSI': trade.get('rsi', 50),
            'HTF_Trend': trade.get('htf_trend', 1),
            'RVOL': trade.get('rvol', 1.0),
            'ADX': trade.get('adx', 25.0),
            'TouchCount': trade.get('touch_count', 0),
            'BaseQuality': trade.get('base_quality', 50.0),
            'DepartureStrength': trade.get('departure_strength', 50.0),
            'LiquidityDistance': trade.get('liquidity_distance', 50.0),
            'LiquiditySpread': trade.get('liquidity_spread', 50.0),
            'ReturnStrength': trade.get('return_strength', 50.0),
            # Target
            'Target': 1 if trade.get('outcome') == 'win' else 0,
            # Metadata (not used in training, but useful for analysis)
            'trade_id': trade.get('id'),
            'symbol': trade.get('symbol'),
            'created_at': trade.get('created_at'),
        }
        training_rows.append(row)

    # Create DataFrame
    df = pd.DataFrame(training_rows)

    # Save to CSV
    output_dir = Path('backtest_data/live')
    output_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.utcnow().strftime('%Y_%m_%d')
    output_path = output_dir / f'training_live_{timestamp}.csv'

    df.to_csv(output_path, index=False)

    print(f"💾 Exported to: {output_path}")
    print(f"   Samples: {len(df)}")
    print(f"   Wins: {df['Target'].sum()}")
    print(f"   Losses: {len(df) - df['Target'].sum()}")
    print(f"   Win Rate: {df['Target'].mean():.1%}")

    # Show feature summary
    print(f"\n📊 Feature Summary:")
    print(f"   Score:              {df['Score'].mean():.1f} ± {df['Score'].std():.1f}")
    print(f"   Freshness:          {df['Freshness'].mean():.1f}")
    print(f"   Liquidity Distance: {df['LiquidityDistance'].mean():.1f} ± {df['LiquidityDistance'].std():.1f}")

    print("\n" + "="*60)
    print("✅ EXPORT COMPLETE")
    print("="*60)
    print("\nNext Steps:")
    print("1. Merge with historical data:")
    print(f"   cat {output_path} >> backtest_data/processed/training_ultimate.csv")
    print("\n2. Retrain model:")
    print("   python scripts/train_enhanced_model.py")
    print("\n3. Deploy new model to production")
    print("="*60)

if __name__ == '__main__':
    export_training_data()
