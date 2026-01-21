#!/usr/bin/env python3
"""
Multi-Pair Backtest Analysis Pipeline
======================================
Analyzes all Notion CSV backtest exports to identify profitable patterns.
Focus: Long-term P&L, expectancy, profit factor (not win rate).

Usage:
    python analyze_all_pairs.py

Output:
    - reports/pair_performance.json
    - reports/optimal_filters.json
    - reports/training_data_enhanced.csv
"""

import os
import pandas as pd
import numpy as np
from pathlib import Path
import json
from datetime import datetime

# Pair folders to analyze
PAIRS = ['XAUUSD', 'GBPJPY', 'USDJPY', 'GBPCAD', 'GBPUSD', 'CHFJPY', 'NAS100']

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
    pair_dir = Path(pair_name)
    if not pair_dir.exists():
        print(f"⚠️  Skipping {pair_name} - folder not found")
        return None
    
    csv_files = list(pair_dir.glob('*.csv'))
    if not csv_files:
        print(f"⚠️  Skipping {pair_name} - no CSV files")
        return None
    
    # Load all CSVs and combine
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
    combined['Pair'] = pair_name
    return combined

def calculate_metrics(df):
    """Calculate comprehensive performance metrics."""
    # Parse R returns
    df['R_Return'] = df['+ R (%)'].apply(parse_rplus)
    
    # Basic stats
    total_trades = len(df)
    wins = df[df['R_Return'] > 0]
    losses = df[df['R_Return'] < 0]
    
    win_count = len(wins)
    loss_count = len(losses)
    win_rate = (win_count / total_trades * 100) if total_trades > 0 else 0
    
    # P&L metrics
    total_r = df['R_Return'].sum()
    avg_win = wins['R_Return'].mean() if len(wins) > 0 else 0
    avg_loss = abs(losses['R_Return'].mean()) if len(losses) > 0 else 1
    
    # Profit factor
    gross_profit = wins['R_Return'].sum() if len(wins) > 0 else 0
    gross_loss = abs(losses['R_Return'].sum()) if len(losses) > 0 else 1
    profit_factor = gross_profit / gross_loss if gross_loss > 0 else 0
    
    # Expectancy (average R per trade)
    expectancy = total_r / total_trades if total_trades > 0 else 0
    
    # Sharpe-like metric
    if len(df) > 1:
        sharpe = df['R_Return'].mean() / df['R_Return'].std() if df['R_Return'].std() > 0 else 0
    else:
        sharpe = 0
    
    return {
        'total_trades': total_trades,
        'win_count': win_count,
        'loss_count': loss_count,
        'win_rate': win_rate,
        'total_r': total_r,
        'avg_win': avg_win,
        'avg_loss': avg_loss,
        'profit_factor': profit_factor,
        'expectancy': expectancy,
        'sharpe': sharpe,
        'rr_ratio': avg_win / avg_loss if avg_loss > 0 else 0
    }

def analyze_by_category(df, category_col):
    """Analyze metrics broken down by a categorical variable."""
    if category_col not in df.columns:
        return {}
    
    results = {}
    for category in df[category_col].dropna().unique():
        subset = df[df[category_col] == category]
        metrics = calculate_metrics(subset)
        results[str(category)] = metrics
    
    return results

def find_optimal_filters(df):
    """Identify filter thresholds that maximize profit factor."""
    recommendations = {}
    
    # Liquidity Distance (if available)
    if 'Liquidity Distance' in df.columns:
        df['Liquidity Distance'] = pd.to_numeric(df['Liquidity Distance'], errors='coerce')
        thresholds = [50, 75, 100, 150, 200]
        best_pf = 0
        best_threshold = None
        
        for thresh in thresholds:
            subset = df[df['Liquidity Distance'] <= thresh]
            if len(subset) > 10:  # Minimum sample size
                metrics = calculate_metrics(subset)
                if metrics['profit_factor'] > best_pf:
                    best_pf = metrics['profit_factor']
                    best_threshold = thresh
        
        if best_threshold:
            recommendations['max_liquidity_distance'] = {
                'value': best_threshold,
                'profit_factor': best_pf
            }
    
    # SL Pips range (if available)
    if 'SL Pips' in df.columns:
        df['SL Pips'] = pd.to_numeric(df['SL Pips'], errors='coerce')
        # Test different ranges
        ranges = [(50, 300), (60, 250), (80, 200), (100, 300)]
        best_pf = 0
        best_range = None
        
        for min_sl, max_sl in ranges:
            subset = df[(df['SL Pips'] >= min_sl) & (df['SL Pips'] <= max_sl)]
            if len(subset) > 10:
                metrics = calculate_metrics(subset)
                if metrics['profit_factor'] > best_pf:
                    best_pf = metrics['profit_factor']
                    best_range = (min_sl, max_sl)
        
        if best_range:
            recommendations['sl_pips_range'] = {
                'min': best_range[0],
                'max': best_range[1],
                'profit_factor': best_pf
            }
    
    return recommendations

def generate_report():
    """Main analysis function."""
    print("="*60)
    print("🚀 MULTI-PAIR BACKTEST ANALYSIS")
    print("="*60)
    print()
    
    all_data = []
    pair_performance = {}
    
    for pair in PAIRS:
        print(f"📊 Analyzing {pair}...")
        df = load_pair_data(pair)
        
        if df is None:
            continue
        
        all_data.append(df)
        
        # Overall metrics
        overall = calculate_metrics(df)
        
        # Breakdown by categories
        by_entry_type = analyze_by_category(df, 'Entry Type')
        by_trade_score = analyze_by_category(df, 'Trade Score')
        by_session = analyze_by_category(df, 'Session')
        
        # Optimal filters
        filters = find_optimal_filters(df)
        
        pair_performance[pair] = {
            'overall': overall,
            'by_entry_type': by_entry_type,
            'by_trade_score': by_trade_score,
            'by_session': by_session,
            'optimal_filters': filters
        }
        
        # Print summary
        print(f"  Total Trades: {overall['total_trades']}")
        print(f"  Win Rate: {overall['win_rate']:.1f}%")
        print(f"  Total R: {overall['total_r']:.2f}R")
        print(f"  Profit Factor: {overall['profit_factor']:.2f}")
        print(f"  Expectancy: {overall['expectancy']:.3f}R per trade")
        print(f"  Verdict: {'✅ PROFITABLE' if overall['profit_factor'] > 1.0 else '❌ LOSING'}")
        print()
    
    # Combined analysis
    if all_data:
        combined_df = pd.concat(all_data, ignore_index=True)
        combined_metrics = calculate_metrics(combined_df)
        
        print("="*60)
        print("🎯 COMBINED PORTFOLIO METRICS")
        print("="*60)
        print(f"Total Trades Across All Pairs: {combined_metrics['total_trades']}")
        print(f"Overall Win Rate: {combined_metrics['win_rate']:.1f}%")
        print(f"Combined Total R: {combined_metrics['total_r']:.2f}R")
        print(f"Combined Profit Factor: {combined_metrics['profit_factor']:.2f}")
        print(f"Combined Expectancy: {combined_metrics['expectancy']:.3f}R per trade")
        print()
        
        pair_performance['COMBINED'] = {
            'overall': combined_metrics
        }
    
    # Save reports
    reports_dir = Path('reports')
    reports_dir.mkdir(exist_ok=True)
    
    with open(reports_dir / 'pair_performance.json', 'w') as f:
        json.dump(pair_performance, f, indent=2)
    
    print("✅ Reports saved to reports/pair_performance.json")
    print()
    
    # Identify best pairs
    profitable_pairs = [
        pair for pair, data in pair_performance.items()
        if pair != 'COMBINED' and data['overall']['profit_factor'] > 1.0
    ]
    
    print("="*60)
    print("💰 MONEY MAKER PAIRS")
    print("="*60)
    for pair in profitable_pairs:
        pf = pair_performance[pair]['overall']['profit_factor']
        exp = pair_performance[pair]['overall']['expectancy']
        print(f"  {pair}: PF={pf:.2f}, Expectancy={exp:.3f}R")
    print()
    
    if not profitable_pairs:
        print("⚠️  No profitable pairs found. Strategy needs optimization!")
    
    return pair_performance

if __name__ == '__main__':
    generate_report()
