#!/usr/bin/env python3
"""
Test chart generator — verify charts render for all asset classes.

Usage:
    python scripts/test_chart_generator.py                    # Test all symbols
    python scripts/test_chart_generator.py EURUSD             # Test one symbol
    python scripts/test_chart_generator.py EURUSD --save      # Save PNG to disk
"""

import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.services.chart_generator import generate_chart_async


def _build_test_cases():
    """Build test cases using current market prices so charts always look correct."""
    import yfinance as yf
    from src.services.chart_generator import YAHOO_TICKER_MAP

    symbols = [
        ("EURUSD", "BUY", "demand", 0.003, 0.006),    # SL 30 pips, TP 60 pips
        ("GBPJPY", "SELL", "supply", 0.500, 1.000),
        ("USDJPY", "BUY", None, 0.300, 0.600),
        ("XAUUSD", "BUY", "demand", 10.0, 25.0),
        ("BTCUSD", "BUY", None, 700.0, 1700.0),
        ("GBPCAD", "SELL", "supply", 0.005, 0.010),
    ]

    cases = []
    for symbol, side, zone_type, sl_dist, tp_dist in symbols:
        ticker_str = YAHOO_TICKER_MAP.get(symbol)
        if not ticker_str:
            continue
        try:
            t = yf.Ticker(ticker_str)
            df = t.history(period="1d", interval="15m")
            if df.empty:
                continue
            price = float(df["Close"].iloc[-1])
        except Exception:
            continue

        if side == "BUY":
            entry = price
            sl = price - sl_dist
            tp = price + tp_dist
        else:
            entry = price
            sl = price + sl_dist
            tp = price - tp_dist

        cases.append((symbol, side, entry, sl, tp, zone_type))

    if not cases:
        # Fallback with static prices if yfinance is unavailable
        cases = [("EURUSD", "BUY", 1.1500, 1.1470, 1.1560, "demand")]

    return cases


TEST_CASES = None  # Built lazily


def main():
    save_to_disk = "--save" in sys.argv
    filter_symbol = None
    for arg in sys.argv[1:]:
        if arg != "--save":
            filter_symbol = arg.upper()

    print("Fetching current prices for test cases...")
    cases = _build_test_cases()
    if filter_symbol:
        cases = [c for c in cases if c[0] == filter_symbol]
        if not cases:
            print(f"No test case for {filter_symbol}. Available: {[c[0] for c in TEST_CASES]}")
            return

    passed = 0
    failed = 0

    for symbol, side, entry, sl, tp, zone_type in cases:
        print(f"\n{'='*60}")
        print(f"Testing: {symbol} {side} entry={entry} sl={sl} tp={tp} zone={zone_type}")
        print(f"{'='*60}")

        result = generate_chart_async(
            symbol=symbol,
            side=side,
            entry=entry,
            sl=sl,
            tp=tp,
            signal_id=9999,
            zone_type=zone_type,
        )

        if result:
            size_kb = len(result) / 1024
            print(f"  OK  {symbol}: {size_kb:.1f} KB PNG generated")
            passed += 1

            if save_to_disk:
                os.makedirs("tmp/charts", exist_ok=True)
                path = f"tmp/charts/{symbol}_{side}.png"
                with open(path, "wb") as f:
                    f.write(result)
                print(f"  Saved to {path}")
        else:
            print(f"  FAIL  {symbol}: No chart generated (check logs)")
            failed += 1

    print(f"\n{'='*60}")
    print(f"Results: {passed} passed, {failed} failed out of {passed + failed}")
    if failed == 0:
        print("All charts generated successfully!")
    else:
        print("Some charts failed — check yfinance availability for those symbols.")


if __name__ == "__main__":
    main()
