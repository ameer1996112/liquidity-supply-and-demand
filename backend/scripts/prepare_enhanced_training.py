#!/usr/bin/env python3
"""
Enhanced Training Data Preparation
===================================
Calculates derived features from raw telemetry:
- Time-to-Target Ratio (TTR)
- Drawdown-Liquidity Alignment (DLA)
- Liquidity Invalidation Rate (LIR)

Usage:
    python prepare_enhanced_training.py
"""

import pandas as pd
import numpy as np
from pathlib import Path
import sqlite3
import json

DB_PATH = Path(__file__).parent.parent / 'trades.db'


def calculate_time_to_target_ratio(df):
    """Calculate Time-to-Target Ratio (TTR)"""
    print("📊 Calculating Time-to-Target Ratio (TTR)...")
    
    wins = df[df['outcome'] == 'win'].copy()
    
    if len(wins) == 0:
        df['time_to_target_ratio'] = np.nan
        return df
    
    wins['tp_pips'] = abs(wins['tp'] - wins['entry'])
    wins['zone_size_pips'] = wins.get('zone_size_pips', 20)
    wins['atr_pips'] = np.where(
        wins['atr_ratio'] > 0,
        wins['zone_size_pips'] / wins['atr_ratio'],
        20
    )
    
    wins['expected_bars'] = (wins['tp_pips'] / wins['atr_pips'].clip(lower=1)) * 14
    wins['actual_bars'] = wins['bars_held'].clip(lower=1)
    wins['ttr_raw'] = wins['expected_bars'] / wins['actual_bars']
    wins['time_to_target_ratio'] = (wins['ttr_raw'] * 50).clip(0, 100)
    
    df['time_to_target_ratio'] = df.index.map(wins['time_to_target_ratio'])
    df.loc[df['outcome'] != 'win', 'time_to_target_ratio'] = np.nan
    
    print(f"  ✅ Calculated TTR for {len(wins)} winning trades")
    return df


def calculate_drawdown_liquidity_alignment(df):
    """Calculate Drawdown-Liquidity Alignment (DLA)"""
    print("📊 Calculating Drawdown-Liquidity Alignment (DLA)...")
    
    valid = df[
        df['mae_pips'].notna() &
        df['liquidity_distance'].notna() &
        (df['liquidity_distance'] > 0)
    ].copy()
    
    if len(valid) == 0:
        df['drawdown_liq_alignment'] = np.nan
        return df
    
    valid['mae_liq_ratio'] = valid['mae_pips'] / valid['liquidity_distance']
    
    def score_alignment(ratio):
        if pd.isna(ratio):
            return np.nan
        if 0.8 <= ratio <= 1.2:
            return 100
        elif 0.5 <= ratio <= 1.5:
            return 70
        elif 0.3 <= ratio <= 2.0:
            return 40
        else:
            return 10
    
    valid['drawdown_liq_alignment'] = valid['mae_liq_ratio'].apply(score_alignment)
    df['drawdown_liq_alignment'] = df.index.map(valid['drawdown_liq_alignment'])
    
    print(f"  ✅ Calculated DLA for {len(valid)} trades")
    return df


def calculate_liquidity_invalidation_rate(df):
    """Calculate Liquidity Invalidation Rate (LIR)"""
    print("📊 Calculating Liquidity Invalidation Rate (LIR)...")
    
    df['lir_base'] = np.where(
        df['liq_swept'] & df['target_swept'],
        100,
        np.where(
            df['liq_swept'] | df['target_swept'],
            70,
            30
        )
    )
    
    df['liq_spread_clean'] = df['liquidity_spread'].fillna(100)
    df['spread_penalty'] = (df['liq_spread_clean'] / 100) * 30
    df['liq_invalidation_rate'] = (df['lir_base'] - df['spread_penalty']).clip(0, 100)
    df.drop(['lir_base', 'liq_spread_clean', 'spread_penalty'], axis=1, inplace=True)
    
    print(f"  ✅ Calculated LIR for {len(df)} trades")
    return df


def calculate_liquidity_confidence_score(df):
    """Calculate Master Liquidity Confidence Score"""
    print("📊 Calculating Master Liquidity Confidence Score...")
    
    score = 50.0
    
    df['dist_score'] = np.where(
        df['liquidity_distance'] <= 50, 20,
        np.where(df['liquidity_distance'] <= 100, 10,
        np.where(df['liquidity_distance'] <= 200, 5, 0))
    )
    
    df['sweep_score'] = np.where(
        df['liq_swept'] & df['target_swept'], 20,
        np.where(df['liq_swept'] | df['target_swept'], 10, -10)
    )
    
    df['spread_score'] = np.where(
        df['liquidity_spread'] <= 50, 10,
        np.where(df['liquidity_spread'] <= 150, 5, -10)
    )
    
    df['fresh_score'] = np.where(
        df['freshness'] <= 1, 10,
        np.where(df['freshness'] <= 2, 5, -10)
    )
    
    df['liq_confidence_score'] = (
        score +
        df['dist_score'] +
        df['sweep_score'] +
        df['spread_score'] +
        df['fresh_score']
    ).clip(0, 100)
    
    df.drop(['dist_score', 'sweep_score', 'spread_score', 'fresh_score'], axis=1, inplace=True)
    
    print(f"  ✅ Mean Confidence: {df['liq_confidence_score'].mean():.1f}")
    return df


def load_trades_from_database():
    """Load all trades from database"""
    print("\n📦 Loading trades from database...")
    
    conn = sqlite3.connect(DB_PATH)
    df = pd.read_sql_query("""
        SELECT * FROM alerts
        WHERE status IN ('closed', 'taken')
        AND outcome IS NOT NULL
    """, conn)
    conn.close()
    
    print(f"  ✅ Loaded {len(df)} closed trades")
    return df


def save_computed_features_to_db(df):
    """Save computed features back to database"""
    print("\n💾 Saving computed features to database...")
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    update_count = 0
    for idx, row in df.iterrows():
        cursor.execute("""
            UPDATE alerts
            SET time_to_target_ratio = ?,
                drawdown_liq_alignment = ?,
                liq_invalidation_rate = ?,
                liq_confidence_score = ?
            WHERE id = ?
        """, (
            row.get('time_to_target_ratio'),
            row.get('drawdown_liq_alignment'),
            row.get('liq_invalidation_rate'),
            row.get('liq_confidence_score'),
            row['id']
        ))
        update_count += 1
    
    conn.commit()
    conn.close()
    
    print(f"  ✅ Updated {update_count} records")


def export_training_data(df, output_path):
    """Export processed training data to CSV"""
    print(f"\n📤 Exporting to {output_path}...")
    
    df['win'] = (df['outcome'] == 'win').astype(int)
    
    training_cols = [
        'win', 'score', 'freshness', 'session', 'atr_ratio', 'trend', 'rsi',
        'htf_trend', 'rvol', 'adx', 'touch_count', 'base_quality',
        'departure_strength', 'liquidity_distance', 'liquidity_spread',
        'return_strength', 'time_to_target_ratio', 'drawdown_liq_alignment',
        'liq_invalidation_rate', 'liq_confidence_score',
        'symbol', 'entry_model', 'zone_type', 'outcome'
    ]
    
    available_cols = [c for c in training_cols if c in df.columns]
    export_df = df[available_cols].copy()
    
    critical_features = ['score', 'freshness', 'session', 'rsi', 'rvol', 'adx']
    export_df = export_df.dropna(subset=critical_features)
    
    export_df.to_csv(output_path, index=False)
    print(f"  ✅ Exported {len(export_df)} training samples")
    
    return export_df


def main():
    """Main execution"""
    print("=" * 60)
    print("🚀 ENHANCED TRAINING DATA PREPARATION")
    print("=" * 60)
    
    df = load_trades_from_database()
    
    if len(df) == 0:
        print("\n❌ No trades found in database. Run some trades first!")
        return
    
    df = calculate_time_to_target_ratio(df)
    df = calculate_drawdown_liquidity_alignment(df)
    df = calculate_liquidity_invalidation_rate(df)
    df = calculate_liquidity_confidence_score(df)
    
    save_computed_features_to_db(df)
    
    output_dir = Path(__file__).parent.parent / 'backtest_data' / 'processed'
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / 'training_with_derived_features.csv'
    
    export_df = export_training_data(df, output_path)
    
    print("\n" + "=" * 60)
    print("✅ FEATURE ENGINEERING COMPLETE")
    print("=" * 60)
    print(f"\nReady for model training with {len(export_df)} samples\n")


if __name__ == '__main__':
    main()
