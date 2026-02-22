import os
import json
from supabase import create_client
from dotenv import load_dotenv

load_dotenv()
url = os.getenv("SUPABASE_URL")
key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")

if key and key.upper().startswith("SUPA") and "=" in key[:50]:
    key = key.split("=", 1)[-1].strip().strip('"\'').strip()

sb = create_client(url, key)

from src.services.account_sync_service import AccountSyncService
sync_service = AccountSyncService(sb)
# Force sync the demo account where EURJPY lives
print("Syncing ACG-DEMO...")
sync_service.sync_account_positions("ACG-DEMO")

res = sb.table("trading_signals").select("id, status").eq("id", 55).execute()
print(f"Trade 55 status after sync: {res.data[0]['status']}")

