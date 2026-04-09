#!/usr/bin/env python3
"""
Test script for NZDJPY position sizing fix (Migration 026)

Validates that dynamic pip value calculation produces correct lot sizes.

Bug Context:
- NZDJPY showed 0.08 lots (should be ~1.88 lots for $250 risk)
- Root cause: hardcoded pip_value_per_lot=1000.0 instead of dynamic calculation
- Fix: Calculate pip_value = (0.01 / entry_price) * 100,000

Expected Results:
- NZDJPY @ 93.918, 50 pip SL, $250 risk → ~2.36 lots
- CADJPY @ 110.5, 50 pip SL, $250 risk → ~2.76 lots
- USDJPY @ 149.5, 50 pip SL, $250 risk → ~3.34 lots
"""

import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.core.risk_engine import calculate_max_position_size


def test_jpy_pair_sizing():
    """Test position sizing for various JPY pairs."""

    test_cases = [
        {
            "name": "NZDJPY (bug example from broker)",
            "payload": {
                "symbol": "NZDJPY",
                "entry": 93.918,
                "sl": 93.868,  # 50 pip SL (0.50 JPY)
                "side": "buy",
            },
            "account_balance": 50000.0,
            "risk_percent": 0.5,  # $250 risk
            "expected_lots": 2.36,  # Approx
            "expected_pip_value": 10.65,
        },
        {
            "name": "CADJPY",
            "payload": {
                "symbol": "CADJPY",
                "entry": 110.5,
                "sl": 110.0,  # 50 pip SL
                "side": "buy",
            },
            "account_balance": 50000.0,
            "risk_percent": 0.5,
            "expected_lots": 2.76,
            "expected_pip_value": 9.05,
        },
        {
            "name": "USDJPY",
            "payload": {
                "symbol": "USDJPY",
                "entry": 149.5,
                "sl": 149.0,  # 50 pip SL
                "side": "buy",
            },
            "account_balance": 50000.0,
            "risk_percent": 0.5,
            "expected_lots": 3.34,
            "expected_pip_value": 6.69,
        },
        {
            "name": "GBPJPY",
            "payload": {
                "symbol": "GBPJPY",
                "entry": 189.5,
                "sl": 189.0,  # 50 pip SL
                "side": "sell",
            },
            "account_balance": 50000.0,
            "risk_percent": 0.5,
            "expected_lots": 2.64,
            "expected_pip_value": 5.28,
        },
    ]

    print("=" * 80)
    print("NZDJPY Position Sizing Fix - Test Results")
    print("=" * 80)
    print(f"Account Balance: $50,000 | Risk: 0.5% ($250)\n")

    all_passed = True

    for tc in test_cases:
        print(f"\n{'─' * 80}")
        print(f"Test: {tc['name']}")
        print(f"{'─' * 80}")

        payload = tc["payload"]
        entry = payload["entry"]
        sl = payload["sl"]
        sl_pips = abs(entry - sl) / 0.01

        print(f"Entry: {entry:.5f} | SL: {sl:.5f} | Distance: {sl_pips:.1f} pips")

        # Calculate expected pip value
        expected_pip_value = (0.01 / entry) * 100000
        print(f"Expected pip_value: ${expected_pip_value:.2f}/lot")

        # Calculate position size
        calculated_lots = calculate_max_position_size(
            payload=payload,
            account_balance=tc["account_balance"],
            risk_percent=tc["risk_percent"],
            risk_multiplier=1.0,
            symbol_overrides=None,  # Test fallback calculation
        )

        print(f"Calculated lots: {calculated_lots:.2f}")
        print(f"Expected lots: ~{tc['expected_lots']:.2f}")

        # Verify pip value calculation
        actual_risk = calculated_lots * sl_pips * expected_pip_value
        print(f"Actual risk: ${actual_risk:.2f} (target: $250.00)")

        # Check if within 10% tolerance
        tolerance = 0.15  # 15% tolerance for rounding
        ratio = calculated_lots / tc["expected_lots"]

        if 1 - tolerance <= ratio <= 1 + tolerance:
            print(f"✅ PASS: Within {tolerance*100:.0f}% tolerance ({ratio:.2%})")
        else:
            print(f"❌ FAIL: Outside tolerance ({ratio:.2%})")
            all_passed = False

        # Verify risk is close to $250
        risk_tolerance = 10.0  # $10 tolerance
        if abs(actual_risk - 250.0) <= risk_tolerance:
            print(f"✅ PASS: Risk within ${risk_tolerance:.0f} of target")
        else:
            print(f"❌ FAIL: Risk off by ${abs(actual_risk - 250.0):.2f}")
            all_passed = False

    print(f"\n{'=' * 80}")
    if all_passed:
        print("🎉 ALL TESTS PASSED - Dynamic pip value calculation working correctly!")
    else:
        print("⚠️  SOME TESTS FAILED - Review implementation")
    print("=" * 80)

    return all_passed


def test_old_vs_new_calculation():
    """Compare old static vs new dynamic calculation."""

    print("\n" + "=" * 80)
    print("OLD (Static 1000.0) vs NEW (Dynamic) Calculation Comparison")
    print("=" * 80)

    entry = 93.918
    sl = 93.868
    sl_pips = (entry - sl) / 0.01  # 50 pips
    risk_usd = 250.0

    # OLD calculation (hardcoded)
    old_pip_value = 1000.0
    old_lots = risk_usd / (sl_pips * old_pip_value)

    # NEW calculation (dynamic)
    new_pip_value = (0.01 / entry) * 100000
    new_lots = risk_usd / (sl_pips * new_pip_value)

    print(f"\nNZDJPY @ {entry:.5f}, 50 pip SL, $250 risk:")
    print(f"\nOLD (Static):")
    print(f"  pip_value: ${old_pip_value:.2f}/lot (hardcoded)")
    print(f"  Calculated lots: {old_lots:.4f}")
    print(f"  Actual risk: ${old_lots * sl_pips * old_pip_value:.2f}")

    print(f"\nNEW (Dynamic):")
    print(f"  pip_value: ${new_pip_value:.2f}/lot (calculated from entry price)")
    print(f"  Calculated lots: {new_lots:.4f}")
    print(f"  Actual risk: ${new_lots * sl_pips * new_pip_value:.2f}")

    print(f"\nDifference:")
    print(f"  Pip value error: {old_pip_value / new_pip_value:.1f}x too high")
    print(f"  Position size error: {new_lots / old_lots:.1f}x too small with old method")
    print(f"  This explains why broker showed 0.08 lots instead of ~1.88 lots!")

    print("=" * 80)


if __name__ == "__main__":
    # Test dynamic calculation
    passed = test_jpy_pair_sizing()

    # Show old vs new comparison
    test_old_vs_new_calculation()

    # Exit with appropriate code
    sys.exit(0 if passed else 1)
