# Trading Filter Optimizer - User Guide

## Overview
The `optimize_filters.py` script uses machine learning (Optuna) to find the best combination of trading signal filters that maximize your net profit.

## Quick Start

### 1. Set Up Environment
```bash
# Set your Supabase credentials
export SUPABASE_URL='https://your-project.supabase.co'
export SUPABASE_KEY='your-anon-or-service-key'

# Install dependencies
pip install -r requirements_optimizer.txt
```

### 2. Run Optimization
```bash
# Run with default 200 trials (recommended: 500-1000 for production)
python optimize_filters.py
```

### 3. Understand the Results

#### Baseline Performance
Shows your current performance **without any filters** - this is your starting point.

#### Golden Combination
The optimal filter parameters found by Optuna. Example:
```
RSI Filter: ENABLED
  - max_rsi = 70 (only take trades when RSI ≤ 70)

Zone Freshness: ENABLED
  - min_freshness = 5 (only take trades from zones with freshness ≥ 5)

Liquidity Sweep: DISABLED
  - Algorithm found this filter doesn't improve results
```

#### Performance Comparison
Shows before/after metrics:
- **Win Rate**: Percentage of winning trades (higher is better)
- **Total PnL**: Cumulative profit/loss (higher is better)
- **Profit Factor**: Total wins ÷ Total losses (>1 is profitable, >2 is excellent)
- **Trade Selectivity**: Percentage of trades that pass filters

## Integration with Your Trading System

After optimization, you'll get `apply_optimal_filters.py` - a ready-to-use function:

```python
from apply_optimal_filters import apply_optimal_filters

# Load your signals
signals_df = load_signals_from_supabase()

# Apply optimal filters
high_quality_signals = apply_optimal_filters(signals_df)

# Trade only these high-quality signals
for signal in high_quality_signals:
    execute_trade(signal)
```

## Best Practices

1. **Minimum 200 trades**: Don't optimize with less historical data
2. **Out-of-sample testing**: After finding optimal filters, test on NEW data
3. **Periodic re-optimization**: Market conditions change - re-run every 3-6 months
4. **Don't overfit**: If filters remove >90% of trades, you're likely overfitting
5. **Paper trade first**: Test optimal filters in paper trading before using real money
