# TradingView Settings Verification Checklist

Use this checklist to ensure your TradingView settings match the backtest.

## 1. Date Range Check

In TradingView, go to **Strategy Settings** → **🎯 Quick Setup**:

- [ ] **Enable Date Range Filter** is checked
- [ ] **Start Date**: ________________ (should match your data: `2025-01-01`)
- [ ] **End Date**: ________________ (should match your data: `2026-02-10`)

**Default Pine Values:**
- Start: `01 Jan 2023 00:00 +0000` (line 393)
- End: `19 Jan 2026 23:59 +0000` (line 394)

⚠️ **IMPORTANT**: If you haven't changed these, TradingView is backtesting from **2023**, but your local data only starts from **2025-01-01**!

---

## 2. Configuration Profile

In **🎯 Quick Setup**:

- [ ] **⚡ Configuration Profile**: Select `"Aggressive (Paper Trading)"`
- [ ] **NOT** "Balanced" or "Conservative"
- [ ] **NOT** "Custom" (unless you manually set all aggressive values)

---

## 3. Account Size

In **🎯 Quick Setup**:

- [ ] **💰 Account Size ($)**: ________________ (default: `50000`)

⚠️ This affects position sizing! Make sure it matches your backtest.

---

## 4. Risk Settings

In **🎯 Quick Setup**:

- [ ] **Risk Per Trade (%)**: ________________ (default: `0.5`)

---

## 5. Trade Direction

In **🎯 Quick Setup**:

- [ ] **Trade Direction**: `Both` / `Long Only` / `Short Only`

Your backtest uses: **Both**

---

## 6. Advanced Settings (should be AUTO-SET by Aggressive Profile)

Go to **⚙️ Advanced / Manual Tweaks** and verify these values:

### Liquidity Detection
- [ ] **Max Liquidity Lines (pvtMax)**: `10` (aggressive)
- [ ] **Pivot Strength (liq_pivot_len)**: `3` (aggressive)
- [ ] **Max Distance - Gold (pips)**: `500.0` (aggressive)
- [ ] **Max Zone-to-Liq Distance (Pips)**: `100.0` (aggressive)
- [ ] **Require Strong Pivots**: `false` (aggressive allows minor pivots)

### Quality Filters
- [ ] **AI Quality Filter**: `true`
- [ ] **Min Score (0-100)**: `50` (aggressive, lower threshold)
- [ ] **Grade Filter**: `false` (aggressive doesn't use grade filter)
- [ ] **Min Grade**: `C` (if enabled)
- [ ] **Return Speed Filter**: `0` (no filter for aggressive)

### Trade Filters
- [ ] **Limit Daily Trades**: `true`
- [ ] **Max Trades/Day**: `2`
- [ ] **Block Dead Zone (xx:50-xx:00)**: `true`
- [ ] **Trading Hours Only**: `true`
- [ ] **Start Hour (UTC)**: `7`
- [ ] **End Hour (UTC)**: `22`
- [ ] **HTF Flip Context**: `false` (aggressive does NOT require HTF FLIP)

### Risk Management
- [ ] **SL Buffer (Pips)**: `1.0`
- [ ] **☐ Override: Use Fixed RR**: `false` (use SL-based)
- [ ] **Custom R:R Ratio**: `1.5` (if override is enabled)
- [ ] **Min TP Distance (Pips)**: `5.0`

### Structure Detection
- [ ] **Structure Detection**: `Relaxed (Wicks)` (not Conservative)

---

## 7. Data Source (XAUUSD)

In TradingView chart:

- [ ] Symbol: ________________ (should be `XAUUSD`)
- [ ] Timeframe: ________________ (should be `5m`)
- [ ] Data provider: ________________ (e.g., Vantage, OANDA)

⚠️ Different brokers can have slightly different candle data!

---

## 8. Check Performance Tab Results

After backtest completes in TradingView:

- Total Trades: ________________
- Net Profit: $________________
- Win Rate: ________________%
- Profit Factor: ________________
- Max Drawdown: $________________

---

## Quick Commands

### Run backtest with exact aggressive profile:
```bash
python scripts/backtest_aggressive_profile.py \
  --symbol XAUUSD \
  --from 2025-01-01 \
  --to 2026-02-10 \
  --timeframe M5 \
  --tv-trades <YOUR_TV_TRADES> \
  --tv-profit <YOUR_TV_PROFIT> \
  --tv-winrate <YOUR_TV_WINRATE>
```

### If date range doesn't match, fetch more data:
```bash
# Fetch from 2023 to match TradingView default
python scripts/fetch_historical_data.py \
  --symbol XAUUSD \
  --timeframe 5m \
  --start 2023-01-01 \
  --end 2026-02-10
```

---

## Common Issues

### Issue: Too many trades in backtest vs TradingView
**Possible causes:**
1. TradingView using shorter date range
2. TradingView has "HTF Flip Context" enabled (should be OFF for aggressive)
3. TradingView has higher AI quality threshold (should be 50, not 60/70)

### Issue: Too few trades in backtest vs TradingView
**Possible causes:**
1. Backtest using shorter date range
2. Different data source (broker differences)
3. Backtest has stricter filters than TradingView

### Issue: Different profit despite same trade count
**Possible causes:**
1. Slippage differences
2. Commission settings
3. Different fill prices (data provider differences)
