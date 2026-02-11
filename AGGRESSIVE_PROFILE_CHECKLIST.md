# ⚡ Aggressive Profile Settings Checklist

## Purpose
Ensure your TradingView backtest uses the **exact same settings** as the Python backtest.

## TradingView Settings to Verify

### 1. Quick Setup Section
- [ ] **Configuration Profile**: "Aggressive (Paper Trading)"
- [ ] **Account Size**: $50,000 (or match your Python backtest)
- [ ] **Risk Per Trade**: 0.5%
- [ ] **Trade Direction**: Both
- [ ] **Date Range Filter**: Enabled
  - [ ] **Start Date**: January 1, 2025 00:00
  - [ ] **End Date**: February 10, 2026 23:59

### 2. Advanced Settings (should auto-set when Aggressive is selected)
⚠️ **These should automatically apply when you select "Aggressive (Paper Trading)"**

**Zone Detection:**
- [ ] Invalidate on Wick Touch: ON
- [ ] Max Zones Displayed: 20
- [ ] Min Body %: 50.0

**Liquidity Detection:**
- [ ] Pivot Strength: 3 ← CRITICAL (Aggressive uses 3, not 5)
- [ ] Structure Detection: "Relaxed (Wicks)"
- [ ] Max Liquidity Lines: 10 ← CRITICAL (Aggressive uses 10, not 5)
- [ ] Require Strong Pivots: OFF ← CRITICAL (Aggressive doesn't require)
- [ ] Allow 1-Candle Swings: ON

**Liquidity Distance:**
- [ ] Max Distance - Forex (pips): 20.0
- [ ] Max Distance - Gold (pips): 500.0 ← CRITICAL (Aggressive uses 500, not 300)
- [ ] Max Distance - Indices (pips): 5000.0

**Risk & Position Sizing:**
- [ ] SL Buffer (Pips): 1.0
- [ ] Override: Use Fixed RR: OFF (uses SL-based for gold)
- [ ] Custom R:R Ratio: 1.5 (if override ON, but should be OFF)
- [ ] Max Zone-to-Liq Distance (Pips): 100.0 ← CRITICAL (Aggressive uses 100, not 50)
- [ ] Min TP Distance (Pips): 5.0

**Trade Filters:**
- [ ] Limit Daily Trades: ON
  - [ ] Max Trades/Day: 2
- [ ] Block Dead Zone (xx:50-xx:00): ON
- [ ] Trading Hours Only: ON
  - [ ] Start Hour (UTC): 7
  - [ ] End Hour (UTC): 22
- [ ] HTF Flip Context: OFF ← CRITICAL (Aggressive doesn't require HTF FLIP)

**AI & Quality Filters:**
- [ ] AI Quality Filter: ON
  - [ ] Min Score (0-100): 50 ← CRITICAL (Aggressive uses 50, not 60 or 70)
- [ ] Grade Filter: OFF ← CRITICAL (Aggressive doesn't use grade filter)
- [ ] Min Grade: C (not used if Grade Filter is OFF)
- [ ] Return Speed Filter: 0 ← CRITICAL (Aggressive has no return speed filter)

**Advanced Features:**
- [ ] Break-Even Mode: OFF
- [ ] Time-Based Exit (Bars): 36
- [ ] Double TP Mode: OFF
- [ ] Require FVG (Imbalance): OFF
- [ ] Accuracy Zones: ON
- [ ] Advanced AI Features: ON

## How to Verify in TradingView

1. Open your TradingView chart with the SND Strategy
2. Click the **gear icon** (⚙️) on the strategy name
3. In the settings panel:
   - **Top section**: Verify "Configuration Profile" = "Aggressive (Paper Trading)"
   - **Date Range**: Verify start = Jan 1, 2025 and end = Feb 10, 2026
   - **Scroll down**: Check "⚙️ Advanced / Manual Tweaks" section
   - **Critical values**: The ones marked with ← CRITICAL above

## Python Backtest Settings (Reference)

These are the settings in `scripts/run_aggressive_backtest.py`:

```python
pvt_max=10,                          # Max Liquidity Lines
liq_pivot_len=3,                     # Pivot Strength
liq_max_distance_pips_gold=500.0,    # Max Distance - Gold
liq_entry_max_dist=100.0,            # Max Zone-to-Liq Distance
ai_quality_threshold=50,             # Min AI Score
min_entry_grade="C",                 # Min Grade (not used)
min_return_strength=0,               # Return Speed Filter
max_trades_per_day=2,                # Daily limit
require_htf_flip=False,              # HTF FLIP not required
filter_dead_zone=True,               # Block dead zone
filter_trading_hours=True,           # Trading hours
risk_reward_ratio=1.5,               # R:R (uses SL-based for gold)
```

## Common Mistakes

❌ **Using "Balanced" profile instead of "Aggressive"**
- Balanced uses stricter filters (pvtMax=5, ai_threshold=60)

❌ **Manually overriding settings in "Custom" mode**
- Always use "Aggressive (Paper Trading)" profile
- Manual overrides can break the profile

❌ **Wrong date range**
- TradingView date picker can reset to default dates
- Always verify: Jan 1, 2025 - Feb 10, 2026

❌ **Running on wrong timeframe**
- Must be **5 minutes (M5)**
- Check chart timeframe in top-left corner

❌ **Different symbol name**
- TradingView: XAUUSD
- Your broker may use: XAUUSDm, XAUUSD.raw, etc.
- Check "Symbol" in strategy settings

## Expected Results

If settings match exactly, you should see:
- **Similar trade count** (±10% difference acceptable due to data source)
- **Similar win rate** (±5% difference acceptable)
- **Similar profit/loss** (±20% difference acceptable due to spread/slippage)

## Troubleshooting

**Q: I selected "Aggressive" but backtest shows only 35 trades (not 2,460)**
- ✅ Correct! This means settings match TradingView
- The 2,460 trades was using wrong settings (ai_threshold=70, no trade limit)

**Q: My results still differ from Python backtest**
- Check if TradingView is using different data source
- Verify symbol name matches exactly
- Check for broker-specific symbol suffixes
- Ensure same date range (not just start/end, but actual data availability)

**Q: How do I see what profile is active?**
- In TradingView, look for "Active Profile" table at bottom-center of chart
- Should show "Aggressive (Paper Trading)"

## Run Python Backtest

```bash
# Quick run (uses dates: 2025-01-01 to 2026-02-10)
./scripts/run_aggressive_backtest.sh

# Custom dates
python3 scripts/run_aggressive_backtest.py \
  --symbol XAUUSD \
  --from 2025-01-01 \
  --to 2026-02-10
```

## Next Steps After Verification

1. ✅ Confirm settings match between TradingView and Python
2. 📊 Run both backtests
3. 📈 Compare results (trade count, win rate, profit)
4. 🔍 If still different:
   - Check data source differences
   - Export TradingView trades to CSV
   - Compare first 10 trades timestamp-by-timestamp
