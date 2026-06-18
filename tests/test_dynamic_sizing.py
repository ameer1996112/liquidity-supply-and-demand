"""
Test script: Dynamic Risk Engine position sizing accuracy.

Verifies that calculate_position_size_with_spread produces the correct
lot sizes for a $50k account at 0.5% risk ($250 target) across multiple
symbol types, with and without spread compensation.

Usage:
    python scripts/test_dynamic_sizing.py
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.core.risk_engine import calculate_position_size_with_spread

ACCOUNT_BALANCE = 50000.0
RISK_PERCENT = 0.5  # 0.5% = $250

# ═══════════════════════════════════════════════════════
# Test cases: (symbol, entry, sl, spread, expected_risk_approx)
# ═══════════════════════════════════════════════════════
test_cases = [
    # ── Forex (USD quote) ──
    {
        "name": "EURUSD — 5 pip SL, 1.2 pip spread",
        "payload": {"symbol": "EURUSD", "entry": 1.08500, "sl": 1.08000, "side": "buy"},
        "spread": 0.00012,  # 1.2 pips
        "broker_spec": {"contractSize": 100000, "digits": 5, "minVolume": 0.01, "volumeStep": 0.01, "maxVolume": 100},
    },
    # ── Forex (JPY pair) ──
    {
        "name": "USDJPY — 10 pip SL, 1.5 pip spread",
        "payload": {"symbol": "USDJPY", "entry": 149.500, "sl": 149.400, "side": "buy"},
        "spread": 0.015,  # 1.5 pips
        "broker_spec": {"contractSize": 100000, "digits": 3, "minVolume": 0.01, "volumeStep": 0.01, "maxVolume": 100},
    },
    # ���─ Gold ──
    {
        "name": "XAUUSD — $5 SL (50 pips), $0.20 spread",
        "payload": {"symbol": "XAUUSD", "entry": 2350.00, "sl": 2345.00, "side": "buy"},
        "spread": 0.20,  # 20 pips
        "broker_spec": {"contractSize": 100, "digits": 2, "minVolume": 0.01, "volumeStep": 0.01, "maxVolume": 50},
    },
    # ── Cross pair (non-USD quote) ──
    {
        "name": "GBPCAD — 7 pip SL, 2 pip spread",
        "payload": {"symbol": "GBPCAD", "entry": 1.75000, "sl": 1.74930, "side": "buy"},
        "spread": 0.00020,  # 2 pips
        "broker_spec": {"contractSize": 100000, "digits": 5, "minVolume": 0.01, "volumeStep": 0.01, "maxVolume": 100},
    },
    # ── Index ──
    {
        "name": "NAS100 — 50 point SL, 2 point spread",
        "payload": {"symbol": "NAS100", "entry": 18500.0, "sl": 18450.0, "side": "buy"},
        "spread": 2.0,  # 2 points
        "broker_spec": {"contractSize": 1, "digits": 1, "minVolume": 0.01, "volumeStep": 0.01, "maxVolume": 500},
    },
    # ── No broker spec (fallback) ──
    {
        "name": "EURUSD — fallback (no broker spec), 5 pip SL",
        "payload": {"symbol": "EURUSD", "entry": 1.08500, "sl": 1.08000, "side": "buy"},
        "spread": 0.00012,
        "broker_spec": None,
    },
    # ── Zero spread (no spread data available) ──
    {
        "name": "EURUSD — zero spread, 5 pip SL",
        "payload": {"symbol": "EURUSD", "entry": 1.08500, "sl": 1.08000, "side": "buy"},
        "spread": 0.0,
        "broker_spec": {"contractSize": 100000, "digits": 5, "minVolume": 0.01, "volumeStep": 0.01, "maxVolume": 100},
    },
]

TARGET_RISK = ACCOUNT_BALANCE * RISK_PERCENT / 100.0  # $250

if __name__ == "__main__":
    TARGET_RISK = ACCOUNT_BALANCE * RISK_PERCENT / 100.0  # $250

    print(f"\n{'='*80}")
    print(f"Dynamic Risk Engine Test — Account: ${ACCOUNT_BALANCE:,.0f} | Risk: {RISK_PERCENT}% = ${TARGET_RISK:.0f}")
    print(f"{'='*80}\n")

    all_passed = True

    for tc in test_cases:
        result = calculate_position_size_with_spread(
            payload=tc["payload"],
            account_balance=ACCOUNT_BALANCE,
            risk_percent=RISK_PERCENT,
            spread=tc["spread"],
            broker_spec=tc["broker_spec"],
        )

        symbol = tc["payload"]["symbol"]
        lots = result["lots"]
        risk_usd = result["risk_usd"]
        target = result.get("target_risk_usd", TARGET_RISK)
        sl_pips = result["sl_pips"]
        spread_pips = result["spread_pips"]
        eff_sl = result["effective_sl_pips"]
        pip_val = result["pip_value_per_lot"]
        rejected = result["rejected"]

        # Verify risk is within 10% of target (rounding and lot step cause small deviations)
        deviation = abs(risk_usd - target) / target * 100 if target > 0 else 0
        ok = not rejected and deviation < 10
        status = "✅ PASS" if ok else "❌ FAIL"
        if not ok:
            all_passed = False

        print(f"  {status} | {tc['name']}")
        print(f"         Lots: {lots:.2f} | Risk: ${risk_usd:.2f} / ${target:.2f} target ({deviation:.1f}% off)")
        print(f"         SL: {sl_pips:.1f} pips + {spread_pips:.1f} spread = {eff_sl:.1f} effective | Pip value: ${pip_val:.4f}")
        if rejected:
            print(f"         REJECTED: {result['rejection_reason']}")
        print()

    print(f"{'='*80}")
    print(f"{'✅ ALL TESTS PASSED' if all_passed else '❌ SOME TESTS FAILED'}")
    print(f"{'='*80}\n")

    sys.exit(0 if all_passed else 1)

