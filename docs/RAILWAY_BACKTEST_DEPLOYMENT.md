# 🚂 Railway Deployment - Backtest UI Integration

## ✅ **What's Already Done**

Your system is **production-ready** for Railway! Here's what's configured:

1. ✅ **Backend API updated** - Bot integration router added to [src/api.py](../src/api.py)
2. ✅ **Frontend API client created** - [src/lib/api.ts](../frontend/src/lib/api.ts) handles Railway URLs
3. ✅ **Backtest page updated** - Uses Railway API instead of localhost
4. ✅ **CORS configured** - Already allows Railway frontend URL

---

## 🚀 **Deployment Steps**

### **1. Set Railway Environment Variables**

In your Railway **backend** project, add these environment variables:

```bash
# MetaApi (for backtest data fetching)
META_API_TOKEN=your-metaapi-token-here
META_API_ACCOUNT_ID=your-metaapi-account-id-here
META_API_REGION=new-york

# Existing env vars (already configured)
# SUPABASE_URL=...
# SUPABASE_KEY=...
# REDIS_URL=...
# etc.
```

**How to add:**
1. Go to Railway dashboard
2. Select your **backend** project
3. Go to **Variables** tab
4. Add the above variables
5. Click **Deploy**

---

### **2. Set Frontend Environment Variable**

In your Railway **frontend** project:

```bash
# Backend API URL (your Railway backend URL)
NEXT_PUBLIC_API_URL=https://your-backend-production.up.railway.app
```

**How to get your backend URL:**
1. Go to Railway dashboard
2. Select your **backend** project
3. Go to **Settings** → **Domains**
4. Copy the **public domain** (e.g., `https://trading-backend-production-abc123.up.railway.app`)
5. Add it to frontend Variables tab as `NEXT_PUBLIC_API_URL`

**Example:**
```
NEXT_PUBLIC_API_URL=https://trading-backend-production-abc123.up.railway.app
```

---

### **3. Deploy to Railway**

#### **Backend Deployment**

Railway will automatically detect changes and deploy when you push to git:

```bash
# From your project root
git add .
git commit -m "Add backtest UI and bot integration"
git push origin main
```

Railway will:
1. Detect the changes
2. Build the backend
3. Deploy the new API endpoints

**Verify backend is deployed:**
```bash
curl https://your-backend.up.railway.app/api/backtest/health

# Expected response:
# {"status":"ok","service":"backtest-api"}
```

#### **Frontend Deployment**

Railway will also auto-deploy the frontend:

```bash
# Same git push triggers frontend deploy
git push origin main
```

**Verify frontend is deployed:**
- Open: `https://your-frontend.up.railway.app/backtest`
- You should see the Backtest Lab page

---

## 🧪 **Testing on Railway**

### **Test 1: Backtest UI**

1. Go to: `https://your-frontend.up.railway.app/backtest`
2. Configure:
   - Symbol: `EURUSD`
   - Date: `2024-01-01` to `2024-01-31`
   - Timeframe: `5m`
   - Reject Compression: ✅
3. Click **"Run Backtest"**
4. Wait ~10-30 seconds
5. Results should appear with:
   - Stats cards
   - TradingView chart
   - FX Replay controls

### **Test 2: Bot Strategy Validation**

Test the new `/api/bot/validate-strategy` endpoint:

```bash
curl -X POST https://your-backend.up.railway.app/api/bot/validate-strategy \
  -H "Content-Type: application/json" \
  -d '{
    "symbol": "EURUSD",
    "days_to_test": 90,
    "timeframe": "5m",
    "risk_percent": 0.5,
    "min_rr_ratio": 2.0,
    "reject_compression_arrival": true,
    "min_trades": 10,
    "min_win_rate": 50.0,
    "min_profit_factor": 1.2,
    "max_drawdown": 20.0
  }'
```

**Expected response:**
```json
{
  "symbol": "EURUSD",
  "timeframe": "5m",
  "total_trades": 15,
  "win_rate": 60.0,
  "total_return": 8.5,
  "is_valid": true,
  "recommendation": "✅ Deploy - Excellent backtest results"
}
```

---

## 🔧 **Troubleshooting**

### **Issue: 404 Not Found on /api/backtest/run**

**Solution:**
1. Verify backend deployed successfully in Railway dashboard
2. Check Railway logs for errors:
   - Go to Railway backend project
   - Click **View Logs**
   - Look for import errors or missing dependencies
3. Ensure `backtesting` library is in `requirements.txt`:
   ```
   backtesting>=0.3.3
   ```
4. Redeploy if needed

### **Issue: CORS Error in Browser Console**

**Solution:**
1. Check `src/api.py` line 29 has your frontend URL:
   ```python
   origins = [
       "https://your-frontend-production.up.railway.app",  # ← UPDATE THIS
       "http://localhost:3000",
   ]
   ```
2. Add your frontend URL to Railway backend environment variables:
   ```bash
   FRONTEND_URL=https://your-frontend-production.up.railway.app
   ```
3. Redeploy backend

### **Issue: Backtest API Returns "MetaApi credentials not configured"**

**Solution:**
1. Add MetaApi env vars to Railway backend:
   ```bash
   META_API_TOKEN=your-token
   META_API_ACCOUNT_ID=your-account-id
   ```
2. Restart backend deployment

### **Issue: Frontend shows "localhost:8000" instead of Railway URL**

**Solution:**
1. Add to Railway frontend Variables:
   ```bash
   NEXT_PUBLIC_API_URL=https://your-backend.up.railway.app
   ```
2. Redeploy frontend
3. Clear browser cache (Ctrl+Shift+R)

---

## 📋 **Deployment Checklist**

Before going live, verify:

- ✅ Backend has `META_API_TOKEN` and `META_API_ACCOUNT_ID` env vars
- ✅ Frontend has `NEXT_PUBLIC_API_URL` pointing to Railway backend
- ✅ CORS allows your Railway frontend URL
- ✅ `/api/backtest/health` returns 200 OK
- ✅ `/backtest` page loads without errors
- ✅ Test backtest runs successfully
- ✅ FX Replay controls work

---

## 🎯 **Usage on Railway**

### **Run Backtest from Frontend**

1. Open: `https://your-frontend.up.railway.app/backtest`
2. Configure parameters
3. Click "Run Backtest"
4. Use FX Replay to review trades

### **Validate Strategy Before Deploy**

Before changing your live bot parameters:

```bash
# Test new parameters via API
curl -X POST https://your-backend.up.railway.app/api/bot/validate-strategy \
  -H "Content-Type: application/json" \
  -d '{
    "symbol": "XAUUSD",
    "days_to_test": 90,
    "risk_percent": 0.7,
    "min_rr_ratio": 2.5,
    "require_liquidity_sweep": true,
    "min_trades": 10,
    "min_win_rate": 55.0
  }'
```

If `is_valid: true` → Update your bot settings and deploy

---

## 🔄 **Integration Workflow**

```
┌──────────────────────────────────────────────────────────────┐
│  1. Test Strategy in Backtest Lab (Railway Frontend)        │
│     https://your-frontend.up.railway.app/backtest           │
│                                                               │
│  2. Validate Performance (API)                               │
│     POST /api/bot/validate-strategy                          │
│                                                               │
│  3. If Valid → Update Bot Settings (Railway Backend)        │
│     Update env vars: RISK_PERCENT, MIN_RR_RATIO, etc.       │
│                                                               │
│  4. Restart Bot Worker (Railway)                            │
│     Worker will pick up new settings automatically          │
│                                                               │
│  5. Monitor Live Performance (Frontend Dashboard)           │
│     https://your-frontend.up.railway.app/analytics          │
└──────────────────────────────────────────────────────────────┘
```

---

## 📞 **Support**

- **Railway Dashboard:** https://railway.app/dashboard
- **Backend Logs:** Railway → Your Backend Project → View Logs
- **Frontend Logs:** Railway → Your Frontend Project → View Logs
- **API Docs:** `https://your-backend.up.railway.app/docs`

---

## 🎉 **You're Done!**

Your backtest UI is now **deployed on Railway** and integrated with your live trading bot!

**Next steps:**
1. Test a backtest on Railway
2. Use FX Replay to review trades
3. Validate your current strategy
4. Share the `/backtest` URL with your team

Happy trading! 🚀
