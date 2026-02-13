#!/usr/bin/env python3
"""
Test different prediction thresholds to find optimal precision/recall balance
"""
import pickle
import pandas as pd
import numpy as np
from sklearn.metrics import precision_score, recall_score, f1_score, accuracy_score

# Load model and test data
print("📊 Loading model and test data...")
with open('ml/model_v3.pkl', 'rb') as f:
    model = pickle.load(f)

df = pd.read_csv('ml/training_data.csv')

# Import engineer_features function
import sys
sys.path.insert(0, 'ml')
from train_ai_guardian_v3_lightgbm import engineer_features

df = engineer_features(df, inplace=True)

# Split same way as training (80/20)
from sklearn.model_selection import train_test_split
feature_cols = [c for c in df.columns if c != 'outcome']
X = df[feature_cols]
y = df['outcome']
X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42, stratify=y)

# Get probabilities
y_pred_proba = model.predict_proba(X_test)[:, 1]

print("\n" + "="*70)
print("🎯 THRESHOLD OPTIMIZATION")
print("="*70)
print(f"Test set: {len(y_test)} trades ({sum(y_test)} wins, {len(y_test)-sum(y_test)} losses)")
print()

# Test different thresholds
thresholds = [0.25, 0.30, 0.35, 0.40, 0.45, 0.50, 0.55, 0.60]

results = []
for threshold in thresholds:
    y_pred = (y_pred_proba >= threshold).astype(int)

    precision = precision_score(y_test, y_pred, zero_division=0)
    recall = recall_score(y_test, y_pred, zero_division=0)
    f1 = f1_score(y_test, y_pred, zero_division=0)
    accuracy = accuracy_score(y_test, y_pred)

    # Calculate expected value with 2:1 R:R
    ev = (precision * 2) - ((1 - precision) * 1)

    # Count predictions
    n_trades = sum(y_pred)

    results.append({
        'threshold': threshold,
        'precision': precision,
        'recall': recall,
        'f1': f1,
        'accuracy': accuracy,
        'ev_2to1': ev,
        'n_trades': n_trades,
        'profitable': 'YES ✅' if ev > 0 else 'NO ❌'
    })

df_results = pd.DataFrame(results)

print("\nThreshold | Precision | Recall | F1    | Trades | EV (2:1) | Profitable")
print("-"*70)
for _, row in df_results.iterrows():
    print(f"  {row['threshold']:.2f}    |   {row['precision']:.3f}   | {row['recall']:.3f} | {row['f1']:.3f} |  {row['n_trades']:4.0f}  |  {row['ev_2to1']:+.3f}   | {row['profitable']}")

print("\n" + "="*70)

# Find best threshold
best_ev = df_results.loc[df_results['ev_2to1'].idxmax()]
best_f1 = df_results.loc[df_results['f1'].idxmax()]

print(f"\n🎯 Best for PROFIT (2:1 R:R):")
print(f"   Threshold: {best_ev['threshold']:.2f}")
print(f"   Precision: {best_ev['precision']:.1%}")
print(f"   Recall: {best_ev['recall']:.1%}")
print(f"   Expected Value: {best_ev['ev_2to1']:+.3f}")
print(f"   Trades: {best_ev['n_trades']:.0f}/{len(y_test)}")

print(f"\n🎯 Best for BALANCE (F1-Score):")
print(f"   Threshold: {best_f1['threshold']:.2f}")
print(f"   Precision: {best_f1['precision']:.1%}")
print(f"   Recall: {best_f1['recall']:.1%}")
print(f"   F1-Score: {best_f1['f1']:.3f}")

print("\n💡 Recommendation:")
if best_ev['ev_2to1'] > 0:
    print(f"   ✅ Model is PROFITABLE at threshold {best_ev['threshold']:.2f}")
    print(f"   Update threshold in train_ai_guardian_v3_lightgbm.py line ~308")
else:
    print(f"   ❌ Model NOT profitable at any threshold (best EV: {df_results['ev_2to1'].max():+.3f})")
    print(f"   Need better features or more diverse training data")
