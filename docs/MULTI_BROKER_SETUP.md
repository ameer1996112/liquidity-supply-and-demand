# Multi-Broker Data Fetching Guide

## 🎯 Overview

Your backtesting system now supports **multiple brokers** with automatic symbol routing:

- **Vantage** → Forex (EURUSD, GBPUSD, USDJPY, etc.)
- **FXCM or IC Markets** → Metals/Indices (XAUUSD, NAS100, US30, etc.)
- **Auto-routing** → System picks the best broker per symbol

---

## 🚨 FXCM REST API Deprecation

FXCM's REST API and `fxcmpy` are **deprecated** and no longer work.

### ❌ **Don't Use:**
- FXCM REST API (deprecated)
- `fxcmpy` Python library (deprecated)
- ForexConnect API (only supports Python 3.5-3.7)

### ✅ **Use Instead:**
**Option 1 (Recommended): FXCM via MetaApi**
- Connect FXCM account to MetaApi platform
- Use same MetaApiDataLoader for all brokers
- Works with Python 3.8+ (your current version)

**Option 2: Alternative Broker for Metals/Indices**
- IC Markets (excellent for gold/indices)
- Pepperstone (also good for metals)
- Continue using Vantage (if they offer good spreads on metals)

---

## 🔧 Setup: Multi-Broker Configuration

### **Step 1: Get MetaApi Credentials**

Go to https://app.metaapi.cloud/ and:

1. **Add Vantage Account** (for Forex) ✅ **You already have this!**
   - Account ID: `c941ad90-40fd-402e-b950-98157fcd3dbb`

2. **Add FXCM Account** (for Metals/Indices) - **Optional**
   - Click "Add Trading Account"
   - Search for "FXCM"
   - Enter your FXCM MT5 credentials
   - Copy the **Account ID** and **Token**

   **OR**

3. **Add IC Markets Account** (Alternative - **Recommended**)
   - Click "Add Trading Account"
   - Select "IC Markets"
   - Enter your IC Markets MT5 credentials
   - Copy the **Account ID** and **Token**

---

### **Step 2: Update `.env` File**

**Current Setup (Vantage only):**
```bash
META_API_TOKEN=eyJhbGciOiJSUzUxMiIsInR5cCI6IkpXVCJ9...  # ✅ Already configured
META_API_ACCOUNT_ID=c941ad90-40fd-402e-b950-98157fcd3dbb  # ✅ Already configured
META_API_REGION=new-york
```

**To add multi-broker (FXCM or IC Markets):**
```bash
# Add these lines to your .env file:
META_API_TOKEN_FXCM=your-fxcm-or-icmarkets-token-here
META_API_ACCOUNT_ID_FXCM=your-fxcm-or-icmarkets-account-id-here
```

---

## 🚀 Usage

### **Option 1: Use Vantage for Everything (Current Setup)**

```python
from src.services.data_loader import MetaApiDataLoader

loader = MetaApiDataLoader.from_env()  # Uses your existing Vantage credentials

# Fetch any symbol via Vantage
df_eurusd = loader.fetch_candles("EURUSD", "2024-01-01", "2024-12-31", "5m")
df_gold = loader.fetch_candles("XAUUSD", "2024-01-01", "2024-12-31", "5m")
df_nas = loader.fetch_candles("NAS100", "2024-01-01", "2024-12-31", "1h")
```

### **Option 2: Multi-Broker with Auto-Routing (After adding FXCM/IC Markets)**

```python
from src.services.multi_broker_data_loader import create_multi_broker_loader

loader = create_multi_broker_loader()  # Auto-loads from .env

# Forex → Vantage
df_eurusd = loader.fetch_candles("EURUSD", "2024-01-01", "2024-12-31", "5m")

# Gold → FXCM/IC Markets (if configured, otherwise Vantage)
df_gold = loader.fetch_candles("XAUUSD", "2024-01-01", "2024-12-31", "5m")

# Index → FXCM/IC Markets (if configured, otherwise Vantage)
df_nas = loader.fetch_candles("NAS100", "2024-01-01", "2024-12-31", "1h")
```

---

## 📊 Symbol Routing Rules

| Symbol | Type | Default Broker | When Multi-Broker Enabled |
|--------|------|----------------|--------------------------|
| EURUSD | Forex | Vantage | Vantage |
| GBPUSD | Forex | Vantage | Vantage |
| USDJPY | Forex | Vantage | Vantage |
| XAUUSD | Metal | Vantage | FXCM/IC Markets |
| XAGUSD | Metal | Vantage | FXCM/IC Markets |
| NAS100 | Index | Vantage | FXCM/IC Markets |
| US30 | Index | Vantage | FXCM/IC Markets |
| BTCUSD | Crypto | Vantage | Vantage |

---

## 🎯 Recommendation for Your Use Case

Based on your requirements:
- **Forex (EURUSD, etc.)** → Use Vantage ✅ **Already configured!**
- **Metals/Indices (XAUUSD, NAS100)** → **3 options:**

### **Option A: Continue with Vantage (Easiest - No Changes Needed)**
- ✅ Already working
- ✅ No additional setup
- ✅ Single broker = simpler
- ⚠️ Spreads may be higher on gold/indices vs specialized brokers

### **Option B: Add IC Markets for Metals/Indices (Recommended)**
- ✅ Better spreads on XAUUSD (~$0.20 vs $0.50 typical)
- ✅ Better spreads on NAS100
- ✅ IC Markets is well-supported on MetaApi
- ⚠️ Requires adding another broker account

### **Option C: Try to add FXCM via MetaApi**
- ⚠️ FXCM may not be available on MetaApi (check their broker list)
- ⚠️ If unavailable, use Option A or B

**My recommendation:** Start with **Option A** (Vantage only) to test the backtest system, then add IC Markets later if you want better spreads on metals/indices.

---

## ✅ Quick Start (Your Current Setup)

You're already configured! Just run:

```bash
# Test with Vantage (already working)
python scripts/test_backtest.py --quick

# Test with real Vantage data
python scripts/test_backtest.py --all

# Backtest Gold on Vantage
python scripts/run_backtest_example.py --symbol XAUUSD --days 30

# Backtest Index on Vantage
python scripts/run_backtest_example.py --symbol NAS100 --days 30 --timeframe 1h
```

---

## 📞 Need Help?

- **MetaApi Supported Brokers:** https://metaapi.cloud/docs/client/brokers
- **Add Account Guide:** https://metaapi.cloud/docs/client/getting-started
- **Full Documentation:** [docs/BACKTEST_METAAPI_GUIDE.md](BACKTEST_METAAPI_GUIDE.md)

**Bottom line:** You're ready to go with Vantage! Multi-broker is optional for optimization.
