#!/usr/bin/env python3
"""
Example: Run Backtest with MetaApi Data

This script demonstrates how to:
1. Fetch historical data from MetaApi
2. Run a backtest with SndStrategy
3. Display results and generate HTML report

Usage:
    # Quick test with synthetic data
    python scripts/run_backtest_example.py --synthetic

    # Real backtest with MetaApi
    export META_API_TOKEN="your-token"
    export META_API_ACCOUNT_ID="your-account-id"
    python scripts/run_backtest_example.py --symbol EURUSD --days 30

    # Custom parameters
    python scripts/run_backtest_example.py \
        --symbol XAUUSD \
        --days 90 \
        --timeframe 15m \
        --risk 0.7 \
        --rr 2.5 \
        --cash 50000

    # Optimize parameters
    python scripts/run_backtest_example.py --symbol EURUSD --optimize
"""

import argparse
import logging
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path

# Add project root to path
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

# Load environment variables from .env file
from dotenv import load_dotenv
load_dotenv(project_root / ".env")

import numpy as np
import pandas as pd
from backtesting import Backtest

from src.services.backtest_engine import SndStrategy
from src.services.data_loader import MetaApiDataLoader

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def generate_synthetic_data(n: int = 2000, symbol: str = "EURUSD") -> pd.DataFrame:
    """
    Generate synthetic OHLC data for testing (no MetaApi required).

    Args:
        n: Number of candles to generate
        symbol: Symbol name (affects base price)

    Returns:
        pandas DataFrame with OHLCV data
    """
    logger.info(f"Generating {n} synthetic candles for {symbol}...")

    np.random.seed(42)

    # Set base price based on symbol
    if "XAU" in symbol or "GOLD" in symbol:
        base_price = 2000.0
        volatility = 2.0
    elif "JPY" in symbol:
        base_price = 150.0
        volatility = 0.15
    else:
        base_price = 1.1000
        volatility = 0.0005

    # Simulate price movement
    returns = np.random.normal(0.0001, volatility / base_price, n)
    prices = base_price * (1 + returns).cumprod()

    # Create OHLC candles
    dates = pd.date_range(end=datetime.now(), periods=n, freq="5min")

    df = pd.DataFrame(
        {
            "Open": prices + np.random.normal(0, volatility * 0.5, n),
            "High": prices + np.abs(np.random.normal(0, volatility, n)),
            "Low": prices - np.abs(np.random.normal(0, volatility, n)),
            "Close": prices,
            "Volume": np.random.randint(100, 1000, n),
        },
        index=dates,
    )

    # Ensure High >= Low
    df["High"] = df[["Open", "High", "Close"]].max(axis=1)
    df["Low"] = df[["Open", "Low", "Close"]].min(axis=1)

    logger.info(f"✅ Generated {len(df)} synthetic candles")
    logger.info(f"Price range: {df['Low'].min():.5f} - {df['High'].max():.5f}")

    return df


def fetch_metaapi_data(
    symbol: str,
    days: int = 30,
    timeframe: str = "5m",
    token: str = None,
    account_id: str = None,
    region: str = "new-york",
) -> pd.DataFrame:
    """
    Fetch historical data from MetaApi.

    Args:
        symbol: Trading symbol (e.g., EURUSD, XAUUSD)
        days: Number of days to fetch (from today backwards)
        timeframe: Candle timeframe (e.g., 5m, 1h, 1d)
        token: MetaApi token (or use META_API_TOKEN env var)
        account_id: MetaApi account ID (or use META_API_ACCOUNT_ID env var)
        region: MetaApi region

    Returns:
        pandas DataFrame with OHLCV data
    """
    # Get credentials
    token = token or os.getenv("META_API_TOKEN")
    account_id = account_id or os.getenv("META_API_ACCOUNT_ID")

    if not token or not account_id:
        raise ValueError(
            "MetaApi credentials missing! Set META_API_TOKEN and META_API_ACCOUNT_ID "
            "environment variables or pass as arguments."
        )

    # Calculate date range
    # Use safe historical dates (avoid future dates if system clock is wrong)
    # Default: fetch last N days from Jan 2024 (safe historical range)
    end_date = datetime(2024, 1, 31)  # Fixed end date
    start_date = end_date - timedelta(days=days)

    logger.info(f"Fetching {symbol} {timeframe} candles from {start_date.date()} to {end_date.date()}...")

    # Estimate candles needed (5m=288/day, 15m=96/day, 1h=24/day, 1d=1/day)
    candles_per_day = {"1m": 1440, "5m": 288, "15m": 96, "30m": 48, "1h": 24, "4h": 6, "1d": 1}
    n_per_day = candles_per_day.get(timeframe, 288)
    limit = min(days * n_per_day + 100, 50000)  # +100 buffer, cap 50k

    # Create loader
    loader = MetaApiDataLoader(token=token, account_id=account_id, region=region)

    # Fetch data (with pagination for >1000 candles)
    df = loader.fetch_candles(
        symbol=symbol,
        start_time=start_date.strftime("%Y-%m-%dT00:00:00.000Z"),
        end_time=end_date.strftime("%Y-%m-%dT23:59:59.999Z"),
        timeframe=timeframe,
        limit=limit,
    )

    if df.empty:
        raise ValueError(f"No data returned for {symbol} {timeframe}")

    logger.info(f"✅ Fetched {len(df)} candles")
    logger.info(f"Date range: {df.index[0]} to {df.index[-1]}")

    return df


def run_backtest(
    df: pd.DataFrame,
    symbol: str = "EURUSD",
    initial_cash: float = 10000.0,
    risk_percent: float = 0.5,
    min_rr_ratio: float = 2.0,
    stop_buffer_pips: float = 1.0,
    commission: float = 0.0002,
) -> dict:
    """
    Run backtest with SndStrategy.

    Args:
        df: pandas DataFrame with OHLCV data
        initial_cash: Initial account balance ($)
        risk_percent: Risk per trade (%)
        min_rr_ratio: Minimum Risk:Reward ratio
        stop_buffer_pips: Stop loss buffer (pips)
        commission: Commission per trade (0.0002 = 2 pips)

    Returns:
        Backtest stats dict
    """
    logger.info("=" * 80)
    logger.info("Running Backtest...")
    logger.info("=" * 80)
    logger.info(f"Candles: {len(df)}")
    logger.info(f"Initial Cash: ${initial_cash:,.2f}")
    logger.info(f"Risk per Trade: {risk_percent}%")
    logger.info(f"Min R:R Ratio: {min_rr_ratio}")
    logger.info(f"Stop Buffer: {stop_buffer_pips} pips")
    logger.info(f"Commission: {commission * 100:.2f}%")
    logger.info("=" * 80)

    # Create backtest
    bt = Backtest(
        df,
        SndStrategy,
        cash=initial_cash,
        commission=commission,
        margin=0.02,  # 50:1 leverage (forex/metals)
        exclusive_orders=True,
    )

    # Run backtest (symbol + account_size_usd required for Pine-aligned position sizing)
    stats = bt.run(
        symbol=symbol,
        account_size_usd=initial_cash,
        risk_percent=risk_percent,
        min_rr_ratio=min_rr_ratio,
        stop_buffer_pips=stop_buffer_pips,
    )

    # Display results
    logger.info("\n" + "=" * 80)
    logger.info("BACKTEST RESULTS")
    logger.info("=" * 80)
    logger.info(f"📊 Total Trades:        {stats['# Trades']}")
    logger.info(f"✅ Win Rate:            {stats['Win Rate [%]']:.2f}%")
    logger.info(f"💰 Total Return:        {stats['Return [%]']:.2f}%")
    logger.info(f"📈 Sharpe Ratio:        {stats['Sharpe Ratio']:.2f}")
    logger.info(f"📉 Max Drawdown:        {stats['Max. Drawdown [%]']:.2f}%")
    logger.info(f"🎯 Profit Factor:       {stats.get('Profit Factor', 0.0):.2f}")
    logger.info(f"💵 Final Equity:        ${stats['Equity Final [$]']:,.2f}")
    logger.info(f"⏱️  Exposure Time:       {stats['Exposure Time [%]']:.2f}%")
    logger.info(f"📅 Avg Trade Duration:  {stats['Avg. Trade Duration']}")

    if stats["# Trades"] > 0:
        logger.info(f"\n💹 Avg Win:              ${stats.get('Avg. Win [%]', 0.0):.2f}%")
        logger.info(f"💸 Avg Loss:             ${stats.get('Avg. Loss [%]', 0.0):.2f}%")
        logger.info(f"🏆 Best Trade:           ${stats.get('Best Trade [%]', 0.0):.2f}%")
        logger.info(f"💥 Worst Trade:          ${stats.get('Worst Trade [%]', 0.0):.2f}%")

    logger.info("=" * 80)

    # Save HTML report
    output_file = project_root / "backtest_results.html"
    bt.plot(filename=str(output_file), open_browser=False)
    logger.info(f"\n📄 HTML report saved to: {output_file}")
    logger.info(f"   Open in browser: file://{output_file}")

    return stats


def optimize_parameters(
    df: pd.DataFrame,
    symbol: str = "EURUSD",
    initial_cash: float = 10000.0,
) -> dict:
    """
    Optimize strategy parameters using backtesting.py optimizer.

    Args:
        df: pandas DataFrame with OHLCV data
        initial_cash: Initial account balance ($)

    Returns:
        Best parameters dict
    """
    logger.info("=" * 80)
    logger.info("Running Parameter Optimization...")
    logger.info("=" * 80)

    bt = Backtest(
        df,
        SndStrategy,
        cash=initial_cash,
        commission=0.0002,
        margin=0.02,  # 50:1 leverage (forex/metals)
    )

    # Define parameter ranges (symbol + account_size fixed for Pine-aligned position sizing)
    stats = bt.optimize(
        symbol=[symbol],
        account_size_usd=[initial_cash],
        risk_percent=[0.3, 0.5, 0.7, 1.0],
        min_rr_ratio=[1.5, 2.0, 2.5, 3.0],
        zone_lookback=range(5, 21, 5),
        stop_buffer_pips=[0.5, 1.0, 1.5, 2.0],
        maximize="Sharpe Ratio",  # Maximize Sharpe Ratio
        constraint=lambda p: p["# Trades"] >= 10,  # At least 10 trades
    )

    logger.info("\n" + "=" * 80)
    logger.info("OPTIMIZATION RESULTS")
    logger.info("=" * 80)
    logger.info(f"Best Parameters:")
    logger.info(f"  Risk %:         {stats._strategy.risk_percent}")
    logger.info(f"  Min R:R:        {stats._strategy.min_rr_ratio}")
    logger.info(f"  Zone Lookback:  {stats._strategy.zone_lookback}")
    logger.info(f"  Stop Buffer:    {stats._strategy.stop_buffer_pips}")
    logger.info(f"\nPerformance:")
    logger.info(f"  Sharpe Ratio:   {stats['Sharpe Ratio']:.2f}")
    logger.info(f"  Total Return:   {stats['Return [%]']:.2f}%")
    logger.info(f"  Win Rate:       {stats['Win Rate [%]']:.2f}%")
    logger.info(f"  Max Drawdown:   {stats['Max. Drawdown [%]']:.2f}%")
    logger.info(f"  Total Trades:   {stats['# Trades']}")
    logger.info("=" * 80)

    return stats


def main():
    parser = argparse.ArgumentParser(description="Run backtest with MetaApi data")

    # Data source
    parser.add_argument(
        "--synthetic",
        action="store_true",
        help="Use synthetic data (no MetaApi required)",
    )
    parser.add_argument("--symbol", default="EURUSD", help="Trading symbol (default: EURUSD)")
    parser.add_argument("--days", type=int, default=30, help="Days of data to fetch (default: 30)")
    parser.add_argument("--timeframe", default="5m", help="Candle timeframe (default: 5m)")

    # MetaApi config
    parser.add_argument("--token", help="MetaApi token (or set META_API_TOKEN env var)")
    parser.add_argument("--account", help="MetaApi account ID (or set META_API_ACCOUNT_ID env var)")
    parser.add_argument("--region", default="new-york", help="MetaApi region (default: new-york)")

    # Backtest parameters
    parser.add_argument("--cash", type=float, default=10000.0, help="Initial cash (default: $10k)")
    parser.add_argument("--risk", type=float, default=0.5, help="Risk per trade %% (default: 0.5)")
    parser.add_argument("--rr", type=float, default=2.0, help="Min R:R ratio (default: 2.0)")
    parser.add_argument("--buffer", type=float, default=1.0, help="Stop buffer pips (default: 1.0)")
    parser.add_argument("--commission", type=float, default=0.0002, help="Commission (default: 0.0002)")

    # Actions
    parser.add_argument("--optimize", action="store_true", help="Run parameter optimization")

    args = parser.parse_args()

    try:
        # 1. Load data
        if args.synthetic:
            df = generate_synthetic_data(n=2000, symbol=args.symbol)
        else:
            df = fetch_metaapi_data(
                symbol=args.symbol,
                days=args.days,
                timeframe=args.timeframe,
                token=args.token,
                account_id=args.account,
                region=args.region,
            )

        # 2. Run backtest or optimization
        if args.optimize:
            stats = optimize_parameters(df, symbol=args.symbol, initial_cash=args.cash)
        else:
            stats = run_backtest(
                df,
                symbol=args.symbol,
                initial_cash=args.cash,
                risk_percent=args.risk,
                min_rr_ratio=args.rr,
                stop_buffer_pips=args.buffer,
                commission=args.commission,
            )

        logger.info("\n✅ Backtest completed successfully!")

    except Exception as exc:
        logger.error(f"\n❌ Backtest failed: {exc}")
        import traceback

        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
