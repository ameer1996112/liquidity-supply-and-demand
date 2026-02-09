# Prop Firm Protection Deployment Guide

## **Trinity Engine v3.0 - Comprehensive Setup**

This guide walks you through deploying the 3 critical prop firm protection features:
1. **MTM Guardian** - Real-time floating PnL tracking
2. **Staleness Guard** - Webhook latency protection
3. **Consistency Analyzer** - FTMO 40% rule enforcement

---

## **📋 PRE-DEPLOYMENT CHECKLIST**

- [ ] Supabase database accessible
- [ ] Redis running
- [ ] Python 3.11+ installed
- [ ] Node.js 18+ installed (for frontend)
- [ ] MetaAPI credentials configured
- [ ] TradingView webhooks configured

---

## **🔧 STEP 1: DATABASE MIGRATION**

### **1.1 Run Migration**

```bash
# Navigate to project root
cd /path/to/trading

# Copy migration SQL
cat migrations/018_prop_firm_metrics.sql
```

### **1.2 Execute in Supabase**

1. Open Supabase Dashboard: https://supabase.com/dashboard
2. Navigate to **SQL Editor**
3. Paste the migration SQL
4. Click **Run**

### **1.3 Verify Table Created**

```sql
-- Run this to verify:
SELECT * FROM prop_firm_metrics LIMIT 1;
```

Expected: Empty table or first snapshot row.

---

## **🛠️ STEP 2: UPDATE ENVIRONMENT VARIABLES**

### **2.1 Update .env File**

```bash
# Copy from example if needed
cp .env.example .env

# Edit .env
nano .env
```

### **2.2 Add New Settings**

Add these lines to your `.env`:

```bash
# =============================================================================
# PROP FIRM PROTECTION FEATURES (Trinity Engine v3.0)
# =============================================================================

# MTM Guardian: Real-time floating PnL tracking
MTM_GUARDIAN_ENABLED=true
MTM_CACHE_TTL_SECONDS=10

# Staleness Guard: Webhook latency protection
ENABLE_STALENESS_GUARD=true
STALENESS_MAX_AGE_SECONDS=5
STALENESS_MAX_PRICE_DEVIATION_PIPS=3.0

# Consistency Analyzer: FTMO 40% rule enforcement
CONSISTENCY_ENABLED=true
CONSISTENCY_LIMIT_PCT=40.0

# Enable evaluation mode for prop firm tracking
EVALUATION_MODE=true
EVALUATION_PHASE=phase1  # Options: phase1, phase2, funded
EVALUATION_START_DATE=2025-02-09  # Format: YYYY-MM-DD
```

### **2.3 Verify Configuration**

```bash
# Test config loads correctly
python -c "from config import get_settings; s = get_settings(); print(f'MTM Enabled: {s.mtm_guardian_enabled}')"
```

Expected output: `MTM Enabled: True`

---

## **🚀 STEP 3: RESTART SERVICES**

### **3.1 Restart Worker**

```bash
# Kill existing worker
pkill -f "python -m src.worker"

# Start worker with new features
python -m src.worker
```

**Look for these log lines:**
```
MTM Guardian: OK
Staleness Guard: PASSED
Consistency OK
📊 Daily reset scheduler initialized for prop firm tracking
```

### **3.2 Restart API**

```bash
# If running locally:
pkill -f "uvicorn src.api:app"
uvicorn src.api:app --host 0.0.0.0 --port 8000 --reload

# If on Railway/Docker: Redeploy
# Railway: git push railway main
# Docker: docker-compose restart api
```

### **3.3 Verify API Endpoints**

```bash
# Test prop firm metrics endpoint
curl http://localhost:8000/api/prop-firm/metrics | jq

# Expected: JSON with equity, drawdown, consistency data
```

---

## **🧪 STEP 4: RUN TESTS**

### **4.1 Unit Tests**

```bash
# Run prop firm guard tests
pytest tests/test_prop_firm_guards.py -v

# Expected: All 10+ tests PASSED
```

### **4.2 Integration Tests**

```bash
# Run manual test script
python scripts/test_prop_firm_guards.py
```

**Expected Output:**
```
TEST 1: MTM GUARDIAN (Floating PnL Tracking)
✅ MTM Guardian: PASSED

TEST 2: STALENESS GUARD (Webhook Latency)
✅ PASSED

TEST 3: CONSISTENCY ANALYZER (FTMO 40% Rule)
✅ CONSISTENCY: PASSED

🎉 ALL TESTS PASSED! Your prop firm protection is working.
```

---

## **📊 STEP 5: DEPLOY FRONTEND WIDGET**

### **5.1 Add Widget to Dashboard**

Edit `frontend/src/app/page.tsx`:

```typescript
import { PropFirmWidget } from '@/components/dashboard/PropFirmWidget';

// Add to your dashboard grid:
<PropFirmWidget />
```

### **5.2 Build Frontend**

```bash
cd frontend
npm install
npm run build
npm start
```

### **5.3 Verify Widget**

Navigate to http://localhost:3000

**You should see:**
- 🏆 Prop Firm Challenge Tracker
- Daily drawdown gauges
- Floating PnL metrics
- Consistency status

---

## **🎯 STEP 6: SCENARIO TESTING**

### **Test 1: MTM Kill Switch**

**Objective:** Verify kill switch engages with floating losses.

```bash
# 1. Open 3 losing trades (don't close them)
# 2. Check dashboard - should show floating PnL
# 3. If total (closed + floating) >= -4%, kill switch should engage
# 4. Try sending new signal - should be REJECTED

# Check Redis:
redis-cli GET trading:kill_switch
# Expected: "1" if kill switch engaged
```

### **Test 2: Staleness Guard**

**Objective:** Verify stale signals are rejected.

```bash
# Method 1: Simulate webhook delay
# In TradingView, add a 10-second delay to webhook URL
# Signal should be rejected with "staleness" error

# Method 2: Manual test
curl -X POST http://localhost:8000/webhook \
  -H "Content-Type: application/json" \
  -d '{
    "symbol": "EURUSD",
    "side": "buy",
    "entry": 1.1000,
    "sl": 1.0950,
    "tp": 1.1100,
    "bar_time": "2025-02-09T10:00:00Z"  # Old timestamp
  }'

# Check worker logs:
# Expected: "STALENESS REJECTED: Signal staleness: 10.0s old"
```

### **Test 3: Consistency Analyzer**

**Objective:** Verify best day can't exceed 40% of total profit.

```bash
# 1. Make $500 total profit over 5 days
# 2. On day 6, try to make $250+ profit
# 3. Signals should be BLOCKED or risk REDUCED

# Check worker logs:
# Expected: "CONSISTENCY REJECTED" or "reducing risk to 50%"
```

---

## **📈 STEP 7: MONITORING & ALERTS**

### **7.1 Setup Daily Reset Cron (Optional)**

The worker automatically resets daily, but you can add a backup cron:

```bash
# Add to crontab
crontab -e

# Add this line:
0 0 * * * curl -X POST http://localhost:8000/api/prop-firm/reset
```

### **7.2 Monitor Logs**

```bash
# Watch worker logs
tail -f logs/worker.log | grep -E "MTM|STALENESS|CONSISTENCY"

# Key patterns:
# - "MTM Kill Switch: ENGAGED" → Critical!
# - "STALENESS REJECTED" → Webhook delay detected
# - "CONSISTENCY REJECTED" → Approaching 40% limit
```

### **7.3 Setup Alerts (Recommended)**

Add Discord/Telegram alerts for critical events:

```python
# In worker.py, after kill switch engagement:
if mtm_kill:
    send_discord({
        "title": "🚨 MTM KILL SWITCH ENGAGED",
        "description": mtm_reason,
        "color": "red"
    })
```

---

## **🔍 TROUBLESHOOTING**

### **Issue 1: MTM Guardian Not Working**

**Symptoms:** Floating PnL always 0

**Fixes:**
```bash
# 1. Check market_data.py exists
ls -la src/adapters/market_data.py

# 2. Test get_current_price()
python -c "from src.adapters.market_data import get_current_price; print(get_current_price('EURUSD'))"

# 3. Check yfinance installed
pip install yfinance

# 4. Verify open positions exist
psql $DATABASE_URL -c "SELECT id, symbol, side, entry FROM trading_signals WHERE status IN ('active', 'executed');"
```

### **Issue 2: Staleness Guard False Positives**

**Symptoms:** Fresh signals rejected

**Fixes:**
```bash
# 1. Check server time vs bar_time
python -c "from datetime import datetime, timezone; print(datetime.now(timezone.utc))"

# 2. Increase tolerance (in .env)
STALENESS_MAX_AGE_SECONDS=10  # Increase if webhook latency is high
STALENESS_MAX_PRICE_DEVIATION_PIPS=5.0  # Increase for volatile pairs

# 3. Check TradingView webhook logs
# Look for delivery time in webhook history
```

### **Issue 3: Consistency Analyzer Not Tracking**

**Symptoms:** Always shows 0%

**Fixes:**
```bash
# 1. Check closed trades exist
psql $DATABASE_URL -c "SELECT COUNT(*) FROM trading_signals WHERE status='closed';"

# 2. Verify pnl_usd populated
psql $DATABASE_URL -c "SELECT symbol, pnl_usd, created_at FROM trading_signals WHERE status='closed' ORDER BY created_at DESC LIMIT 5;"

# 3. Check evaluation mode enabled
python -c "from config import get_settings; print(get_settings().evaluation_mode)"
```

---

## **✅ POST-DEPLOYMENT VERIFICATION**

Run this checklist after deployment:

```bash
# 1. Database migration applied
psql $DATABASE_URL -c "\d prop_firm_metrics"

# 2. Worker logs show new guards
tail -50 logs/worker.log | grep -E "MTM|Staleness|Consistency"

# 3. API endpoints working
curl http://localhost:8000/api/prop-firm/metrics | jq '.status'

# 4. Redis kill switch can be set
redis-cli SET trading:kill_switch 1
redis-cli GET trading:kill_switch

# 5. Frontend widget displays
curl http://localhost:3000 | grep "Prop Firm Challenge Tracker"
```

**All checks should PASS.**

---

## **📞 SUPPORT**

If you encounter issues:

1. Check logs: `tail -f logs/worker.log`
2. Run tests: `python scripts/test_prop_firm_guards.py`
3. Verify config: `python -c "from config import get_settings; print(get_settings().mtm_guardian_enabled)"`
4. Open issue: https://github.com/your-repo/issues

---

## **🎓 NEXT STEPS**

After successful deployment:

1. **Monitor for 1 week** on paper trading
2. **Review metrics daily** in PropFirmWidget
3. **Fine-tune thresholds** if needed
4. **Enable on funded account** once confident

---

## **📚 RELATED DOCUMENTATION**

- [MTM Guardian Architecture](./ARCHITECTURE.md#mtm-guardian)
- [Staleness Guard Design](./ARCHITECTURE.md#staleness-guard)
- [Consistency Analyzer Logic](./ARCHITECTURE.md#consistency-analyzer)
- [API Reference](./API.md#prop-firm-endpoints)

---

**Deployment Complete! 🚀**

Your trading system is now protected against the 3 critical prop firm failure modes. Good luck with your challenge!
