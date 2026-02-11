# TradingView Pine v6 Backtesting System

Python backtesting system matching TradingView Pine v6 strategy semantics for the SND (Supply & Demand) strategy.

## Summary

### Pine Inputs + Execution Assumptions Extracted

| Property | Value |
|----------|-------|
| `process_orders_on_close` | `true` – orders filled at bar close |
| `pyramiding` | `0` – no stacking positions |
| `slippage` | `3` ticks |
| `commission_type` | `percent`, `commission_value` = 0 |
| `default_qty_type` | `fixed`, `default_qty_value` = 100 |
| `calc_on_every_tick` | `false` – evaluate once per bar |

**Key inputs (Balanced profile):**
- `config_profile`: Balanced (Recommended)
- `trade_direction`: Both
- `account_size_usd`: 50000
- `risk_per_trade_pct`: 0.5
- `stop_loss_buffer_pips`: 1.0
- `ai_quality_threshold`: 60
- `max_trades_per_day`: 2
- `trading_start_hour`: 7 (UTC), `trading_end_hour`: 22 (UTC)
- `filter_dead_zone`: true (block xx:50–xx:00)
- `require_htf_flip`: true (flip entries at :00, :15, :30, :45)

### Folder Structure

```
app/
├── __init__.py
├── config.py       # BacktestConfig dataclass (Pine inputs)
├── data.py         # Data pipeline: MetaApi / Parquet / CSV
├── engine.py       # Bar-by-bar execution engine
├── snd_utils.py    # Ported from SND_Utils.pine
├── snd_core.py     # Zone, scoring (from SND_Core.pine)
├── snd_strategy.py # Stateful strategy (zone creation, priming, entries)
├── outputs.py      # trades.csv, equity, summary
├── backtest_run.py # CLI: python -m app.backtest_run
└── parity_check.py # CLI: python -m app.parity_check
```

### Key Classes

- **BacktestConfig** – All Pine inputs as a dataclass
- **BacktestEngine** – Event-driven engine: `process_bar()`, `run()`
- **SNDStrategy** – `on_bar(bar_idx, bar, history, has_position) -> list[Order]`
- **Zone** – Demand/supply zone dataclass

### Parity Drift Logging

The system logs:
- `tick_size` (configurable; XAUUSD default 0.01)
- `timezone` (UTC)
- `slippage` (3 ticks)
- Bar alignment (timeframe boundaries)

## Usage

### Run Backtest

```bash
# With MetaApi (fetches candles, persists to Parquet)
python -m app.backtest_run --symbol XAUUSD --from 2026-01-01 --to 2026-02-10 --timeframe M5

# Local data only (no MetaApi fetch)
python -m app.backtest_run --symbol XAUUSD --from 2026-01-01 --to 2026-02-10 --timeframe M5 --no-fetch
```

Requires `META_API_TOKEN_VANTAGE` and `META_API_ACCOUNT_ID_VANTAGE` (or `META_API_TOKEN` / `META_API_ACCOUNT_ID`) when fetching.

### Strategy Tester (View Results)

A TradingView-style UI to view backtest results: equity curve, trade list, summary metrics.

```bash
# 1. Run backtest first
python -m app.backtest_run --symbol XAUUSD --from 2026-01-01 --to 2026-02-10 --no-fetch

# 2. Launch Strategy Tester (requires: pip install streamlit)
streamlit run app/backtest_viewer.py
```

Opens a web UI at `http://localhost:8501` with:
- **Performance Summary** – Net profit, win rate, profit factor, etc.
- **Equity Curve** – Account balance over time
- **Trade List** – Filterable by side, entry model (FLIP/DIR_CLOSE/BREAK_CANDLE), exit reason

### Chart (TradingView-Style)

Interactive candlestick chart with trade markers, SL/TP lines, and zone boundaries:

```bash
# 1. Run backtest first (writes trades with stop_price, limit_price, zone)
python -m app.backtest_run --symbol XAUUSD --from 2026-01-01 --to 2026-02-10 --no-fetch

# 2. Generate chart
python -m app.backtest_chart --symbol XAUUSD --from 2026-01-01 --to 2026-02-10
```

Creates `data/backtest/XAUUSD/chart.html` and opens in browser. Shows:
- **Candlesticks** – Price data (green/red)
- **Entry markers** – L/S + entry model (FLIP, BREAK_CANDLE, DIR_CLOSE) at entry price
- **Exit markers** – Purple markers at exit with PnL
- **SL/TP lines** – Red dashed (SL), green dashed (TP)
- **Zone lines** – Demand (teal) / supply (red) zone boundaries

### Parity Check

```bash
python -m app.parity_check --tv trades_tv.csv --py trades.csv
```

Input: TradingView "List of Trades" CSV export. Matches by (entry_time, side) with price tolerance in ticks.

### Create Sample Candles

```bash
python scripts/create_sample_candles.py
```

## Data Pipeline

1. **Local first**: Load from `data/backtest_candles/{symbol}/{timeframe}/{from}_{to}.parquet` or `.csv`
2. **MetaApi**: If missing, fetch from MetaApi historical candles API (different hostname)
3. **Persist**: Save to Parquet when fetching
4. **Schema**: `time`, `open`, `high`, `low`, `close`, `volume` (UTC, bar close time)

## Tests

```bash
pytest tests/unit/test_backtest.py -v
```

Covers: tick rounding, slippage, candle normalization, deterministic engine run, single entry/exit.

## Ambiguities (Config + Warning)

- **tick_size**: XAUUSD commonly 0.01; configurable via `--tick-size`
- **Symbol suffix**: MT5 may use `XAUUSDm`; `symbol_aliases` in config
- **Bid/ask vs mid**: Uses `close` for fill (mid); slippage models spread
