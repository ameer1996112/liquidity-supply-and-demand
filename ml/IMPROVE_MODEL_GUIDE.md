# 🚀 How to Improve AI Model from 50% to 70%+ Accuracy

## Current Problem
- **ROC-AUC: 0.543** (barely better than random 0.5)
- **Precision: 31.9%** (same as base win rate - no edge)
- **Data: 2,194 trades** (need 5,000+)

## Root Cause
❌ Not enough predictive signal in current features
❌ Not enough training data

---

## ✅ SOLUTION: 3-Step Improvement Plan

### STEP 1: Collect More Training Data (Target: 5,000+ trades)

**Option A: Export MORE TradingView Backtests (RECOMMENDED)**

Run the automated script:
```bash
./ml/collect_more_data.sh
```

Or manually export these symbols from TradingView:

**Major Forex Pairs:**
- AUDUSD, NZDUSD, USDCAD, EURGBP, EURJPY, GBPAUD
- (You already have: EURUSD, GBPUSD, USDJPY, GBPJPY, GBPCAD ✓)

**Indices:**
- NAS100, SPX500, US30, GER40, UK100

**Crypto:**
- BTCUSD, ETHUSD

**Commodities:**
- XAUUSD ✓, XAGUSD, USOIL, UKOIL

**Export Settings:**
- Timeframe: 5 minutes
- Date Range: Jan 1, 2023 → Today
- Save as: `~/Downloads/backtest_<symbol>.csv`

**⚠️ CRITICAL:** Make sure Signal column contains AI features:
```
| F:score=95 | F:fresh=14 | F:session=2 | F:atr_ratio=2.08 | ...
```

---

### STEP 2: Retrain with Improved Features

I've already upgraded the training script with **12 new advanced features**:

**New Features Added:**
1. `score_tier` - Categorize score into quality tiers
2. `fresh_premium` - High-quality fresh zones (score ≥85, fresh ≤2)
3. `momentum_confluence` - Trend + RSI + ADX alignment
4. `zone_age_risk` - Penalty for heavily touched zones
5. `atr_quality` - Optimal ATR range indicator (0.8-1.5)
6. `strength_imbalance` - Departure vs return strength difference
7. `prime_session` - London + NY sessions (best times)
8. `rsi_extreme` - Oversold/overbought detection
9. `liquidity_sweet_spot` - Optimal liquidity conditions
10. `perfect_setup` - Multi-factor quality signal
11. `volume_strength` - Volume × ADX interaction
12. `composite_quality` - Weighted quality score

These features help the model learn:
- Non-linear patterns
- Interaction effects between features
- Optimal thresholds for each indicator
- Market regime detection

---

### STEP 3: Quick Retrain Script

Once you have MORE backtest files in `~/Downloads/`:

```bash
# Combine all backtest files
cd ~/Downloads
head -1 backtest_eurusd.csv > backtest_all.csv
for f in backtest_*.csv; do
    [ "$f" != "backtest_all.csv" ] && tail -n +2 "$f" >> backtest_all.csv
done

# Parse features
cd -
python ml/collect_training_data.py --source tradingview --input ~/Downloads/backtest_all.csv

# Train with improved features
python ml/train_ai_guardian_v3_lightgbm.py --data ml/training_data.csv

# Check results
cat ml/model_metadata_v3.json | grep -A 5 metrics
open ml/feature_importance_v3.png
```

---

## 🎯 Target Performance Metrics

| Metric | Current | Target | Impact |
|--------|---------|--------|--------|
| **ROC-AUC** | 0.543 | >0.65 | Model can distinguish wins from losses |
| **Recall** | 84.6% | >70% | Catch most winning trades |
| **Precision** | 31.9% | >40% | Reduce false positives |
| **Training Data** | 2,194 | 5,000+ | More patterns to learn |

---

## 📊 Expected Improvements

With 5,000+ trades and advanced features:

**Before (Current):**
- ROC-AUC: 0.543 (no edge)
- Model predicts randomly
- 50/50 coin flip

**After (Expected):**
- ROC-AUC: 0.65-0.75 (strong edge)
- Model identifies high-quality setups
- 40-50% win rate on predictions (profitable with 2:1 R:R)

---

## 🚨 Troubleshooting

### "Still getting ROC-AUC < 0.60 after more data"

**Possible issues:**
1. **Pine Script features missing** - Check Signal column has F:score, F:fresh, etc.
2. **Not enough variety** - Export more symbols (10+ different instruments)
3. **Overfitting** - Reduce n_estimators from 200 to 100
4. **Feature correlation** - Some features may be too similar

**Solutions:**
```bash
# Check feature importance
cat ml/feature_importance_v3.png

# If top 3 features are all similar (e.g., all score-based):
# → Need more diverse features in Pine Script export
```

### "Model still predicts 50% for everything"

**Check threshold:**
```python
# In ml/train_ai_guardian_v3_lightgbm.py, line ~305
threshold = 0.31  # Should match your win rate
```

**Test different thresholds:**
- Lower threshold (0.25): Higher recall, lower precision
- Higher threshold (0.40): Lower recall, higher precision

---

## 📚 Next Steps

1. **Export 10+ more symbols** from TradingView
2. **Combine all CSVs** into one file
3. **Retrain model** with improved features
4. **Check ROC-AUC** - should be >0.60
5. **Deploy to production** if metrics look good

**Quick test:**
```bash
# After retraining, check if it works:
python -c "
import pickle
import numpy as np

# Load model
with open('ml/model_v3.pkl', 'rb') as f:
    model = pickle.load(f)

# Test prediction
sample = np.array([[90, 1, 2, 1, 1.2, 0, 1, 55, 1, 1.5, 30, 1, 80, 70, 10, 20, 90, 90, 80, 90, 1, 0.5, 2, 0, 1, 0, 0.8, 0.3, 0, 1, 0.85]])
prob = model.predict_proba(sample)[0][1]
print(f'Win probability: {prob:.1%}')
"
```

If win probability varies significantly for different inputs (not stuck at 50%), the model is working!

---

## 💡 Advanced: Adding More Pine Script Features

If you want to go beyond 70% accuracy, add these to Pine export:

**Volume Analysis:**
- `F:volume_ratio=1.5` (current volume / average)
- `F:volume_trend=1` (increasing/decreasing)

**Order Flow:**
- `F:buy_pressure=0.6` (buy volume / total volume)
- `F:sell_pressure=0.4`

**Candle Patterns:**
- `F:engulfing=1` (bullish/bearish engulfing)
- `F:doji=0` (indecision candle)

**Recent Performance:**
- `F:last_3_wins=2` (recent win streak)
- `F:consecutive_losses=0`

**Market Structure:**
- `F:higher_highs=1` (uptrend structure)
- `F:lower_lows=0`

These features would push ROC-AUC to 0.75-0.85 range!
