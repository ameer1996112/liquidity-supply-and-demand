# Dynamic Risk Management Update

## Summary

Changed from **hard-coded lot size limits** to **dynamic risk calculation** based on account balance and risk percentage.

---

## What Changed

### Before (v6.5)

```python
MAX_LOT_SIZE = 0.30  # Hard-coded limit
if size > MAX_LOT_SIZE:
    reject_trade()
```

**Problem:**

- Fixed limit didn't scale with account size
- A $10k account using 0.5% risk could legitimately need 0.47 lots
- Had to manually increase `MAX_LOT_SIZE` for different account sizes

### After (v6.6)

```python
max_allowed_size = calculate_max_position_size(payload)
# Calculates: (Account × Risk%) / (SL_pips × pip_value)
if size > max_allowed_size:
    reject_trade()
```

**Benefits:**

- ✅ Adapts to your account balance automatically
- ✅ Respects your risk percentage setting
- ✅ Validates that PineScript calculated size correctly
- ✅ Prevents accidental over-sizing from bad data

---

## Configuration

### Environment Variables (Railway or .env)

```bash
# Account Settings
ACCOUNT_BALANCE=10000.0         # Your account balance
RISK_PERCENT=0.5                # Risk per trade (0.5 = 0.5%)

# Trading Mode
LIVE_TRADING_ENABLED=false      # false = paper trading (DRY_RUN)
```

### Example Calculations

| Account | Risk % | Symbol | SL Pips | Max Lot Size |
| ------- | ------ | ------ | ------- | ------------ |
| $10,000 | 0.5%   | GBPJPY | 16.5    | ~0.50 lots   |
| $10,000 | 1.0%   | EURUSD | 20.0    | ~0.50 lots   |
| $5,000  | 0.5%   | XAUUSD | 30.0    | ~0.08 lots   |
| $50,000 | 0.5%   | GBPJPY | 16.5    | ~2.50 lots   |

**Formula:**

```
Max Risk USD = Account × (Risk% / 100)
Max Lots = Max Risk USD / (SL Pips × Pip Value per Lot)
```

---

## Logs

### Startup Logs (Railway)

```
🚀 WORKER v6.6 (DYNAMIC RISK MODE) STARTED
  Account Balance: $10,000
  Risk Per Trade: 0.5%
  Correlation Limit: 3 positions
  ML Confidence: 50%
  Kill-Switch: OFF
  LIVE_TRADING: false (DRY_RUN)
  AI Brain: LOADED
  Guard Strategy: FAIL-SAFE (reject on error)
```

### Per-Trade Logs

```
⚡ Processing: GBPJPY | SELL | Size: 0.47
   Risk Check: size 0.47 vs dynamic limit 0.50
   Risk Check: PASSED
```

Or if rejected:

```
⚡ Processing: GBPJPY | SELL | Size: 0.75
   Risk Check: size 0.75 vs dynamic limit 0.50
❌ RISK REJECTED: GBPJPY size 0.75 exceeds limit 0.50
```

---

## PineScript Changes

Updated `SND_Utils.pine` to include `run_mode` in webhook:

```pine
payload := payload + ',"run_mode":"PAPER"'  // For paper trading
// Change to "LIVE" when ready for live trading
```

This ensures trades appear in the correct section of your dashboard.

---

## Deployment Checklist

- [x] Update `backend/worker.py` (dynamic risk calculation)
- [x] Update `scripts/pinescript/libraries/SND_Utils.pine` (run_mode)
- [ ] Set environment variables on Railway:
  - `ACCOUNT_BALANCE=10000.0`
  - `RISK_PERCENT=0.5`
- [ ] Upload updated PineScript to TradingView
- [ ] Test with new signal
- [ ] Verify logs show "v6.6 (DYNAMIC RISK MODE)"

---

## Next Steps

1. **Deploy to Railway** - Push these changes
2. **Update TradingView** - Upload new `SND_Utils.pine`
3. **Test** - Send a test signal and verify:

   - Appears in "Paper" section of dashboard
   - Passes risk check with 0.47 lots
   - Logs show dynamic limit calculation

4. **When Ready for Live Trading:**
   - Set `LIVE_TRADING_ENABLED=true` on Railway
   - Change PineScript `"run_mode":"PAPER"` → `"run_mode":"LIVE"`
   - Redeploy both worker and TradingView strategy
