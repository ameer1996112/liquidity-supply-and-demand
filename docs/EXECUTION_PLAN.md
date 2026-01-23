# EXECUTION PLAN: From Functional Bot → Money Printer

**Author:** Lead Quant Strategist
**Date:** 2026-01-22
**Status:** Shadow Mode Validation Phase
**Timeline:** 7-14 Days

---

## CURRENT STATE ASSESSMENT

### ✅ What's Working
- **Deployment**: Live on Railway
- **Data Pipeline**: Supabase storing all signals with 17 AI features
- **Model Trained**: `model_ultimate.pkl` (76.6% accuracy, 710 samples)
- **Telemetry**: Collecting entry + exit data (outcome, MAE, bars held, P&L)
- **Alerts**: Discord notifications working

### ⚠️ Critical Issues Identified
1. **Model Disabled**: `AI_FILTER_ENABLED=false` (good for now!)
2. **High False Negative Rate**: Model rejects 72% of winners (161 FN vs 63 TP)
3. **Limited Live Data**: 0-10 trades (need 50+ for validation)
4. **No Automated Retraining**: Manual process, data not merged

---

## THE STRATEGY

### Phase 1: Prove It Works (Days 1-7)
**Goal:** Collect 50+ closed trades with AI predictions logged

### Phase 2: Decide (Days 8-10)
**Goal:** Analyze shadow mode results, make enable/retrain/iterate decision

### Phase 3: Optimize (Days 11-14)
**Goal:** Either enable AI filter OR retrain model based on Phase 2 results

---

## WEEK 1: SHADOW MODE VALIDATION

### Daily Routine (Every Morning)

```bash
# Run daily report
python daily_report.py

# Track progress toward 50 trades
# Monitor: Win rate, R:R, symbols performance
```

**What You're Watching:**
- **Signal Volume**: Are you getting enough alerts? (Target: 5-10/day)
- **Win Rate**: Baseline performance without AI filter (Target: >55%)
- **Trade Distribution**: Which symbols perform best?
- **Data Quality**: Are all 17 features being captured?

### Key Metrics to Track

| Metric | Target | Critical Threshold |
|--------|--------|-------------------|
| Total Signals (7 days) | 30-50 | <20 = not enough data |
| Closed Trades (7 days) | 10-20 | <5 = too slow |
| Win Rate (no filter) | >50% | <45% = strategy issue |
| Avg R:R | >1.5 | <1.2 = poor setups |

---

## DECISION TREE (After 50 Closed Trades)

```bash
# Run shadow mode analysis
python monitor_shadow_mode.py
```

This will generate a **recommendation**. Follow the decision tree:

### Scenario A: Model Shows Value ✅
**Indicators:**
- Model Precision >65%
- Model Recall >50%
- Missed Winners (FN) < True Positives (TP)
- Would improve P&L by >5%

**Action:** Enable AI Filter
```bash
# Update .env
AI_FILTER_ENABLED=true
AI_MIN_WIN_PROBABILITY=0.45  # Start conservative

# Redeploy to Railway
git add .env
git commit -m "Enable AI filter with threshold 0.45"
git push railway main
```

### Scenario B: Model Hurts Performance ❌
**Indicators:**
- Model Precision <60%
- Missed Winners (FN) >> True Positives (TP)
- Would reduce P&L

**Action:** Retrain Model
```bash
# Export live data
python export_training_data.py

# Merge with historical
cd backtest_data/processed
cat ../live/training_live_*.csv >> training_ultimate.csv

# Retrain with combined dataset
python scripts/train_enhanced_model.py

# Test new model in shadow mode again
```

### Scenario C: Inconclusive 🤷
**Indicators:**
- Model accuracy 60-65%
- Not enough data (<50 trades)
- Mixed signals

**Action:** Collect More Data (7 more days)

---

## MONITORING SCRIPTS CREATED

### 1. **daily_report.py** (Run Every Morning)
Shows:
- Last 24h signal volume
- Last 7 days performance
- Win rate by symbol
- Progress toward 50-trade target

```bash
python daily_report.py
```

### 2. **monitor_shadow_mode.py** (Run Weekly)
Shows:
- Model predictions vs actual outcomes
- Precision, Recall, F1-Score
- Missed winners analysis
- Enable/Don't Enable recommendation

```bash
python monitor_shadow_mode.py
```

### 3. **export_training_data.py** (Run Before Retraining)
Exports Supabase → CSV for model retraining

```bash
python export_training_data.py
```

---

## LOW-HANGING FRUIT OPTIMIZATIONS

### Quick Win #1: Feature Pruning
**Problem:** `rsi` and `news_event` have 0% importance
**Fix:** Retrain without useless features

```python
# In train_model.py, remove these from training:
# - rsi (importance: 0.0)
# - news_event (importance: 0.0)
```

### Quick Win #2: Threshold Calibration
**Problem:** 50% threshold too conservative (high FN rate)
**Fix:** Test multiple thresholds

```bash
# Test thresholds: 0.40, 0.45, 0.50, 0.55
# Find optimal balance between precision and recall
```

### Quick Win #3: Symbol-Specific Models
**Hypothesis:** XAUUSD behaves differently than GBPJPY
**Test:** Train XAUUSD-only model, compare win rate

```bash
# If XAUUSD model improves >5%, deploy separate models per symbol
```

---

## AUTOMATED RETRAINING PIPELINE (Phase 3)

### Weekly Retraining Schedule

```bash
# Every Sunday at 00:00 UTC (cron job)
0 0 * * 0 /path/to/retrain_weekly.sh
```

**retrain_weekly.sh:**
```bash
#!/bin/bash
cd /path/to/webhook_backend

# Export live data
python export_training_data.py

# Check if we have enough new data (50+ new samples)
NEW_SAMPLES=$(wc -l < backtest_data/live/training_live_*.csv)

if [ $NEW_SAMPLES -ge 50 ]; then
    echo "✅ Retraining with $NEW_SAMPLES new samples"

    # Merge with historical
    cat backtest_data/live/training_live_*.csv >> backtest_data/processed/training_ultimate.csv

    # Retrain
    python scripts/train_enhanced_model.py

    # Backup old model
    cp models/model_ultimate.pkl models/model_ultimate_backup_$(date +%Y%m%d).pkl

    # Archive live data
    mv backtest_data/live/*.csv backtest_data/archive/

    echo "✅ Retraining complete. Review model_performance.json before deploying."
else
    echo "⏳ Only $NEW_SAMPLES samples. Need 50+. Skipping retraining."
fi
```

---

## SUCCESS CRITERIA

### Short-Term (Week 1)
- [ ] Collect 50+ closed trades
- [ ] Run shadow mode analysis
- [ ] Make enable/retrain decision

### Medium-Term (Weeks 2-4)
- [ ] If enabled: AI filter improves win rate by >5%
- [ ] If retrained: New model shows >70% accuracy
- [ ] Automated weekly retraining functional

### Long-Term (Month 2+)
- [ ] Win rate >60% (filtered trades)
- [ ] Model continuously learning from live data
- [ ] System running autonomously with monitoring

---

## EMERGENCY PROCEDURES

### If Model Goes Rogue
```bash
# Immediately disable AI filter
AI_FILTER_ENABLED=false
git push railway main
```

### If Win Rate Drops >10%
```bash
# 1. Check for market regime change
python daily_report.py

# 2. Export data and analyze
python export_training_data.py

# 3. Check feature drift
# Are live features matching training distribution?
```

### If System Goes Down
```bash
# Check Railway logs
railway logs

# Check Supabase connection
python -c "import supabase_db; supabase_db.init_supabase()"
```

---

## RISK MANAGEMENT

### During Shadow Mode
- **Zero Risk**: Model predicts but doesn't filter
- **Focus**: Data collection quality over quantity
- **Validate**: All 17 features being captured correctly

### When Enabling AI Filter
- **Start Conservative**: Threshold 0.45 (not 0.50)
- **Monitor Daily**: First 3 days after enabling
- **Quick Disable**: If win rate drops >10% in first week

### During Live Trading
- **Never** disable exit webhooks (critical for learning)
- **Always** log model predictions (even if filtered)
- **Review** model performance monthly

---

## FAQ

### Q: How long until I can enable the AI filter?
**A:** Minimum 7 days shadow mode + 50 closed trades. Conservative: 14 days + 100 trades.

### Q: What if I'm not getting enough signals?
**A:** Check TradingView alerts are firing. Lower Pine Script filters if <5 signals/day.

### Q: Should I retrain with every new trade?
**A:** No. Weekly retraining with 50+ new samples is optimal. More frequent = overfitting risk.

### Q: Can I use the model on other symbols?
**A:** Yes, but test first. Model trained on XAUUSD/GBPJPY/etc. may not work on BTC or stocks.

### Q: What if shadow mode shows model is worthless?
**A:** Either: (1) Retrain with better features, (2) Keep collecting data (regime change?), or (3) Focus on improving base strategy (Pine Script logic).

---

## NEXT ACTIONS (This Week)

### Monday
- [x] Scripts created: `daily_report.py`, `monitor_shadow_mode.py`, `export_training_data.py`
- [ ] Run `python daily_report.py` to check current state
- [ ] Verify all 17 features being captured in webhook

### Tuesday-Sunday
- [ ] Run `daily_report.py` every morning
- [ ] Track progress toward 50 closed trades
- [ ] Monitor Discord for any webhook errors

### Next Monday (Week 2)
- [ ] Run `python monitor_shadow_mode.py`
- [ ] Review recommendation
- [ ] Make decision: Enable / Retrain / Continue monitoring

---

## CONTACT & SUPPORT

If you encounter issues:
1. Check Railway logs: `railway logs --tail`
2. Check Supabase dashboard for data consistency
3. Run `python daily_report.py` to diagnose

**Remember:** The goal is sustainable, profitable automation. Rush = mistakes. Conservative validation = confidence.

---

**Good luck! 🚀**
