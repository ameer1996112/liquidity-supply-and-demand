import os
import json
import logging
from supabase import create_client
from dotenv import load_dotenv

logging.basicConfig(level=logging.DEBUG)

load_dotenv()
url = os.getenv("SUPABASE_URL")
key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")

if key and key.upper().startswith("SUPA") and "=" in key[:50]:
    key = key.split("=", 1)[-1].strip().strip('"\'').strip()

sb = create_client(url, key)

from src.services.account_sync_service import AccountSyncService
sync_service = AccountSyncService(sb)

# Fetch trade 55 DB info directly
res = sb.table("trading_signals").select("*").eq("id", 55).execute()
trade = res.data[0]
print(json.dumps(trade, indent=2))

print(f"Syncing ACG-DEMO...")
sync_service._reconcile_positions("ACG-DEMO", "2026-02-22T00:00:00.000000+00:00")

res3 = sb.table("trading_signals").select("status").eq("id", 55).execute()
print(f"Status after reconcile: {res3.data[0]['status']}")
