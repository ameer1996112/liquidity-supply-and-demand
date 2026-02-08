# Kelly Criterion Position Sizing

## Overview

The Kelly Criterion is a mathematical formula that calculates the optimal position size to maximize long-term capital growth while managing risk. This bot implements **Fractional Kelly** (default: quarter-Kelly) for more conservative position sizing.

## How It Works

### Full Kelly Formula

```
f* = (p×b - q) / b
```

Where:
- `f*` = fraction of capital to risk
- `p` = win rate (probability of winning)
- `q` = 1 - p (probability of losing)
- `b` = avg_win / avg_loss (in R multiples)

### Fractional Kelly (Recommended)

Full Kelly can be aggressive and lead to large drawdowns. Fractional Kelly reduces the position size:

```
Fractional Kelly = Full Kelly × kelly_fraction
```

**Default:** `kelly_fraction = 0.25` (quarter-Kelly)

## Configuration

### Enable Kelly Criterion

In your `.env` file or settings:

```bash
# Enable Kelly Criterion position sizing
KELLY_ENABLED=true

# Fractional Kelly multiplier (0.25 = quarter-Kelly, conservative)
KELLY_FRACTION=0.25  # Range: 0.01 to 1.0
```

### How It Integrates with Risk Management

Kelly Criterion works **in combination** with your base risk settings:

1. **Base Risk:** `risk_percent = 0.5%` (from PineScript alignment)
2. **Kelly Optimization:** Calculates optimal risk based on edge
3. **Final Risk:** `min(base_risk, kelly_risk)` (takes the smaller, more conservative value)

## Example Calculations

### Scenario 1: Strong Edge (60% Win Rate, 2:1 RR)

```python
win_rate = 0.60
avg_win_r = 2.0
avg_loss_r = 1.0

# Full Kelly
p = 0.60, q = 0.40, b = 2.0
f* = (0.60 × 2.0 - 0.40) / 2.0 = 0.40 (40% of capital!)

# Fractional Kelly (0.25)
fractional_kelly = 0.40 × 0.25 = 0.10 (10% of capital)

# With base risk = 0.5%
final_risk = min(0.5%, 10%) = 0.5% ← Conservative limit applied
```

**Result:** Kelly suggests 10% risk, but base risk limit caps it at 0.5%

### Scenario 2: Weak Edge (55% Win Rate, 1.5:1 RR)

```python
win_rate = 0.55
avg_win_r = 1.5
avg_loss_r = 1.0

# Full Kelly
f* = (0.55 × 1.5 - 0.45) / 1.5 = 0.25 (25%)

# Fractional Kelly (0.25)
fractional_kelly = 0.25 × 0.25 = 0.0625 (6.25%)

# With base risk = 0.5%
final_risk = min(0.5%, 6.25%) = 0.5%
```

**Result:** Kelly allows more risk, but we stay at 0.5% base risk

### Scenario 3: Negative Edge (45% Win Rate, 2:1 RR)

```python
win_rate = 0.45
avg_win_r = 2.0

# Full Kelly
f* = (0.45 × 2.0 - 0.55) / 2.0 = 0.175 (17.5%)

# But wait - this is only 45% win rate with 2:1 RR
# Expected value = 0.45 × 2.0 - 0.55 × 1.0 = 0.35 (positive, but small)
```

**Important:** Kelly will suggest small sizes for weak edges and **zero** for negative edges.

## When Kelly Helps

### ✅ Scenarios Where Kelly Adds Value

1. **High Win Rate + Good RR:** Kelly allows you to size up conservatively when you have a strong edge
2. **Varying Strategy Performance:** Kelly automatically scales down during losing periods
3. **Multi-Strategy Portfolio:** Different strategies have different optimal sizes
4. **Adaptive Risk:** Kelly adjusts based on actual performance metrics

### ⚠️ Scenarios Where Kelly May Not Help

1. **Small Sample Size:** Need >30 trades for reliable win rate estimates
2. **Unstable Win Rate:** If win rate varies wildly, Kelly becomes unstable
3. **Already Conservative:** With 0.5% base risk and 2:1 min RR, Kelly often agrees with base risk
4. **Prop Firm Constraints:** Prop firms have fixed risk rules that override Kelly

## Integration with Bot Components

### In `src/services/position_optimizer.py`

```python
optimizer = PositionOptimizer()

# Suggest optimal risk
suggested_risk = optimizer.suggest_position_size(
    base_risk_pct=0.5,      # Your base risk (Pine aligned)
    win_rate=0.60,          # From ML model or historical data
    avg_win_r=2.5,          # Average win in R
    kelly_fraction=0.25,    # Quarter-Kelly
    use_kelly=True          # Enable Kelly
)

# Returns: min(base_risk, kelly_risk)
```

### In `src/logic.py` (Trade Execution)

Kelly is applied **before** PropGuard scaling:

```python
# 1. Calculate base risk
base_risk_usd = account_balance × (risk_percent / 100)

# 2. Apply Kelly optimization (if enabled)
if kelly_enabled:
    kelly_risk_pct = optimizer.suggest_position_size(...)
    risk_percent = kelly_risk_pct

# 3. Calculate position size
lots = calculate_max_position_size(payload, account_balance, risk_percent)

# 4. Apply PropGuard multiplier
lots = lots × risk_multiplier
```

## Monitoring Kelly Performance

### Via API Endpoint

```bash
GET /api/portfolio/kelly-analysis
```

Returns:
```json
{
  "kelly_enabled": true,
  "kelly_fraction": 0.25,
  "current_win_rate": 0.62,
  "avg_win_r": 2.3,
  "full_kelly_suggestion": 0.087,  // 8.7%
  "fractional_kelly": 0.022,       // 2.2%
  "base_risk": 0.005,              // 0.5%
  "applied_risk": 0.005,           // min(0.5%, 2.2%) = 0.5%
  "kelly_recommendation": "Kelly suggests 2.2% but base risk limit applied"
}
```

### In Logs

```
[INFO] Position sizing: base=0.50%, Kelly=2.20%, suggested=0.50%
```

## Recommended Settings

### Conservative (Live Trading)

```bash
KELLY_ENABLED=true
KELLY_FRACTION=0.10  # One-tenth Kelly (very conservative)
```

### Balanced (Recommended)

```bash
KELLY_ENABLED=true
KELLY_FRACTION=0.25  # Quarter Kelly (standard)
```

### Aggressive (Paper Trading Only)

```bash
KELLY_ENABLED=true
KELLY_FRACTION=0.50  # Half Kelly (aggressive)
```

### Disable Kelly

```bash
KELLY_ENABLED=false  # Use base risk_percent only
```

## Safety Limits

Even with Kelly enabled, these hard limits always apply:

1. ✅ **Min RR Ratio:** 2.0 (Pine requirement)
2. ✅ **Max Lot Size:** 10.0 lots (Pine default)
3. ✅ **PropGuard:** Dynamic scaling (0.25x-2.0x)
4. ✅ **Base Risk Cap:** 0.5% (Pine Balanced profile)
5. ✅ **Trinity Guards:** Daily loss, drawdown, max positions

## Further Reading

- [Kelly Criterion - Wikipedia](https://en.wikipedia.org/wiki/Kelly_criterion)
- [Fractional Kelly - Quantitative Trading](https://www.quantstart.com/articles/kelly-criterion-for-position-sizing/)
- [Ed Thorp's Paper on Kelly](https://www.princeton.edu/~wbialek/rome/refs/kelly_56.pdf)

## Support

For questions about Kelly Criterion:
- Check bot logs for `Position sizing:` messages
- Monitor via `/api/portfolio/risk-dashboard`
- Review `src/services/position_optimizer.py::suggest_position_size()`
