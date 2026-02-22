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

res = sb.table("trading_signals").select("id, symbol, created_at, status, updated_at").eq("id", 55).execute()
print(json.dumps(res.data, indent=2))
