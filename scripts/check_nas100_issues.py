#!/usr/bin/env python3
"""
NAS100 Diagnostic Script
Identifies why NAS100 isn't triggering trades
"""

from datetime import datetime
import pytz

print("=" * 80)
print("🔍 NAS100 TRADING DIAGNOSTIC")
print("=" * 80)
print()

print("📊 PINE SCRIPT FILTERS AFFECTING NAS100:")
print()

print("1. ⏰ TIMING FILTERS (CRITICAL ISSUE FOR NAS100)")
print("-" * 80)
print("   Setting: filter_trading_hours = TRUE")
print("   Hours: 07:00 - 22:00 Israel time (Asia/Jerusalem)")
print()
print("   🚨 PROBLEM: This blocks most of NAS100's active trading hours!")
print()
print("   NAS100 US Market Hours (Israel Time):")
israel_tz = pytz.timezone('Asia/Jerusalem')
et_tz = pytz.timezone('America/New_York')

# Regular market hours in ET
market_open_et = datetime.now(et_tz).replace(hour=9, minute=30, second=0)
market_close_et = datetime.now(et_tz).replace(hour=16, minute=0, second=0)

# Convert to Israel time
market_open_israel = market_open_et.astimezone(israel_tz)
market_close_israel = market_close_et.astimezone(israel_tz)

print(f"   • US Market Open (9:30 AM ET)  → {market_open_israel.strftime('%H:%M')} Israel")
print(f"   • US Market Close (4:00 PM ET) → {market_close_israel.strftime('%H:%M')} Israel")
print()

# Check if blocked
blocked_hours = []
for hour in range(24):
    if hour < 7 or hour >= 22:
        blocked_hours.append(hour)

print(f"   ❌ BLOCKED: {blocked_hours[:7]} and {blocked_hours[7:]} Israel time")
print()

# Calculate overlap
if market_close_israel.hour >= 22:
    print(f"   ⚠️  WARNING: US market close ({market_close_israel.strftime('%H:%M')}) is AFTER")
    print("      the 22:00 Israel cutoff, blocking afternoon US session!")
print()

print("2. ⏰ DEAD ZONE FILTER")
print("-" * 80)
print("   Setting: filter_dead_zone = TRUE")
print("   Blocks: Last 10 minutes of each hour (XX:50 - XX:00)")
print("   Impact: ~16% of trading time blocked (10 min/hour)")
print()

print("3. 🎯 ACCURACY ZONES DISABLED FOR INDICES")
print("-" * 80)
print("   Setting: should_use_accuracy_zones = FALSE for NAS100")
print("   Impact: Only normal zones allowed (no accuracy zones)")
print("   Status: ✅ This is CORRECT (indices don't support accuracy zones)")
print()

print("4. 🔄 HTF FLIP REQUIREMENT")
print("-" * 80)
print("   Setting: require_htf_flip = TRUE (depends on profile)")
print("   Requirement: Flip entries only near 30m/1H candle opens")
print("   Impact: Restricts flip entry timing (first 10 min of each 30min)")
print()

print()
print("=" * 80)
print("💡 RECOMMENDED FIXES FOR NAS100")
print("=" * 80)
print()

print("🎯 OPTION 1: Disable Timing Filters in Pine Script (Quick Fix)")
print("-" * 80)
print("In your Pine Script settings, change:")
print()
print("   Filter Trading Hours (07:00-22:00):  FALSE  (disable)")
print("   Filter Dead Zone (xx:50-xx:00):      FALSE  (disable)")
print()
print("This allows NAS100 to trade during full US market hours.")
print()

print("🎯 OPTION 2: Use Aggressive Profile")
print("-" * 80)
print("Configuration Profile → 'Aggressive (Paper Trading)'")
print()
print("This automatically sets:")
print("   • filter_dead_zone: FALSE")
print("   • filter_trading_hours: FALSE")
print("   • Less strict filters overall")
print()

print("🎯 OPTION 3: Create NAS100-Specific Timing Rules")
print("-" * 80)
print("Modify Pine Script to detect NAS100 and use different hours:")
print()
print("   if is_index")
print("       // Use US market hours for indices")
print("       trading_start_hour := 14  // 7:00 AM ET")
print("       trading_end_hour := 23    // 4:00 PM ET")
print("   else")
print("       // Use Israel hours for Forex")
print("       trading_start_hour := 7")
print("       trading_end_hour := 22")
print()

print()
print("=" * 80)
print("🔍 OTHER POTENTIAL ISSUES")
print("=" * 80)
print()

print("1. No Valid Setups Found")
print("   Check Strategy Tester in TradingView:")
print("   • Are there ANY trades on NAS100 chart?")
print("   • If NO → Filters too strict or no valid zones created")
print()

print("2. TradingView Alert Not Created")
print("   • Alert must be created with webhook URL")
print("   • Message: {{strategy.order.alert_message}}")
print()

print("3. Zone Creation Issues")
print("   Check chart for:")
print("   • Are zones being drawn?")
print("   • Are they showing zone IDs (D-XXX, S-XXX)?")
print("   • Are liquidity sweeps happening?")
print()

print()
print("=" * 80)
print("✅ IMMEDIATE ACTION STEPS")
print("=" * 80)
print()
print("1. Open NAS100 chart in TradingView")
print("2. Open Pine Script settings")
print("3. Set Configuration Profile → 'Aggressive (Paper Trading)'")
print("   OR manually disable:")
print("   • Filter Trading Hours → FALSE")
print("   • Filter Dead Zone → FALSE")
print("4. Check if Strategy Tester shows trades now")
print("5. If YES → Create TradingView alert with webhook")
print()
print("🔗 Webhook URL: https://grand-learning-production-bc96.up.railway.app/webhook")
print()
print("=" * 80)
