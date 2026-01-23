#!/usr/bin/env python3
"""
Trading Bot Diagnostic Script
Checks why you're not receiving real trading alerts
"""

import os
import sys
from datetime import datetime, timedelta
from dotenv import load_dotenv

# Add parent directory to path to import from tests
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'tests'))
load_dotenv(os.path.join(os.path.dirname(__file__), '..', 'tests', '.env'))

from supabase import create_client

SUPABASE_URL = os.getenv('SUPABASE_URL')
SUPABASE_KEY = os.getenv('SUPABASE_ANON_KEY')

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

print("=" * 80)
print("🔍 TRADING BOT DIAGNOSTIC REPORT")
print("=" * 80)
print(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")

# Check alerts from last 7 days
seven_days_ago = (datetime.now() - timedelta(days=7)).isoformat()
result = supabase.table('trading_signals').select('*').gte('created_at', seven_days_ago).order('created_at', desc=True).execute()

total_alerts = len(result.data)
print(f"📊 ALERTS IN LAST 7 DAYS: {total_alerts}\n")

if total_alerts == 0:
    print("❌ NO ALERTS RECEIVED!")
    print("\nPossible causes:")
    print("1. TradingView alert not created or configured incorrectly")
    print("2. Pine Script 'Enable Webhook Alerts' is disabled")
    print("3. Webhook URL in TradingView alert is wrong")
    print("4. Pine Script has no valid setups (filters too strict)")
    sys.exit(1)

# Analyze alerts
test_alerts = [a for a in result.data if a.get('zone_id') in [12345, 99999]]
real_alerts = [a for a in result.data if a.get('zone_id') not in [12345, 99999]]
filtered = [a for a in result.data if a.get('status') == 'filtered']
active = [a for a in result.data if a.get('status') == 'active']

print(f"📈 ALERT BREAKDOWN:")
print(f"  • Test alerts (zone_id 12345/99999): {len(test_alerts)}")
print(f"  • Real strategy alerts: {len(real_alerts)}")
print(f"  • Filtered: {len(filtered)}")
print(f"  • Active (not filtered): {len(active)}\n")

if len(real_alerts) == 0:
    print("⚠️  WARNING: NO REAL STRATEGY ALERTS!")
    print("\nThis means your Pine Script is NOT generating actual trades.")
    print("\nTroubleshooting steps:")
    print("1. Check TradingView Chart:")
    print("   • Are there any BUY/SELL signals on the chart?")
    print("   • Are zones being created?")
    print("   • Check the strategy tester - any trades executed?")
    print("\n2. Check Pine Script Settings:")
    print("   • Configuration Profile: Should match your testing (Conservative/Balanced/Aggressive)")
    print("   • Enable Webhook Alerts: Must be TRUE")
    print("   • Min Entry Grade: Check if it's too strict (try 'C' for testing)")
    print("   • AI Quality Threshold: Lower it temporarily (try 30-40)")
    print("   • Min Return Strength: Set to 0 for testing")
    print("\n3. Create TradingView Alert:")
    print("   • Chart → Add Alert → Condition: Your Strategy Name")
    print("   • Webhook URL: https://grand-learning-production-bc96.up.railway.app/webhook")
    print("   • Message: Use {{strategy.order.alert_message}}")
    print()

# Show filter reasons
if len(filtered) > 0:
    print("🚫 FILTERED ALERTS ANALYSIS:")
    from collections import Counter
    reasons = Counter([a.get('notes') for a in filtered])
    for reason, count in reasons.most_common():
        print(f"  • {reason}: {count}")
    print()

# Show recent alerts
print("📋 RECENT ALERTS (Last 5):")
for alert in result.data[:5]:
    created = alert.get('created_at', 'N/A')
    status = alert.get('status', 'N/A')
    symbol = alert.get('symbol', 'N/A')
    side = alert.get('side', 'N/A')
    zone_id = alert.get('zone_id', 'N/A')
    notes = alert.get('notes', '')

    status_icon = "✅" if status == "active" else "🚫"
    zone_type = "🧪 TEST" if zone_id in [12345, 99999] else "🎯 REAL"

    print(f"\n{status_icon} {zone_type} | {symbol} {side.upper()} | Zone #{zone_id}")
    print(f"   Created: {created} | Status: {status}")
    if notes:
        print(f"   Reason: {notes}")

print("\n" + "=" * 80)
print("💡 RECOMMENDATIONS:")
print("=" * 80)

if len(real_alerts) == 0:
    print("\n🎯 PRIMARY ACTION: Configure TradingView Alert")
    print("\nStep-by-step:")
    print("1. Open your TradingView chart with the Pine Script strategy")
    print("2. Click the 'Alert' button (clock icon) or right-click → Add Alert")
    print("3. Condition: Select your strategy name (e.g., 'S&D Algo [Pro]')")
    print("4. Options: Select 'Any alert() function call'")
    print("5. Webhook URL: https://grand-learning-production-bc96.up.railway.app/webhook")
    print("6. Message: {{strategy.order.alert_message}}")
    print("7. Click 'Create'")
    print("\n📌 IMPORTANT: The alert MUST use {{strategy.order.alert_message}} to send trade data!")

if len(filtered) > 0:
    print("\n⚙️  SECONDARY ACTION: Adjust Bot Filters")
    print("\nTo receive more alerts, consider:")
    print("  • Lower MIN_RR_RATIO in backend/.env (currently rejecting 1:1 R:R)")
    print("  • Disable session filters temporarily")
    print("  • Check TRADING_SESSIONS setting")

print("\n✅ Once configured, test with:")
print("   cd tests && python3 e2e_test.py")
print("=" * 80)
