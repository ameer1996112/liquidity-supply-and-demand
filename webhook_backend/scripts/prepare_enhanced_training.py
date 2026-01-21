#!/usr/bin/env python3
"""
Enhanced AI Training Data Generator
====================================
Combines all profitable pairs' backtest data into a single training set.
Adds engineered features and prepares data for model retraining.

Usage:
    python prepare_enhanced_training.py

Output:
    - data/training_enhanced.csv
    - data/features_metadata.json
"""

import pandas as pd
import numpy as np
from pathlib import Path
import json

# Profitable pairs to include
PROFITABLE_PAIRS = ['XAUUSD', 'GBPJPY', 'USDJPY', 'GBPCAD', 'CHFJPY', 'NAS100']

def parse_rplus(value):
    """Convert '3%' or '-1%' to float."""
    if pd.isna(value):
        return 0.0
    try:
        return float(str(value).replace('%', ''))
    except:
        return 0.0

def load_pair_data(pair_name):
    """Load all CSV files for a given pair."""
    pair_dir = Path('backtest_data/notion_exports') / pair_name
    if not pair_dir.exists():
        return None
    
    csv_files = list(pair_dir.glob('*.csv'))
    if not csv_files:
        return None
    
    dfs = []
    for csv_file in csv_files:
        try:
            df = pd.read_csv(csv_file, encoding='utf-8-sig')
            dfs.append(df)
        except Exception as e:
            print(f"⚠️  Error reading {csv_file}: {e}")
    
    if not dfs:
        return None
    
    combined = pd.concat(dfs, ignore_index=True)
    combined['pair'] = pair_name
    return combined

def engineer_features(df):
    """Add engineered features for AI training."""
    
    # 1. Parse R returns and create binary target
    df['r_return'] = df['+ R (%)'].apply(parse_rplus)
    df['win'] = (df['r_return'] > 0).astype(int)
    
    # 2. Entry Type one-hot encoding
    df['entry_default'] = (df['Entry Type'] == 'Default').astype(int)
    df['entry_flip'] = (df['Entry Type'] == 'Flip').astype(int)
    df['entry_boc'] = (df['Entry Type'] == 'BOC').astype(int)
    
    # 3. Trade Score mapping (A+=5, A=4, B+=3, B=2, C+=1)
    score_map = {'A+': 5, 'A': 4, 'B+': 3, 'B': 2, 'C+': 1}
    df['trade_score_numeric'] = df['Trade Score'].map(score_map).fillna(2)
    
    # 4. Session encoding (most common sessions)
    df['session_london'] = df['Session'].fillna('').str.contains('London').astype(int)
    df['session_newyork'] = df['Session'].fillna('').str.contains('New York').astype(int)
    df['session_tokyo'] = df['Session'].fillna('').str.contains('Tokyo').astype(int)
    df['session_sydney'] = df['Session'].fillna('').str.contains('Sydney').astype(int)
    
    # 5. Numeric features
    df['liquidity_distance'] = pd.to_numeric(df.get('Liquidity Distance', 0), errors='coerce').fillna(0)
    df['sl_pips'] = pd.to_numeric(df.get('SL Pips', 0), errors='coerce').fillna(0)
    df['rsi'] = pd.to_numeric(df.get('RSI', 50), errors='coerce').fillna(50)
    
    # 6. Zone type (Demand=0, Supply=1)
    df['zone_supply'] = (df.get('Zone Type', '') == 'Supply').astype(int)
    
    # 7. News flag
    df['news_event'] = (df.get('News', 'No') == 'Yes').astype(int)
    
    # 8. Pair encoding (one-hot)
    for pair in PROFITABLE_PAIRS:
        df[f'pair_{pair.lower()}'] = (df['pair'] == pair).astype(int)
    
    # 9. Potential R (risk-reward)
    df['potential_rr'] = pd.to_numeric(
        df.get('Potential R', '2%').astype(str).str.replace('%', ''), 
        errors='coerce'
    ).fillna(2.0)
    
    # 10. Candle close direction
    df['close_bullish'] = (df.get('Candle Close', '') == 'Bullish').astype(int)
    
    return df

def create_training_dataset():
    """Generate enhanced training dataset."""
    print("="*60)
    print("🧠 CREATING ENHANCED AI TRAINING DATA")
    print("="*60)
    print()
    
    all_data = []
    
    for pair in PROFITABLE_PAIRS:
        print(f"📦 Loading {pair}...")
        df = load_pair_data(pair)
        
        if df is None:
            print(f"  ⚠️  Skipped (no data)")
            continue
        
        print(f"  ✅ {len(df)} trades")
        all_data.append(df)
    
    # Combine all pairs
    combined = pd.concat(all_data, ignore_index=True)
    print()
    print(f"📊 Total trades combined: {len(combined)}")
    
    # Engineer features
    print("🔧 Engineering features...")
    enhanced = engineer_features(combined)
    
    # Select feature columns for training
    feature_cols = [
        # Pair identification
        'pair_xauusd', 'pair_gbpjpy', 'pair_usdjpy', 
        'pair_gbpcad', 'pair_chfjpy', 'pair_nas100',
        
        # Entry characteristics
        'entry_default', 'entry_flip', 'entry_boc',
        'trade_score_numeric',
        
        # Market conditions
        'session_london', 'session_newyork', 'session_tokyo', 'session_sydney',
        'rsi', 'news_event',
        
        # Zone properties
        'zone_supply', 'liquidity_distance', 'sl_pips', 'potential_rr',
        
        # Price action
        'close_bullish',
        
        # Target
        'win'
    ]
    
    # Filter to only rows with complete data
    training_data = enhanced[feature_cols].dropna()
    
    print(f"✅ Training samples: {len(training_data)}")
    print(f"✅ Features: {len(feature_cols) - 1} (+ 1 target)")
    print(f"✅ Win rate: {training_data['win'].mean() * 100:.1f}%")
    print()
    
    # Save training data
    data_dir = Path('backtest_data/processed')
    data_dir.mkdir(parents=True, exist_ok=True)
    
    training_data.to_csv(data_dir / 'training_enhanced.csv', index=False)
    print(f"💾 Saved to backtest_data/processed/training_enhanced.csv")
    
    # Save feature metadata
    feature_metadata = {
        'features': feature_cols[:-1],  # Exclude target
        'target': 'win',
        'total_samples': len(training_data),
        'win_rate': float(training_data['win'].mean()),
        'pairs_included': PROFITABLE_PAIRS
    }
    
    with open(data_dir / 'features_metadata.json', 'w') as f:
        json.dump(feature_metadata, f, indent=2)
    
    print(f"💾 Saved metadata to backtest_data/processed/features_metadata.json")
    print()
    print("="*60)
    print("✅ READY FOR AI MODEL TRAINING")
    print("="*60)
    
    return training_data

if __name__ == '__main__':
    create_training_dataset()
