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

res = sb.table("trading_signals").select("id, status, symbol, broker_order_id, account_name, created_at").eq("id", 55).execute()
print(f"Trade 55 in DB: {res.data[0]}")

res = sb.table("position_snapshots").select("id, broker_position_id, symbol, account_name, snapshot_time").eq("account_name", "ACG-DEMO").order("snapshot_time", desc=True).limit(5).execute()
print(f"Recent position snapshots for ACG-DEMO: {len(res.data)}")
for p in res.data:
    print(p)
