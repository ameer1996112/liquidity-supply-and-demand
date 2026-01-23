#!/usr/bin/env python3
"""
Enhanced AI Model Trainer
==========================
Trains RandomForest classifier on 572 profitable trades with 21 features.
Saves model to models/model_enhanced.pkl for deployment.

Usage:
    python train_enhanced_model.py

Output:
    - models/model_enhanced.pkl
    - models/model_performance.json
"""

import pandas as pd
import numpy as np
from pathlib import Path
import pickle
import json
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split, cross_val_score
from sklearn.metrics import classification_report, confusion_matrix, roc_auc_score

def load_training_data():
    """Load the ultimate training dataset."""
    # Try ultimate dataset first, fallback to enhanced
    ultimate_path = Path('backtest_data/processed/training_ultimate.csv')
    enhanced_path = Path('backtest_data/processed/training_enhanced.csv')
    
    if ultimate_path.exists():
        df = pd.read_csv(ultimate_path)
        print(f"✅ Loaded ULTIMATE dataset: {len(df)} training samples")
        print(f"   - Notion trades: {len(df[df['source'] == 'notion'])}")
        print(f"   - TradingView trades: {len(df[df['source'] == 'tradingview'])}")
    elif enhanced_path.exists():
        df = pd.read_csv(enhanced_path)
        print(f"✅ Loaded enhanced dataset: {len(df)} training samples")
    else:
        raise FileNotFoundError(
            "Training data not found. Run 'python scripts/combine_all_data.py' first."
        )
    
    # Drop source column if exists (not a feature)
    if 'source' in df.columns:
        df = df.drop('source', axis=1)
    
    return df

def train_model(X_train, y_train, X_test, y_test):
    """Train Random Forest classifier."""
    print("\n🤖 Training Enhanced AI Model...")
    print(f"   Training samples: {len(X_train)}")
    print(f"   Test samples: {len(X_test)}")
    print(f"   Features: {X_train.shape[1]}")
    
    # RandomForest with optimized hyperparameters
    model = RandomForestClassifier(
        n_estimators=200,
        max_depth=10,
        min_samples_split=5,
        min_samples_leaf=2,
        random_state=42,
        n_jobs=-1
    )
    
    model.fit(X_train, y_train)
    
    # Cross-validation score
    cv_scores = cross_val_score(model, X_train, y_train, cv=5, scoring='accuracy')
    print(f"   Cross-validation accuracy: {cv_scores.mean():.3f} (+/- {cv_scores.std():.3f})")
    
    return model

def evaluate_model(model, X_test, y_test, feature_names):
    """Evaluate model performance."""
    print("\n📊 Model Performance:")
    
    y_pred = model.predict(X_test)
    y_proba = model.predict_proba(X_test)[:, 1]
    
    # Accuracy
    accuracy = (y_pred == y_test).mean()
    print(f"   Accuracy: {accuracy:.3f}")
    
    # AUC
    auc = roc_auc_score(y_test, y_proba)
    print(f"   AUC-ROC: {auc:.3f}")
    
    # Classification report
    print("\n   Classification Report:")
    print(classification_report(y_test, y_pred, target_names=['Loss', 'Win']))
    
    # Confusion Matrix
    cm = confusion_matrix(y_test, y_pred)
    print("   Confusion Matrix:")
    print(f"   [[TN={cm[0][0]:3d}, FP={cm[0][1]:3d}]")
    print(f"    [FN={cm[1][0]:3d}, TP={cm[1][1]:3d}]]")
    
    # Feature importance
    feature_importance = pd.DataFrame({
        'feature': feature_names,
        'importance': model.feature_importances_
    }).sort_values('importance', ascending=False)
    
    print("\n   Top 10 Most Important Features:")
    for idx, row in feature_importance.head(10).iterrows():
        print(f"   {row['feature']:30s} {row['importance']:.4f}")
    
    return {
        'accuracy': float(accuracy),
        'auc': float(auc),
        'confusion_matrix': cm.tolist(),
        'feature_importance': feature_importance.to_dict('records')
    }

def save_model(model, performance_metrics):
    """Save model and performance metrics."""
    models_dir = Path('models')
    models_dir.mkdir(exist_ok=True)
    
    # Save model
    model_path = models_dir / 'model_ultimate.pkl'
    with open(model_path, 'wb') as f:
        pickle.dump(model, f)
    
    print(f"\n💾 Model saved to {model_path}")
    
    # Save performance metrics
    metrics_path = models_dir / 'model_performance.json'
    with open(metrics_path, 'w') as f:
        json.dump(performance_metrics, f, indent=2)
    
    print(f"💾 Performance metrics saved to {metrics_path}")

def main():
    print("="*60)
    print("🚀 ENHANCED AI MODEL TRAINING")
    print("="*60)
    
    # Load data
    df = load_training_data()
    
    # Separate features and target
    X = df.drop('win', axis=1)
    y = df['win']
    
    # Train/test split (80/20)
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42, stratify=y
    )
    
    # Train model
    model = train_model(X_train, y_train, X_test, y_test)
    
    # Evaluate
    performance = evaluate_model(model, X_test, y_test, X.columns)
    
    # Save
    save_model(model, performance)
    
    print("\n="*60)
    print("✅ ENHANCED MODEL READY FOR DEPLOYMENT")
    print("="*60)
    print("\nTo use this model:")
    print("1. Copy models/model_enhanced.pkl to your server")
    print("2. Update trading_bot.py to load 'model_enhanced.pkl'")
    print("3. Ensure bot sends all 21 features to the model")
    print()

if __name__ == '__main__':
    main()
