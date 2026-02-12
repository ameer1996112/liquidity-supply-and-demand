#!/usr/bin/env python3
"""
Test script for MetaApi Backtest System

Tests the complete backtest pipeline:
1. MetaApiDataLoader - fetch historical candles
2. SndStrategy - run backtest
3. API endpoint - full integration test

Usage:
    # Test data loader only
    python scripts/test_backtest.py --test-data

    # Test strategy only (requires data)
    python scripts/test_backtest.py --test-strategy

    # Test API endpoint
    python scripts/test_backtest.py --test-api

    # Run all tests
    python scripts/test_backtest.py --all

    # Run quick test with sample data
    python scripts/test_backtest.py --quick

Prerequisites:
    - Set environment variables: META_API_TOKEN, META_API_ACCOUNT_ID
    - Or pass as command line args: --token YOUR_TOKEN --account YOUR_ACCOUNT_ID
"""

import argparse
import json
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

import pandas as pd
import requests
from backtesting import Backtest

from src.services.backtest_engine import SndStrategy
from src.services.data_loader import MetaApiDataLoader

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def test_data_loader(token: str, account_id: str, symbol: str = "EURUSD", region: str = "new-york") -> pd.DataFrame:
    """
    Test MetaApiDataLoader - fetch 1 week of 5m candles.

    Args:
        token: MetaApi token
        account_id: MetaApi account ID
        symbol: Trading symbol (default: EURUSD)
        region: MetaApi region (default: new-york)

    Returns:
        pandas DataFrame with candles
    """
    logger.info("=" * 60)
    logger.info("TEST 1: MetaApiDataLoader")
    logger.info("=" * 60)

    # Use safe historical date range (January 2024)
    # Avoid using datetime.now() in case system clock is wrong
    # MetaApi format: YYYY-MM-DDTHH:MM:SSZ (no milliseconds!)
    start_str = "2024-01-01"  # Will be converted to 2024-01-01T00:00:00Z
    end_str = "2024-01-31"    # Will be converted to 2024-01-31T00:00:00Z

    logger.info(f"Fetching {symbol} candles from {start_str} to {end_str}")

    try:
        loader = MetaApiDataLoader(token=token, account_id=account_id, region=region)
        df = loader.fetch_candles(
            symbol=symbol,
            start_time=start_str,
            end_time=end_str,
            timeframe="5m",
        )

        logger.info(f"✅ Successfully fetched {len(df)} candles")
        logger.info(f"Date range: {df.index[0]} to {df.index[-1]}")
        logger.info(f"\nFirst 5 candles:\n{df.head()}")
        logger.info(f"\nDataFrame info:\n{df.info()}")

        return df

    except Exception as exc:
        logger.error(f"❌ Data loader test failed: {exc}")
        raise


def test_strategy(
    df: pd.DataFrame,
    symbol: str = "EURUSD",
    initial_cash: float = 10000.0,
) -> None:
    """
    Test SndStrategy - run backtest on provided data.

    Args:
        df: pandas DataFrame with OHLCV data
        symbol: Trading symbol for position sizing (default: EURUSD)
        initial_cash: Initial account balance (default: $10k)
    """
    logger.info("=" * 60)
    logger.info("TEST 2: SndStrategy Backtest")
    logger.info("=" * 60)

    try:
        bt = Backtest(
            df,
            SndStrategy,
            cash=initial_cash,
            commission=0.0002,  # 2 pips commission
            margin=0.02,  # 50:1 leverage (forex)
            exclusive_orders=True,
        )

        logger.info(f"Running backtest on {len(df)} candles (symbol={symbol})...")
        stats = bt.run(symbol=symbol, account_size_usd=initial_cash)

        logger.info("✅ Backtest completed successfully!")
        logger.info("\n" + "=" * 60)
        logger.info("BACKTEST RESULTS")
        logger.info("=" * 60)
        logger.info(f"Total Trades:       {stats['# Trades']}")
        logger.info(f"Win Rate:           {stats['Win Rate [%]']:.2f}%")
        logger.info(f"Total Return:       {stats['Return [%]']:.2f}%")
        logger.info(f"Sharpe Ratio:       {stats['Sharpe Ratio']:.2f}")
        logger.info(f"Max Drawdown:       {stats['Max. Drawdown [%]']:.2f}%")
        logger.info(f"Profit Factor:      {stats.get('Profit Factor', 0.0):.2f}")
        logger.info(f"Final Equity:       ${stats['Equity Final [$]']:.2f}")
        logger.info(f"Exposure Time:      {stats['Exposure Time [%]']:.2f}%")
        logger.info("=" * 60)

        # Show trade details if any trades were executed
        if stats["# Trades"] > 0 and hasattr(stats, "_trades"):
            logger.info("\nTrade Details:")
            logger.info(stats._trades.to_string())

        return stats

    except Exception as exc:
        logger.error(f"❌ Strategy test failed: {exc}")
        raise


def test_api_endpoint(
    symbol: str = "EURUSD",
    start_date: str = None,
    end_date: str = None,
    api_url: str = "http://localhost:8000",
) -> dict:
    """
    Test /api/backtest/run endpoint.

    Args:
        symbol: Trading symbol (default: EURUSD)
        start_date: Start date YYYY-MM-DD (default: 7 days ago)
        end_date: End date YYYY-MM-DD (default: today)
        api_url: API base URL (default: http://localhost:8000)

    Returns:
        Response JSON dict
    """
    logger.info("=" * 60)
    logger.info("TEST 3: API Endpoint Integration")
    logger.info("=" * 60)

    # Default dates
    if not end_date:
        end_date = datetime.now().strftime("%Y-%m-%d")
    if not start_date:
        start_date = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")

    payload = {
        "symbol": symbol,
        "start_date": start_date,
        "end_date": end_date,
        "timeframe": "5m",
        "initial_cash": 10000,
        "risk_percent": 0.5,
        "min_rr_ratio": 2.0,
        "stop_buffer_pips": 1.0,
    }

    logger.info(f"Sending POST request to {api_url}/api/backtest/run")
    logger.info(f"Payload: {json.dumps(payload, indent=2)}")

    try:
        response = requests.post(
            f"{api_url}/api/backtest/run",
            json=payload,
            timeout=60,
        )

        if response.status_code == 404:
            logger.warning("⚠️ API endpoint not found (404). Is the server running? Skipping API test.")
            return {"skipped": True}

        if response.status_code == 200:
            result = response.json()
            logger.info("✅ API request successful!")
            logger.info(f"\nCandles received: {len(result.get('candles', []))}")
            logger.info(f"Trades executed: {len(result.get('trades', []))}")
            logger.info(f"Equity points: {len(result.get('equity_curve', []))}")
            logger.info(f"\nStats:")
            stats = result.get("stats", {})
            logger.info(f"  Total Trades:   {stats.get('total_trades', 0)}")
            logger.info(f"  Win Rate:       {stats.get('win_rate', 0.0):.2f}%")
            logger.info(f"  Total Return:   {stats.get('total_return', 0.0):.2f}%")
            logger.info(f"  Sharpe Ratio:   {stats.get('sharpe_ratio', 0.0):.2f}")
            logger.info(f"  Max Drawdown:   {stats.get('max_drawdown', 0.0):.2f}%")
            logger.info(f"  Final Equity:   ${result.get('final_equity', 0.0):.2f}")

            return result
        else:
            logger.error(f"❌ API request failed: HTTP {response.status_code}")
            logger.error(f"Response: {response.text}")
            raise RuntimeError(f"API request failed: {response.status_code}")

    except (requests.ConnectionError, requests.ConnectTimeout) as exc:
        logger.warning("⚠️ Cannot connect to API server. Is it running? Skipping API test.")
        return {"skipped": True}
    except Exception as exc:
        logger.error(f"❌ API endpoint test failed: {exc}")
        raise


def quick_test_with_sample_data() -> None:
    """
    Quick test using synthetic sample data (no MetaApi required).

    Generates 1000 candles of synthetic EURUSD data for rapid testing.
    """
    logger.info("=" * 60)
    logger.info("QUICK TEST: Using synthetic sample data")
    logger.info("=" * 60)

    # Generate synthetic data
    import numpy as np

    np.random.seed(42)
    n = 1000

    # Simulate EURUSD price movement (starts at 1.1000)
    base_price = 1.1000
    returns = np.random.normal(0.0001, 0.0005, n)  # Small random returns
    prices = base_price * (1 + returns).cumprod()

    # Create OHLC candles
    dates = pd.date_range(end=datetime.now(), periods=n, freq="5min")

    df = pd.DataFrame(
        {
            "Open": prices + np.random.normal(0, 0.0002, n),
            "High": prices + np.abs(np.random.normal(0, 0.0005, n)),
            "Low": prices - np.abs(np.random.normal(0, 0.0005, n)),
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

    # Run backtest (synthetic EURUSD data)
    test_strategy(df, symbol="EURUSD", initial_cash=10000.0)


def main():
    parser = argparse.ArgumentParser(description="Test MetaApi Backtest System")
    parser.add_argument("--token", help="MetaApi token (or set META_API_TOKEN env var)")
    parser.add_argument("--account", help="MetaApi account ID (or set META_API_ACCOUNT_ID env var)")
    parser.add_argument("--region", default="new-york", help="MetaApi region (default: new-york)")
    parser.add_argument("--symbol", default="EURUSD", help="Trading symbol (default: EURUSD)")
    parser.add_argument("--cash", type=float, default=10000.0, help="Initial cash for backtest (default: 10000)")
    parser.add_argument("--api-url", default="http://localhost:8000", help="API base URL")

    parser.add_argument("--test-data", action="store_true", help="Test data loader only")
    parser.add_argument("--test-strategy", action="store_true", help="Test strategy only")
    parser.add_argument("--test-api", action="store_true", help="Test API endpoint only")
    parser.add_argument("--all", action="store_true", help="Run all tests")
    parser.add_argument("--quick", action="store_true", help="Quick test with synthetic data (no MetaApi)")

    args = parser.parse_args()

    # Quick test (no credentials needed)
    if args.quick:
        quick_test_with_sample_data()
        return

    # Get credentials
    token = args.token or os.getenv("META_API_TOKEN")
    account_id = args.account or os.getenv("META_API_ACCOUNT_ID")

    if not token or not account_id:
        logger.error("❌ MetaApi credentials missing!")
        logger.error("Provide --token and --account arguments or set environment variables:")
        logger.error("  export META_API_TOKEN=your_token")
        logger.error("  export META_API_ACCOUNT_ID=your_account_id")
        logger.error("\nAlternatively, run quick test with synthetic data:")
        logger.error("  python scripts/test_backtest.py --quick")
        sys.exit(1)

    # Determine which tests to run
    run_all = args.all or not (args.test_data or args.test_strategy or args.test_api)

    df = None

    try:
        # Test 1: Data Loader
        if args.test_data or run_all:
            df = test_data_loader(token, account_id, args.symbol, args.region)
            logger.info("✅ Test 1 PASSED\n")

        # Test 2: Strategy
        if args.test_strategy or run_all:
            if df is None:
                logger.info("Fetching data for strategy test...")
                df = test_data_loader(token, account_id, args.symbol, args.region)

            test_strategy(df, symbol=args.symbol, initial_cash=float(args.cash))
            logger.info("✅ Test 2 PASSED\n")

        # Test 3: API Endpoint
        if args.test_api or run_all:
            result = test_api_endpoint(
                symbol=args.symbol,
                api_url=args.api_url,
            )
            if result.get("skipped"):
                logger.info("⚠️ Test 3 SKIPPED (API server not running)\n")
            else:
                logger.info("✅ Test 3 PASSED\n")

        logger.info("=" * 60)
        logger.info("🎉 ALL TESTS PASSED!")
        logger.info("=" * 60)

    except Exception as exc:
        logger.error(f"\n❌ TEST FAILED: {exc}")
        sys.exit(1)


if __name__ == "__main__":
    main()
