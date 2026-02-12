# 🎯 Backtest UI & Bot Integration Guide

## Overview

Your trading bot now has a **TradingView-style backtest UI** with **FX Replay** and **live bot integration**!

### What's New

1. ✅ **TradingView-Style Charts** - Professional candlestick charts using `lightweight-charts`
2. ✅ **FX Replay Mode** - Bar-by-bar playback with play/pause/speed controls
3. ✅ **Trade Markers** - Visual entry/exit points on chart
4. ✅ **Zone Overlays** - Supply/Demand zones displayed on chart
5. ✅ **Bot Integration** - Validate strategies before deploying to live trading

---

## 📁 Files Created

### Frontend Components

1. **[BacktestChart.tsx](../frontend/src/components/backtest/BacktestChart.tsx)**
   - TradingView-style candlestick chart
   - Trade markers (entry/exit with P&L)
   - Zone overlays (supply/demand)
   - Crosshair with time/price display

2. **[FXReplayController.tsx](../frontend/src/components/backtest/FXReplayController.tsx)**
   - Play/Pause controls
   - Speed control (0.5x, 1x, 2x, 5x, 10x)
   - Step forward/backward
   - Progress bar with scrubbing
   - Current candle OHLC display

3. **[/backtest/page.tsx](../frontend/src/app/backtest/page.tsx)**
   - Full backtest dashboard
   - Configuration panel
   - Stats cards (Total Trades, Win Rate, Return, Drawdown)
   - Trade history list

### Backend API

4. **[api_backtest_integration.py](../src/api_backtest_integration.py)**
   - `/api/bot/validate-strategy` - Validate strategy before deploying
   - Integration with live trading bot
   - Performance threshold validation

---

## 🚀 Quick Start

### 1. Start the Backend

```bash
# Ensure backend is running
uvicorn main:app --reload
```

### 2. Start the Frontend

```bash
cd frontend
npm run dev
```

### 3. Access the Backtest UI

Open [http://localhost:3000/backtest](http://localhost:3000/backtest)

---

## 🎬 How to Use FX Replay

### Step 1: Configure Backtest

1. **Enter Symbol:** EURUSD, XAUUSD, etc.
2. **Select Date Range:** Start and end dates
3. **Choose Timeframe:** 5m, 15m, 1h, 4h, 1d
4. **Set AI Guardian Filters:**
   - ✅ **Reject Compression** (recommended - enabled by default)
   - ⬜ **Require Liquidity Sweep** (optional - for high-quality setups)
   - ⬜ **Require Structure Break** (optional - for trend continuation)

### Step 2: Run Backtest

Click **"Run Backtest"** button.

The system will:
1. Fetch historical data from MetaApi
2. Run your SND strategy
3. Display stats and chart

### Step 3: Use FX Replay

Once backtest completes:

#### **Playback Controls**

- **Play/Pause** ▶️ ⏸️ - Auto-advance candles
- **Step Forward** ⏭️ - Move 1 candle forward
- **Step Backward** ⏮️ - Move 1 candle backward
- **Skip +10** ⏩ - Jump 10 candles ahead
- **Reset** 🔄 - Go back to start

#### **Speed Control**

Choose replay speed:
- **0.5x** - Slow (2 seconds per candle)
- **1x** - Normal (1 second per candle)
- **2x** - Fast (0.5 seconds per candle)
- **5x** - Very Fast (0.2 seconds per candle)
- **10x** - Ultra Fast (0.1 seconds per candle)

#### **Scrub Through Time**

Click anywhere on the **progress bar** to jump to that time.

---

## 📊 Understanding the Chart

### **Candlesticks**

- 🟢 **Green** - Bullish candles (close > open)
- 🔴 **Red** - Bearish candles (close < open)
- Gray bars at bottom - Volume

### **Trade Markers**

- ⬆️ **Green Arrow Up** - LONG entry
- ⬇️ **Red Arrow Down** - SHORT entry
- 🟢 **Green Circle** - Winning exit
- 🔴 **Red Circle** - Losing exit

Hover over markers to see:
- Entry price
- P&L in USD

### **Supply/Demand Zones**

- 🟢 **Green Dashed Lines** - Demand zones (support)
- 🔴 **Red Dashed Lines** - Supply zones (resistance)

Zones appear when they're created and extend 7 days forward.

---

## 🤖 Bot Integration: Validate Before Deploy

### Why Validate?

Before deploying a new strategy or changing parameters on your **live bot**, you should validate it with historical data to ensure:

✅ Minimum win rate is achieved
✅ Profit factor is acceptable
✅ Max drawdown is within tolerance
✅ Sufficient trades generated

### How to Validate

#### **Method 1: Via Frontend**

1. Go to [http://localhost:3000/backtest](http://localhost:3000/backtest)
2. Configure strategy parameters
3. Run backtest
4. Review stats:
   - **Total Trades** ≥ 10
   - **Win Rate** ≥ 50%
   - **Profit Factor** ≥ 1.2
   - **Max Drawdown** ≤ 20%

If all thresholds pass → ✅ **Deploy to live bot**

#### **Method 2: Via API (Automated)**

```bash
curl -X POST http://localhost:8000/api/bot/validate-strategy \
  -H "Content-Type: application/json" \
  -d '{
    "symbol": "EURUSD",
    "days_to_test": 90,
    "timeframe": "5m",
    "risk_percent": 0.5,
    "min_rr_ratio": 2.0,
    "reject_compression_arrival": true,
    "min_trades": 10,
    "min_win_rate": 50.0,
    "min_profit_factor": 1.2,
    "max_drawdown": 20.0
  }'
```

**Response:**

```json
{
  "symbol": "EURUSD",
  "timeframe": "5m",
  "test_period_days": 90,
  "total_trades": 15,
  "win_rate": 60.0,
  "total_return": 8.5,
  "profit_factor": 1.8,
  "max_drawdown": 12.3,
  "sharpe_ratio": 1.4,
  "is_valid": true,
  "failed_checks": [],
  "recommendation": "✅ Deploy - Excellent backtest results"
}
```

If `is_valid: true` → ✅ **Deploy to live bot**

---

## 🔗 Integration with Live Trading Bot

### Workflow

```
┌─────────────────────────────────────────────────────────────┐
│  1. Backtest Lab (Test Strategy)                            │
│     ↓                                                        │
│  2. Validate Performance                                    │
│     ↓                                                        │
│  3. If Valid → Deploy to Paper Trading (worker.py)         │
│     ↓                                                        │
│  4. Monitor Live Performance vs Backtest                    │
│     ↓                                                        │
│  5. If Aligned → Deploy to Live Trading                     │
└─────────────────────────────────────────────────────────────┘
```

### Step-by-Step Integration

#### **1. Test Strategy in Backtest Lab**

Go to `/backtest` page → Configure → Run backtest

#### **2. Validate Performance**

Check if backtest meets minimum thresholds:
- Win rate ≥ 50%
- Profit factor ≥ 1.2
- Max drawdown ≤ 20%

#### **3. Deploy to Paper Trading**

If backtest passes, update your bot settings:

```python
# config/settings.py or .env

# Strategy parameters (from successful backtest)
RISK_PERCENT=0.5
MIN_RR_RATIO=2.0
STOP_LOSS_BUFFER_PIPS=1.0

# AI Guardian filters (match backtest config)
REJECT_COMPRESSION_ARRIVAL=True  # If used in backtest
REQUIRE_LIQUIDITY_SWEEP=False
REQUIRE_STRUCTURE_BREAK=False
```

Restart your bot:

```bash
python src/worker.py
```

#### **4. Monitor Live Performance**

Compare live trades vs backtest predictions:
- Are win rates aligned?
- Is P&L distribution similar?
- Are drawdowns within expected range?

Use your existing analytics dashboard to track:
- [/analytics](http://localhost:3000/analytics)
- [/journal](http://localhost:3000/journal)

#### **5. Deploy to Live**

If paper trading aligns with backtest (after 30+ trades):
- Change `RUN_MODE=LIVE` in settings
- Restart bot
- Monitor closely for first week

---

## 🎨 Customizing the Chart

### Theme Colors

Edit `BacktestChart.tsx` to change colors:

```typescript
// Dark theme (current)
background: { type: ColorType.Solid, color: "#0a0a0a" }
textColor: "#d1d5db"

// Light theme (example)
background: { type: ColorType.Solid, color: "#ffffff" }
textColor: "#1f1f1f"
```

### Trade Marker Colors

```typescript
// Bullish trades
upColor: "#22c55e"  // Green

// Bearish trades
downColor: "#ef4444"  // Red
```

### Zone Colors

```typescript
// Demand zones
color: "#22c55e"  // Green

// Supply zones
color: "#ef4444"  // Red
```

---

## 📈 Advanced Features

### Export Backtest Results

Add export functionality to save results:

```typescript
// In BacktestDashboard page
const handleExport = () => {
  const data = {
    config,
    stats: backtestResult?.stats,
    trades: backtestResult?.trades,
  };

  const blob = new Blob([JSON.stringify(data, null, 2)], {
    type: "application/json",
  });

  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `backtest_${config.symbol}_${new Date().toISOString()}.json`;
  a.click();
};
```

### Compare Multiple Backtests

Run backtests with different AI Guardian filter combinations:

1. **Baseline** (no filters)
2. **Compression only** (default)
3. **All filters** (strictest)

Compare:
- Total trades
- Win rate
- Max drawdown
- Sharpe ratio

Choose the configuration that balances:
- **Quality** (high win rate)
- **Frequency** (enough trades)
- **Risk** (acceptable drawdown)

---

## 🐛 Troubleshooting

### Issue: Chart Not Rendering

**Fix:**
1. Check browser console for errors
2. Ensure `lightweight-charts` is installed: `npm list lightweight-charts`
3. Clear cache: `Ctrl+Shift+R` (Windows) or `Cmd+Shift+R` (Mac)

### Issue: Backtest API Returns 404

**Fix:**
1. Ensure backend is running: `uvicorn main:app --reload`
2. Check [api_backtest.py](../src/api_backtest.py) is imported in `main.py`:

```python
# main.py
from src.api_backtest import router as backtest_router
app.include_router(backtest_router)
```

### Issue: No Trades Generated

**Fix:**
1. Check if AI Guardian filters are too strict
2. Disable filters temporarily: `reject_compression_arrival=False`
3. Increase date range: `days_to_test=180`
4. Check symbol has sufficient data in MetaApi

### Issue: FX Replay is Laggy

**Fix:**
1. Reduce candle count: Test with shorter date range (30 days vs 90 days)
2. Use higher timeframe: 15m or 1h instead of 5m
3. Close other browser tabs to free memory

---

## 📚 Next Steps

1. **Run Your First Backtest**
   - Go to [http://localhost:3000/backtest](http://localhost:3000/backtest)
   - Test EURUSD for Jan 2024 (30 days)
   - Use default settings

2. **Experiment with AI Guardian Filters**
   - Run 3 backtests: No filters, Compression only, All filters
   - Compare results
   - Choose best configuration

3. **Validate Current Live Strategy**
   - Use `/api/bot/validate-strategy` to test your current bot settings
   - Compare live performance vs backtest

4. **Integrate with Your Workflow**
   - Before changing bot parameters → Run backtest
   - Before deploying new symbol → Validate strategy
   - Weekly: Review backtest vs live alignment

---

## 🔥 Pro Tips

1. **Use Realistic Timeframes**
   - Test at least 60-90 days for statistical significance
   - More trades = more reliable results

2. **Match Live Conditions**
   - Use same timeframe as live bot (e.g., 5m)
   - Use realistic commission (0.0002 = ~2 pips)
   - Test on symbols you actually trade

3. **Don't Overfit**
   - Don't optimize until backtest looks perfect
   - If win rate is >80% → probably overfitted
   - Target realistic metrics: 50-60% win rate, 1.5-2.5 R:R

4. **Validate Regularly**
   - Rerun backtests monthly
   - Market conditions change
   - Ensure strategy still works

5. **Use FX Replay for Learning**
   - Watch how zones form
   - See when AI Guardian filters reject trades
   - Understand why trades fail

---

## 📞 Support

- **Issues:** [GitHub Issues](https://github.com/anthropics/claude-code/issues)
- **Documentation:** [/docs](../docs/)
- **API Reference:** [http://localhost:8000/docs](http://localhost:8000/docs)

Happy backtesting! 🚀
