# MetaApi Backtest System - Complete Guide

## 🎯 Overview

A production-ready Python backtesting system for the **SND (Supply & Demand) Strategy** that runs on **real MetaTrader 5 data** fetched via **MetaApi REST API**.

### Key Features

✅ **Real MT5 Data** - Fetch historical candles from your broker (Vantage FX, FTMO, Oanda)
✅ **Python Strategy** - SND_Strategy.pine converted to Python using `backtesting.py`
✅ **FastAPI Integration** - Run backtests via REST API
✅ **Lightweight-Charts Format** - Results ready for frontend visualization
✅ **Full Statistics** - Win rate, Sharpe ratio, drawdown, profit factor, etc.
✅ **Optimizable Parameters** - Risk %, R:R ratio, zone lookback, stop buffer

---

## 📁 Architecture

### 1. **Data Loader** (`src/services/data_loader.py`)

```python
from src.services.data_loader import MetaApiDataLoader

loader = MetaApiDataLoader(
    token="your-metaapi-token",
    account_id="your-account-id",
    region="new-york"
)

df = loader.fetch_candles(
    symbol="EURUSD",
    start_time="2024-01-01",
    end_time="2024-12-31",
    timeframe="5m"
)
```

**Supported Timeframes:**
- `1m`, `5m`, `15m`, `30m`, `1h`, `4h`, `1d`
- TradingView format: `M5`, `M15`, `H1`, `H4`, `D1`

**Data Format:**
```
                       Open     High      Low    Close  Volume
2024-01-01 00:00:00  1.10450  1.10480  1.10420  1.10455   1200
2024-01-01 00:05:00  1.10455  1.10490  1.10430  1.10470   1350
...
```

---

### 2. **Backtest Engine** (`src/services/backtest_engine.py`)

Converts SND_Strategy.pine logic to Python:

**Core Features:**
- ✅ **Supply/Demand Zone Detection** - Swing high/low identification
- ✅ **Break of Candle (BoC)** - Entry trigger: close > previous high (demand) / close < previous low (supply)
- ✅ **Zone Strength Scoring** - Volume, rejection wicks, ATR normalization
- ✅ **Position Sizing** - Risk-based lot calculation (0.5% default)
- ✅ **Stop Loss Buffer** - 1.0 pip cushion beyond zone boundary
- ✅ **R:R Validation** - Minimum 2:1 risk-reward ratio

**Strategy Parameters (Optimizable):**

| Parameter | Default | Description |
|-----------|---------|-------------|
| `risk_percent` | 0.5 | Risk per trade (% of account balance) |
| `min_rr_ratio` | 2.0 | Minimum Risk:Reward ratio |
| `zone_lookback` | 10 | Bars to look back for swing detection |
| `zone_strength_min` | 50.0 | Minimum zone strength to trade (0-100) |
| `stop_buffer_pips` | 1.0 | Extra pips added to SL beyond zone |
| `max_lot_size` | 10.0 | Maximum position size (lots) |

**Example Usage:**

```python
from backtesting import Backtest
from src.services.backtest_engine import SndStrategy

bt = Backtest(
    df,
    SndStrategy,
    cash=10000,
    commission=0.0002  # 2 pips
)

stats = bt.run(
    risk_percent=0.5,
    min_rr_ratio=2.0,
    stop_buffer_pips=1.0
)

print(stats)
bt.plot()  # Interactive HTML chart
```

---

### 3. **API Endpoint** (`src/api_backtest.py`)

**POST /api/backtest/run** - Run a backtest

**Request Body:**
```json
{
  "symbol": "EURUSD",
  "start_date": "2024-01-01",
  "end_date": "2024-12-31",
  "timeframe": "5m",
  "initial_cash": 10000,
  "commission": 0.0002,

  // Optional strategy overrides
  "risk_percent": 0.5,
  "min_rr_ratio": 2.0,
  "zone_lookback": 10,
  "stop_buffer_pips": 1.0,

  // Optional MetaApi config (or use env vars)
  "meta_api_token": "your-token",
  "meta_api_account_id": "your-account-id",
  "meta_api_region": "new-york"
}
```

**Response:**
```json
{
  "success": true,
  "message": "Backtest completed successfully",

  "candles": [
    {
      "time": 1704067200,  // Unix timestamp
      "open": 1.10450,
      "high": 1.10480,
      "low": 1.10420,
      "close": 1.10455,
      "volume": 1200
    }
  ],

  "trades": [
    {
      "entry_time": 1704070800,
      "exit_time": 1704074400,
      "entry_price": 1.10500,
      "exit_price": 1.10600,
      "size": 0.5,
      "pnl": 50.0,
      "pnl_percent": 0.5,
      "side": "long",
      "return_pct": 0.5
    }
  ],

  "equity_curve": [
    {"time": 1704067200, "equity": 10000.0},
    {"time": 1704074400, "equity": 10050.0}
  ],

  "stats": {
    "total_trades": 25,
    "winning_trades": 18,
    "losing_trades": 7,
    "win_rate": 72.0,
    "total_return": 15.5,
    "sharpe_ratio": 1.8,
    "max_drawdown": -5.2,
    "profit_factor": 2.4,
    "avg_win": 120.0,
    "avg_loss": -50.0
  },

  "final_equity": 11550.0,
  "candles_count": 8640
}
```

**GET /api/backtest/health** - Health check

---

## 🚀 Quick Start

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

New dependencies added:
- `backtesting>=0.3.3` - Backtest framework

### 2. Configure MetaApi Credentials

**Option A: Environment Variables**
```bash
export META_API_TOKEN="your-metaapi-token"
export META_API_ACCOUNT_ID="your-account-id"
export META_API_REGION="new-york"  # Optional
```

**Option B: Pass in API request**
```json
{
  "meta_api_token": "...",
  "meta_api_account_id": "..."
}
```

### 3. Start API Server

```bash
uvicorn src.api:app --reload --port 8000
```

### 4. Run Your First Backtest

**Method A: Using cURL**
```bash
curl -X POST http://localhost:8000/api/backtest/run \
  -H "Content-Type: application/json" \
  -d '{
    "symbol": "EURUSD",
    "start_date": "2024-01-01",
    "end_date": "2024-03-31",
    "timeframe": "5m",
    "initial_cash": 10000,
    "risk_percent": 0.5,
    "min_rr_ratio": 2.0
  }'
```

**Method B: Using Python**
```python
import requests

response = requests.post(
    "http://localhost:8000/api/backtest/run",
    json={
        "symbol": "EURUSD",
        "start_date": "2024-01-01",
        "end_date": "2024-03-31",
        "timeframe": "5m",
        "initial_cash": 10000
    }
)

result = response.json()
print(f"Trades: {result['stats']['total_trades']}")
print(f"Win Rate: {result['stats']['win_rate']:.1f}%")
print(f"Total Return: {result['stats']['total_return']:.2f}%")
```

**Method C: Run Test Script**
```bash
# Quick test with synthetic data (no MetaApi needed)
python scripts/test_backtest.py --quick

# Full test with MetaApi
python scripts/test_backtest.py --all --token YOUR_TOKEN --account YOUR_ACCOUNT

# Test individual components
python scripts/test_backtest.py --test-data
python scripts/test_backtest.py --test-strategy
python scripts/test_backtest.py --test-api
```

---

## 📊 Frontend Integration

### Render Candles with Lightweight-Charts

```typescript
import { createChart } from 'lightweight-charts';

// Fetch backtest results
const response = await fetch('/api/backtest/run', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    symbol: 'EURUSD',
    start_date: '2024-01-01',
    end_date: '2024-12-31',
    timeframe: '5m'
  })
});

const data = await response.json();

// Create chart
const chart = createChart(document.getElementById('chart'), {
  width: 800,
  height: 400
});

const candleSeries = chart.addCandlestickSeries();
candleSeries.setData(data.candles);  // ✅ Ready to use!

// Add trade markers
data.trades.forEach(trade => {
  candleSeries.setMarkers([
    {
      time: trade.entry_time,
      position: trade.side === 'long' ? 'belowBar' : 'aboveBar',
      color: trade.pnl > 0 ? '#26a69a' : '#ef5350',
      shape: trade.side === 'long' ? 'arrowUp' : 'arrowDown',
      text: `Entry: ${trade.entry_price.toFixed(5)}`
    }
  ]);
});

// Add equity curve
const equityChart = createChart(document.getElementById('equity-chart'));
const equityLine = equityChart.addLineSeries({ color: '#2962FF' });
equityLine.setData(data.equity_curve);
```

---

## 🔧 Advanced Usage

### Parameter Optimization

```python
from backtesting import Backtest
from src.services.backtest_engine import SndStrategy

# Load data
df = loader.fetch_candles("EURUSD", "2024-01-01", "2024-12-31", "5m")

# Run optimization
bt = Backtest(df, SndStrategy, cash=10000, commission=0.0002)

stats = bt.optimize(
    risk_percent=[0.3, 0.5, 0.7, 1.0],
    min_rr_ratio=[1.5, 2.0, 2.5, 3.0],
    zone_lookback=range(5, 21, 5),
    stop_buffer_pips=[0.5, 1.0, 1.5, 2.0],
    maximize='Sharpe Ratio',  # Or 'Return [%]', 'Profit Factor'
    constraint=lambda p: p['Max. Drawdown [%]'] < 15.0
)

print(f"Optimal parameters: {stats._strategy}")
print(f"Sharpe Ratio: {stats['Sharpe Ratio']:.2f}")
```

### Walk-Forward Analysis

```python
# Train on Q1-Q3, test on Q4
train_df = loader.fetch_candles("EURUSD", "2024-01-01", "2024-09-30", "5m")
test_df = loader.fetch_candles("EURUSD", "2024-10-01", "2024-12-31", "5m")

# Optimize on training data
bt_train = Backtest(train_df, SndStrategy, cash=10000)
best_params = bt_train.optimize(
    risk_percent=[0.3, 0.5, 0.7],
    min_rr_ratio=[1.5, 2.0, 2.5],
    maximize='Sharpe Ratio'
)

# Test on out-of-sample data
bt_test = Backtest(test_df, SndStrategy, cash=10000)
test_stats = bt_test.run(**best_params._strategy)

print(f"Training Sharpe: {best_params['Sharpe Ratio']:.2f}")
print(f"Test Sharpe: {test_stats['Sharpe Ratio']:.2f}")
```

---

## 🐛 Troubleshooting

### Issue: "No candles found"
**Cause:** Invalid date range or symbol not available on broker
**Fix:**
- Check symbol is correctly spelled (e.g., `EURUSD` not `EUR/USD`)
- Verify date range is within broker's historical data availability
- Try a different timeframe (e.g., `1h` instead of `5m` for older data)

### Issue: "MetaApi credentials missing"
**Cause:** Token/Account ID not provided
**Fix:**
```bash
export META_API_TOKEN="your-token-here"
export META_API_ACCOUNT_ID="your-account-id"
```

### Issue: "Module 'backtesting' not found"
**Cause:** Missing dependency
**Fix:**
```bash
pip install backtesting>=0.3.3
```

### Issue: "API request timeout"
**Cause:** Large date range or slow MetaApi response
**Fix:**
- Reduce date range (try 1 month instead of 1 year)
- Increase timeout in API call: `timeout=120`
- Use higher timeframe (`1h` instead of `5m`)

### Issue: "No trades executed"
**Cause:** Strategy parameters too restrictive or no signals in data
**Fix:**
- Lower `zone_strength_min` (e.g., from 50 to 30)
- Lower `min_rr_ratio` (e.g., from 2.0 to 1.5)
- Check if data has enough volatility (try different symbol/period)

---

## 📈 Performance Metrics Explained

| Metric | Description | Good Value |
|--------|-------------|------------|
| **Win Rate** | % of winning trades | > 50% |
| **Sharpe Ratio** | Risk-adjusted returns | > 1.0 |
| **Max Drawdown** | Largest peak-to-trough decline | < 15% |
| **Profit Factor** | Gross profit / Gross loss | > 1.5 |
| **Avg Win / Avg Loss** | Average $ per winning vs losing trade | > 1.5:1 |
| **Exposure Time** | % of time in the market | 30-60% |

---

## 🔐 Security Best Practices

1. **Never commit `.env` files** with MetaApi tokens
2. **Use environment variables** for production deployments
3. **Rotate tokens** regularly (every 90 days)
4. **Limit API access** to specific IPs in MetaApi dashboard
5. **Use read-only tokens** for backtesting (no trading permissions needed)

---

## 🚀 Deployment

### Railway / Heroku / DigitalOcean

```bash
# Set environment variables in platform dashboard
META_API_TOKEN=your-token
META_API_ACCOUNT_ID=your-account-id
META_API_REGION=new-york

# Build command
pip install -r requirements.txt

# Start command
uvicorn src.api:app --host 0.0.0.0 --port $PORT
```

### Docker

```dockerfile
FROM python:3.11-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .

ENV META_API_TOKEN=""
ENV META_API_ACCOUNT_ID=""

CMD ["uvicorn", "src.api:app", "--host", "0.0.0.0", "--port", "8000"]
```

```bash
docker build -t trading-backtest .
docker run -p 8000:8000 \
  -e META_API_TOKEN=your-token \
  -e META_API_ACCOUNT_ID=your-account \
  trading-backtest
```

---

## 📚 API Reference

### Data Loader Methods

#### `MetaApiDataLoader.__init__(token, account_id, region="new-york")`
Initialize data loader with MetaApi credentials.

#### `fetch_candles(symbol, start_time, end_time, timeframe="5m", limit=10000)`
Fetch historical candles and return pandas DataFrame.

#### `get_latest_price(symbol)`
Get current bid/ask prices for a symbol.

### Strategy Parameters

#### `SndStrategy.init()`
Initialize strategy indicators and state variables.

#### `SndStrategy.next()`
Execute strategy logic on each bar (called by backtesting.py).

---

## 📞 Support

- **Issues:** [GitHub Issues](https://github.com/your-repo/issues)
- **Docs:** [Full Documentation](./README.md)
- **MetaApi Docs:** [https://metaapi.cloud/docs](https://metaapi.cloud/docs)

---

## ✅ Next Steps

1. ✅ **Test the system** - Run `python scripts/test_backtest.py --quick`
2. ✅ **Run with real data** - Configure MetaApi credentials and fetch EURUSD
3. ✅ **Optimize parameters** - Use `bt.optimize()` to find best settings
4. ✅ **Build frontend** - Integrate with lightweight-charts
5. ✅ **Deploy to production** - Use Railway/Heroku with env vars

---

**Built with ❤️ for institutional-grade backtesting on real MT5 data.**
