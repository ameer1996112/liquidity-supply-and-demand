"""
AI Guardian Training Script v2.0 LITE - Memory-Efficient Version
================================================================

This is a lightweight version optimized for low-memory environments like VSCode.

CHANGES FROM FULL VERSION:
- Single RandomForest model (no ensemble) - saves ~60% memory
- Reduced cross-validation (3-fold instead of 5-fold)
- Simplified feature engineering (core interactions only)
- Aggressive garbage collection
- No SHAP analysis during training (can add later)

Still maintains:
- All 18 Pine Script features
- Proper validation and metrics
- Production-ready model output
"""

import pandas as pd
import numpy as np
import pickle
import json
import argparse
from pathlib import Path
from datetime import datetime
import gc

# ML imports
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split, StratifiedKFold, cross_val_score
from sklearn.preprocessing import StandardScaler, LabelEncoder
from sklearn.metrics import (
    accuracy_score, precision_score, recall_score, f1_score,
    roc_auc_score, confusion_matrix, classification_report,
    roc_curve, precision_recall_curve
)
import matplotlib
matplotlib.use('Agg')  # Non-interactive backend
import matplotlib.pyplot as plt
import seaborn as sns

# Expected Pine Script features (19 total from actual CSV export)
EXPECTED_FEATURES = [
    'score', 'fresh', 'session', 'zone_type', 'atr_ratio', 'is_accuracy',
    'trend', 'rsi', 'htf_trend', 'rvol', 'adx', 'touch_count',
    'base_quality', 'departure_strength', 'liquidity_distance',
    'liquidity_spread', 'liquidity_distance_score', 'liquidity_spread_score',
    'return_strength'
]

def engineer_features(df):
    """
    Create ESSENTIAL engineered features only (memory-efficient)
    """
    print("\n🔧 Engineering features (lite mode)...")

    # Make a copy to avoid modifying original
    df_eng = df.copy()

    # Core interactions (most important)
    df_eng['score_x_fresh'] = df_eng['score'] * df_eng['fresh']
    df_eng['trend_alignment'] = (df_eng['trend'] == df_eng['htf_trend']).astype(int)

    # Liquidity metrics
    df_eng['liquidity_quality'] = df_eng['liquidity_distance'] / (df_eng['liquidity_spread'] + 0.001)

    # Strength composite
    df_eng['strength_composite'] = (
        df_eng['base_quality'] +
        df_eng['departure_strength'] +
        df_eng['return_strength']
    ) / 3

    # Momentum indicators
    df_eng['rsi_neutral'] = ((df_eng['rsi'] >= 40) & (df_eng['rsi'] <= 60)).astype(int)
    df_eng['strong_adx'] = (df_eng['adx'] > 25).astype(int)

    print(f"✅ Created {len(df_eng.columns) - len(df.columns)} engineered features")

    # Clean memory
    gc.collect()

    return df_eng

def build_model():
    """
    Build RandomForest model (memory-efficient)
    """
    print("\n🏗️  Building RandomForest model (lite)...")

    model = RandomForestClassifier(
        n_estimators=100,      # Reduced from 200
        max_depth=10,          # Limit depth to reduce memory
        min_samples_split=10,  # Prevent overfitting
        min_samples_leaf=5,
        class_weight='balanced',
        random_state=42,
        n_jobs=-1,
        verbose=0
    )

    print("✅ Model configured")
    return model

def train_model(data_path):
    """
    Main training pipeline
    """
    print("=" * 60)
    print("🚀 AI GUARDIAN TRAINING v2.0 LITE")
    print("=" * 60)

    # Load data
    print(f"\n📂 Loading data from: {data_path}")
    df = pd.read_csv(data_path)
    print(f"✅ Loaded {len(df)} samples")

    # Check required columns
    if 'outcome' not in df.columns:
        raise ValueError("CSV must have 'outcome' column (1=Win, 0=Loss)")

    missing_features = [f for f in EXPECTED_FEATURES if f not in df.columns]
    if missing_features:
        print(f"⚠️  Missing features: {missing_features}")

    # Engineer features
    df = engineer_features(df)

    # Prepare features and target
    feature_cols = [c for c in df.columns if c != 'outcome']
    X = df[feature_cols]
    y = df['outcome']

    print(f"\n📊 Dataset summary:")
    print(f"   Features: {len(feature_cols)}")
    print(f"   Total samples: {len(X)}")
    print(f"   Wins: {sum(y == 1)} ({sum(y == 1)/len(y)*100:.1f}%)")
    print(f"   Losses: {sum(y == 0)} ({sum(y == 0)/len(y)*100:.1f}%)")

    # Encode categorical features
    print("\n🔢 Encoding features...")
    encoders = {}
    for col in X.select_dtypes(include=['object', 'category']).columns:
        le = LabelEncoder()
        X[col] = le.fit_transform(X[col].astype(str))
        encoders[col] = le

    # Scale features
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)

    # Clean memory
    gc.collect()

    # Split data
    X_train, X_test, y_train, y_test = train_test_split(
        X_scaled, y, test_size=0.2, random_state=42, stratify=y
    )

    print(f"✅ Train: {len(X_train)} | Test: {len(X_test)}")

    # Build and train model
    model = build_model()

    print("\n🎯 Training model...")
    model.fit(X_train, y_train)
    print("✅ Training complete")

    # Clean memory
    gc.collect()

    # Evaluate on test set
    print("\n📈 Evaluating model...")
    y_pred = model.predict(X_test)
    y_pred_proba = model.predict_proba(X_test)[:, 1]

    accuracy = accuracy_score(y_test, y_pred)
    precision = precision_score(y_test, y_pred, zero_division=0)
    recall = recall_score(y_test, y_pred, zero_division=0)
    f1 = f1_score(y_test, y_pred, zero_division=0)
    roc_auc = roc_auc_score(y_test, y_pred_proba)

    print("\n" + "=" * 60)
    print("📊 MODEL PERFORMANCE")
    print("=" * 60)
    print(f"Accuracy:  {accuracy:.3f}")
    print(f"Precision: {precision:.3f}")
    print(f"Recall:    {recall:.3f}")
    print(f"F1-Score:  {f1:.3f}")
    print(f"ROC-AUC:   {roc_auc:.3f}")
    print("=" * 60)

    # Confusion matrix
    cm = confusion_matrix(y_test, y_pred)
    print("\nConfusion Matrix:")
    print(f"  TN: {cm[0,0]:4d}  |  FP: {cm[0,1]:4d}")
    print(f"  FN: {cm[1,0]:4d}  |  TP: {cm[1,1]:4d}")

    # Cross-validation (3-fold for memory efficiency)
    print("\n🔄 Running 3-fold cross-validation...")
    cv_scores = cross_val_score(model, X_scaled, y, cv=3, scoring='roc_auc', n_jobs=-1)
    print(f"✅ CV ROC-AUC: {cv_scores.mean():.3f} (+/- {cv_scores.std():.3f})")

    # Clean memory
    gc.collect()

    # Feature importance
    print("\n🎯 Top 10 Most Important Features:")
    feature_importance = pd.DataFrame({
        'feature': feature_cols,
        'importance': model.feature_importances_
    }).sort_values('importance', ascending=False)

    for idx, row in feature_importance.head(10).iterrows():
        print(f"  {row['feature']:30s}: {row['importance']:.4f}")

    # Validation check
    if roc_auc < 0.55:
        print("\n⚠️  WARNING: Model performance is low (ROC-AUC < 0.55)")
        print("   This suggests the training data may not have enough signal.")
        print("   Consider collecting more diverse examples.")
        return False

    # Save model artifacts
    print("\n💾 Saving model artifacts...")
    output_dir = Path("ml")
    output_dir.mkdir(exist_ok=True)

    # Save model
    with open(output_dir / "model_v2.pkl", "wb") as f:
        pickle.dump(model, f)
    print("✅ Saved: ml/model_v2.pkl")

    # Save scaler
    with open(output_dir / "scaler_v2.pkl", "wb") as f:
        pickle.dump(scaler, f)
    print("✅ Saved: ml/scaler_v2.pkl")

    # Save encoders
    with open(output_dir / "encoders_v2.pkl", "wb") as f:
        pickle.dump(encoders, f)
    print("✅ Saved: ml/encoders_v2.pkl")

    # Save metadata
    metadata = {
        'version': '2.0-lite',
        'trained_at': datetime.now().isoformat(),
        'n_samples': len(df),
        'n_features': len(feature_cols),
        'features': feature_cols,
        'win_rate': float(sum(y == 1) / len(y)),
        'metrics': {
            'accuracy': float(accuracy),
            'precision': float(precision),
            'recall': float(recall),
            'f1_score': float(f1),
            'roc_auc': float(roc_auc),
            'cv_roc_auc_mean': float(cv_scores.mean()),
            'cv_roc_auc_std': float(cv_scores.std())
        }
    }

    with open(output_dir / "model_metadata_v2.json", "w") as f:
        json.dump(metadata, f, indent=2)
    print("✅ Saved: ml/model_metadata_v2.json")

    # Create visualizations
    print("\n📊 Creating visualizations...")
    create_plots(feature_importance, y_test, y_pred_proba, cm)

    print("\n" + "=" * 60)
    print("✅ TRAINING COMPLETE!")
    print("=" * 60)
    print("\n📁 Generated files:")
    print("   - ml/model_v2.pkl")
    print("   - ml/scaler_v2.pkl")
    print("   - ml/encoders_v2.pkl")
    print("   - ml/model_metadata_v2.json")
    print("   - ml/feature_importance_v2.png")
    print("   - ml/model_metrics_v2.png")

    return True

def create_plots(feature_importance, y_test, y_pred_proba, cm):
    """
    Create visualization plots
    """
    # Feature importance plot
    plt.figure(figsize=(10, 6))
    top_features = feature_importance.head(15)
    plt.barh(top_features['feature'], top_features['importance'])
    plt.xlabel('Importance')
    plt.title('Top 15 Feature Importance')
    plt.tight_layout()
    plt.savefig('ml/feature_importance_v2.png', dpi=150, bbox_inches='tight')
    plt.close()
    print("✅ Saved: ml/feature_importance_v2.png")

    # Metrics plots
    fig, axes = plt.subplots(1, 2, figsize=(12, 5))

    # ROC curve
    fpr, tpr, _ = roc_curve(y_test, y_pred_proba)
    axes[0].plot(fpr, tpr, label=f'ROC (AUC={roc_auc_score(y_test, y_pred_proba):.3f})')
    axes[0].plot([0, 1], [0, 1], 'k--', label='Random')
    axes[0].set_xlabel('False Positive Rate')
    axes[0].set_ylabel('True Positive Rate')
    axes[0].set_title('ROC Curve')
    axes[0].legend()
    axes[0].grid(True, alpha=0.3)

    # Confusion matrix
    sns.heatmap(cm, annot=True, fmt='d', cmap='Blues', ax=axes[1])
    axes[1].set_title('Confusion Matrix')
    axes[1].set_ylabel('True Label')
    axes[1].set_xlabel('Predicted Label')

    plt.tight_layout()
    plt.savefig('ml/model_metrics_v2.png', dpi=150, bbox_inches='tight')
    plt.close()
    print("✅ Saved: ml/model_metrics_v2.png")

    # Clean memory
    gc.collect()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Train AI Guardian v2.0 LITE")
    parser.add_argument(
        '--data',
        type=str,
        default='ml/training_data.csv',
        help='Path to training data CSV'
    )

    args = parser.parse_args()

    try:
        success = train_model(args.data)
        exit(0 if success else 1)
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        exit(1)
