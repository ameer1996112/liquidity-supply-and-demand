# Backtest Verification Guide - How to Ensure Accuracy vs TradingView

## 🎯 Current Status

### ✅ Bugs Fixed (2026-02-11)
- **Entry price clamping**: Entries now forced within zone boundaries
- **Stop loss placement**: No more backwards SL (e.g., long SL above entry)
- **Quick stop-outs**: Reduced from 48.6% to 27.8%

### ❌ Remaining Issues
- **Overall P&L**: Currently negative (-$4,448 on 2026-01-01 to 2026-02-10)
- **Win rate**: 41.7% (below expected)
- **Can't verify**: TradingView export is from 2025, Python is from 2026

---

## 📊 Step-by-Step Verification Process

### **Step 1: Visual Verification (Do This First!)**

Open the interactive debug chart:

```bash
# Generate enhanced chart with zones
python -m app.backtest_debug --from 2026-01-01 --to 2026-01-05

# Opens: data/backtest/XAUUSD/chart_debug.html
```

**What to look for:**
- ✅ Are entry markers **inside green/red zone boxes**?
- ✅ Are SL lines (red dashed) **below long entries** and **above short entries**?
- ✅ Do entries happen when price **touches zones**?
- ✅ Do exit markers show reasonable P&L?

**Click on trades** in the bottom list to zoom to that trade on the chart.

---

### **Step 2: Run TradingView on SAME Dates**

⚠️ **CRITICAL**: You MUST compare the same time period!

1. Open TradingView with your SND strategy
2. Set backtest range: **2026-01-01 to 2026-02-10**
3. Run strategy tester
4. Export "List of Trades" → Save as `data/backtest/XAUUSD/trades_tv.csv`

---

### **Step 3: Compare Trade-by-Trade**

```bash
python -m app.parity_check \
  --tv data/backtest/XAUUSD/trades_tv.csv \
  --py data/backtest/XAUUSD/trades.csv
```

This will show:
- Entry time matches (tolerance: ±5 minutes)
- Entry price matches (tolerance: ±3 ticks)
- Side matches (long/short)
- Mismatched trades

---

### **Step 4: Diagnostic Analysis**

```bash
python -m app.trade_diagnostic --from 2026-01-01 --to 2026-02-10
```

This analyzes:
- Quick stop-outs (why they happen)
- Stop loss distances (too tight?)
- Entry price patterns (outside zones?)
- Entry model performance (FLIP vs BOC vs DIR_CLOSE)

---

## 🔍 Common Issues & Solutions

### Issue 1: Different Trade Count

**Problem:** TradingView shows 20 trades, Python shows 15 trades

**Causes:**
1. **Zone creation** differs (check zone patterns)
2. **Liquidity sweep** detection simplified (10-bar vs pivot-based)
3. **Entry models** not matching (FLIP/BOC/DIR_CLOSE logic)
4. **Time filters** different (UTC vs Asia/Jerusalem)

**Solution:**
```bash
# Compare first 3 trades visually
python -m app.backtest_debug --from 2026-01-01 --to 2026-01-03
```

Look at TradingView chart side-by-side and check:
- Are zones being created at the same candles?
- Are liquidity sweeps detected at the same times?

---

### Issue 2: Entry Prices Different

**Problem:** TradingView entry: $2650.50, Python entry: $2650.20

**Causes:**
1. **Slippage**: Python uses 3 ticks slippage, TradingView might use different
2. **Fill logic**: TradingView uses `process_orders_on_close=true`, check Python engine
3. **Entry price clamping**: Python now clamps to zone boundaries (NEW FIX)

**Solution:**
Check [app/engine.py:92-97](../app/engine.py) slippage logic:
```python
def apply_slippage_entry(close: float, side: OrderSide, slippage_ticks: int, tick_size: float) -> float:
    slip = slippage_ticks * tick_size
    if side == OrderSide.LONG:
        return round_to_tick(close + slip, tick_size)
    return round_to_tick(close - slip, tick_size)
```

If TradingView doesn't use slippage, set `slippage_ticks=0` in [app/backtest_run.py:86](../app/backtest_run.py).

---

### Issue 3: Stop Loss Hit Immediately

**Problem:** Trades stop out within 1-2 bars (27.8% of trades)

**Causes:**
1. **SL buffer too small**: Default 1.0 pips for gold might be tight
2. **Zone size small**: Narrow zones = tight SL
3. **Volatility**: Market moving fast, SL gets hit

**Solution:**
Adjust in [app/config.py](../app/config.py):
```python
stop_loss_buffer_pips: float = 2.0  # Increase from 1.0
```

Or check if TradingView uses a different SL calculation:
```bash
# Check SL distances in diagnostic
python -m app.trade_diagnostic --from 2026-01-01 --to 2026-02-05 | grep "SL distances"
```

---

### Issue 4: Low Win Rate (41.7%)

**Problem:** Expected 50-60% win rate, getting 41.7%

**Causes:**
1. **Zone quality filtering**: `ai_quality_threshold=60` might be too low
2. **Entry model logic**: DIR_CLOSE might be triggering too aggressively
3. **TP levels**: Take profit too far (not getting hit)
4. **Time-based exit**: `max_bars_held=36` forcing losers closed

**Solution A - Stricter zone filtering:**
```python
# In app/config.py
ai_quality_threshold: int = 70  # Increase from 60
min_entry_grade: str = "B"  # Require B+ zones
```

**Solution B - Check TP ratio:**
```bash
# Look at limit vs stop exits
python -m app.trade_diagnostic --from 2026-01-01 --to 2026-02-05 | grep "Exit reason"
```

If most exits are "stop" instead of "limit", TP might be too far.

---

## 📋 Recommended Workflow

### Quick Verification (5 minutes)
```bash
# 1. Generate visual chart
python -m app.backtest_debug --from 2026-01-01 --to 2026-01-03

# 2. Open chart_debug.html and verify:
#    - Entries inside zones?
#    - SL on correct side?
#    - Reasonable trades?
```

### Deep Verification (30 minutes)
```bash
# 1. Run TradingView on SAME dates (2026-01-01 to 2026-02-10)
# 2. Export trades_tv.csv

# 3. Compare
python -m app.parity_check --tv trades_tv.csv --py trades.csv

# 4. Analyze differences
python -m app.trade_diagnostic --from 2026-01-01 --to 2026-02-10
```

---

## 🛠️ Configuration Alignment Checklist

Compare these settings between TradingView Pine and Python:

| Setting | Pine (scripts/pinescript/strategies/SND_Strategy.pine) | Python (app/config.py) |
|---------|------|--------|
| Risk per trade | `risk_per_trade_pct` (line 261) | `risk_per_trade_pct: float = 0.5` |
| SL buffer | `stop_loss_buffer_pips` (line 263) | `stop_loss_buffer_pips: float = 1.0` |
| AI quality threshold | `ai_quality_threshold` (line 270) | `ai_quality_threshold: int = 60` |
| Max bars held | `max_bars_held` (line 274) | `max_bars_held: int = 36` |
| HTF flip required | `require_htf_flip` (line 280) | `require_htf_flip: bool = True` |
| Dead zone filter | `filter_dead_zone` (line 283) | `filter_dead_zone: bool = True` |

---

## 🚀 Next Steps

1. **Visual Check (NOW)**:
   ```bash
   python -m app.backtest_debug --from 2026-01-01 --to 2026-01-05
   open data/backtest/XAUUSD/chart_debug.html
   ```

2. **Run TV on Same Dates**: Get TradingView export from 2026-01-01 to 2026-02-10

3. **Compare**: Use parity_check.py to find differences

4. **Iterate**: Adjust config based on findings

---

## 📁 Generated Files

After running backtests and diagnostics, you'll have:

```
data/backtest/XAUUSD/
├── trades.csv           # Python backtest trades
├── equity.csv           # Equity curve
├── chart.html           # Basic chart (original)
├── chart_debug.html     # Enhanced chart with zones (NEW!)
└── trades_tv.csv        # TradingView export (you create this)
```

---

## ❓ Still Not Matching?

If after following all steps, trades still don't match:

1. **Check zone creation logic**: [docs/STRATEGY_LOGIC_AUDIT.md](./STRATEGY_LOGIC_AUDIT.md)
2. **Review known differences**: Liquidity detection (10-bar vs pivot), timezone (UTC vs Asia/Jerusalem)
3. **Consider simplifications**: Python backtest simplified some Pine logic for speed

The goal isn't 100% match - it's **directional accuracy**:
- Similar trade count (±10%)
- Similar win rate (±5%)
- Similar P&L trend (both positive or both negative)
