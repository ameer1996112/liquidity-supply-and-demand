#!/bin/bash
# AI Guardian v2.0 - One-Click Upgrade Script
# ============================================
#
# 🎯 PURPOSE:
# Automatically upgrade your AI brain from v1 (broken, 50% predictions)
# to v2 (professional ensemble model)
#
# 🚀 USAGE:
# bash ml/upgrade_ai.sh
#
# 📊 WHAT THIS DOES:
# 1. Install required Python packages
# 2. Generate synthetic test data (500 trades)
# 3. Train ensemble model (RF + XGBoost + LightGBM)
# 4. Run evaluation and show results
# 5. Backup old model and deploy new model
# 6. Update brain.py to use v2 model

set -e  # Exit on error

echo ""
echo "═══════════════════════════════════════════════════════════"
echo "🚀 AI GUARDIAN v2.0 - PROFESSIONAL UPGRADE"
echo "═══════════════════════════════════════════════════════════"
echo ""

# Navigate to project root
cd "$(dirname "$0")/.."
PROJECT_ROOT=$(pwd)
ML_DIR="$PROJECT_ROOT/ml"

echo "📁 Project root: $PROJECT_ROOT"
echo ""

# ══════════════════════════════════════════════════════════
# STEP 1: Install Dependencies
# ══════════════════════════════════════════════════════════

echo "📦 Step 1/6: Installing Python dependencies..."
echo ""

# Check if venv exists
if [ ! -d "venv" ]; then
    echo "⚠️  Virtual environment not found. Creating..."
    python3 -m venv venv
fi

# Activate venv
source venv/bin/activate

# Install packages
pip install -q --upgrade pip
pip install -q scikit-learn pandas numpy matplotlib seaborn
pip install -q xgboost lightgbm shap || echo "⚠️  Some optional packages failed (not critical)"

echo "✅ Dependencies installed"
echo ""

# ══════════════════════════════════════════════════════════
# STEP 2: Check for Existing Training Data
# ══════════════════════════════════════════════════════════

echo "📊 Step 2/6: Checking for training data..."
echo ""

TRAINING_DATA="$ML_DIR/training_data.csv"

if [ -f "$TRAINING_DATA" ]; then
    # Count lines (subtract 1 for header)
    SAMPLE_COUNT=$(($(wc -l < "$TRAINING_DATA") - 1))
    echo "✅ Found existing training data: $SAMPLE_COUNT samples"

    if [ $SAMPLE_COUNT -lt 200 ]; then
        echo "⚠️  WARNING: Only $SAMPLE_COUNT samples (need 200+ for good accuracy)"
        echo "   Recommendation: Collect more data from TradingView Strategy Tester"
        echo ""
        read -p "Continue anyway? (y/n) " -n 1 -r
        echo ""
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            echo "❌ Aborted. Please collect more data and retry."
            exit 1
        fi
    fi
else
    echo "⚠️  No training data found. Generating synthetic data for testing..."
    echo ""

    python ml/collect_training_data.py --source synthetic --count 500

    echo ""
    echo "⚠️  IMPORTANT: Synthetic data is for TESTING ONLY!"
    echo "   For production, collect real data from TradingView:"
    echo "   1. Run your Pine Script strategy"
    echo "   2. Export trades from Strategy Tester"
    echo "   3. Run: python ml/collect_training_data.py --source tradingview --input backtest_results.csv"
    echo ""
fi

# ══════════════════════════════════════════════════════════
# STEP 3: Backup Old Model
# ══════════════════════════════════════════════════════════

echo "💾 Step 3/6: Backing up old model..."
echo ""

BACKUP_DIR="$ML_DIR/backup_v1_$(date +%Y%m%d_%H%M%S)"
mkdir -p "$BACKUP_DIR"

# Backup v1 files if they exist
if [ -f "$ML_DIR/model.pkl" ]; then
    cp "$ML_DIR/model.pkl" "$BACKUP_DIR/"
    echo "✅ Backed up model.pkl"
fi

if [ -f "$ML_DIR/encoders.pkl" ]; then
    cp "$ML_DIR/encoders.pkl" "$BACKUP_DIR/"
    echo "✅ Backed up encoders.pkl"
fi

if [ -f "$ML_DIR/scaler.pkl" ]; then
    cp "$ML_DIR/scaler.pkl" "$BACKUP_DIR/"
    echo "✅ Backed up scaler.pkl"
fi

if [ -f "$ML_DIR/model_metadata.json" ]; then
    cp "$ML_DIR/model_metadata.json" "$BACKUP_DIR/"
    echo "✅ Backed up model_metadata.json"
fi

echo ""
echo "📁 Backup saved to: $BACKUP_DIR"
echo ""

# ══════════════════════════════════════════════════════════
# STEP 4: Train v2 Model
# ══════════════════════════════════════════════════════════

echo "🤖 Step 4/6: Training AI Guardian v2.0..."
echo ""
echo "   This will take 2-5 minutes..."
echo ""

python ml/train_ai_guardian_v2_pro.py --data "$TRAINING_DATA"

echo ""

# ══════════════════════════════════════════════════════════
# STEP 5: Validate Model
# ══════════════════════════════════════════════════════════

echo "✅ Step 5/6: Validating model..."
echo ""

# Check if v2 model was created
if [ ! -f "$ML_DIR/model_v2.pkl" ]; then
    echo "❌ ERROR: Model training failed! model_v2.pkl not found."
    echo "   Check logs above for errors."
    exit 1
fi

# Check metadata
if [ ! -f "$ML_DIR/model_metadata_v2.json" ]; then
    echo "❌ ERROR: Model metadata not found!"
    exit 1
fi

# Parse and display metrics
echo "📊 Model Performance:"
python3 -c "
import json
with open('$ML_DIR/model_metadata_v2.json') as f:
    meta = json.load(f)
print(f\"   CV Accuracy:   {meta.get('cv_accuracy_mean', 0):.1%} (+/- {meta.get('cv_accuracy_std', 0):.1%})\")
print(f\"   Test Accuracy: {meta.get('test_accuracy', 0):.1%}\")
print(f\"   ROC-AUC:       {meta.get('test_roc_auc', 0):.3f}\")
print(f\"   Total Samples: {meta.get('total_samples', 0)}\")
print(f\"   Win Rate:      {meta.get('win_rate', 0):.1%}\")
"

echo ""

# Check if metrics are acceptable
python3 -c "
import json
import sys
with open('$ML_DIR/model_metadata_v2.json') as f:
    meta = json.load(f)

accuracy = meta.get('test_accuracy', 0)
roc_auc = meta.get('test_roc_auc', 0)

if accuracy < 0.52:
    print('⚠️  WARNING: Test accuracy is very low (< 52%). Model may not be useful.')
    print('   Recommendation: Collect more training data.')
    sys.exit(1)

if roc_auc < 0.55:
    print('⚠️  WARNING: ROC-AUC is very low (< 0.55). Model barely better than random.')
    print('   Recommendation: Check feature quality and collect more data.')
    sys.exit(1)

print('✅ Model validation passed!')
" || {
    echo ""
    echo "❌ Model validation failed!"
    echo "   The model was trained but performance is too low."
    echo "   Please collect more training data and retry."
    exit 1
}

echo ""

# ══════════════════════════════════════════════════════════
# STEP 6: Deploy Model
# ══════════════════════════════════════════════════════════

echo "🚀 Step 6/6: Deploying model..."
echo ""

# Update brain.py to use v2 model
BRAIN_FILE="$PROJECT_ROOT/src/ai/brain.py"

if [ -f "$BRAIN_FILE" ]; then
    # Backup brain.py
    cp "$BRAIN_FILE" "$BRAIN_FILE.backup"
    echo "✅ Backed up brain.py to brain.py.backup"

    # Update model paths
    sed -i.bak 's/MODEL_PATH = _ROOT \/ "ml" \/ "model.pkl"/MODEL_PATH = _ROOT \/ "ml" \/ "model_v2.pkl"/' "$BRAIN_FILE"
    sed -i.bak 's/ENCODERS_PATH = _ROOT \/ "ml" \/ "encoders.pkl"/ENCODERS_PATH = _ROOT \/ "ml" \/ "encoders_v2.pkl"/' "$BRAIN_FILE"
    sed -i.bak 's/SCALER_PATH = _ROOT \/ "ml" \/ "scaler.pkl"/SCALER_PATH = _ROOT \/ "ml" \/ "scaler_v2.pkl"/' "$BRAIN_FILE"

    # Remove backup files created by sed
    rm -f "$BRAIN_FILE.bak"

    echo "✅ Updated brain.py to use v2 model"
else
    echo "⚠️  brain.py not found. You'll need to manually update model paths."
fi

echo ""

# ══════════════════════════════════════════════════════════
# DONE
# ══════════════════════════════════════════════════════════

echo "═══════════════════════════════════════════════════════════"
echo "🎉 AI GUARDIAN v2.0 UPGRADE COMPLETE!"
echo "═══════════════════════════════════════════════════════════"
echo ""
echo "📊 What was done:"
echo "   ✅ Installed dependencies (XGBoost, LightGBM, SHAP)"
echo "   ✅ Backed up old model to: $BACKUP_DIR"
echo "   ✅ Trained new ensemble model (RF + XGBoost + LightGBM)"
echo "   ✅ Validated model performance"
echo "   ✅ Deployed v2 model to brain.py"
echo ""
echo "📁 Files created:"
echo "   • $ML_DIR/model_v2.pkl"
echo "   • $ML_DIR/scaler_v2.pkl"
echo "   • $ML_DIR/encoders_v2.pkl"
echo "   • $ML_DIR/model_metadata_v2.json"
echo "   • $ML_DIR/model_metrics_v2.png"
echo "   • $ML_DIR/feature_importance_v2.png"
echo ""
echo "📈 Next steps:"
echo "   1. Review metrics: open ml/model_metrics_v2.png"
echo "   2. Review features: open ml/feature_importance_v2.png"
echo "   3. Restart your worker: python src/worker.py"
echo "   4. Send test webhook and check logs"
echo ""
echo "🎯 Expected behavior:"
echo "   ✅ Model returns probabilities between 0.3-0.8 (not always 0.5)"
echo "   ✅ AI approves ~40-60% of signals (not 0%)"
echo "   ✅ 'AI_REJECTED' messages show real probabilities, not 50%"
echo ""
echo "📚 For more info, see: ml/README_UPGRADE.md"
echo ""

# Open metrics plot
if command -v open &> /dev/null; then
    echo "📊 Opening metrics plot..."
    open "$ML_DIR/model_metrics_v2.png" 2>/dev/null || true
fi

echo "═══════════════════════════════════════════════════════════"
