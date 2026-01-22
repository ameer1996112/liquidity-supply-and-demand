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
    pair_dir = Path('backtest_data/notion_exports') / pair_name
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


def calculate_liquidity_confidence_score_simple(trade_row):
    """
    Calculate liquidity confidence (0-100) for a single trade.
    Used for weighting "Golden Parameters"
    """
    score = 50.0

    # Factor 1: Liquidity Distance
    liq_dist = trade_row.get('Liquidity Distance', 100)
    if liq_dist <= 50:
        score += 20
    elif liq_dist <= 100:
        score += 10
    elif liq_dist > 200:
        score -= 15

    # Factor 2: Sweep Status
    liq_swept = trade_row.get('Liq Swept', False)
    target_swept = trade_row.get('Target Swept', False)
    if liq_swept and target_swept:
        score += 20
    elif liq_swept or target_swept:
        score += 10
    else:
        score -= 10

    # Factor 3: Liquidity Spread
    liq_spread = trade_row.get('Liquidity Spread', 100)
    if liq_spread <= 50:
        score += 10
    elif liq_spread > 150:
        score -= 10

    # Factor 4: Zone Freshness
    touch_count = trade_row.get('Touch Count', 3)
    if touch_count <= 1:
        score += 10
    elif touch_count >= 3:
        score -= 10

    return max(0, min(100, score))


def calculate_weighted_score(metrics, avg_liq_confidence):
    """
    Calculate weighted "Golden Parameter" score.

    Formula:
        Final_Score = (Win_Rate * 0.4) + (Profit_Factor * 0.3) + (Liq_Confidence * 0.3)

    Args:
        metrics: Dict with 'win_rate' and 'profit_factor'
        avg_liq_confidence: Average liquidity confidence (0-100)

    Returns:
        float: Weighted score (0-100)
    """
    # Normalize components to 0-1 scale
    win_rate_norm = metrics['win_rate'] / 100  # Already in 0-100

    # Profit factor normalization: PF=2.0 = 1.0, PF=1.0 = 0.5, PF=0.5 = 0.25
    pf_norm = min(1.0, metrics['profit_factor'] / 2.0)

    liq_conf_norm = avg_liq_confidence / 100  # Already in 0-100

    # Weighted combination (returns 0-1)
    weighted = (win_rate_norm * 0.4) + (pf_norm * 0.3) + (liq_conf_norm * 0.3)

    # Scale back to 0-100
    return weighted * 100


def find_optimal_filters_weighted(df):
    """
    Enhanced version that weights profit factor by liquidity confidence.
    Returns parameter sets with confidence-adjusted performance metrics.
    """
    print("\n🔍 Finding Optimal Filters (Liquidity-Weighted)...")

    # Add liquidity confidence score to each trade
    if 'Liquidity Distance' not in df.columns:
        print("  ⚠️  Missing liquidity data, using unweighted analysis")
        return find_optimal_filters(df)  # Fallback to old method

    df['liq_confidence'] = df.apply(calculate_liquidity_confidence_score_simple, axis=1)

    recommendations = {}

    # === SEGMENT BY CONFIDENCE TIER ===
    tiers = {
        'high': df[df['liq_confidence'] >= 70],
        'medium': df[(df['liq_confidence'] >= 50) & (df['liq_confidence'] < 70)],
        'low': df[df['liq_confidence'] < 50]
    }

    for tier_name, tier_df in tiers.items():
        if len(tier_df) < 10:
            continue

        metrics = calculate_metrics(tier_df)
        avg_conf = tier_df['liq_confidence'].mean()
        weighted_score = calculate_weighted_score(metrics, avg_conf)

        recommendations[f'{tier_name}_confidence'] = {
            'trade_count': len(tier_df),
            'win_rate': metrics['win_rate'],
            'profit_factor': metrics['profit_factor'],
            'expectancy': metrics['expectancy'],
            'avg_liquidity_confidence': avg_conf,
            'weighted_score': weighted_score,
            'avg_liquidity_distance': tier_df['Liquidity Distance'].mean() if 'Liquidity Distance' in tier_df else None,
            'avg_sl_pips': tier_df['SL Pips'].mean() if 'SL Pips' in tier_df else None
        }

    # === FIND OPTIMAL SL RANGE (WEIGHTED) ===
    if 'SL Pips' in df.columns:
        df['SL Pips'] = pd.to_numeric(df['SL Pips'], errors='coerce')
        sl_ranges = [(50, 300), (60, 250), (80, 200), (100, 300)]

        best_weighted_score = 0
        best_sl_range = None

        for min_sl, max_sl in sl_ranges:
            subset = df[(df['SL Pips'] >= min_sl) & (df['SL Pips'] <= max_sl)]
            if len(subset) < 10:
                continue

            metrics = calculate_metrics(subset)
            avg_conf = subset['liq_confidence'].mean()
            weighted_score = calculate_weighted_score(metrics, avg_conf)

            if weighted_score > best_weighted_score:
                best_weighted_score = weighted_score
                best_sl_range = (min_sl, max_sl)

        if best_sl_range:
            recommendations['optimal_sl_range'] = {
                'min': best_sl_range[0],
                'max': best_sl_range[1],
                'weighted_score': best_weighted_score
            }

    # === FIND OPTIMAL LIQUIDITY DISTANCE (WEIGHTED) ===
    if 'Liquidity Distance' in df.columns:
        df['Liquidity Distance'] = pd.to_numeric(df['Liquidity Distance'], errors='coerce')
        liq_thresholds = [50, 75, 100, 150, 200]

        best_weighted_score = 0
        best_threshold = None

        for thresh in liq_thresholds:
            subset = df[df['Liquidity Distance'] <= thresh]
            if len(subset) < 10:
                continue

            metrics = calculate_metrics(subset)
            avg_conf = subset['liq_confidence'].mean()
            weighted_score = calculate_weighted_score(metrics, avg_conf)

            if weighted_score > best_weighted_score:
                best_weighted_score = weighted_score
                best_threshold = thresh

        if best_threshold:
            recommendations['optimal_liq_distance'] = {
                'max_distance': best_threshold,
                'weighted_score': best_weighted_score
            }

    # Print summary
    print(f"  ✅ Analysis complete")
    print(f"\n  📊 Confidence Tiers:")
    for tier_name in ['high', 'medium', 'low']:
        tier_key = f'{tier_name}_confidence'
        if tier_key in recommendations:
            data = recommendations[tier_key]
            print(f"     {tier_name.upper():8s}: {data['trade_count']:3d} trades | "
                  f"WR: {data['win_rate']:.1f}% | "
                  f"PF: {data['profit_factor']:.2f} | "
                  f"Score: {data['weighted_score']:.1f}")

    return recommendations


def generate_report():
    """Main analysis function - UPDATED to use weighted scoring"""
    print("="*60)
    print("🚀 MULTI-PAIR BACKTEST ANALYSIS (LIQUIDITY-WEIGHTED)")
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
        
        # WEIGHTED optimal filters (NEW)
        filters = find_optimal_filters_weighted(df)

        pair_performance[pair] = {
            'overall': overall,
            'by_entry_type': by_entry_type,
            'by_trade_score': by_trade_score,
            'by_session': by_session,
            'optimal_filters_weighted': filters  # Updated key name
        }

        # Print summary
        print(f"  Total Trades: {overall['total_trades']}")
        print(f"  Win Rate: {overall['win_rate']:.1f}%")
        print(f"  Total R: {overall['total_r']:.2f}R")
        print(f"  Profit Factor: {overall['profit_factor']:.2f}")
        print(f"  Expectancy: {overall['expectancy']:.3f}R per trade")

        # Show weighted score if available
        if 'high_confidence' in filters:
            high_conf_score = filters['high_confidence']['weighted_score']
            print(f"  High-Conf Weighted Score: {high_conf_score:.1f}/100")

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

    with open(reports_dir / 'pair_performance_weighted.json', 'w') as f:
        json.dump(pair_performance, f, indent=2)

    print("✅ Reports saved to reports/pair_performance_weighted.json")
    print()

    # Identify best pairs (using weighted score)
    profitable_pairs = []
    for pair, data in pair_performance.items():
        if pair == 'COMBINED':
            continue
        if data['overall']['profit_factor'] > 1.0:
            # Calculate weighted score for overall pair
            filters = data.get('optimal_filters_weighted', {})
            if 'high_confidence' in filters:
                weighted_score = filters['high_confidence']['weighted_score']
                profitable_pairs.append((pair, weighted_score))

    # Sort by weighted score
    profitable_pairs.sort(key=lambda x: x[1], reverse=True)

    print("="*60)
    print("💰 MONEY MAKER PAIRS (SORTED BY WEIGHTED SCORE)")
    print("="*60)
    for pair, score in profitable_pairs:
        pf = pair_performance[pair]['overall']['profit_factor']
        exp = pair_performance[pair]['overall']['expectancy']
        print(f"  {pair}: Score={score:.1f}/100, PF={pf:.2f}, Expectancy={exp:.3f}R")
    print()

    if not profitable_pairs:
        print("⚠️  No profitable pairs found. Strategy needs optimization!")

    return pair_performance

if __name__ == '__main__':
    generate_report()
