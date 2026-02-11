#!/usr/bin/env python3
"""
Fetch REAL XAUUSD data from Meta API and replace synthetic data.

Usage:
  python scripts/fetch_real_gold_data.py
"""
import os
import sys
from pathlib import Path
from datetime import datetime, timezone

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.data import get_candles
from dotenv import load_dotenv

load_dotenv()

def main():
    # Date range (same as your TradingView backtest)
    from_date = datetime(2026, 1, 1, tzinfo=timezone.utc)
    to_date = datetime(2026, 1, 10, 23, 59, 59, tzinfo=timezone.utc)

    # Meta API credentials
    token = os.getenv("META_API_TOKEN_VANTAGE") or os.getenv("META_API_TOKEN")
    account_id = os.getenv("META_API_ACCOUNT_ID_VANTAGE") or os.getenv("META_API_ACCOUNT_ID")

    if not token or not account_id:
        print("❌ ERROR: Meta API credentials not found!")
        print("Set environment variables:")
        print("  - META_API_TOKEN_VANTAGE")
        print("  - META_API_ACCOUNT_ID_VANTAGE")
        return 1

    print(f"✅ Meta API credentials found")
    print(f"📅 Fetching XAUUSD M5 data from {from_date.date()} to {to_date.date()}")

    # Delete synthetic data first
    synthetic_file = Path("data/backtest_candles/XAUUSD/M5/2026-01-01_2026-02-10.csv")
    if synthetic_file.exists():
        print(f"🗑️  Deleting synthetic data: {synthetic_file}")
        synthetic_file.unlink()

    # Fetch real data
    try:
        candles = get_candles(
            symbol="XAUUSD",
            from_date=from_date,
            to_date=to_date,
            timeframe="M5",
            data_dir=Path("data/backtest_candles"),
            metaapi_token=token,
            metaapi_account_id=account_id,
            symbol_aliases={"XAUUSD": ["XAUUSDm", "GOLD"]},
            persist=True,
        )

        print(f"✅ Fetched {len(candles)} real candles")
        print(f"📊 Date range: {candles['time'].min()} to {candles['time'].max()}")
        print(f"💰 Price range: ${candles['low'].min():.2f} - ${candles['high'].max():.2f}")
        print(f"📁 Saved to: data/backtest_candles/XAUUSD/M5/2026-01-01_2026-02-10.parquet")

        # Show sample
        print("\n📋 First 5 candles:")
        print(candles.head().to_string(index=False))

        return 0

    except Exception as e:
        print(f"❌ ERROR fetching data: {e}")
        import traceback
        traceback.print_exc()
        return 1

if __name__ == "__main__":
    sys.exit(main())
