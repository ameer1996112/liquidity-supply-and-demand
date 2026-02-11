# 🚀 Quick Start Guide - FX Replay System

Get your professional backtesting dashboard running in **5 minutes**.

---

## Step 1: Install Dependencies

```bash
cd /path/to/trading
pip install -r requirements_backtest.txt
```

**Expected output:**
```
Successfully installed streamlit-1.30.0 numba-0.58.1 streamlit-lightweight-charts-0.5.0...
```

---

## Step 2: Set Environment Variables (Optional)

Create `.env` file in project root:

```bash
# For Israel/Middle East - FXCM is recommended
FXCM_API_TOKEN=your_fxcm_demo_token

# Fallback: MetaApi
META_API_TOKEN=your_metaapi_token
META_API_ACCOUNT_ID=your_metaapi_account_id

# Logging
LOG_LEVEL=INFO
```

> **Note:** If you skip this, the system will use cached Parquet files in `data/backtest_candles/`

---

## Step 3: Choose Your Interface

### Option A: Streamlit Dashboard (Recommended) ⭐

```bash
streamlit run app/app.py
```

**What you get:**
- TradingView dark theme (#131722)
- Interactive candlestick charts
- Entry/exit markers (FLIP, BoC, DIR_CLOSE models)
- Real-time performance metrics
- Trade table with drill-down

**Browser opens automatically at `http://localhost:8501`**

---

### Option B: CLI (For Scripts/Automation)

```bash
python -m app.backtest_run \
    --symbol XAUUSD \
    --from 2026-01-01 \
    --to 2026-02-10 \
    --timeframe M5 \
    --engine fast
```

**Output:**
```
✅ Loaded 10,234 candles
🚀 Running FAST engine (Numba JIT)
✅ Fast engine completed in 0.52s (19,680 bars/sec)

═══════════════════════════════════════
BACKTEST SUMMARY
═══════════════════════════════════════
Net Profit:        $12,450.00
ROI:               24.9%
Win Rate:          65.2%
Total Trades:      42
Max Drawdown:      8.3%
Profit Factor:     2.15
Sharpe Ratio:      1.82
═══════════════════════════════════════
```

Files saved to:
- `data/backtest/XAUUSD/trades.csv`
- `data/backtest/XAUUSD/equity.csv`

---

### Option C: Demo Script (Compare Engines)

```bash
python scripts/demo_fx_replay.py --mode compare
```

**What it does:**
- Runs **legacy** Python engine (baseline)
- Runs **fast** Numba engine
- Compares runtime and results
- Shows speedup factor (typically 20-50×)

---

## Step 4: Verify Results

### Chart Visualization

```bash
python -m app.backtest_chart \
    --symbol XAUUSD \
    --from 2026-01-01 \
    --to 2026-02-10
```

Opens `data/backtest/XAUUSD/chart.html` in browser with:
- Candlestick chart (TradingView style)
- Entry arrows (green ↑ for longs, red ↓ for shorts)
- Exit markers (circles with SL/TP/TIME labels)
- SL/TP price lines (dashed)

---

## Advanced Usage

### A/B Test: Fill at Close vs Next Open

```bash
# TradingView mode (fill at bar N close)
python scripts/demo_fx_replay.py --mode fast

# Strict N+1 mode (fill at bar N+1 open)
python scripts/demo_fx_replay.py --mode n_plus_1
```

**Expected difference:**
- N+1 mode typically has slightly worse fills (more realistic)
- Compare net profit to see impact of execution delay

---

### Run Backtest on Custom Date Range

```python
from datetime import datetime, timezone
from app.config import BacktestConfig
from app.data_loader import get_candles_auto
from app.engine_core import FastBacktestEngine
from app.outputs import compute_summary

# Load data
candles = get_candles_auto(
    symbol="EURUSD",
    from_date=datetime(2025, 6, 1, tzinfo=timezone.utc),
    to_date=datetime(2025, 12, 31, tzinfo=timezone.utc),
    timeframe="M15"
)

# Config
config = BacktestConfig(
    symbol="EURUSD",
    timeframe="M15",
    tick_size=0.00001,
    pip_size=0.0001,
    risk_per_trade_pct=0.5,
    account_size_usd=100_000
)

# Run fast backtest
engine = FastBacktestEngine(config=config)
trades = engine.run(candles)

# Summary
summary = compute_summary(trades, engine.equity_curve)
print(f"Net Profit: ${summary['net_profit']:,.2f}")
print(f"Win Rate: {summary['win_rate']:.1f}%")
```

---

## Troubleshooting

### Issue: ImportError: No module named 'numba'

**Solution:**
```bash
pip install numba>=0.58.0
```

If still fails:
```bash
pip install coverage>=7.6.1  # Required for Numba compatibility
```

---

### Issue: Streamlit chart not rendering

**Solution:**
```bash
pip install --upgrade streamlit-lightweight-charts
streamlit cache clear
```

---

### Issue: "No candles fetched from FXCM"

**Possible causes:**
1. Symbol not supported by FXCM
2. API token invalid
3. Date range too large

**Solution:**
- Check `FXCM_SYMBOLS` mapping in `app/data_loader.py`
- Set fallback: `export META_API_TOKEN=your_token`
- Use cached data if available

---

### Issue: "Numba compilation failed"

**Solution:**
Use legacy engine (slower but works):
```bash
python -m app.backtest_run --engine legacy
```

Or fix Numba:
```bash
pip uninstall numba
pip install numba==0.58.1  # Known working version
```

---

## Performance Tips

### Speed Up Backtests

1. **Use Parquet cache** (auto-saved on first run)
   - 10× faster load than fetching from API
   - Files stored in `data/backtest_candles/`

2. **Use Fast engine**
   - 20-50× faster than legacy
   - Enable with `--engine fast`

3. **Reduce date range** for testing
   - Start with 1-2 months
   - Expand once strategy is validated

4. **Disable logging** for max speed
   ```bash
   export LOG_LEVEL=ERROR
   ```

---

## Next Steps

1. **Customize Strategy**
   - Edit `app/snd_strategy.py` for custom entry/exit logic
   - Adjust `BacktestConfig` parameters

2. **Parameter Optimization**
   - See `scripts/backtest_optimization.py`
   - Grid search over risk%, TP ratio, filters

3. **Walk-Forward Analysis**
   - Split data: train (60%), validate (20%), test (20%)
   - Avoid overfitting

4. **Export Results**
   - `trades.csv` → import to Excel/Google Sheets
   - `chart.html` → share with team
   - Streamlit → deploy to cloud for remote access

---

## Key Files

| File                    | Purpose                                      |
|-------------------------|----------------------------------------------|
| `app/app.py`            | Streamlit dashboard (main UI)                |
| `app/engine_core.py`    | Fast Numba engine (20-50× speedup)           |
| `app/engine_enhanced.py`| N+1 parity support                           |
| `app/data_loader.py`    | Multi-source data loader (Parquet → FXCM)    |
| `app/snd_strategy.py`   | Supply/Demand strategy logic                 |
| `scripts/demo_fx_replay.py` | Demo script (compare engines)            |

---

## Example Workflow

```bash
# 1. Run backtest (first time - fetches from FXCM)
python -m app.backtest_run --symbol XAUUSD --from 2026-01-01 --to 2026-02-10 --engine fast

# 2. View chart
python -m app.backtest_chart --symbol XAUUSD --from 2026-01-01 --to 2026-02-10

# 3. Launch dashboard for interactive analysis
streamlit run app/app.py

# 4. (Optional) Compare with N+1 execution
python scripts/demo_fx_replay.py --mode n_plus_1
```

---

## Support

- **GitHub Issues**: [Report bugs](https://github.com/your-repo/issues)
- **Documentation**: `BACKTEST_README.md`
- **Memory**: `~/.claude/projects/.../memory/MEMORY.md` (bug fixes, known issues)

---

**Happy Backtesting! 🚀📈**
