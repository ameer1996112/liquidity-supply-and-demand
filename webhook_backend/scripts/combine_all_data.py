#!/usr/bin/env python3
"""
Ultimate Training Data Merger
==============================
Combines ALL data sources:
1. Notion manual backtests (572 trades, quality assessments)
2. TradingView exports (2,974 trades, V3 features)

Creates unified dataset with shared + unique features.

Usage:
    python combine_all_data.py

Output:
    - backtest_data/processed/training_ultimate.csv (~3,500 trades)
"""

import pandas as pd
import numpy as np
from pathlib import Path
import json

# TradingView export files
TV_FILES = [
    'backtest_data/tradingview_exports/trades_XAUUSD_1_1_2023_19_1_2026.csv',
    'backtest_data/tradingview_exports/trades_GBPJPY_1_1_2023_19_1_2026.csv',
    'backtest_data/tradingview_exports/trades_USDJPY_1_1_2023_19_1_2026.csv',
    'backtest_data/tradingview_exports/trades_GBPCAD_1_1_2023_19_1_2026.csv',
    'backtest_data/tradingview_exports/trades_EURUSD_1_1_2023_19_1_2026.csv'
]

def load_tradingview_exports():
    """Load and process TradingView export CSVs."""
    print("📦 Loading TradingView Exports...")
    
    all_tv_data = []
    
    for filename in TV_FILES:
        filepath = Path(filename)
        if not filepath.exists():
            print(f"  ⚠️  Skipping {filename} - not found")
            continue
        
        try:
            df = pd.read_csv(filepath, encoding='utf-8-sig')
            
            # Extract pair name from filename
            pair = filename.split('_')[1]  # e.g., "XAUUSD"
            df['pair'] = pair
            df['source'] = 'tradingview'
            
            all_tv_data.append(df)
            print(f"  ✅ {pair}: {len(df)} trades")
            
        except Exception as e:
            print(f"  ⚠️  Error loading {filename}: {e}")
    
    if not all_tv_data:
        return None
    
    combined = pd.concat(all_tv_data, ignore_index=True)
    print(f"\n  📊 Total TradingView trades: {len(combined)}")
    return combined

def load_notion_data():
    """Load processed Notion data."""
    print("\n📦 Loading Notion Data...")
    
    notion_path = Path('backtest_data/processed/training_enhanced.csv')
    if not notion_path.exists():
        print("  ⚠️  Notion data not found - run prepare_enhanced_training.py first")
        return None
    
    df = pd.read_csv(notion_path)
    df['source'] = 'notion'
    
    print(f"  ✅ Notion trades: {len(df)}")
    return df

def engineer_tv_features(df):
    """Engineer features from TradingView exports to match Notion format."""
    
    # Create win/loss target
    df['win'] = (df['Net P&L USD'] > 0).astype(int)
    
    # Pair encoding
    for pair in ['XAUUSD', 'GBPJPY', 'USDJPY', 'GBPCAD', 'EURUSD']:
        df[f'pair_{pair.lower()}'] = (df['pair'] == pair).astype(int)
    df['pair_chfjpy'] = 0  # Not in TV exports
    df['pair_nas100'] = 0  # Not in TV exports
    
    # Default values for features not in TV exports
    df['entry_default'] = 1  # Assume all are default entry
    df['entry_flip'] = 0
    df['entry_boc'] = 0
    
    df['trade_score_numeric'] = 3  # Default to "B" quality
    
    df['session_london'] = 1  # Assume all happened during London (conservative)
    df['session_newyork'] = 0
    df['session_tokyo'] = 0
    df['session_sydney'] = 0
    
    # Placeholder for missing features (will be NaN or default)
    df['liquidity_distance'] = 0  # Unknown
    df['sl_pips'] = 0  # Can calculate if SL data exists
    df['rsi'] = 50  # Neutral default
    df['zone_supply'] = (df.get('Type', '') == 'Short').astype(int) if 'Type' in df.columns else 0
    df['news_event'] = 0  # Unknown
    df['potential_rr'] = 2.0  # Standard 2:1
    df['close_bullish'] = (df.get('Type', '') == 'Long').astype(int) if 'Type' in df.columns else 0
    
    # Select only the features that match Notion format
    feature_cols = [
        'pair_xauusd', 'pair_gbpjpy', 'pair_usdjpy', 'pair_gbpcad', 
        'pair_eurusd', 'pair_chfjpy', 'pair_nas100',
        'entry_default', 'entry_flip', 'entry_boc',
        'trade_score_numeric',
        'session_london', 'session_newyork', 'session_tokyo', 'session_sydney',
        'rsi', 'news_event',
        'zone_supply', 'liquidity_distance', 'sl_pips', 'potential_rr',
        'close_bullish',
        'win', 'source'
    ]
    
    # Add pair_eurusd to match
    if 'pair_eurusd' not in df.columns:
        df['pair_eurusd'] = 0
    
    return df[feature_cols]

def combine_datasets(notion_df, tv_df):
    """Merge Notion and TradingView data."""
    print("\n🔧 Combining datasets...")
    
    # Notion already has correct format
    notion_processed = notion_df.copy()
    
    # Process TradingView data
    tv_processed = engineer_tv_features(tv_df)
    
    # Ensure both have same columns
    all_cols = set(notion_processed.columns) | set(tv_processed.columns)
    for col in all_cols:
        if col not in notion_processed.columns:
            notion_processed[col] = 0 if col != 'source' else 'notion'
        if col not in tv_processed.columns:
            tv_processed[col] = 0 if col != 'source' else 'tradingview'
    
    # Combine
    combined = pd.concat([notion_processed, tv_processed], ignore_index=True)
    
    print(f"  ✅ Combined dataset: {len(combined)} total trades")
    print(f"     - Notion (high quality): {len(notion_processed)} trades")
    print(f"     - TradingView (volume): {len(tv_processed)} trades")
    print(f"     - Win rate: {combined['win'].mean() * 100:.1f}%")
    
    return combined

def save_ultimate_dataset(df):
    """Save the ultimate training dataset."""
    output_dir = Path('backtest_data/processed')
    output_dir.mkdir(parents=True, exist_ok=True)
    
    output_path = output_dir / 'training_ultimate.csv'
    df.to_csv(output_path, index=False)
    
    print(f"\n💾 Saved to {output_path}")
    
    # Save metadata
    metadata = {
        'total_samples': len(df),
        'notion_samples': len(df[df['source'] == 'notion']),
        'tradingview_samples': len(df[df['source'] == 'tradingview']),
        'win_rate': float(df['win'].mean()),
        'features': [col for col in df.columns if col not in ['win', 'source']]
    }
    
    metadata_path = output_dir / 'ultimate_metadata.json'
    with open(metadata_path, 'w') as f:
        json.dump(metadata, f, indent=2)
    
    print(f"💾 Saved metadata to {metadata_path}")
    
    return output_path

def main():
    print("="*60)
    print("🚀 CREATING ULTIMATE TRAINING DATASET")
    print("="*60)
    print()
    
    # Load both sources
    notion_df = load_notion_data()
    tv_df = load_tradingview_exports()
    
    if notion_df is None and tv_df is None:
        print("\n❌ No data found. Cannot proceed.")
        return
    
    # Use available data
    if notion_df is not None and tv_df is not None:
        ultimate_df = combine_datasets(notion_df, tv_df)
    elif notion_df is not None:
        print("\n⚠️  Only Notion data available")
        ultimate_df = notion_df
    else:
        print("\n⚠️  Only TradingView data available")
        ultimate_df = engineer_tv_features(tv_df)
    
    # Save
    output_path = save_ultimate_dataset(ultimate_df)
    
    print("\n="*60)
    print("✅ ULTIMATE DATASET READY")
    print("="*60)
    print(f"\nNext: Run 'python scripts/train_enhanced_model.py' with this dataset")
    print()

if __name__ == '__main__':
    main()
