# Quick Reference Guide - Trading Filter Optimizer

## 🚀 3-Minute Quick Start

```bash
# 1. Setup
./setup_optimizer.sh

# 2. Test
python3 test_optimizer_setup.py

# 3. Optimize
python3 optimize_filters.py

# 4. Done! Check optimized_filters.json
```

---

## 📁 File Reference

| File | Use Case | Command |
|------|----------|---------|
| **setup_optimizer.sh** | First-time setup | `./setup_optimizer.sh` |
| **test_optimizer_setup.py** | Validate configuration | `python3 test_optimizer_setup.py` |
| **optimize_filters.py** | Run optimization | `python3 optimize_filters.py` |
| **apply_optimized_filters.py** | Use filters in production | `python3 apply_optimized_filters.py` |
| **README_OPTIMIZER.md** | Complete documentation | Read for full details |
| **OPTIMIZER_GUIDE.md** | Advanced customization | Read for customization |

---

## ⚙️ Environment Setup

### Option 1: Using .env file (Recommended)

```bash
# Copy template
cp .env.example .env

# Edit with your credentials
nano .env
```

Add:
```env
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_KEY=your-anon-key
```

### Option 2: Export directly

```bash
export SUPABASE_URL='https://xxxxx.supabase.co'
export SUPABASE_KEY='eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...'
```

---

## 🎯 Common Commands

### Run Full Optimization (Default: 200 trials)
```bash
python3 optimize_filters.py
```

### Quick Test (50 trials)
Edit `optimize_filters.py` line 293:
```python
results = optimizer.optimize(n_trials=50)
```

### Thorough Search (500 trials)
Edit `optimize_filters.py` line 293:
```python
results = optimizer.optimize(n_trials=500)
```

---

## 📊 Database Schema Required

Your `trading_signals` table needs:

```sql
CREATE TABLE trading_signals (
  id UUID PRIMARY KEY,
  pnl_percent FLOAT,
  exit_type TEXT,  -- "Win" or "Loss"
  ai_features JSONB
);
```

`ai_features` structure:
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

## 🔍 Troubleshooting Checklist

- [ ] Python 3.8+ installed? → `python3 --version`
- [ ] Dependencies installed? → `pip3 install -r requirements_optimizer.txt`
- [ ] Environment variables set? → `echo $SUPABASE_URL`
- [ ] Supabase connection works? → `python3 test_optimizer_setup.py`
- [ ] Table has data? Check Supabase dashboard
- [ ] ai_features has correct fields? Check one record manually

---

## 📈 Reading the Results

### optimized_filters.json
```json
{
  "best_params": {
    "min_freshness": 5,        ← Use these in your bot
    "max_rsi": 65,
    "min_adx": 25,
    "min_zone_quality": 0.65,
    "require_liquidity_sweep": true
  },
  "best_value": 125.3          ← Total PnL improvement
}
```

### Applying Filters in Code

```python
from apply_optimized_filters import OptimizedFilterApplicator

# Initialize
applicator = OptimizedFilterApplicator()

# Check a signal
signal = {
    'symbol': 'BTCUSD',
    'ai_features': {
        'rsi': 58.5,
        'adx': 32.0,
        'zone_freshness': 7,
        'liquidity_swept': True,
        'zone_quality': 0.75
    }
}

if applicator.should_take_trade(signal):
    # Execute trade
    pass
```

---

## ⚡ Performance Tips

### Faster Optimization
- Use fewer trials for testing: `n_trials=50`
- Use more CPU cores: Add `n_jobs=-1` to `study.optimize()`

### Better Results
- More data = better optimization (aim for 100+ trades)
- Re-run optimization 2-3 times to verify consistency
- Always backtest on out-of-sample data

### Avoid Overfitting
- The optimizer penalizes filters that eliminate >95% of trades
- Don't optimize on ALL your data - save some for validation
- Monitor live performance vs. optimized expectations

---

## 🛠️ Quick Fixes

### "No module named 'optuna'"
```bash
pip3 install -r requirements_optimizer.txt
```

### "No data found in trading_signals table"
- Check Supabase dashboard
- Verify table name is exactly `trading_signals`
- Ensure you have data in the table

### "KeyError: 'rsi'"
- Check one record in Supabase
- Verify ai_features has: rsi, adx, zone_freshness, liquidity_swept, zone_quality

### Optimization returns negative PnL
- Check that pnl_percent values are correct (positive for wins, negative for losses)
- Verify exit_type is "Win" or "Loss" (case-sensitive)
- Ensure enough trades have valid ai_features

---

## 📝 Workflow Summary

```
1. Setup (One Time)
   └─> ./setup_optimizer.sh
   └─> Create .env file
   └─> python3 test_optimizer_setup.py

2. Optimize (Run Weekly/Monthly)
   └─> python3 optimize_filters.py
   └─> Review optimized_filters.json
   └─> Backtest on out-of-sample data

3. Deploy (Use in Production)
   └─> Update your trading bot with new filters
   └─> Monitor live performance
   └─> Re-optimize every 3-6 months
```

---

## 🎓 Learning Resources

- **Optuna Basics**: https://optuna.org/
- **Optimization Algorithms**: Read about TPE (Tree-structured Parzen Estimator)
- **Trading Filters**: Understand each indicator (RSI, ADX, etc.)
- **Backtesting**: Learn about in-sample vs out-of-sample testing

---

## 📞 Need Help?

1. ✅ Run `python3 test_optimizer_setup.py` for diagnostics
2. ✅ Check [OPTIMIZER_GUIDE.md](OPTIMIZER_GUIDE.md) for detailed docs
3. ✅ Review [README_OPTIMIZER.md](README_OPTIMIZER.md) for examples
4. ✅ Check your Supabase data directly in the dashboard

---

## ⚠️ Important Reminders

- 🔴 **Always backtest** optimized filters on out-of-sample data
- 🔴 **Never trade live** without validating results first
- 🔴 **Re-optimize regularly** as market conditions change
- 🔴 **Monitor performance** - past results don't guarantee future success

---

**That's it! You're ready to optimize your trading filters. Good luck! 🚀**
