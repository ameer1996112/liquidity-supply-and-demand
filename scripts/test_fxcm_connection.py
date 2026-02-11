"""
FXCM Connection Test Script

Verifies FXCM API token and tests data fetching.

Usage:
    python scripts/test_fxcm_connection.py

Environment:
    FXCM_API_TOKEN - Your FXCM API token (required)
    FXCM_ENVIRONMENT - "demo" or "live" (default: demo)
"""

from __future__ import annotations

import logging
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

# Add app to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
load_dotenv()

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)


def test_fxcmpy_import():
    """Test 1: Verify fxcmpy is installed."""
    logger.info("=" * 60)
    logger.info("TEST 1: Checking fxcmpy installation")
    logger.info("=" * 60)

    try:
        import fxcmpy
        logger.info(f"✅ fxcmpy installed (version: {fxcmpy.__version__})")
        return True
    except ImportError:
        logger.error("❌ fxcmpy not installed")
        logger.info("Install with: pip install fxcmpy")
        return False


def test_fxcm_connection():
    """Test 2: Connect to FXCM and verify credentials."""
    logger.info("\n" + "=" * 60)
    logger.info("TEST 2: Testing FXCM connection")
    logger.info("=" * 60)

    api_token = os.getenv("FXCM_API_TOKEN")
    environment = os.getenv("FXCM_ENVIRONMENT", "demo")

    if not api_token:
        logger.error("❌ FXCM_API_TOKEN not set in environment")
        logger.info("Set it with: export FXCM_API_TOKEN=your_token")
        return False

    try:
        import fxcmpy

        logger.info(f"Connecting to FXCM ({environment})...")
        server = "demo" if environment == "demo" else "real"
        con = fxcmpy.fxcmpy(access_token=api_token, log_level="error", server=server)

        logger.info("✅ Connected to FXCM!")

        # Get account info
        account_ids = con.get_accounts()
        logger.info(f"\n📊 Account Info:")
        logger.info(f"   - Account IDs: {account_ids}")

        # Get account summary
        if account_ids:
            summary = con.get_accounts_summary()
            logger.info(f"   - Balance: ${summary['balance'].iloc[0]:,.2f}")
            logger.info(f"   - Equity: ${summary['equity'].iloc[0]:,.2f}")
            logger.info(f"   - Currency: {summary['currency'].iloc[0]}")

        # Get available instruments
        instruments = con.get_instruments()
        logger.info(f"\n📈 Available Instruments: {len(instruments)} total")
        logger.info(f"   Sample: {', '.join(instruments[:10])}")

        con.close()
        return True

    except Exception as e:
        logger.error(f"❌ Connection failed: {e}")
        logger.info("\nTroubleshooting:")
        logger.info("  1. Check token is valid (regenerate in FXCM Trading Station)")
        logger.info("  2. Verify environment is correct (demo vs live)")
        logger.info("  3. Check internet connection")
        return False


def test_data_fetch():
    """Test 3: Fetch sample candles."""
    logger.info("\n" + "=" * 60)
    logger.info("TEST 3: Testing data fetch")
    logger.info("=" * 60)

    from app.data_loader_fxcm import get_candles_fxcm

    # Fetch last 100 M5 candles (~ 8 hours)
    to_date = datetime.now(timezone.utc)
    from_date = to_date - timedelta(hours=24)

    symbols = ["EURUSD", "XAUUSD"]
    timeframe = "m5"

    for symbol in symbols:
        logger.info(f"\n📊 Fetching {symbol} ({timeframe})...")
        logger.info(f"   From: {from_date}")
        logger.info(f"   To: {to_date}")

        try:
            df = get_candles_fxcm(
                symbol=symbol,
                from_date=from_date,
                to_date=to_date,
                timeframe=timeframe,
                force_fetch=True  # Skip cache for test
            )

            if df is not None and len(df) > 0:
                logger.info(f"✅ Fetched {len(df)} candles")
                logger.info(f"   First candle: {df.iloc[0]['time']}")
                logger.info(f"   Last candle: {df.iloc[-1]['time']}")
                logger.info(f"   Sample: O={df.iloc[-1]['open']:.5f}, "
                          f"H={df.iloc[-1]['high']:.5f}, "
                          f"L={df.iloc[-1]['low']:.5f}, "
                          f"C={df.iloc[-1]['close']:.5f}")
            else:
                logger.warning(f"⚠️  No candles returned for {symbol}")

        except Exception as e:
            logger.error(f"❌ Fetch failed for {symbol}: {e}")

    return True


def test_cache():
    """Test 4: Verify Parquet caching works."""
    logger.info("\n" + "=" * 60)
    logger.info("TEST 4: Testing Parquet cache")
    logger.info("=" * 60)

    from app.data_loader_fxcm import get_candles_fxcm

    to_date = datetime.now(timezone.utc)
    from_date = to_date - timedelta(hours=24)

    # First fetch (from API)
    logger.info("First fetch (should hit API)...")
    df1 = get_candles_fxcm(
        symbol="EURUSD",
        from_date=from_date,
        to_date=to_date,
        timeframe="m5",
        force_fetch=True
    )

    # Second fetch (from cache)
    logger.info("\nSecond fetch (should use cache)...")
    df2 = get_candles_fxcm(
        symbol="EURUSD",
        from_date=from_date,
        to_date=to_date,
        timeframe="m5",
        force_fetch=False
    )

    if len(df1) == len(df2):
        logger.info("✅ Cache working correctly!")
        logger.info(f"   Cached: {len(df2)} candles")
    else:
        logger.warning("⚠️  Cache mismatch")

    # Check cache file exists
    cache_path = Path("data/backtest_candles/EURUSD/m5")
    if cache_path.exists():
        files = list(cache_path.glob("*.parquet"))
        logger.info(f"   Cache files: {len(files)}")
        if files:
            logger.info(f"   Latest: {files[-1].name}")
    else:
        logger.warning("   Cache directory not found")

    return True


def main():
    logger.info("╔" + "═" * 58 + "╗")
    logger.info("║" + " " * 15 + "FXCM CONNECTION TEST" + " " * 23 + "║")
    logger.info("╚" + "═" * 58 + "╝")

    results = []

    # Test 1: fxcmpy installation
    results.append(("fxcmpy installed", test_fxcmpy_import()))

    if not results[-1][1]:
        logger.info("\n⚠️  Install fxcmpy first: pip install fxcmpy")
        sys.exit(1)

    # Test 2: FXCM connection
    results.append(("FXCM connection", test_fxcm_connection()))

    if not results[-1][1]:
        logger.info("\n⚠️  Fix connection issues before proceeding")
        sys.exit(1)

    # Test 3: Data fetch
    results.append(("Data fetch", test_data_fetch()))

    # Test 4: Cache
    results.append(("Parquet cache", test_cache()))

    # Summary
    logger.info("\n" + "=" * 60)
    logger.info("TEST SUMMARY")
    logger.info("=" * 60)

    for test_name, passed in results:
        status = "✅ PASS" if passed else "❌ FAIL"
        logger.info(f"{status} - {test_name}")

    all_passed = all(r[1] for r in results)

    if all_passed:
        logger.info("\n" + "=" * 60)
        logger.info("🎉 ALL TESTS PASSED!")
        logger.info("=" * 60)
        logger.info("\nYou're ready to run backtests with FXCM!")
        logger.info("Next steps:")
        logger.info("  1. Run backtest: python -m app.backtest_run --symbol XAUUSD --from 2026-01-01 --to 2026-02-10")
        logger.info("  2. Or launch dashboard: streamlit run app/app.py")
    else:
        logger.error("\n⚠️  Some tests failed. Check logs above.")
        sys.exit(1)


if __name__ == "__main__":
    main()
