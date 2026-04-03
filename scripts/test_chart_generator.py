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


TEST_CASES = [
    # (symbol, side, entry, sl, tp, zone_type)
    ("EURUSD", "BUY", 1.0850, 1.0820, 1.0910, "demand"),
    ("GBPJPY", "SELL", 193.500, 194.000, 192.500, "supply"),
    ("USDJPY", "BUY", 149.500, 149.200, 150.100, None),
    ("XAUUSD", "BUY", 2340.50, 2335.00, 2355.00, "demand"),
    ("NAS100", "SELL", 18250.0, 18350.0, 18050.0, "supply"),
    ("BTCUSD", "BUY", 68500.0, 67800.0, 70200.0, None),
    ("NZDJPY", "BUY", 93.500, 93.200, 94.100, "demand"),
    ("GBPCAD", "SELL", 1.7250, 1.7300, 1.7150, "supply"),
]


def main():
    save_to_disk = "--save" in sys.argv
    filter_symbol = None
    for arg in sys.argv[1:]:
        if arg != "--save":
            filter_symbol = arg.upper()

    cases = TEST_CASES
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
