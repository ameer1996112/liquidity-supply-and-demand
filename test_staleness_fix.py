"""Quick verification that the staleness guard pip fix is correct."""
import sys
sys.path.insert(0, '.')

from src.core.guard_rails.staleness_guard import get_pip_size, get_deviation_threshold

BASE = 3.0

cases = [
    # (symbol, signal_price, current_price, expected_result)
    ("NAS100",  25008.29, 25079.50, "PASS"),   # 71.21 pts / 1.0 = 71.21 < 150 → PASS
    ("US30",    39000.00, 39120.00, "PASS"),   # 120 pts < 150 → PASS
    ("SPX500",  5200.00,  5350.00,  "PASS"),   # 150 pts == threshold → PASS (guard uses >, not >=)
    ("SPX500",  5200.00,  5351.00,  "REJECT"), # 151 pts > 150 threshold → REJECT
    ("EURUSD",  1.10000,  1.10035,  "REJECT"), # 3.5 pips > 3.0 → REJECT
    ("EURUSD",  1.10000,  1.10025,  "PASS"),   # 2.5 pips < 3.0 → PASS
    ("USDJPY",  150.000,  150.040,  "REJECT"), # 4 pips > 3.0 → REJECT
    ("USDJPY",  150.000,  150.020,  "PASS"),   # 2 pips < 3.0 → PASS
    ("XAUUSD",  2650.00,  2650.10,  "PASS"),   # 10 pips < 15 → PASS
    ("XAUUSD",  2650.00,  2651.60,  "REJECT"), # 160 pips > 15 → REJECT
    ("BTCUSD",  70000.0,  70450.0,  "PASS"),   # 450 pts < 600 → PASS
    ("BTCUSD",  70000.0,  70700.0,  "REJECT"), # 700 pts > 600 → REJECT
]

print(f"{'Symbol':<10} {'pip_size':<10} {'deviation':>12} {'threshold':>12}  {'expected':<8} {'actual':<8} {'ok'}")
print("-" * 75)

all_ok = True
for sym, sig, cur, expected in cases:
    ps  = get_pip_size(sym)
    thr = get_deviation_threshold(sym, BASE)
    dev = abs(cur - sig) / ps
    actual = "PASS" if dev <= thr else "REJECT"
    ok = "✅" if actual == expected else "❌ FAIL"
    if actual != expected:
        all_ok = False
    print(f"{sym:<10} {ps:<10} {dev:>12.2f} {thr:>12.1f}  {expected:<8} {actual:<8} {ok}")

print()
print("All tests passed ✅" if all_ok else "SOME TESTS FAILED ❌")
