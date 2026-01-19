
import logging
from datetime import datetime, timedelta
import pytz
from news_filter import NewsFilter

# Setup simple logging
logging.basicConfig(level=logging.INFO)
print("=== TESTING NEWS FILTER ===")

# 1. Initialize Filter
nf = NewsFilter(block_minutes_before=30, block_minutes_after=30)

# 2. Mock Data: Create a FAKE High Impact event happening right now
print("\n[TEST] Creating fake 'High Impact' USD news occurring NOW...")
now_utc = datetime.now(pytz.utc)
fake_event = {
    "title": "FAKE NEWS: USD CRASH",
    "country": "USD",
    "date": now_utc.strftime("%Y-%m-%dT%H:%M:%S%z"), # e.g. 2024-01-01T12:00:00+0000
    "impact": "High"
}

# Override the cache manually to force this event
nf.cache = [fake_event]
nf.last_fetch = 9999999999 # Future timestamp so it doesn't refetch real data

# 3. Test Check
symbol = "XAUUSD"
print(f"Checking if {symbol} is blocked...")
is_blocked = nf.is_news_imminent(symbol)

if is_blocked:
    print(f"✅ SUCCESS: {symbol} trading is BLOCKED due to news!")
else:
    print(f"❌ FAILURE: {symbol} was NOT blocked.")

# 4. Test Safe Symbol
symbol_safe = "BTCJPY" # Should usually be safe from USD news if logic is strict, but my logic maps USD to everything just in case. 
# actually my logic: is_news_imminent("BTCJPY") -> relevant currencies: ["JPY"]. USD event shouldn't block it.
print(f"\nChecking if {symbol_safe} is blocked (Should be FALSE)...")
is_blocked_safe = nf.is_news_imminent(symbol_safe)

if not is_blocked_safe:
    print(f"✅ SUCCESS: {symbol_safe} is NOT blocked (Correct).")
else:
    print(f"❌ FAILURE: {symbol_safe} WAS blocked unexpectedly.")
