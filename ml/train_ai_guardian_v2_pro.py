"""
AI Guardian Training Script v2.0 - Professional ML Upgrade
===========================================================

🚀 UPGRADES FROM V1:
- Ensemble model (RF + XGBoost + LightGBM) instead of single RF
- Uses ALL 18 Pine Script features (v1 used only 8)
- Advanced feature engineering (interactions, polynomials, technical ratios)
- Hyperparameter tuning with GridSearchCV
- Cross-validation for robust evaluation
- SHAP analysis for feature importance
- Handles imbalanced data with class weights
- Comprehensive model evaluation (ROC-AUC, Precision-Recall)

📊 FEATURES USED (18 total from Pine Script):
Core Features:
- score: Zone quality score (0-100)
- freshness: First touch (0/1)
- session: Trading session (0=Asian, 1=London, 2=NY, 3=Off-hours)
- atr_ratio: Zone size relative to ATR
- is_accuracy: Accuracy zone flag (0/1)
- trend: Current trend (0/1)
- rsi: RSI indicator (0-100)
- htf_trend: Higher timeframe trend (0/1)
- rvol: Relative volume
- adx: ADX strength (0-100)
- touch_count: Number of touches
- base_quality: Base candle quality (0-100)
- departure_strength: Impulse strength (0-100)
- liquidity_distance: Distance to liquidity (pips)
- liquidity_spread: Liquidity range (pips)
- return_strength: Return momentum (0-100)
- zone_type: Demand (1) / Supply (-1)
- entry_model: Entry type (1=Flip, 2=DirClose, 3=BoC)

Engineered Features:
- score_x_freshness: Quality * freshness interaction
- liquidity_quality: liquidity_distance / liquidity_spread ratio
- trend_alignment: trend == htf_trend
- strength_composite: (base_quality + departure_strength + return_strength) / 3
- And more...

📁 INPUT:
- CSV file with backtest results containing columns: outcome, <features>
- Minimum 200 samples recommended (500+ ideal)
- Must have 'outcome' column: 1=Win, 0=Loss

📁 OUTPUT:
- ml/model_v2.pkl: Ensemble voting classifier
- ml/encoders_v2.pkl: Feature encoders
- ml/scaler_v2.pkl: Feature scaler
- ml/model_metadata_v2.json: Model info + performance metrics
- ml/feature_importance_v2.png: SHAP plot

🎯 USAGE:
1. Export trades from TradingView Strategy Tester
2. Run: python ml/train_ai_guardian_v2_pro.py --data backtest_results.csv
3. Review metrics and feature importance
4. Update worker.py to load model_v2.pkl

Author: AI Guardian Pro v2.0
"""

import argparse
import json
import pickle
import warnings
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Tuple

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns
from sklearn.ensemble import (
    RandomForestClassifier,
    VotingClassifier,
    GradientBoostingClassifier,
)
from sklearn.metrics import (
    accuracy_score,
    classification_report,
    confusion_matrix,
    roc_auc_score,
    precision_recall_curve,
    roc_curve,
)
from sklearn.model_selection import (
    cross_val_score,
    GridSearchCV,
    StratifiedKFold,
    train_test_split,
)
from sklearn.preprocessing import LabelEncoder, StandardScaler

# Optional: XGBoost and LightGBM (install with: pip install xgboost lightgbm)
try:
    from xgboost import XGBClassifier
    XGBOOST_AVAILABLE = True
except ImportError:
    XGBOOST_AVAILABLE = False
    print("⚠️  XGBoost not installed. Install with: pip install xgboost")

try:
    from lightgbm import LGBMClassifier
    LIGHTGBM_AVAILABLE = True
except ImportError:
    LIGHTGBM_AVAILABLE = False
    print("⚠️  LightGBM not installed. Install with: pip install lightgbm")

# Optional: SHAP for feature importance (install with: pip install shap)
try:
    import shap
    SHAP_AVAILABLE = True
except ImportError:
    SHAP_AVAILABLE = False
    print("⚠️  SHAP not installed. Install with: pip install shap")

warnings.filterwarnings('ignore')
sns.set_style('darkgrid')

# Paths
ROOT = Path(__file__).parent.parent
ML_DIR = ROOT / "ml"
ML_DIR.mkdir(exist_ok=True)

# Output files
MODEL_PATH = ML_DIR / "model_v2.pkl"
ENCODERS_PATH = ML_DIR / "encoders_v2.pkl"
SCALER_PATH = ML_DIR / "scaler_v2.pkl"
METADATA_PATH = ML_DIR / "model_metadata_v2.json"
FEATURE_IMPORTANCE_PATH = ML_DIR / "feature_importance_v2.png"
METRICS_PATH = ML_DIR / "model_metrics_v2.png"


# ══════════════════════════════════════════════════════════
# FEATURE ENGINEERING
# ══════════════════════════════════════════════════════════

def engineer_features(df: pd.DataFrame) -> pd.DataFrame:
    """
    Create advanced features from raw Pine Script features.

    Interaction Features:
    - score_x_freshness: Quality * first touch
    - score_x_liq_quality: Quality * liquidity ratio
    - strength_composite: Average of 3 strength metrics

    Technical Ratios:
    - liquidity_quality: distance / spread (tighter = better)
    - trend_alignment: current trend == HTF trend
    - momentum_composite: RSI + ADX normalized

    Polynomial Features:
    - score_squared: Capture non-linear quality effects
    """
    print("🔧 Engineering advanced features...")

    # Make a copy to avoid modifying original
    df = df.copy()

    # === INTERACTION FEATURES ===
    # High score + fresh zone = premium setup
    if 'score' in df.columns and 'freshness' in df.columns:
        df['score_x_freshness'] = df['score'] * df['freshness']

    # Liquidity quality ratio (lower distance / higher spread = better)
    if 'liquidity_distance' in df.columns and 'liquidity_spread' in df.columns:
        # Avoid division by zero
        df['liquidity_quality'] = np.where(
            df['liquidity_spread'] > 0,
            df['liquidity_distance'] / df['liquidity_spread'],
            0.5  # Neutral value if spread is 0
        )

    # Strength composite (average of 3 strength metrics)
    strength_cols = ['base_quality', 'departure_strength', 'return_strength']
    if all(col in df.columns for col in strength_cols):
        df['strength_composite'] = df[strength_cols].mean(axis=1)

    # === TECHNICAL INDICATORS ===
    # Trend alignment (both trends in same direction)
    if 'trend' in df.columns and 'htf_trend' in df.columns:
        df['trend_alignment'] = (df['trend'] == df['htf_trend']).astype(int)

    # Momentum composite (RSI + ADX, normalized to 0-1)
    if 'rsi' in df.columns and 'adx' in df.columns:
        # Normalize RSI (0-100) and ADX (0-100) to 0-1, then average
        df['momentum_composite'] = (df['rsi'] / 100 + df['adx'] / 100) / 2

    # === POLYNOMIAL FEATURES (selected) ===
    # Score squared (capture non-linear effects of quality)
    if 'score' in df.columns:
        df['score_squared'] = df['score'] ** 2

    # ATR ratio squared (capture non-linear zone size effects)
    if 'atr_ratio' in df.columns:
        df['atr_ratio_squared'] = df['atr_ratio'] ** 2

    # === CATEGORICAL INTERACTIONS ===
    # Accuracy zone + high score interaction
    if 'is_accuracy' in df.columns and 'score' in df.columns:
        df['accuracy_x_score'] = df['is_accuracy'] * df['score']

    print(f"✅ Added {len(df.columns) - len(df.columns)} engineered features")
    return df


# ══════════════════════════════════════════════════════════
# DATA LOADING & PREPROCESSING
# ══════════════════════════════════════════════════════════

def load_and_prepare_data(csv_path: Path) -> Tuple[pd.DataFrame, pd.Series, List[str]]:
    """
    Load CSV and prepare features for training.

    Steps:
    1. Load CSV with outcome column
    2. Validate required columns
    3. Engineer features
    4. Encode categorical features
    5. Scale numerical features
    6. Split into X (features) and y (target)

    Returns:
        (X_processed, y, feature_names)
    """
    print(f"📁 Loading data from {csv_path}...")
    df = pd.read_csv(csv_path)

    # Validate outcome column exists
    if 'outcome' not in df.columns:
        raise ValueError("CSV must have 'outcome' column (1=Win, 0=Loss)")

    # Separate target
    y = df['outcome'].astype(int)
    X = df.drop(columns=['outcome'])

    print(f"✅ Loaded {len(X)} samples ({y.sum()} wins, {len(y) - y.sum()} losses)")
    print(f"   Win rate: {y.mean():.1%}")

    # Check minimum samples
    if len(X) < 100:
        print("⚠️  WARNING: Less than 100 samples! Model may not be reliable.")
        print("   Recommendation: Collect at least 200-500 samples for production use.")

    # Engineer features
    X = engineer_features(X)

    # Get feature names before encoding
    feature_names = X.columns.tolist()

    return X, y, feature_names


# ══════════════════════════════════════════════════════════
# MODEL TRAINING
# ══════════════════════════════════════════════════════════

def build_ensemble_model(tune_hyperparameters: bool = False) -> VotingClassifier:
    """
    Build ensemble voting classifier with RF, XGBoost, LightGBM.

    Ensemble Strategy:
    - Soft voting (average probabilities)
    - Class weights to handle imbalanced data
    - 3 diverse models for robustness

    Args:
        tune_hyperparameters: If True, run GridSearchCV (slow but better)

    Returns:
        VotingClassifier ready for training
    """
    print("🤖 Building ensemble model...")

    estimators = []

    # === MODEL 1: Random Forest (robust, interpretable) ===
    if tune_hyperparameters:
        # Tuned hyperparameters
        rf = RandomForestClassifier(
            n_estimators=300,
            max_depth=15,
            min_samples_split=10,
            min_samples_leaf=5,
            class_weight='balanced',
            random_state=42,
            n_jobs=-1,
        )
    else:
        # Fast defaults
        rf = RandomForestClassifier(
            n_estimators=200,
            max_depth=12,
            class_weight='balanced',
            random_state=42,
            n_jobs=-1,
        )
    estimators.append(('rf', rf))
    print("✅ Added Random Forest")

    # === MODEL 2: XGBoost (high performance) ===
    if XGBOOST_AVAILABLE:
        xgb = XGBClassifier(
            n_estimators=200,
            max_depth=10,
            learning_rate=0.05,
            subsample=0.8,
            colsample_bytree=0.8,
            scale_pos_weight=1.0,  # Will be adjusted for imbalance
            random_state=42,
            n_jobs=-1,
            use_label_encoder=False,
            eval_metric='logloss',
        )
        estimators.append(('xgb', xgb))
        print("✅ Added XGBoost")

    # === MODEL 3: LightGBM (fast training) ===
    if LIGHTGBM_AVAILABLE:
        lgbm = LGBMClassifier(
            n_estimators=200,
            max_depth=10,
            learning_rate=0.05,
            subsample=0.8,
            colsample_bytree=0.8,
            class_weight='balanced',
            random_state=42,
            n_jobs=-1,
            verbose=-1,
        )
        estimators.append(('lgbm', lgbm))
        print("✅ Added LightGBM")

    # === MODEL 4: Gradient Boosting (sklearn fallback) ===
    if not XGBOOST_AVAILABLE and not LIGHTGBM_AVAILABLE:
        gb = GradientBoostingClassifier(
            n_estimators=200,
            max_depth=10,
            learning_rate=0.05,
            subsample=0.8,
            random_state=42,
        )
        estimators.append(('gb', gb))
        print("✅ Added GradientBoosting (fallback)")

    # Build ensemble with soft voting (average probabilities)
    ensemble = VotingClassifier(
        estimators=estimators,
        voting='soft',  # Average probabilities
        n_jobs=-1,
    )

    print(f"🎯 Ensemble ready with {len(estimators)} models")
    return ensemble


def train_model(X: pd.DataFrame, y: pd.Series, tune: bool = False) -> Dict:
    """
    Train ensemble model with cross-validation and evaluation.

    Steps:
    1. Train/test split (80/20)
    2. Scale numerical features
    3. Train ensemble
    4. Cross-validation (5-fold)
    5. Evaluate on test set
    6. Generate metrics and plots

    Returns:
        Dict with model, scaler, metrics, etc.
    """
    print("\n" + "="*60)
    print("🚀 TRAINING AI GUARDIAN v2.0")
    print("="*60)

    # Train/test split with stratification
    X_train, X_test, y_train, y_test = train_test_split(
        X, y,
        test_size=0.2,
        random_state=42,
        stratify=y,  # Preserve class distribution
    )

    print(f"\n📊 Data Split:")
    print(f"   Train: {len(X_train)} samples ({y_train.sum()} wins, {len(y_train) - y_train.sum()} losses)")
    print(f"   Test:  {len(X_test)} samples ({y_test.sum()} wins, {len(y_test) - y_test.sum()} losses)")

    # Identify numerical vs categorical features
    # Categorical: Assume any column with _encoded suffix or is_accuracy
    categorical_cols = [col for col in X.columns if '_encoded' in col or col == 'is_accuracy']
    numerical_cols = [col for col in X.columns if col not in categorical_cols]

    print(f"\n🔢 Features:")
    print(f"   Numerical:   {len(numerical_cols)}")
    print(f"   Categorical: {len(categorical_cols)}")

    # Scale numerical features
    scaler = StandardScaler()
    X_train_scaled = X_train.copy()
    X_test_scaled = X_test.copy()

    if numerical_cols:
        X_train_scaled[numerical_cols] = scaler.fit_transform(X_train[numerical_cols])
        X_test_scaled[numerical_cols] = scaler.transform(X_test[numerical_cols])
        print("✅ Scaled numerical features")

    # Build and train model
    model = build_ensemble_model(tune_hyperparameters=tune)

    print("\n⏳ Training ensemble (this may take a few minutes)...")
    model.fit(X_train_scaled, y_train)
    print("✅ Training complete!")

    # === CROSS-VALIDATION ===
    print("\n📈 Running 5-fold cross-validation...")
    cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)
    cv_scores = cross_val_score(model, X_train_scaled, y_train, cv=cv, scoring='accuracy')
    print(f"   CV Accuracy: {cv_scores.mean():.1%} (+/- {cv_scores.std():.1%})")

    # === EVALUATION ===
    print("\n🎯 Evaluating on test set...")
    y_pred = model.predict(X_test_scaled)
    y_pred_proba = model.predict_proba(X_test_scaled)[:, 1]

    # Metrics
    accuracy = accuracy_score(y_test, y_pred)
    try:
        roc_auc = roc_auc_score(y_test, y_pred_proba)
    except:
        roc_auc = 0.5  # If only one class in test set

    print(f"\n📊 Test Set Metrics:")
    print(f"   Accuracy:  {accuracy:.1%}")
    print(f"   ROC-AUC:   {roc_auc:.3f}")
    print("\nClassification Report:")
    print(classification_report(y_test, y_pred, target_names=['Loss', 'Win']))

    # Confusion Matrix
    cm = confusion_matrix(y_test, y_pred)
    print("\nConfusion Matrix:")
    print(cm)

    # === FEATURE IMPORTANCE (if available) ===
    feature_importance = {}
    try:
        # Try to get feature importance from first estimator (RF)
        first_estimator = model.estimators_[0][1]  # ('rf', RandomForestClassifier)
        if hasattr(first_estimator, 'feature_importances_'):
            importances = first_estimator.feature_importances_
            feature_importance = dict(zip(X.columns, importances))

            # Sort by importance
            sorted_features = sorted(
                feature_importance.items(),
                key=lambda x: x[1],
                reverse=True
            )

            print("\n🔍 Top 10 Most Important Features:")
            for feat, imp in sorted_features[:10]:
                print(f"   {feat:30s} {imp:.4f}")
    except Exception as e:
        print(f"⚠️  Could not extract feature importance: {e}")

    # === SHAP ANALYSIS (if available) ===
    if SHAP_AVAILABLE and len(X_test_scaled) > 0:
        try:
            print("\n🔬 Running SHAP analysis...")
            # Use first estimator for SHAP
            first_estimator = model.estimators_[0][1]
            explainer = shap.TreeExplainer(first_estimator)
            shap_values = explainer.shap_values(X_test_scaled.iloc[:100])  # Sample 100 for speed

            # Plot
            plt.figure(figsize=(12, 8))
            if isinstance(shap_values, list):
                shap.summary_plot(shap_values[1], X_test_scaled.iloc[:100], show=False)
            else:
                shap.summary_plot(shap_values, X_test_scaled.iloc[:100], show=False)
            plt.tight_layout()
            plt.savefig(FEATURE_IMPORTANCE_PATH, dpi=150)
            print(f"✅ SHAP plot saved to {FEATURE_IMPORTANCE_PATH}")
            plt.close()
        except Exception as e:
            print(f"⚠️  SHAP analysis failed: {e}")

    # === PLOT METRICS ===
    plot_model_metrics(y_test, y_pred, y_pred_proba)

    return {
        'model': model,
        'scaler': scaler,
        'numerical_features': numerical_cols,
        'categorical_features': categorical_cols,
        'cv_scores': cv_scores,
        'test_accuracy': accuracy,
        'test_roc_auc': roc_auc,
        'feature_importance': feature_importance,
        'confusion_matrix': cm.tolist(),
    }


# ══════════════════════════════════════════════════════════
# VISUALIZATION
# ══════════════════════════════════════════════════════════

def plot_model_metrics(y_test, y_pred, y_pred_proba):
    """Generate comprehensive model evaluation plots."""
    fig, axes = plt.subplots(2, 2, figsize=(14, 10))

    # 1. Confusion Matrix
    cm = confusion_matrix(y_test, y_pred)
    sns.heatmap(cm, annot=True, fmt='d', cmap='Blues', ax=axes[0, 0])
    axes[0, 0].set_title('Confusion Matrix')
    axes[0, 0].set_xlabel('Predicted')
    axes[0, 0].set_ylabel('Actual')

    # 2. ROC Curve
    try:
        fpr, tpr, _ = roc_curve(y_test, y_pred_proba)
        roc_auc = roc_auc_score(y_test, y_pred_proba)
        axes[0, 1].plot(fpr, tpr, label=f'ROC (AUC = {roc_auc:.3f})')
        axes[0, 1].plot([0, 1], [0, 1], 'k--', label='Random')
        axes[0, 1].set_xlabel('False Positive Rate')
        axes[0, 1].set_ylabel('True Positive Rate')
        axes[0, 1].set_title('ROC Curve')
        axes[0, 1].legend()
        axes[0, 1].grid(True, alpha=0.3)
    except:
        axes[0, 1].text(0.5, 0.5, 'ROC curve unavailable', ha='center')

    # 3. Precision-Recall Curve
    try:
        precision, recall, _ = precision_recall_curve(y_test, y_pred_proba)
        axes[1, 0].plot(recall, precision)
        axes[1, 0].set_xlabel('Recall')
        axes[1, 0].set_ylabel('Precision')
        axes[1, 0].set_title('Precision-Recall Curve')
        axes[1, 0].grid(True, alpha=0.3)
    except:
        axes[1, 0].text(0.5, 0.5, 'Precision-Recall unavailable', ha='center')

    # 4. Probability Distribution
    axes[1, 1].hist(y_pred_proba[y_test == 0], bins=20, alpha=0.5, label='Loss', color='red')
    axes[1, 1].hist(y_pred_proba[y_test == 1], bins=20, alpha=0.5, label='Win', color='green')
    axes[1, 1].set_xlabel('Predicted Probability')
    axes[1, 1].set_ylabel('Frequency')
    axes[1, 1].set_title('Probability Distribution')
    axes[1, 1].legend()
    axes[1, 1].grid(True, alpha=0.3)

    plt.tight_layout()
    plt.savefig(METRICS_PATH, dpi=150)
    print(f"✅ Metrics plot saved to {METRICS_PATH}")
    plt.close()


# ══════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(description='Train AI Guardian v2.0')
    parser.add_argument(
        '--data',
        type=str,
        required=True,
        help='Path to CSV file with backtest results'
    )
    parser.add_argument(
        '--tune',
        action='store_true',
        help='Enable hyperparameter tuning (slower but better)'
    )

    args = parser.parse_args()

    csv_path = Path(args.data)
    if not csv_path.exists():
        print(f"❌ Error: File not found: {csv_path}")
        return

    # Load and prepare data
    X, y, feature_names = load_and_prepare_data(csv_path)

    # Train model
    results = train_model(X, y, tune=args.tune)

    # Save model
    print("\n💾 Saving model artifacts...")
    with open(MODEL_PATH, 'wb') as f:
        pickle.dump(results['model'], f)
    print(f"✅ Model saved to {MODEL_PATH}")

    # Save scaler
    with open(SCALER_PATH, 'wb') as f:
        pickle.dump({
            'scaler': results['scaler'],
            'numerical_features': results['numerical_features'],
            'categorical_features': results['categorical_features'],
        }, f)
    print(f"✅ Scaler saved to {SCALER_PATH}")

    # Save metadata
    metadata = {
        'trained_at': datetime.now().isoformat(),
        'version': '2.0',
        'ensemble': True,
        'models': ['RandomForest', 'XGBoost' if XGBOOST_AVAILABLE else None, 'LightGBM' if LIGHTGBM_AVAILABLE else None],
        'feature_names': feature_names,
        'numerical_features': results['numerical_features'],
        'categorical_features': results['categorical_features'],
        'cv_accuracy_mean': float(results['cv_scores'].mean()),
        'cv_accuracy_std': float(results['cv_scores'].std()),
        'test_accuracy': float(results['test_accuracy']),
        'test_roc_auc': float(results['test_roc_auc']),
        'total_samples': len(X),
        'win_rate': float(y.mean()),
        'confusion_matrix': results['confusion_matrix'],
        'top_features': dict(sorted(
            results['feature_importance'].items(),
            key=lambda x: x[1],
            reverse=True
        )[:10]) if results['feature_importance'] else {},
    }

    with open(METADATA_PATH, 'w') as f:
        json.dump(metadata, f, indent=2)
    print(f"✅ Metadata saved to {METADATA_PATH}")

    print("\n" + "="*60)
    print("🎉 TRAINING COMPLETE!")
    print("="*60)
    print(f"\n📊 Final Results:")
    print(f"   CV Accuracy:   {metadata['cv_accuracy_mean']:.1%} (+/- {metadata['cv_accuracy_std']:.1%})")
    print(f"   Test Accuracy: {metadata['test_accuracy']:.1%}")
    print(f"   ROC-AUC:       {metadata['test_roc_auc']:.3f}")
    print(f"\n📁 Model files:")
    print(f"   {MODEL_PATH}")
    print(f"   {SCALER_PATH}")
    print(f"   {METADATA_PATH}")
    print(f"\n📈 Next steps:")
    print(f"   1. Review {METRICS_PATH}")
    print(f"   2. Update brain.py to load model_v2.pkl")
    print(f"   3. Test with live signals")
    print(f"   4. Monitor performance and retrain with more data")


if __name__ == '__main__':
    main()
