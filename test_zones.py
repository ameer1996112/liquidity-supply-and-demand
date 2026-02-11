#!/usr/bin/env python3
"""Test zone creation after fix."""

import numpy as np
import pandas as pd
from datetime import datetime, timezone
from app.engine_core import FastBacktestEngine
from app.config import BacktestConfig
from app.data_loader_fxcm import load_historical_csv

# Load 2 days of data
from_dt = datetime(2026, 1, 1, tzinfo=timezone.utc)
to_dt = datetime(2026, 1, 3, tzinfo=timezone.utc)
df = load_historical_csv('XAUUSD', from_dt, to_dt, 'M5')

print(f'Loaded {len(df)} candles\n')

# Create config with relaxed thresholds for testing
config = BacktestConfig(
    symbol='XAUUSD',
    timeframe='M5',
    tick_size=0.01,
    pip_size=0.01,
    start_date=from_dt,
    end_date=to_dt,
    account_size_usd=50000.0,
    risk_per_trade_pct=0.5,
    ai_quality_threshold=0.0,  # Allow all zones
    min_bar_index_for_entries=10,  # Lower threshold
)

# Run backtest
engine = FastBacktestEngine(config=config)
trades = engine.run(df)

print(f'\n=== RESULTS ===')
print(f'Trades executed: {len(trades)}')
print(f'Zone manager zone_count: {engine.zone_manager.zone_count}')

demand_count, supply_count = engine.zone_manager.get_active_count()
print(f'Active zones: {demand_count} demand, {supply_count} supply')

# Show first few zones
print(f'\nFirst 5 zones created:')
for i in range(min(5, engine.zone_manager.zone_count)):
    z = engine.zone_manager.zones[i]
    ztype = 'DEMAND' if z['is_demand'] else 'SUPPLY'
    print(f'  Zone {i+1}: {ztype}, active={z["active"]}, created_bar={z["created_bar"]}, score={z["score"]:.1f}')

if len(trades) > 0:
    print(f'\nFirst trade:')
    t = trades[0]
    print(f'  Entry: {t.entry_time}, ${t.entry_price:.2f}')
    print(f'  Exit: {t.exit_time}, ${t.exit_price:.2f}')
    print(f'  P&L: ${t.pnl:.2f}')
else:
    print('\n⚠️  No trades executed. Checking entry conditions...')
    # Check if any zones were primed/swept
    primed = sum(1 for i in range(engine.zone_manager.zone_count) if engine.zone_manager.zones[i]['primed'])
    swept = sum(1 for i in range(engine.zone_manager.zone_count) if engine.zone_manager.zones[i]['liquidity_swept'])
    print(f'  Primed zones: {primed}')
    print(f'  Liquidity swept zones: {swept}')
