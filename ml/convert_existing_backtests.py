#!/usr/bin/env python3
"""
Convert existing backtest CSV files to AI training format.
Handles both GBPJPY format (with Trade Score columns) and XAUUSD format (with diagnostics JSON).
"""

import pandas as pd
import json
import sys
from pathlib import Path

def convert_gbpjpy_format(csv_path):
    """Convert GBPJPY backtest format to training data."""
    print(f"📊 Converting GBPJPY format: {csv_path}")

    df = pd.read_csv(csv_path, encoding='utf-8-sig')  # Handle BOM

    # Map columns to expected format
    training_data = []

    for _, row in df.iterrows():
        # Determine outcome
        outcome = None
        if pd.notna(row.get('Win')):
            outcome = 'Win'
        elif pd.notna(row.get('Loss')):
            outcome = 'Loss'
        elif pd.notna(row.get('BE')):
            outcome = 'Win'  # Treat BE as Win for binary classification
        else:
            continue  # Skip if no outcome

        # Map score (A=90, A-=85, B+=75, B=70, C+=65, C=60)
        score_map = {
            'A': 90, 'A-': 85, 'B+': 75, 'B': 70, 'C+': 65, 'C': 60
        }
        score = score_map.get(str(row.get('Trade Score', 'B')).strip(), 70)

        # Map RSI sentiment to numeric (-1=Bearish, 0=Between, 1=Bullish)
        rsi_map = {'Bearish': -1, 'Between': 0, 'Bullish': 1}
        rsi = rsi_map.get(str(row.get('RSI', 'Between')).strip(), 0)

        # Map strength to numeric
        strength_map = {'Strongest': 3, 'Strong': 2, 'Weak': 1}
        strength = strength_map.get(str(row.get('Leg-out Strength', 'Strong')).strip(), 2)

        # Extract features
        record = {
            'symbol': 'GBPJPY',  # Known from filename
            'outcome': outcome,
            'score': score,
            'zone_type': str(row.get('Zone Type', 'Demand')).lower(),
            'entry_model': str(row.get('Entry model', 'S&D Retest')).replace(' ', '_').upper(),
            'liquidity_distance': float(row.get('Liquidity Distance', 0)),
            'rsi': rsi,
            'session': str(row.get('Session', 'London')),
            'departure_strength': strength,
            'sl_pips': float(row.get('SL Pips', 10)),
            # Set defaults for missing features
            'freshness': 1,  # Assume fresh
            'atr_ratio': 1.0,
            'is_accuracy': 1,
            'trend': rsi,  # Use RSI as proxy for trend
            'htf_trend': rsi,
            'rvol': 1.0,
            'adx': 25.0,
            'touch_count': 0,
            'base_quality': strength,
            'return_strength': strength,
            'liquidity_spread': 100.0,  # Default
        }

        training_data.append(record)

    return pd.DataFrame(training_data)


def convert_xauusd_diagnostics_format(csv_path):
    """Convert XAUUSD format with diagnostics JSON to training data."""
    print(f"📊 Converting XAUUSD diagnostics format: {csv_path}")

    df = pd.read_csv(csv_path)

    training_data = []

    for _, row in df.iterrows():
        # Determine outcome from P&L
        pnl = float(row.get('pnl', 0))
        outcome = 'Win' if pnl > 0 else 'Loss'

        # Parse diagnostics JSON
        try:
            diag = json.loads(row.get('diagnostics', '{}'))
        except:
            diag = {}

        # Extract features
        record = {
            'symbol': 'XAUUSD',
            'outcome': outcome,
            'score': float(diag.get('zone_score', 70)),
            'zone_type': str(diag.get('zone_type', 'demand')).lower(),
            'entry_model': str(diag.get('entry_model', 'FLIP')).upper(),
            'liquidity_distance': float(diag.get('liq_distance_pips', 0)),
            'touch_count': int(diag.get('touch_count', 0)),
            'freshness': 1 if diag.get('rule_zone_fresh_24h', False) else 0,
            # Set defaults for missing features
            'rsi': 0,
            'session': 'Unknown',
            'atr_ratio': 1.0,
            'is_accuracy': 1,
            'trend': 0,
            'htf_trend': 0,
            'rvol': 1.0,
            'adx': 25.0,
            'base_quality': 2,
            'departure_strength': 2,
            'return_strength': 2,
            'liquidity_spread': 100.0,
            'sl_pips': 10.0,
        }

        training_data.append(record)

    return pd.DataFrame(training_data)


def main():
    """Convert all available backtest files and combine them."""

    project_root = Path(__file__).parent.parent
    backtest_dir = project_root / "data" / "backtest"

    print("🔍 Searching for backtest CSV files...")
    print()

    all_data = []

    # Process GBPJPY files
    gbpjpy_files = list((backtest_dir / "GBPJPY").glob("*.csv"))
    for csv_file in gbpjpy_files:
        try:
            df = convert_gbpjpy_format(csv_file)
            all_data.append(df)
            print(f"   ✅ Converted {len(df)} trades from {csv_file.name}")
        except Exception as e:
            print(f"   ❌ Failed to convert {csv_file.name}: {e}")

    # Process XAUUSD files with diagnostics
    xauusd_files = [
        backtest_dir / "XAUUSD" / "trades.csv"
    ]
    for csv_file in xauusd_files:
        if csv_file.exists():
            try:
                df = convert_xauusd_diagnostics_format(csv_file)
                all_data.append(df)
                print(f"   ✅ Converted {len(df)} trades from {csv_file.name}")
            except Exception as e:
                print(f"   ❌ Failed to convert {csv_file.name}: {e}")

    if not all_data:
        print("❌ No backtest files could be converted!")
        print()
        print("Please export fresh data from TradingView Strategy Tester.")
        return 1

    # Combine all data
    combined_df = pd.concat(all_data, ignore_index=True)

    print()
    print(f"📊 Combined Statistics:")
    print(f"   Total trades: {len(combined_df)}")
    print(f"   Wins: {len(combined_df[combined_df['outcome'] == 'Win'])}")
    print(f"   Losses: {len(combined_df[combined_df['outcome'] == 'Loss'])}")
    print(f"   Win rate: {len(combined_df[combined_df['outcome'] == 'Win']) / len(combined_df) * 100:.1f}%")
    print()

    # Save to training_data.csv
    output_path = project_root / "ml" / "training_data.csv"
    combined_df.to_csv(output_path, index=False)

    print(f"✅ Training data saved to: {output_path}")
    print()
    print("📈 Next steps:")
    print(f"   1. Train model: python ml/train_ai_guardian_v2_pro.py --data {output_path}")
    print("   2. Review results: open ml/model_metrics_v2.png")
    print("   3. Deploy to Railway: git add ml/ && git commit && git push")
    print()

    # Check if we have enough data
    if len(combined_df) < 100:
        print("⚠️  WARNING: Less than 100 samples may result in poor model performance.")
        print("   Recommendation: Export more data from TradingView Strategy Tester.")
        print()

    return 0


if __name__ == "__main__":
    sys.exit(main())
