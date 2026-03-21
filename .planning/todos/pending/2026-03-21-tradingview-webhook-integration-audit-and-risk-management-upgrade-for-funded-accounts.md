---
created: 2026-03-21T13:58:19.000Z
title: TradingView webhook integration audit and risk management upgrade for funded accounts
area: api
files:
  - src/api.py
  - src/worker.py
  - src/core/risk_engine.py
  - src/core/guard_rails/prop_guard.py
  - config/settings.py
---

## Problem

Two connected needs:

**1. TradingView → Bot integration audit**
The bot receives webhook payloads from TradingView (S&D Algo [Pro] strategy) and executes trades on MetaTrader via Vantage broker. Need to verify the full payload flow is correct end-to-end:
- What fields TradingView sends (symbol, side, entry, sl, tp, size, signal_time, bar_time, zone_id, etc.)
- How `src/api.py` receives and validates the payload at `POST /webhook`
- How `src/worker.py` consumes the signal from Redis and routes it through guard rails → risk engine → execution
- Whether the SL/TP/size values from Pine Script are used as-is or recalculated
- Whether any fields are being dropped or misinterpreted

**2. Risk management upgrade for funded accounts (prop firm pass + long-term profitability)**
Review and optimize the risk management pipeline:
- Current strategy backtest shows -4.96% P&L, 28.57% win rate (63 trades) — clearly not passing FTMO-style challenges as-is
- Need to tune: AI filter thresholds, ML guardian confidence, session filters, correlation limits, and BE/trail parameters
- Ensure Trinity engine limits are appropriate for each phase (Phase 1 / Phase 2 / Funded)
- Add or improve: max consecutive loss protection, daily drawdown recovery logic, RR ratio enforcement
- Goal: system should reliably pass funded account challenges and compound profits over time

## Solution

### Phase A — Integration Audit
1. Document the full webhook payload schema (what Pine sends vs what the bot expects)
2. Trace a single signal through the stack: API → Redis → worker → guards → execution → DB
3. Fix any field mapping issues or dropped data
4. Add a `/webhook/debug` endpoint (dry-run mode) that logs full parsed payload without executing

### Phase B — Risk Management Upgrade
1. Audit current guard rail settings per instrument type (forex vs indices vs gold)
2. Tune AI_MIN_CONFIDENCE and ML_MIN_CONFIDENCE based on historical signal results
3. Implement consecutive loss streak protection (e.g. reduce size 50% after 3 losses in a row)
4. Enforce minimum RR ratio per symbol class
5. Add funded account profile presets (FTMO Phase1 / Phase2 / Funded) that auto-apply correct limits
6. Backtest the optimized configuration against historical signals
