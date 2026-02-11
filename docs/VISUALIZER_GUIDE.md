# SND Backtester Pro - Visualizer Guide

## Overview

Professional-grade backtesting visualization using Streamlit + Plotly.

**Features:**
- ✅ Interactive candlestick charts with zoom/pan
- ✅ Trade markers (entry/exit) with color-coded PnL
- ✅ SL/TP shaded boxes for risk visualization
- ✅ Performance metrics dashboard (Sharpe, PF, Win Rate, Drawdown)
- ✅ Equity curve and drawdown charts
- ✅ Trade distribution analytics
- ✅ Multi-tab layout (Chart, Analytics, Optimization)
- ✅ Real-time parameter tuning via sidebar

## Quick Start

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

Requires:
- `streamlit>=1.28.0`
- `plotly>=5.18.0`
- `numba>=0.58.0`
- `pandas>=2.0.0`
- `numpy>=1.24.0`

### 2. Launch Visualizer

```bash
streamlit run app/visualizer.py
```

Opens at: `http://localhost:8501`

### 3. Configure & Run

**Sidebar Controls:**
1. **Symbol & Timeframe**: XAUUSD, EURUSD, etc. + M5, M15, H1
2. **Date Range**: Select backtest period
3. **Risk Settings**:
   - Risk per Trade: 0.5% (default)
   - SL Buffer: 1.0 pips
   - TP Ratio: 2.0 R:R
4. **Filters**:
   - AI Quality Threshold: 50 (0-100)
   - Require HTF FLIP: OFF (for testing)
5. **Entry Models**: FLIP, BREAK_CANDLE, DIR_CLOSE
6. **Data Source**: Use Sample Data (for quick testing)

Click **"🚀 Run Backtest"** to execute.

## UI Walkthrough

### Tab 1: Chart & Trades

**Performance Summary (Metrics)**
```
Net Profit    Win Rate    Profit Factor    Total Trades    Sharpe Ratio
$2,450        62%         1.8              24              1.2

Gross Profit  Gross Loss  Avg Win          Avg Loss        Max DD %
$5,680        $3,230      $237             -$134           8.5%
```

**Price Chart**
- **Candlesticks**: Green (up) / Red (down)
- **Entry Markers**:
  - 🔺 Green triangle = Long entry
  - 🔻 Red triangle = Short entry
  - Hover for: Entry model (FLIP/BREAK/DIR_CLOSE), entry price
- **Exit Markers**:
  - 🟢 Green circle = Profitable exit
  - 🔴 Red circle = Loss
  - Hover for: Exit price, PnL, exit reason (STOP/LIMIT/TIME)
- **SL/TP Boxes**:
  - Red shaded = Stop loss zone
  - Green shaded = Take profit zone
  - Width = trade duration

**Trade List Table**
- Filterable, sortable DataFrame
- Columns: Entry Time, Exit Time, Side, Entry Model, Prices, PnL, Bars Held, Exit Reason

### Tab 2: Analytics

**Equity Curve**
- Cumulative PnL over time
- Shows account growth/drawdown
- Green fill = underwater area

**Drawdown Chart**
- Percentage drawdown from peak
- Red fill = drawdown depth
- Identify worst drawdown periods

**PnL Distribution (Histogram)**
- Shows win/loss size distribution
- Identify if strategy is skewed (many small losses + few big wins, or vice versa)

**Entry Model Breakdown (Pie Chart)**
- % of trades by entry model (FLIP, BREAK_CANDLE, DIR_CLOSE)
- Identify which model performs best

### Tab 3: Optimization (Placeholder)

**Coming Soon:**
- Walk-Forward Analysis
- Bayesian Optimization (Optuna)
- Parameter Heatmaps
- Monte Carlo Robustness Testing

## Performance

**With Numba-Optimized Engine:**
- 10,000 bars processed in **~0.03s** (after JIT compilation)
- **28x faster** than legacy Python engine
- Real-time parameter tuning (re-run in <1s for 1k bars)

**Chart Rendering:**
- Plotly handles 10k+ candles smoothly
- Interactive zoom/pan
- Responsive on modern browsers

## Tips & Tricks

### Testing with Sample Data

1. Check **"Use Sample Data"**
2. This generates synthetic 1000-bar OHLC data
3. Fast iteration for UI testing
4. No need for MetaApi credentials

### Real Data (MetaApi)

1. Uncheck **"Use Sample Data"**
2. Ensure `META_API_TOKEN` and `META_API_ACCOUNT_ID` in `.env`
3. Data cached in `data/backtest_candles/` as Parquet
4. First fetch may take 10-30s, then instant from cache

### Adjusting Filters

**Too many trades?**
- Increase AI Quality Threshold (60 → 80)
- Enable "Require HTF FLIP" (filters to M15 boundaries)
- Reduce TP Ratio (more conservative exits)

**Too few trades?**
- Decrease AI Quality Threshold (60 → 40)
- Disable "Require HTF FLIP"
- Enable all entry models

### Understanding Metrics

**Sharpe Ratio:**
- >1.0 = Good
- >2.0 = Excellent
- <1.0 = Needs improvement

**Profit Factor:**
- >1.5 = Good
- >2.0 = Excellent
- <1.0 = Losing strategy

**Max Drawdown %:**
- <10% = Excellent
- 10-20% = Acceptable
- >20% = High risk

## Troubleshooting

**Issue: "No trades generated"**
- **Solution**: Lower AI quality threshold or extend date range

**Issue: Streamlit not found**
- **Solution**: `pip install streamlit`

**Issue: Chart not rendering**
- **Solution**: Check browser console, refresh page

**Issue: Slow performance**
- **Solution**: Reduce date range or use sample data for testing

## Advanced: Custom Themes

Streamlit supports custom themes. Edit `.streamlit/config.toml`:

```toml
[theme]
primaryColor = "#26a69a"
backgroundColor = "#1e1e1e"
secondaryBackgroundColor = "#2e2e2e"
textColor = "#ffffff"
font = "sans serif"
```

## Next Steps

After Week 3 completion, **Week 4: Optimization** will add:
1. Walk-forward analysis engine
2. Bayesian optimization with Optuna
3. Parameter heatmaps (2D sensitivity)
4. Export optimization results to CSV

---

**Enjoy the professional backtesting experience!** 🚀
