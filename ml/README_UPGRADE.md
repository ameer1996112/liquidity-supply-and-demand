# AI Guardian v2.0 - Professional ML Upgrade

## 🎯 Overview

**Problem:** Your current RF model returns 50% probability (coin flip) because it was trained on only 41 samples.

**Solution:** Upgraded to a professional ensemble model (RF + XGBoost + LightGBM) with advanced feature engineering and proper data collection.

---

## 📊 What Changed?

### v1.0 (Current - BROKEN)
- ❌ Single Random Forest model
- ❌ Only 41 training samples
- ❌ Uses only 8 features (wastes data from Pine Script)
- ❌ No feature engineering
- ❌ Returns 50% probability → Vetos all trades

### v2.0 (Upgraded - PROFESSIONAL)
- ✅ Ensemble model (RF + XGBoost + LightGBM)
- ✅ Supports 500+ training samples
- ✅ Uses all 18 Pine Script features
- ✅ Advanced feature engineering (interactions, polynomials)
- ✅ Hyperparameter tuning
- ✅ Cross-validation
- ✅ SHAP feature importance

---

## 🚀 Quick Start (5 Minutes)

### Option A: Test with Synthetic Data (FASTEST)

```bash
# 1. Generate synthetic test data (500 trades)
python ml/collect_training_data.py --source synthetic --count 500

# 2. Train the model
python ml/train_ai_guardian_v2_pro.py --data ml/training_data.csv

# 3. Check results
cat ml/model_metadata_v2.json
```

### Option B: Use Real TradingView Data (RECOMMENDED)

```bash
# 1. In TradingView:
#    - Run your Pine Script strategy
#    - Open "Strategy Tester" → "List of Trades"
#    - Copy all trades (Ctrl+A, Ctrl+C)
#    - Paste into Excel, save as backtest_results.csv

# 2. Convert TradingView export to training data
python ml/collect_training_data.py --source tradingview --input backtest_results.csv

# 3. Train the model
python ml/train_ai_guardian_v2_pro.py --data ml/training_data.csv

# 4. Review results
open ml/model_metrics_v2.png
cat ml/model_metadata_v2.json
```

---

## 📁 File Structure

```
ml/
├── train_ai_guardian_v2_pro.py      # NEW: Professional training script
├── collect_training_data.py         # NEW: Data collection helper
├── README_UPGRADE.md                # This file
│
├── model_v2.pkl                     # NEW: Ensemble model (after training)
├── scaler_v2.pkl                    # NEW: Feature scaler
├── encoders_v2.pkl                  # NEW: Label encoders
├── model_metadata_v2.json           # NEW: Model info + metrics
├── feature_importance_v2.png        # NEW: SHAP feature importance
├── model_metrics_v2.png             # NEW: ROC curve, confusion matrix
│
├── model.pkl                        # OLD: v1 model (41 samples - broken)
├── encoders.pkl                     # OLD: v1 encoders
├── scaler.pkl                       # OLD: v1 scaler
└── train_ai_guardian.py             # OLD: v1 training script
```

---

## 📊 Data Collection Guide

### Method 1: TradingView Strategy Tester (BEST for Backtesting)

**Step-by-Step:**

1. **Run your Pine Script in TradingView**
   - Load `SND_Strategy.pine`
   - Set timeframe to 5m
   - Set date range (e.g., 6 months)
   - Click "Add to Chart"

2. **Open Strategy Tester**
   - Bottom panel → "Strategy Tester" tab
   - Click "List of Trades"

3. **Export trades**
   - Select all trades (Ctrl+A)
   - Copy (Ctrl+C)
   - Paste into Excel/Google Sheets
   - Save as CSV: `backtest_results.csv`

4. **Convert to training data**
   ```bash
   python ml/collect_training_data.py --source tradingview --input backtest_results.csv
   ```

5. **Verify output**
   ```bash
   head ml/training_data.csv
   wc -l ml/training_data.csv  # Should show 200+ lines
   ```

### Method 2: Database Export (BEST for Live Trading)

```bash
# Extract last 30 days of real trades
python ml/collect_training_data.py --source database --days 30
```

**Requirements:**
- Database connection configured in `.env`
- `trading_signals` table with AI features
- At least 100 closed trades

### Method 3: Synthetic Data (TESTING ONLY)

```bash
# Generate 500 synthetic trades for testing
python ml/collect_training_data.py --source synthetic --count 500 --win-rate 0.55
```

⚠️ **WARNING:** Synthetic data is for TESTING ONLY. Do NOT use in production!

---

## 🎓 Training the Model

### Basic Training (Fast)

```bash
python ml/train_ai_guardian_v2_pro.py --data ml/training_data.csv
```

**Output:**
```
📊 Data Split:
   Train: 400 samples (220 wins, 180 losses)
   Test:  100 samples (55 wins, 45 losses)

🤖 Building ensemble model...
✅ Added Random Forest
✅ Added XGBoost
✅ Added LightGBM
🎯 Ensemble ready with 3 models

⏳ Training ensemble (this may take a few minutes)...
✅ Training complete!

📈 Running 5-fold cross-validation...
   CV Accuracy: 62.5% (+/- 4.2%)

🎯 Evaluating on test set...
   Accuracy:  64.0%
   ROC-AUC:   0.712

🔍 Top 10 Most Important Features:
   score                          0.1823
   liquidity_distance             0.1245
   return_strength                0.0987
   freshness                      0.0842
   trend_alignment                0.0756
   ...
```

### Advanced Training (Slower but Better)

```bash
# Enable hyperparameter tuning
python ml/train_ai_guardian_v2_pro.py --data ml/training_data.csv --tune
```

**Training time:**
- Basic: 2-5 minutes (500 samples)
- Advanced (--tune): 10-30 minutes (500 samples)

---

## 📊 Evaluating Results

### 1. Check Model Metadata

```bash
cat ml/model_metadata_v2.json
```

**Good indicators:**
- ✅ CV Accuracy > 60%
- ✅ ROC-AUC > 0.65
- ✅ Test accuracy close to CV accuracy (no overfitting)

**Bad indicators:**
- ❌ CV Accuracy < 55% (barely better than random)
- ❌ ROC-AUC < 0.55
- ❌ Large gap between train and test (overfitting)

### 2. Review Metrics Plot

```bash
open ml/model_metrics_v2.png
```

**Check for:**
- ROC curve well above diagonal (random line)
- Confusion matrix: More TP+TN than FP+FN
- Probability distribution: Good separation between wins/losses

### 3. Review Feature Importance

```bash
open ml/feature_importance_v2.png
```

**Insights:**
- Which features matter most?
- Are engineered features helping?
- Any features with zero importance? (remove them)

---

## 🔧 Integration with Your System

### Option 1: Update brain.py to Auto-Detect v2

**Edit:** `src/ai/brain.py`

```python
# Line 20-23: Change model paths
MODEL_PATH = _ROOT / "ml" / "model_v2.pkl"  # Was: model.pkl
ENCODERS_PATH = _ROOT / "ml" / "encoders_v2.pkl"
SCALER_PATH = _ROOT / "ml" / "scaler_v2.pkl"
```

### Option 2: Test v2 in Parallel

**Keep v1 running, test v2 separately:**

```python
# In worker.py
from src.ai.brain import ensemble_decision as ensemble_v1
from src.ai.brain_v2 import ensemble_decision as ensemble_v2

# Run both
result_v1 = ensemble_v1(payload)
result_v2 = ensemble_v2(payload)

logger.info(f"v1: {result_v1['rf_prob']:.2%}, v2: {result_v2['rf_prob']:.2%}")

# Use v2 for decision
ai_result = result_v2
```

---

## 📈 Performance Benchmarks

### Minimum Requirements
- ✅ 200+ training samples
- ✅ CV Accuracy > 55%
- ✅ ROC-AUC > 0.60

### Good Performance
- ✅ 500+ training samples
- ✅ CV Accuracy > 60%
- ✅ ROC-AUC > 0.65

### Excellent Performance
- ✅ 1000+ training samples
- ✅ CV Accuracy > 65%
- ✅ ROC-AUC > 0.70

**Current v1 Model:**
- ❌ Only 41 samples
- ❌ CV Accuracy: ~50% (coin flip)
- ❌ ROC-AUC: ~0.50
- ❌ Returns 50% probability → Vetos all trades

---

## 🐛 Troubleshooting

### Issue: "Model returns 50% probability"

**Cause:** Not enough training data or model not trained properly

**Solution:**
1. Check training data size: `wc -l ml/training_data.csv`
2. Should be 200+ lines (excluding header)
3. If < 200, collect more data from TradingView
4. Retrain: `python ml/train_ai_guardian_v2_pro.py --data ml/training_data.csv`

### Issue: "XGBoost/LightGBM not installed"

**Solution:**
```bash
pip install xgboost lightgbm
```

### Issue: "SHAP not working"

**Solution:**
```bash
pip install shap
```

SHAP is optional - model will still train without it.

### Issue: "Low accuracy (< 55%)"

**Possible causes:**
- Not enough training data (need 500+)
- Data quality issues (wrong labels)
- Features not predictive
- Win rate too close to 50% (hard to predict)

**Solutions:**
1. Collect more data (target 500-1000 samples)
2. Verify outcome labels are correct
3. Check feature distributions
4. Review SHAP importance plot
5. Try different threshold (55% instead of 63%)

### Issue: "Overfitting (train >> test accuracy)"

**Solution:**
1. Increase training data size
2. Reduce model complexity: Edit `train_ai_guardian_v2_pro.py`
   ```python
   # Reduce max_depth
   rf = RandomForestClassifier(
       n_estimators=200,
       max_depth=8,  # Was: 12
       ...
   )
   ```
3. Add regularization
4. Use more cross-validation folds

---

## 📚 Next Steps

### Short-term (This Week)
1. ✅ Collect 500+ training samples from TradingView
2. ✅ Train v2 model
3. ✅ Review metrics and feature importance
4. ✅ Deploy v2 model

### Medium-term (This Month)
1. Monitor v2 performance in live trading
2. Collect more data (target 1000+ samples)
3. Retrain monthly with new data
4. Tune threshold based on risk appetite

### Long-term (Ongoing)
1. Implement online learning (update model weekly)
2. Add more features (orderbook data, sentiment, etc.)
3. Experiment with deep learning (LSTM, Transformers)
4. Build separate models per symbol
5. Implement model A/B testing

---

## 🎯 Success Criteria

**You'll know v2 is working when:**

1. ✅ Model returns probabilities between 0.3-0.8 (not always 0.5)
2. ✅ ROC-AUC > 0.65
3. ✅ AI approves ~40-60% of signals (not 0%)
4. ✅ Approved signals have >55% win rate
5. ✅ SHAP plot shows clear feature importance

**Current v1 Status:**
- ❌ Returns 50% probability for ALL trades
- ❌ Vetos 100% of signals
- ❌ Model trained on only 41 samples
- ❌ ROC-AUC ~0.50 (random)

---

## 📞 Support

**Questions?**
- Review this guide carefully
- Check `ml/model_metadata_v2.json` for training results
- Review plots: `ml/model_metrics_v2.png`, `ml/feature_importance_v2.png`
- Test with synthetic data first: `python ml/collect_training_data.py --source synthetic --count 500`

**Common Issues:**
- Model returns 50%: Not enough training data (need 200+)
- Low accuracy: Collect more data or check feature quality
- Import errors: Install dependencies: `pip install xgboost lightgbm shap`

---

## 🚀 Quick Command Reference

```bash
# 1. Generate test data (fast)
python ml/collect_training_data.py --source synthetic --count 500

# 2. Train model
python ml/train_ai_guardian_v2_pro.py --data ml/training_data.csv

# 3. Check results
cat ml/model_metadata_v2.json
open ml/model_metrics_v2.png

# 4. Deploy (edit brain.py to use model_v2.pkl)
# Edit: src/ai/brain.py, line 21
# Change: MODEL_PATH = _ROOT / "ml" / "model_v2.pkl"

# 5. Test
python src/worker.py  # Send test signal via webhook
```

---

**Good luck with your AI upgrade!** 🚀
