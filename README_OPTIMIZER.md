# 🎯 Trading Filter Optimizer

**Automatically discover the optimal combination of trading signal filters to maximize your profits.**

Stop guessing whether "RSI < 30" is better than "RSI < 35". Let machine learning find the answer.

## 🌟 What This Does

This Python toolkit uses **Optuna** (a state-of-the-art hyperparameter optimization library) to:

1. ✅ Load your historical trading data from Supabase
2. ✅ Test thousands of filter combinations automatically
3. ✅ Find the "Golden Combination" that maximizes Net Profit
4. ✅ Show you the exact performance improvement (Win Rate, PnL, etc.)

### Example Result

```
Original Performance:  45% Win Rate, -12% Total PnL
Optimized Performance: 68% Win Rate, +87% Total PnL

Golden Combination:
  ✓ min_freshness = 6
  ✓ max_rsi = 62
  ✓ min_adx = 28
  ✓ min_zone_quality = 0.72
  ✓ require_liquidity_sweep = True
```

---

## 🚀 Quick Start (3 Steps)

### Step 1: Run Setup Script

```bash
./setup_optimizer.sh
```

This will:
- Install all dependencies (pandas, optuna, supabase, etc.)
- Guide you through creating your `.env` file
- Validate your Supabase connection
- Check your data structure

### Step 2: Validate Setup

```bash
python3 test_optimizer_setup.py
```

This verifies:
- ✓ Environment variables are set
- ✓ Supabase connection works
- ✓ `trading_signals` table has data
- ✓ `ai_features` column has correct structure

### Step 3: Run Optimizer

```bash
python3 optimize_filters.py
```

This will:
- Load your trading data
- Run 200 optimization trials (~2-5 minutes)
- Display the best filter combination
- Save results to `optimized_filters.json`

---

## 📦 Files Included

| File | Purpose |
|------|---------|
| **[optimize_filters.py](optimize_filters.py)** | Main optimization script |
| **[test_optimizer_setup.py](test_optimizer_setup.py)** | Validation script to test setup |
| **[setup_optimizer.sh](setup_optimizer.sh)** | Automated setup script |
| **[requirements_optimizer.txt](requirements_optimizer.txt)** | Python dependencies |
| **[OPTIMIZER_GUIDE.md](OPTIMIZER_GUIDE.md)** | Detailed usage guide and customization |
| **[.env.example](.env.example)** | Template for environment variables |

---

## ⚙️ Manual Setup (Alternative)

If you prefer manual setup instead of using the setup script:

### 1. Install Dependencies

```bash
pip3 install -r requirements_optimizer.txt
```

### 2. Set Environment Variables

Create a `.env` file:

```bash
cp .env.example .env
```

Edit `.env` and add your credentials:

```env
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_KEY=your-anon-key-here
```

Or export directly in terminal:

```bash
export SUPABASE_URL='https://xxxxx.supabase.co'
export SUPABASE_KEY='eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...'
```

### 3. Run Validation

```bash
python3 test_optimizer_setup.py
```

### 4. Run Optimizer

```bash
python3 optimize_filters.py
```

---

## 📊 Required Database Schema

Your `trading_signals` table must have:

| Column | Type | Description |
|--------|------|-------------|
| `pnl_percent` | float | Trade PnL as percentage |
| `exit_type` | text | "Win" or "Loss" |
| `ai_features` | jsonb | JSON with indicator values |

### `ai_features` structure:

```json
{
  "rsi": 45.2,
  "adx": 32.5,
  "zone_freshness": 7,
  "liquidity_swept": true,
  "zone_quality": 0.85
}
```

---

## 🎛️ Optimization Parameters

The optimizer searches these ranges:

| Parameter | Range | What It Does |
|-----------|-------|--------------|
| `min_freshness` | 1-10 | Minimum zone freshness score |
| `max_rsi` | 50-90 | Maximum RSI (oversold threshold) |
| `min_adx` | 10-40 | Minimum ADX (trend strength) |
| `min_zone_quality` | 0.1-1.0 | Minimum zone quality score |
| `require_liquidity_sweep` | True/False | Require liquidity sweep or not |

---

## 📈 Understanding the Output

### Console Output

```
📊 ORIGINAL PERFORMANCE (No Filters)
============================================================
Total Trades:     250
Win Rate:         44.80%
Total PnL:        -45.50%
============================================================

🚀 Starting optimization with 200 trials...

🏆 OPTIMIZATION COMPLETE!
============================================================
Best Total PnL Found: 125.30%

🎯 GOLDEN COMBINATION (Best Parameters):
------------------------------------------------------------
  min_freshness                  = 5
  max_rsi                        = 65
  min_adx                        = 25
  min_zone_quality               = 0.65
  require_liquidity_sweep        = True
============================================================

📊 PERFORMANCE COMPARISON
============================================================
Win Rate             | Original:    44.80% → Optimized:    80.00% (+35.20%)
Total PnL            | Original:   -45.50% → Optimized:   125.30% (+170.80%)
Trade Count          | Original:      250 → Optimized:       85 (34.0% of original)
============================================================
```

### JSON Output (`optimized_filters.json`)

```json
{
  "best_params": {
    "min_freshness": 5,
    "max_rsi": 65,
    "min_adx": 25,
    "min_zone_quality": 0.65,
    "require_liquidity_sweep": true
  },
  "best_value": 125.3,
  "original_stats": { ... },
  "optimized_stats": { ... }
}
```

---

## 🔧 Customization

### Change Number of Trials

Edit [optimize_filters.py](optimize_filters.py#L293):

```python
# Faster testing (50 trials)
results = optimizer.optimize(n_trials=50)

# Default (200 trials)
results = optimizer.optimize(n_trials=200)

# Thorough search (500 trials)
results = optimizer.optimize(n_trials=500)
```

### Add New Filter Parameters

See [OPTIMIZER_GUIDE.md](OPTIMIZER_GUIDE.md) for detailed instructions on:
- Adding new indicator filters
- Changing optimization metrics (Win Rate, Sharpe Ratio, etc.)
- Custom penalty functions
- Advanced optimization strategies

---

## 💡 Tips for Best Results

1. **Minimum Data**: Have at least 100+ trades for meaningful results
2. **Data Quality**: Ensure all `ai_features` are populated
3. **Multiple Runs**: Run optimization 2-3 times to verify consistency
4. **Backtest**: Always validate on out-of-sample data
5. **Re-optimize**: Re-run every 3-6 months as market conditions change

---

## ⚠️ Important Warnings

### Overfitting Prevention

The optimizer includes built-in protections:
- ✅ Penalizes filter combinations that eliminate >95% of trades
- ✅ Requires minimum trade counts for valid results
- ✅ Shows trade count reduction in output

### Always Backtest

Optimized results are based on **historical data**. You must:
1. Test on out-of-sample data (data not used in optimization)
2. Paper trade before going live
3. Monitor performance vs. expectations

---

## 🐛 Troubleshooting

### Common Issues

| Problem | Solution |
|---------|----------|
| "No data found" | Verify Supabase credentials and table name |
| "KeyError: 'rsi'" | Check `ai_features` JSONB structure |
| "Connection timeout" | Check network/firewall settings |
| All trials fail | Verify `pnl_percent` is numeric and `exit_type` is "Win"/"Loss" |

### Getting Help

1. Run `python3 test_optimizer_setup.py` for diagnostics
2. Check [OPTIMIZER_GUIDE.md](OPTIMIZER_GUIDE.md) for detailed docs
3. Review Supabase dashboard for data issues

---

## 📚 Additional Resources

- **[Optuna Documentation](https://optuna.readthedocs.io/)** - Learn about optimization
- **[Supabase Docs](https://supabase.com/docs)** - Database queries and structure
- **[OPTIMIZER_GUIDE.md](OPTIMIZER_GUIDE.md)** - In-depth customization guide

---

## 🎓 How It Works

### The Science Behind It

1. **Trial Generation**: Optuna suggests parameter combinations using Tree-structured Parzen Estimator (TPE)
2. **Evaluation**: Each combination filters your trades and calculates Total PnL
3. **Learning**: Optuna learns which parameter ranges produce better results
4. **Convergence**: After 200 trials, it finds the optimal combination

### Why Optuna?

- ✅ **Smart Search**: Uses Bayesian optimization, not random search
- ✅ **Fast**: Converges quickly to optimal solutions
- ✅ **Proven**: Used by researchers and quant firms worldwide

---

## 📝 Next Steps After Optimization

1. **Document Results**: Save `optimized_filters.json` with a timestamp
2. **Implement Filters**: Add the golden combination to your trading bot
3. **Monitor Live**: Track if live performance matches optimization
4. **A/B Test**: Consider running filtered vs. unfiltered in parallel
5. **Re-optimize**: Update filters every 3-6 months

---

## 📄 License

This optimizer toolkit is part of your trading system. Use it responsibly and always backtest before live trading.

---

## 🙏 Credits

Built with:
- **[Optuna](https://optuna.org/)** - Hyperparameter optimization framework
- **[Pandas](https://pandas.pydata.org/)** - Data analysis library
- **[Supabase](https://supabase.com/)** - Open-source Firebase alternative

---

**Happy Optimizing! 🚀📈**

*Remember: Past performance doesn't guarantee future results. Always validate on out-of-sample data.*
