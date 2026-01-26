# TradingView Backtest Import Guide

## 🎯 Three Ways to Get Data for Optimization

### Option 1: TradingView Backtest Export (Recommended for Historical Data)
### Option 2: Generate Sample Data (Quick Testing)
### Option 3: Manual CSV Upload

---

## 📊 Option 1: Import TradingView Backtest

### Step 1: Export from TradingView

1. **Open your strategy** in TradingView
2. **Run a backtest**:
   - Click "Strategy Tester" at the bottom
   - Set your date range (e.g., Jan 1, 2023 - Jan 21, 2026)
   - Wait for backtest to complete

3. **Export the trades list**:
   - Go to **"List of Trades"** tab
   - Click the **Download** icon (📥)
   - Save as CSV (e.g., `eurusd_backtest.csv`)

### Step 2: Prepare Your Export

TradingView exports typically look like this:

```csv
Trade #,Signal,Date/Time,Price,Contracts,P&L,Cum. Profit,Run-up,Drawdown
1,Entry Long,2023-01-02 09:00,1.0850,1,,,0.00%,0.00%
2,Exit Long,2023-01-02 15:30,1.0920,1,0.65%,0.65%,0.70%,-0.05%
3,Entry Short,2023-01-03 10:15,1.0915,1,,,0.00%,0.00%
4,Exit Short,2023-01-03 18:45,1.0880,1,0.32%,0.97%,0.35%,-0.02%
...
```

### Step 3: Import to Supabase

Run the import script:

```bash
python import_tradingview_backtest.py eurusd_backtest.csv
```

**What it does:**
- Parses TradingView CSV format
- Groups entry/exit pairs into complete trades
- Calculates P&L if not provided
- Adds placeholder indicator values (⚠️ see note below)
- Uploads to your Supabase `trading_signals` table

### ⚠️ IMPORTANT: About Indicator Values

The import script adds **random indicator values** for demonstration. This means:
- ✅ The optimizer will run
- ✅ You'll see how it works
- ❌ The filters won't be accurate (because indicators are random)

**For production use**, you need to:
1. Calculate actual RSI, ADX, zone freshness, etc. **at entry time**
2. Store these in your TradingView strategy
3. Export them along with trade data

**How to do this in TradingView Pine Script:**

```pinescript
strategy("My Strategy with Indicators", overlay=true)

// Calculate indicators
rsi_value = ta.rsi(close, 14)
adx_value = ta.adx(14)
// ... your other indicators

// On trade entry, log indicators (for later export)
if (buy_condition)
    strategy.entry("Long", strategy.long)
    // Note: TradingView doesn't export custom data, so you'll need to
    // manually record indicator values or use alerts

// Alternative: Use TradingView alerts to send data to your webhook
if (buy_condition)
    alert_message = '{"rsi":' + str.tostring(rsi_value) + ',"adx":' + str.tostring(adx_value) + '}'
    alert(alert_message, alert.freq_once_per_bar)
```

---

## 🎲 Option 2: Generate Sample Data (For Testing)

To test the optimizer **right now** without real data:

```bash
# Generate 200 sample trades with 55% win rate
python generate_sample_data.py --trades 200 --win-rate 0.55

# Generate and upload directly to Supabase
python generate_sample_data.py --trades 500 --upload

# Custom CSV filename
python generate_sample_data.py --trades 300 --csv my_sample.csv
```

**What you get:**
- Realistic trade data with correlated indicators
- Winners have: Lower RSI, Higher ADX, Fresh zones, High quality
- Losers have: Higher RSI, Lower ADX, Old zones, Low quality
- This simulates realistic market behavior

**Sample output:**
```
Total Trades:      200
Winning Trades:    110 (55.0%)
Losing Trades:     90 (45.0%)
Total P&L:         +145.30%
Avg P&L/Trade:     +0.73%

Avg RSI (Wins):    45.2
Avg RSI (Losses):  59.8
Avg ADX (Wins):    37.5
Avg ADX (Losses):  20.3
```

---

## 📝 Option 3: Manual CSV Import

If you have your own CSV format:

### 1. Create a CSV with these columns:

```csv
symbol,side,entry,sl,tp,close_price,pnl,exit_type,rsi,adx,freshness,base_quality,liq_swept,created_at,close_time
EURUSD,BUY,1.0850,1.0800,1.0950,1.0920,2.10,Win,42.5,35.2,7,0.75,true,2023-01-02T09:00:00,2023-01-02T15:30:00
EURUSD,SELL,1.0915,1.0965,1.0865,1.0880,1.80,Win,38.1,40.5,8,0.82,true,2023-01-03T10:15:00,2023-01-03T18:45:00
EURUSD,BUY,1.0880,1.0830,1.0980,1.0840,-1.50,Loss,65.3,18.7,3,0.35,false,2023-01-04T11:00:00,2023-01-04T16:20:00
```

### 2. Import using pandas:

```python
import pandas as pd
from supabase import create_client
import os
from dotenv import load_dotenv

load_dotenv('tests/.env')

# Read CSV
df = pd.read_csv('your_trades.csv')

# Upload to Supabase
supabase = create_client(os.getenv('SUPABASE_URL'), os.getenv('SUPABASE_ANON_KEY'))
records = df.to_dict('records')

# Upload in batches of 100
for i in range(0, len(records), 100):
    batch = records[i:i+100]
    supabase.table('trading_signals').insert(batch).execute()
    print(f"Uploaded batch {i//100 + 1}")

print(f"✅ Uploaded {len(records)} trades!")
```

---

## 🚀 After Import: Run the Optimizer

Once you have data in Supabase:

```bash
python optimize_filters.py
```

The optimizer will:
1. Load your historical trades
2. Test thousands of filter combinations
3. Find the "Golden Combination" that maximizes profit
4. Show you before/after metrics
5. Generate ready-to-use filter code

**Example output:**
```
📈 BASELINE PERFORMANCE (No Filters Applied)
Total Trades:      200
Win Rate:          55.00%
Total PnL:         +145.30%

🏆 OPTIMIZATION COMPLETE - GOLDEN COMBINATION FOUND!

🎯 ACTIVE FILTERS (Best Parameters):
  RSI:
    ✅ use_rsi_filter = True (Filter ENABLED)
       max_rsi = 55

  ADX:
    ✅ use_adx_filter = True (Filter ENABLED)
       min_adx = 25

  Zone Freshness:
    ✅ use_freshness_filter = True (Filter ENABLED)
       min_freshness = 6

📊 PERFORMANCE COMPARISON:
Win Rate:     55.00% → 68.50% (+13.50%)
Total PnL:    145.30% → 189.75% (+44.45%)
Trade Count:  200 → 125 (62.5% of all trades)
```

---

## 💡 Best Practices

### 1. **Minimum Data Requirements**
- At least **200 trades** for meaningful optimization
- Ideally **500-1000 trades** for robust results
- More data = better statistical significance

### 2. **Out-of-Sample Testing**
After optimization:
1. Split your data: 70% training, 30% testing
2. Optimize on training data only
3. Test filters on the 30% holdout set
4. If results are similar, filters are robust

### 3. **Time-Based Splits**
Even better than random splits:
- Train on 2023-2024 data
- Test on 2025-2026 data
- Ensures filters work on new market conditions

### 4. **Indicator Quality Matters**
Remember:
- ❌ Random indicators → Random results
- ✅ Real indicators → Meaningful optimization
- Calculate RSI, ADX, etc. at actual entry time

### 5. **Re-optimize Periodically**
- Markets change over time
- Re-run optimization every 3-6 months
- Compare new filters to old ones

---

## 🔧 Troubleshooting

### "No data found in trading_signals table"
- Check Supabase connection
- Verify table name is `trading_signals`
- Run import script first

### "Total valid records with PnL data: 0"
- Your `pnl` column has NULL values
- Check CSV export includes P&L data
- Verify column mapping in import script

### "Column mapping issues"
- TradingView formats vary by strategy
- Check the column names in your CSV
- Modify `import_tradingview_backtest.py` if needed

### "Import fails with Supabase error"
- Check your table schema matches expected columns
- Verify SUPABASE_URL and SUPABASE_ANON_KEY are correct
- Check if you have write permissions

---

## 📚 Quick Reference

```bash
# Generate 200 sample trades for testing
python generate_sample_data.py --trades 200 --upload

# Import TradingView backtest
python import_tradingview_backtest.py eurusd_backtest.csv

# Run optimization
python optimize_filters.py

# View results
cat optimization_results.txt
cat optimized_filters.json
```

---

## 🎯 Next Steps

1. ✅ Get historical trade data (TradingView or sample)
2. ✅ Import to Supabase
3. ✅ Run optimizer
4. ✅ Review results
5. ✅ Apply filters to live trading
6. ✅ Monitor performance
7. ✅ Re-optimize periodically

Happy optimizing! 🚀
