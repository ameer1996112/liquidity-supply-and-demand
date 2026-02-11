# ⚡ FXCM Quick Start (5 Minutes)

Get your FXCM-powered backtesting system running **right now**.

---

## Step 1: Install Dependencies (2 minutes)

```bash
cd /path/to/trading
pip install -r requirements_backtest.txt
```

This installs:
- ✅ `fxcmpy` - Official FXCM SDK
- ✅ `numba` - 20-50× speedup
- ✅ `streamlit` - Dashboard UI
- ✅ `pyarrow` - Fast Parquet caching

---

## Step 2: Get FXCM Token (1 minute)

### Option A: Demo Account (FREE) ⭐

1. **Sign up**: https://www.fxcm.com/markets/demo-account/
2. **Get token**: Trading Station → Account → API Access → Generate Token
3. **Copy token** (looks like: `a1b2c3d4e5f6g7h8...`)

### Option B: Use Existing Token

If you already have FXCM account, just generate token from Trading Station.

---

## Step 3: Configure Environment (1 minute)

```bash
# Copy example file
cp .env.fxcm.example .env

# Edit .env file
nano .env  # or use your editor
```

Add your token:
```bash
FXCM_API_TOKEN=your_actual_token_here
FXCM_ENVIRONMENT=demo
```

Save and exit.

---

## Step 4: Test Connection (30 seconds)

```bash
python scripts/test_fxcm_connection.py
```

**Expected output:**
```
✅ fxcmpy installed
✅ Connected to FXCM!
📊 Account Info:
   - Balance: $50,000.00
   - Currency: USD
✅ Fetched 100 candles
✅ Cache working correctly!

🎉 ALL TESTS PASSED!
```

If tests fail, see **Troubleshooting** below.

---

## Step 5: Run Your First Backtest (30 seconds)

### Option A: Streamlit Dashboard (Visual) ⭐

```bash
streamlit run app/app.py
```

Browser opens automatically at `http://localhost:8501`

**What you get:**
- 📈 Interactive TradingView-style chart
- 📊 Performance metrics (Net Profit, Win Rate, Sharpe)
- 📋 Trade table with drill-down
- 🎨 Dark mode (#131722)

---

### Option B: CLI (Fast)

```bash
python -m app.backtest_run \
    --symbol XAUUSD \
    --from 2026-01-01 \
    --to 2026-02-10 \
    --engine fast
```

**Output:**
```
📦 Loading candles from FXCM...
✅ Fetched 10,234 candles
🚀 Running FAST engine (Numba JIT)
✅ Completed in 0.52s (19,680 bars/sec)

Net Profit: $12,450.00
Win Rate: 65.2%
Total Trades: 42
```

---

## Done! 🎉

Your system is now:
- ✅ Connected to FXCM (Israel-optimized)
- ✅ Caching to Parquet (10× faster reload)
- ✅ Using Numba engine (20-50× speedup)
- ✅ Ready for production backtesting

---

## Next Steps

### 1. Run More Symbols

```bash
# EURUSD
python -m app.backtest_run --symbol EURUSD --from 2026-01-01 --to 2026-02-10

# GBPUSD
python -m app.backtest_run --symbol GBPUSD --from 2026-01-01 --to 2026-02-10
```

Supported symbols: XAUUSD, EURUSD, GBPUSD, USDJPY, AUDUSD, USDCAD

---

### 2. Compare Engines

```bash
python scripts/demo_fx_replay.py --mode compare
```

Compares:
- Legacy Python engine (baseline)
- Fast Numba engine (20-50× speedup)

Shows actual speedup on your machine.

---

### 3. Test N+1 Execution

```bash
python scripts/demo_fx_replay.py --mode n_plus_1
```

Fills orders at **next bar open** instead of current bar close (more realistic).

---

### 4. Customize Strategy

Edit `app/snd_strategy.py` to change:
- Entry models (FLIP, BoC, DIR_CLOSE)
- Zone creation logic
- Risk management rules

Then re-run backtest to see impact.

---

## Troubleshooting

### ❌ "fxcmpy not installed"

```bash
pip install fxcmpy
```

---

### ❌ "FXCM_API_TOKEN not set"

```bash
# Check .env file exists
ls -la .env

# Check token is set
cat .env | grep FXCM_API_TOKEN

# If missing, copy example and edit
cp .env.fxcm.example .env
nano .env
```

---

### ❌ "Connection failed"

**Possible causes:**
1. Token expired → Regenerate in Trading Station
2. Wrong environment → Check `FXCM_ENVIRONMENT=demo` (not `live`)
3. Internet issue → Check connection

**Solution:**
```bash
# Regenerate token in Trading Station
# Update .env file
# Run test again
python scripts/test_fxcm_connection.py
```

---

### ❌ "Symbol not found"

**Possible causes:**
- Symbol not supported by FXCM
- Wrong symbol name

**Solution:**
Check supported symbols:
```python
# In Python
from app.data_loader_fxcm import FXCM_SYMBOLS
print(FXCM_SYMBOLS)
```

Or see `app/data_loader_fxcm.py` line 37.

---

### ❌ "No candles returned"

**Possible causes:**
- Date range too large (FXCM limits: 10,000 candles per request)
- Market closed (weekends, holidays)

**Solution:**
```bash
# Reduce date range
python -m app.backtest_run \
    --symbol EURUSD \
    --from 2026-02-01 \
    --to 2026-02-07  # 1 week only
```

---

## Performance Tips

### 1. Use Cache (10× faster)

First run fetches from FXCM → saves to Parquet.
Subsequent runs load from Parquet (instant).

**Cache location:** `data/backtest_candles/XAUUSD/M5/*.parquet`

---

### 2. Use Fast Engine (20-50× faster)

```bash
python -m app.backtest_run --engine fast  # ← Always use this
```

Legacy engine is only for reference.

---

### 3. Reduce Logging (5-10% faster)

```bash
export LOG_LEVEL=ERROR
python -m app.backtest_run --symbol XAUUSD ...
```

---

## Command Cheat Sheet

```bash
# Test FXCM connection
python scripts/test_fxcm_connection.py

# Run backtest (CLI)
python -m app.backtest_run --symbol XAUUSD --from 2026-01-01 --to 2026-02-10 --engine fast

# Launch dashboard
streamlit run app/app.py

# Compare engines
python scripts/demo_fx_replay.py --mode compare

# Test N+1 execution
python scripts/demo_fx_replay.py --mode n_plus_1

# View chart
python -m app.backtest_chart --symbol XAUUSD --from 2026-01-01 --to 2026-02-10
```

---

## File Reference

| File                          | Purpose                              |
|-------------------------------|--------------------------------------|
| `.env`                        | Your FXCM token (create from example)|
| `app/data_loader_fxcm.py`     | FXCM data fetcher                    |
| `app/app.py`                  | Streamlit dashboard                  |
| `scripts/test_fxcm_connection.py` | Connection test                  |
| `FXCM_SETUP.md`               | Detailed FXCM guide                  |

---

## Support

- **FXCM Docs**: https://fxcm.github.io/rest-api-docs/
- **SDK Docs**: https://github.com/fxcm/fxcmpy
- **Israel Support**: support.israel@fxcm.com

---

**You're ready! Happy trading! 📈🚀**
