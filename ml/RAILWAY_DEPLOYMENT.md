# 🚂 AI Guardian v2.0 - Railway Deployment Guide

## 🎯 Overview

Your bot runs on **Railway** with:
- **Backend:** Worker (processes webhooks, executes trades)
- **Frontend:** Dashboard (displays signals, metrics)

**Important:** Model training happens **locally** (your machine), then deployed to Railway.

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────┐
│ LOCAL (Your Machine)                                │
│                                                     │
│ 1. Export TradingView trades                       │
│ 2. Train model → model_v2.pkl (5 min)             │
│ 3. Test locally                                    │
│ 4. Commit to Git                                   │
└─────────────────────────────────────────────────────┘
                        │
                        │ git push
                        ▼
┌─────────────────────────────────────────────────────┐
│ RAILWAY (Cloud)                                     │
│                                                     │
│ Backend:                                           │
│  • worker.py (loads model_v2.pkl)                 │
│  • brain.py (RF predictions)                      │
│  • PostgreSQL (trades database)                   │
│                                                     │
│ Frontend:                                          │
│  • Next.js dashboard                              │
│  • Shows AI decisions in real-time                │
└─────────────────────────────────────────────────────┘
```

---

## 📦 Step 1: Train Model Locally

**On your local machine:**

```bash
# Navigate to project
cd /Users/ameeramer/dev/projects/galilsoftware/sources/trading

# Option A: Quick test with synthetic data
bash ml/upgrade_ai.sh

# Option B: Real data from TradingView
python ml/collect_training_data.py --source tradingview --input backtest_results.csv
python ml/train_ai_guardian_v2_pro.py --data ml/training_data.csv
```

**Expected output:**
```
✅ Model trained successfully!
   CV Accuracy:   62.5% (+/- 4.2%)
   Test Accuracy: 64.0%
   ROC-AUC:       0.712

📁 Model files created:
   ml/model_v2.pkl
   ml/scaler_v2.pkl
   ml/encoders_v2.pkl
   ml/model_metadata_v2.json
```

---

## 🚀 Step 2: Deploy to Railway

### Method 1: Git Deployment (RECOMMENDED)

Railway auto-deploys from your Git repository.

**Step 1: Commit model files**

```bash
# Add model files to git
git add ml/model_v2.pkl
git add ml/scaler_v2.pkl
git add ml/encoders_v2.pkl
git add ml/model_metadata_v2.json

# Commit
git commit -m "🤖 Upgrade AI Guardian to v2.0

- Ensemble model (RF + XGBoost + LightGBM)
- Trained on 500+ samples
- CV Accuracy: 62.5%, ROC-AUC: 0.712
- Uses all 18 Pine Script features
"

# Push to Railway
git push origin main
```

**Step 2: Update brain.py to use v2**

```bash
# Edit src/ai/brain.py (lines 20-23)
# Change:
MODEL_PATH = _ROOT / "ml" / "model_v2.pkl"
ENCODERS_PATH = _ROOT / "ml" / "encoders_v2.pkl"
SCALER_PATH = _ROOT / "ml" / "scaler_v2.pkl"

# Commit and push
git add src/ai/brain.py
git commit -m "🔧 Update brain.py to use v2 model"
git push origin main
```

**Step 3: Wait for Railway deployment**

```
Railway will automatically:
1. Detect git push
2. Build new Docker image
3. Install dependencies
4. Deploy updated backend
5. Restart worker.py

⏱️  Deployment time: 2-5 minutes
```

**Step 4: Verify deployment**

```bash
# Watch Railway logs
railway logs --service backend

# Look for:
"Brain online. Features: 18"  # ✅ v2 loaded (v1 had 8)
"Scaler loaded: numerical=11, categorical=7"  # ✅ Scaler active
```

### Method 2: Railway CLI Upload (FAST)

If you don't want to commit large model files to Git:

```bash
# Install Railway CLI
npm install -g @railway/cli

# Login
railway login

# Link to your project
railway link

# Upload model files directly
railway up ml/model_v2.pkl
railway up ml/scaler_v2.pkl
railway up ml/encoders_v2.pkl

# Restart backend
railway restart --service backend
```

### Method 3: Environment Variables (ADVANCED)

Store model as base64-encoded env var (not recommended for large files):

```bash
# Encode model
base64 ml/model_v2.pkl > model_v2_base64.txt

# In Railway dashboard:
# Settings → Variables → Add Variable
# Name: MODEL_V2_BASE64
# Value: [paste contents of model_v2_base64.txt]

# Update brain.py to decode from env var
# (Implementation needed)
```

---

## 🔧 Step 3: Update Railway Dependencies

### Update requirements.txt

Railway needs ML dependencies to load the model.

**Check if these are in `requirements.txt`:**

```txt
# ML Dependencies (for AI Guardian v2.0)
scikit-learn>=1.3.0
xgboost>=2.0.0
lightgbm>=4.0.0
numpy>=1.24.0
pandas>=2.0.0
```

**If missing, add them:**

```bash
# Edit requirements.txt
echo "" >> requirements.txt
echo "# AI Guardian v2.0 Dependencies" >> requirements.txt
echo "scikit-learn>=1.3.0" >> requirements.txt
echo "xgboost>=2.0.0" >> requirements.txt
echo "lightgbm>=4.0.0" >> requirements.txt

# Commit and push
git add requirements.txt
git commit -m "📦 Add ML dependencies for AI Guardian v2.0"
git push origin main
```

**Alternative: Use pyproject.toml (if using Poetry)**

```toml
[tool.poetry.dependencies]
scikit-learn = "^1.3.0"
xgboost = "^2.0.0"
lightgbm = "^4.0.0"
numpy = "^1.24.0"
pandas = "^2.0.0"
```

---

## 🐳 Step 4: Update Dockerfile (if applicable)

If Railway uses a custom Dockerfile:

```dockerfile
# Install ML dependencies
RUN pip install --no-cache-dir \
    scikit-learn>=1.3.0 \
    xgboost>=2.0.0 \
    lightgbm>=4.0.0

# Copy model files
COPY ml/model_v2.pkl /app/ml/
COPY ml/scaler_v2.pkl /app/ml/
COPY ml/encoders_v2.pkl /app/ml/
```

---

## ✅ Step 5: Verify Deployment

### Check 1: Railway Logs

```bash
# Watch backend logs
railway logs --service backend --follow

# Expected output:
✅ "Brain online. Features: 18"
✅ "Scaler loaded: numerical=11, categorical=7"
✅ "LLM client initialized"
✅ "Worker ready"
```

### Check 2: Send Test Webhook

**From TradingView or Postman:**

```json
POST https://your-railway-backend.up.railway.app/webhook

{
  "symbol": "GBPJPY",
  "side": "buy",
  "entry": 208.312,
  "sl": 208.389,
  "tp": 208.120,
  "zone_id": 123,
  "score": 75,
  "freshness": 1,
  "session": 1,
  "atr_ratio": 1.2,
  "is_accuracy": 0,
  "trend": 1,
  "rsi": 55,
  "htf_trend": 1,
  "rvol": 1.1,
  "adx": 32,
  "touch_count": 1,
  "base_quality": 65,
  "departure_strength": 70,
  "liquidity_distance": 12.3,
  "liquidity_spread": 25.6,
  "return_strength": 68,
  "zone_type": "demand",
  "entry_model": "DIR_CLOSE"
}
```

**Expected response:**

```json
{
  "decision": "GO",
  "reason": "RF pass and LLM filter disabled.",
  "rf_prob": 0.683,
  "rf_note": "AI Confidence: 68.3%"
}
```

### Check 3: Frontend Dashboard

Navigate to your Railway frontend URL:
```
https://your-frontend.up.railway.app
```

**Expected:**
- Signal shows `AI_APPROVED` (not `AI_REJECTED`)
- AI Reasoning shows real probability (not 50.0%)
- Approved signals appear in dashboard

---

## 🐛 Troubleshooting

### Issue: "Model file not found"

**Symptoms:**
```
ERROR: Brain missing: /app/ml/model_v2.pkl
RF probability 50.0% below 63% threshold.
```

**Solutions:**

1. **Verify model exists in Railway file system**
   ```bash
   railway run ls -lh ml/

   # Should show:
   # model_v2.pkl (401K)
   # scaler_v2.pkl (793B)
   # encoders_v2.pkl (767B)
   ```

2. **Check git repository**
   ```bash
   # Locally
   git ls-files ml/

   # Should include model_v2.pkl
   # If missing, add it:
   git add -f ml/model_v2.pkl
   git commit -m "Add v2 model"
   git push origin main
   ```

3. **Verify Railway build includes ml/ directory**
   - Railway Dashboard → Deployment Logs
   - Look for: `COPY ml/ /app/ml/`

### Issue: "Import error: No module named 'xgboost'"

**Symptoms:**
```
ModuleNotFoundError: No module named 'xgboost'
```

**Solution:**
```bash
# Add to requirements.txt
echo "xgboost>=2.0.0" >> requirements.txt
echo "lightgbm>=4.0.0" >> requirements.txt

# Commit and push
git add requirements.txt
git commit -m "Add XGBoost/LightGBM"
git push origin main
```

### Issue: "Still returns 50% probability"

**Diagnosis steps:**

1. **Check Railway logs for "Brain online"**
   ```bash
   railway logs --service backend | grep "Brain"

   # Expected:
   # "Brain online. Features: 18"
   ```

2. **Verify brain.py uses v2 paths**
   ```bash
   # Locally
   grep "model_v2" src/ai/brain.py

   # Should show:
   # MODEL_PATH = _ROOT / "ml" / "model_v2.pkl"
   ```

3. **Check model metadata on Railway**
   ```bash
   railway run cat ml/model_metadata_v2.json

   # Should show version: "2.0"
   ```

4. **Restart Railway service**
   ```bash
   railway restart --service backend
   ```

### Issue: "Out of memory during prediction"

**Symptoms:**
```
MemoryError: Unable to allocate array
Railway crashed: Exit code 137 (OOM killed)
```

**Solution:**

Railway free tier has memory limits. Optimize model size:

```bash
# Reduce ensemble to RF only (smaller)
# Edit train_ai_guardian_v2_pro.py, line 200:
# Comment out XGBoost and LightGBM estimators

# Retrain
python ml/train_ai_guardian_v2_pro.py --data ml/training_data.csv

# Or upgrade Railway plan:
# Dashboard → Settings → Change Plan → Hobby ($5/month)
```

---

## 📊 Railway Resource Usage

### Free Tier Limits:
- **Memory:** 512 MB
- **CPU:** Shared
- **Storage:** 1 GB
- **Hours:** 500 hrs/month

### Model File Sizes:
```
model_v2.pkl       ~400 KB   (Ensemble)
scaler_v2.pkl      ~1 KB
encoders_v2.pkl    ~1 KB
------------------------------------
Total:             ~402 KB   ✅ (fits in free tier)
```

### Runtime Memory:
```
Worker (no AI):    ~150 MB
Worker + AI v2:    ~280 MB
------------------------------------
Total:             ~280 MB   ✅ (fits in 512 MB limit)
```

**If you hit limits:**
- Upgrade to Hobby plan ($5/month): 2 GB RAM
- Or use RF-only model (remove XGBoost/LightGBM)

---

## 🔄 Monthly Retraining Workflow

**Every month, retrain with fresh data:**

```bash
# 1. Export latest trades from TradingView (monthly)
# 2. Train locally
python ml/collect_training_data.py --source tradingview --input backtest_latest.csv
python ml/train_ai_guardian_v2_pro.py --data ml/training_data.csv

# 3. Review metrics
cat ml/model_metadata_v2.json
open ml/model_metrics_v2.png

# 4. Deploy to Railway
git add ml/model_v2.pkl ml/model_metadata_v2.json
git commit -m "🤖 Monthly model retrain: $(date +%Y-%m-%d)"
git push origin main

# 5. Monitor performance
railway logs --service backend | grep "Brain"
```

**Automation (Advanced):**

Use GitHub Actions to retrain automatically:

```yaml
# .github/workflows/retrain-ai.yml
name: Retrain AI Guardian
on:
  schedule:
    - cron: '0 0 1 * *'  # First day of each month
  workflow_dispatch:  # Manual trigger

jobs:
  retrain:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - name: Train model
        run: |
          python ml/collect_training_data.py --source database --days 30
          python ml/train_ai_guardian_v2_pro.py --data ml/training_data.csv
      - name: Commit and push
        run: |
          git add ml/model_v2.pkl
          git commit -m "🤖 Auto-retrain: $(date +%Y-%m-%d)"
          git push
```

---

## 📈 Monitoring AI Performance on Railway

### 1. Railway Metrics Dashboard

**Add custom metrics:**

```python
# In worker.py, after AI decision:
from prometheus_client import Counter, Histogram

ai_decisions = Counter('ai_decisions_total', 'AI decisions', ['decision'])
ai_probabilities = Histogram('ai_probability', 'AI prediction probability')

# After ensemble_decision():
ai_decisions.labels(decision=ai_result['decision']).inc()
ai_probabilities.observe(ai_result['rf_prob'])
```

### 2. Database Logging

Track AI decisions in PostgreSQL:

```python
# In worker.py, save AI decision:
await db.execute("""
    INSERT INTO ai_decisions (signal_id, decision, rf_prob, reason)
    VALUES ($1, $2, $3, $4)
""", signal_id, ai_result['decision'], ai_result['rf_prob'], ai_result['reason'])
```

**Query in Railway console:**

```sql
-- Check AI approval rate (last 24h)
SELECT
    decision,
    COUNT(*) as count,
    AVG(rf_prob) as avg_probability
FROM ai_decisions
WHERE created_at > NOW() - INTERVAL '24 hours'
GROUP BY decision;

-- Expected:
-- GO:    ~50 (60% of signals, avg prob 68%)
-- NO_GO: ~30 (40% of signals, avg prob 42%)
```

### 3. Frontend Dashboard

**Display AI metrics:**

```typescript
// frontend/src/app/ai-metrics/page.tsx
export default function AIMetrics() {
  const { data } = useSWR('/api/ai/metrics', fetcher);

  return (
    <div>
      <h1>AI Guardian Performance</h1>
      <MetricCard title="Approval Rate" value={data.approvalRate} />
      <MetricCard title="Avg Probability" value={data.avgProb} />
      <MetricCard title="Win Rate (Approved)" value={data.approvedWinRate} />
    </div>
  );
}
```

---

## ✅ Deployment Checklist

Before deploying to Railway:

- [ ] Model trained locally with 200+ samples
- [ ] CV Accuracy > 55%, ROC-AUC > 0.60
- [ ] Reviewed metrics plot (`model_metrics_v2.png`)
- [ ] Added ML dependencies to `requirements.txt`
- [ ] Updated `brain.py` to use `model_v2.pkl`
- [ ] Committed model files to git
- [ ] Pushed to Railway (`git push origin main`)
- [ ] Watched Railway deployment logs
- [ ] Verified "Brain online. Features: 18" in logs
- [ ] Sent test webhook, received real probability (not 50%)
- [ ] Checked frontend dashboard shows approved signals
- [ ] Monitored for 24h to ensure stability

---

## 🎯 Success Criteria

**You'll know it's working when:**

1. ✅ Railway logs show: `"Brain online. Features: 18"`
2. ✅ Test webhook returns probability 0.3-0.8 (not 0.5)
3. ✅ Frontend shows `AI_APPROVED` signals (not all rejected)
4. ✅ Approval rate ~40-60% (not 0%)
5. ✅ No memory errors or crashes

**Before (v1.0):**
```
Railway Logs:
❌ "Brain online. Features: 8"
❌ "RF probability 50.0% below 63% threshold."
❌ All signals rejected
```

**After (v2.0):**
```
Railway Logs:
✅ "Brain online. Features: 18"
✅ "RF probability 68.3% above 60% threshold."
✅ Signals approved/rejected intelligently
```

---

## 📞 Support

**Railway-Specific Issues:**

1. **Check Railway logs first:**
   ```bash
   railway logs --service backend --tail 100
   ```

2. **Verify environment:**
   ```bash
   railway run env | grep MODEL
   railway run python -c "import sklearn; print(sklearn.__version__)"
   ```

3. **Test locally before deploying:**
   ```bash
   # Simulate Railway environment locally
   python src/worker.py
   ```

**Common Railway Issues:**
- Model file not found → Check git includes `ml/model_v2.pkl`
- Import errors → Add dependencies to `requirements.txt`
- Memory errors → Upgrade plan or use RF-only model
- Still 50% → Verify `brain.py` uses v2 paths and restart service

---

**Ready to deploy to Railway?**

```bash
# 1. Train locally
bash ml/upgrade_ai.sh

# 2. Commit and push
git add ml/model_v2.pkl ml/scaler_v2.pkl ml/encoders_v2.pkl src/ai/brain.py
git commit -m "🤖 Deploy AI Guardian v2.0 to Railway"
git push origin main

# 3. Watch deployment
railway logs --service backend --follow
```

**Questions? Check the main guide:**
```bash
cat ml/README_UPGRADE.md
```
