#!/usr/bin/env python3
"""
Quick test script to run XAUUSD backtest with enhanced logging.
"""

import sys
import logging
import os
from datetime import datetime, timedelta
import pandas as pd
import numpy as np
from backtesting import Backtest
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Setup logging to see INFO level
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Add src to path
sys.path.insert(0, '/Users/ameeramer/dev/projects/galilsoftware/sources/trading')

from src.services.backtest_engine import SndStrategy
from src.services.data_loader import MetaApiDataLoader

def main():
    """Run XAUUSD backtest with enhanced logging"""
    logger.info("=" * 80)
    logger.info("XAUUSD BACKTEST - Enhanced Logging Test")
    logger.info("=" * 80)

    # 1. Fetch XAUUSD data
    symbol = "XAUUSD"
    timeframe = "5m"
    start_date = datetime(2026, 1, 1)
    end_date = datetime(2026, 2, 12)

    logger.info(f"Fetching {symbol} {timeframe} data from {start_date} to {end_date}...")

    # Get MetaAPI credentials from environment
    meta_token = os.getenv("META_API_TOKEN")
    meta_account = os.getenv("META_API_ACCOUNT_ID")

    if not meta_token or not meta_account:
        logger.error("Missing META_API_TOKEN or META_API_ACCOUNT_ID in environment")
        return

    loader = MetaApiDataLoader(token=meta_token, account_id=meta_account)
    df = loader.fetch_candles(
        symbol=symbol,
        timeframe=timeframe,
        start_time=start_date,
        end_time=end_date
    )

    logger.info(f"Fetched {len(df)} candles")
    logger.info(f"Date range: {df.index[0]} to {df.index[-1]}")
    logger.info(f"Columns: {list(df.columns)}")

    # 2. Run backtest with Aggressive profile
    logger.info("\nRunning backtest with Aggressive profile...")

    bt = Backtest(
        df,
        SndStrategy,
        cash=10000,
        commission=0.00005,
        exclusive_orders=True,
        finalize_trades=True  # Close all open trades at end for accurate stats
    )

    # Aggressive profile settings
    stats = bt.run(
        symbol=symbol,  # NEW: Pass symbol for instrument-specific logic
        risk_percent=10.0,  # 10% risk for reasonable position sizes
        min_rr_ratio=2.0,
        zone_lookback=100,
        stop_buffer_pips=1.0,
        require_liquidity_sweep=True,
        liq_pivot_len=2,
        liq_entry_max_dist=500.0,  # Gold needs larger distance (500 pips vs 50 default)
        ai_quality_threshold=60,
        min_entry_grade="C+",
        entry_model="AUTO"
    )

    # 3. Print results
    logger.info("\n" + "=" * 80)
    logger.info("BACKTEST RESULTS")
    logger.info("=" * 80)
    logger.info(f"Total Trades: {stats['# Trades']}")
    logger.info(f"Win Rate: {stats.get('Win Rate [%]', 0):.2f}%")
    logger.info(f"Total Return: {stats['Return [%]']:.2f}%")
    logger.info(f"Max Drawdown: {stats['Max. Drawdown [%]']:.2f}%")
    logger.info(f"Sharpe Ratio: {stats.get('Sharpe Ratio', 0):.2f}")
    logger.info(f"Final Equity: ${stats['Equity Final [$]']:.2f}")
    logger.info(f"Initial Cash: ${stats.get('Equity Initial [$]', 10000):.2f}")
    logger.info(f"Equity Peak: ${stats.get('Equity Peak [$]', 10000):.2f}")

    # Print ALL stats for debugging
    logger.info("\nALL STATS:")
    for key, value in stats.items():
        if not key.startswith('_'):
            logger.info(f"  {key}: {value}")

    if stats['# Trades'] == 0:
        logger.warning("\n⚠️  TRADES DETECTED (equity changed) but not counted as 'trades'. Checking _trades...")
        logger.warning(f"Stats type: {type(stats)}")
        if hasattr(stats, '_trades'):
            logger.warning(f"_trades: {stats._trades}")

    logger.info("=" * 80)

if __name__ == "__main__":
    main()
