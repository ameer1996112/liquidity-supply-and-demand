# FXCM REST API Setup Guide

Complete guide to set up FXCM as your primary data source for backtesting.

---

## 🌍 Why FXCM for Israel?

- **Low latency**: Servers optimized for Middle East region
- **Free demo access**: No subscription needed for historical data
- **Reliable data**: Tier-1 broker with accurate tick data
- **Simple API**: REST-based (no complex libraries)

---

## Step 1: Get FXCM API Credentials

### Option A: Demo Account (Free)

1. **Sign up for FXCM Demo Account**
   - Go to: https://www.fxcm.com/markets/demo-account/
   - Fill in your details (Israel supported)
   - Receive demo account credentials via email

2. **Generate API Token**
   - Log in to FXCM Trading Station (demo)
   - Navigate to: **Account → API Access**
   - Click **Generate Token**
   - Copy your token (looks like: `a1b2c3d4e5f6g7h8i9j0...`)

3. **Save Token to Environment**
   ```bash
   # Add to .env file
   FXCM_API_TOKEN=your_fxcm_demo_token_here
   FXCM_ENVIRONMENT=demo  # or 'live' for real account
   ```

---

### Option B: Live Account (Real Trading)

1. **Open FXCM Live Account**
   - Go to: https://www.fxcm.com/uk/
   - Complete KYC verification
   - Fund account (minimum varies by region)

2. **Get Live API Token**
   - Log in to FXCM Trading Station
   - Navigate to: **Account → API Access**
   - Generate **Live API Token**
   - **⚠️ Keep this secret!** (never commit to Git)

3. **Save Token to Environment**
   ```bash
   # Add to .env file
   FXCM_API_TOKEN=your_fxcm_live_token_here
   FXCM_ENVIRONMENT=live
   ```

---

## Step 2: Install FXCM Dependencies

```bash
pip install fxcmpy  # Official FXCM Python SDK
pip install requests  # Already installed
```

---

## Step 3: Test FXCM Connection

Run the test script:

```bash
python scripts/test_fxcm_connection.py
```

**Expected output:**
```
✅ FXCM connection successful!
📊 Account Info:
   - Account ID: 12345678
   - Balance: $50,000.00
   - Currency: USD

📈 Testing data fetch (EURUSD, last 100 candles)...
✅ Fetched 100 candles
   - First candle: 2026-02-10 00:00:00 UTC
   - Last candle: 2026-02-10 08:20:00 UTC
   - Sample: Open=1.0350, High=1.0355, Low=1.0348, Close=1.0352
```

---

## Step 4: Configure Your Backtest

Add FXCM settings to your `.env`:

```bash
# FXCM Configuration
FXCM_API_TOKEN=your_token_here
FXCM_ENVIRONMENT=demo  # or 'live'

# Optional: Override default symbols
FXCM_SYMBOL_XAUUSD=XAUUSD
FXCM_SYMBOL_EURUSD=EUR/USD
FXCM_SYMBOL_GBPUSD=GBP/USD

# Fallback to MetaApi if FXCM fails
META_API_TOKEN=your_metaapi_token
META_API_ACCOUNT_ID=your_metaapi_account
```

---

## Step 5: Run Backtest with FXCM

```bash
# Streamlit dashboard (auto-detects FXCM)
streamlit run app/app.py

# Or CLI
python -m app.backtest_run \
    --symbol XAUUSD \
    --from 2026-01-01 \
    --to 2026-02-10 \
    --engine fast
```

**Data fetching priority:**
1. ✅ Local Parquet cache (instant)
2. ✅ **FXCM API** (your primary source)
3. ✅ MetaApi (fallback if FXCM fails)

---

## Supported FXCM Symbols

| Symbol  | FXCM Code | Timeframes        |
|---------|-----------|-------------------|
| XAUUSD  | XAU/USD   | m1, m5, m15, H1, H4, D1 |
| EURUSD  | EUR/USD   | m1, m5, m15, H1, H4, D1 |
| GBPUSD  | GBP/USD   | m1, m5, m15, H1, H4, D1 |
| USDJPY  | USD/JPY   | m1, m5, m15, H1, H4, D1 |
| AUDUSD  | AUD/USD   | m1, m5, m15, H1, H4, D1 |
| USDCAD  | USD/CAD   | m1, m5, m15, H1, H4, D1 |

---

## Troubleshooting

### Issue: "FXCM connection failed"

**Possible causes:**
1. Invalid token
2. Token expired
3. Wrong environment (demo vs live)

**Solution:**
```bash
# Regenerate token in Trading Station
# Update .env file
FXCM_API_TOKEN=new_token_here

# Test connection
python scripts/test_fxcm_connection.py
```

---

### Issue: "Symbol not found"

**Possible causes:**
- FXCM uses different symbol names (EUR/USD vs EURUSD)

**Solution:**
Check symbol mapping in `app/data_loader_fxcm.py`:
```python
FXCM_SYMBOLS = {
    "XAUUSD": "XAU/USD",
    "EURUSD": "EUR/USD",
    # Add your custom mapping
}
```

---

### Issue: "Rate limit exceeded"

**Possible causes:**
- Too many API requests in short time
- FXCM demo has lower limits than live

**Solution:**
```bash
# Use Parquet cache (auto-saved after first fetch)
# Subsequent runs will be instant (no API calls)

# Or add delay between requests in data_loader_fxcm.py
import time
time.sleep(1)  # 1 second delay
```

---

## FXCM API Limits

| Account Type | Max Requests/Min | Max Candles/Request |
|--------------|------------------|---------------------|
| Demo         | 50               | 10,000              |
| Live         | 100              | 10,000              |

**Recommendation:** Always cache data to Parquet to avoid hitting limits.

---

## Advanced Configuration

### Custom Symbol Mapping

Edit `app/data_loader_fxcm.py`:

```python
FXCM_SYMBOLS = {
    "XAUUSD": "XAU/USD",
    "XAGUSD": "XAG/USD",  # Silver
    "BTCUSD": "BTC/USD",  # Bitcoin (if supported)
    # Add custom pairs
}
```

### Custom Timeframe Mapping

```python
FXCM_TIMEFRAMES = {
    "M1": "m1",
    "M5": "m5",
    "M15": "m15",
    "M30": "m30",
    "H1": "H1",
    "H4": "H4",
    "D1": "D1",
    # FXCM supports: m1, m5, m15, m30, H1, H2, H3, H4, H6, H8, D1, W1, M1
}
```

---

## Security Best Practices

1. **Never commit `.env` to Git**
   ```bash
   # Add to .gitignore
   echo ".env" >> .gitignore
   ```

2. **Use separate tokens for demo/live**
   ```bash
   FXCM_API_TOKEN_DEMO=demo_token
   FXCM_API_TOKEN_LIVE=live_token  # Keep secret!
   ```

3. **Rotate tokens regularly**
   - Regenerate every 90 days
   - Immediately if compromised

4. **Use environment-specific tokens**
   ```bash
   # Development
   FXCM_API_TOKEN=$FXCM_API_TOKEN_DEMO

   # Production
   FXCM_API_TOKEN=$FXCM_API_TOKEN_LIVE
   ```

---

## Next Steps

1. ✅ Get FXCM demo account
2. ✅ Generate API token
3. ✅ Run test script (`scripts/test_fxcm_connection.py`)
4. ✅ Run first backtest
5. ✅ Verify Parquet cache created (`data/backtest_candles/`)

---

## Support

- **FXCM API Docs**: https://fxcm.github.io/rest-api-docs/
- **FXCM Python SDK**: https://github.com/fxcm/fxcmpy
- **Israel Support**: support.israel@fxcm.com

---

**Your data pipeline is now ready! 🚀**
