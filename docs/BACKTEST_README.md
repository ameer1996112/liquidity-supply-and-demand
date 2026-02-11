# SND Backtesting System – Session Summary

This document summarizes the backtesting system built for the SND (Supply & Demand) strategy, aligned with TradingView Pine v6 logic.

---

## Quick Start

```bash
# 1. Run backtest
python -m app.backtest_run --symbol XAUUSD --from 2026-01-01 --to 2026-02-10 --no-fetch

# 2. Generate chart
python -m app.backtest_chart --symbol XAUUSD --from 2026-01-01 --to 2026-02-10
```

---

## What Was Built

### 1. Backtesting Engine
- **Bar-by-bar execution** matching TradingView Pine semantics
- `process_orders_on_close=True` – orders filled at bar close
- `pyramiding=0` – single position only
- `slippage=3` ticks
- Time-based exit after 36 bars (max_bars_held)

### 2. SND Strategy (Ported from Pine)
- **Zone creation** – Demand/supply patterns from bullish/bearish reversals
- **Priming** – liquidity sweep + target swept + caused sweep required
- **Entry models** – FLIP, DirClose, BreakOfCandle (same order as Pine)
- **Touch check** – Demand: low inside zone; Supply: high inside zone

### 3. Strategy Logic Alignment
| Fix | Description |
|-----|-------------|
| Block historical zones | No entries from backfill zones (`is_historical=True`) |
| **Pivot liquidity** | 3-candle Makuchaku pivots; inducement above zone (demand) |
| targetSwept | Demand: high ≥ liq_high; Supply: low ≤ liq_low |
| causedSweep | Set when liquidity sweep detected |
| touchedPreSweep | Zone invalid if touched before sweep (mitigation) |
| liq_entry_max_dist | Zone within N pips of liquidity |
| 24h freshness | Zone must be < 24h old |
| Touch in zone | Low/high must be inside `[z.bottom, z.top]` |

### 4. Strategy Tester (Streamlit)
- Equity curve, trade list, summary metrics
- Filter by side, entry model, exit reason

### 5. Chart (TradingView-Style)
- Candlestick chart with entry markers
- SL/TP lines (last 3 trades)
- Uses Lightweight Charts (TradingView)

---

## Commands Reference

### Backtest
```bash
# With MetaApi (fetches candles)
python -m app.backtest_run --symbol XAUUSD --from 2026-01-01 --to 2026-02-10

# Local data only
python -m app.backtest_run --symbol XAUUSD --from 2026-01-01 --to 2026-02-10 --no-fetch

# Debug: log each trade with entry model
python -m app.backtest_run --symbol XAUUSD --from 2026-01-01 --to 2026-02-10 --no-fetch --debug-trades
```

### Chart
```bash
python -m app.backtest_chart --symbol XAUUSD --from 2026-01-01 --to 2026-02-10

# Don't open browser
python -m app.backtest_chart --symbol XAUUSD --from 2026-01-01 --to 2026-02-10 --no-open
```

### Strategy Tester (Streamlit)
```bash
streamlit run app/backtest_viewer.py
```

### Parity Check (Python vs TradingView)
```bash
python -m app.parity_check --tv trades_tv.csv --py trades.csv
```

---

## File Structure

```
app/
├── config.py          # BacktestConfig (Pine inputs)
├── data.py            # MetaApi / Parquet / CSV data pipeline
├── engine.py          # BacktestEngine, Order, Position, ClosedTrade
├── snd_utils.py       # Helpers from SND_Utils.pine
├── snd_core.py        # Zone, scoring from SND_Core.pine
├── snd_strategy.py    # SNDStrategy (zone creation, priming, entries)
├── outputs.py         # trades.csv, equity.csv, summary
├── backtest_run.py    # CLI
├── backtest_chart.py  # Chart generator (HTML + Lightweight Charts)
├── backtest_viewer.py # Streamlit Strategy Tester
└── parity_check.py   # TV vs Python trade comparison

data/
├── backtest_candles/{symbol}/{timeframe}/  # Candle data (CSV/Parquet)
└── backtest/{symbol}/
    ├── trades.csv     # Trade list (entry, exit, SL, TP, zone)
    ├── equity.csv     # Equity curve
    └── chart.html     # Interactive chart
```

---

## Outputs

### zones.csv (when using legacy engine)
| Column | Description |
|--------|-------------|
| zone_id, type | Demand/supply zone ID and type |
| created_bar, created_time | Bar index and timestamp when zone was created |
| top, bottom | Zone boundaries |
| is_accuracy, is_historical | Zone flags |
| score, grade | Quality score (0–100) and grade (A+–C) |

Use for overlaying demand/supply zones on charts.

### trades.csv
| Column | Description |
|--------|-------------|
| entry_time, exit_time | Timestamps |
| side | long / short |
| entry_price, exit_price | Fill prices |
| pnl, pnl_pct | PnL |
| bars_held | Bars in trade |
| reason | stop / limit / time |
| entry_model | FLIP / BREAK_CANDLE / DIR_CLOSE |
| stop_price, limit_price | SL/TP levels |
| zone_bottom, zone_top | Zone boundaries |

### chart.html
- Candlesticks (green/red)
- Entry markers: L/S + entry model
- SL/TP lines (last 3 trades)
- Opens in browser

---

## Data Pipeline

1. **Local first** – `data/backtest_candles/{symbol}/{timeframe}/{from}_{to}.csv` or `.parquet`
2. **MetaApi** – If missing, fetch (requires `META_API_TOKEN_VANTAGE`, `META_API_ACCOUNT_ID_VANTAGE`)
3. **Schema** – `time`, `open`, `high`, `low`, `close`, `volume` (UTC)

---

## Known Differences vs Pine

| Area | Pine | Python |
|------|------|--------|
| Liquidity | Pivot-based inducement/target | ✅ Pivot-based (ported) |
| touchedPreSweep | Invalid if touched before sweep | ✅ Tracked |
| liq_entry_max_dist | 50 pips | ✅ Enforced |
| Mitigation | Kill zone on touch before sweep | ✅ Implemented |
| Timezone | Asia/Jerusalem | UTC |
| Candle direction | Hammer / inv. hammer | Body only |

See `docs/PINE_TO_PYTHON_SPEC.md` for full logic mapping.

---

## Dependencies

- `streamlit` – Strategy Tester UI
- `pandas`, `numpy` – Data
- `python-dotenv` – .env loading
- MetaApi for live candle fetch (optional)

---

## Related Docs

- `docs/BACKTEST_SYSTEM.md` – Full system docs
- `docs/STRATEGY_LOGIC_AUDIT.md` – Pine vs Python logic audit
