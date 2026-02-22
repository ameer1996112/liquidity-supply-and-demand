import os
import json
from supabase import create_client
from dotenv import load_dotenv
from datetime import datetime, timezone

load_dotenv()
url = os.getenv("SUPABASE_URL")
key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")

if key and key.upper().startswith("SUPA") and "=" in key[:50]:
    key = key.split("=", 1)[-1].strip().strip('"\'').strip()

sb = create_client(url, key)

res = sb.table("trading_signals").update({
    "status": "closed",
    "closed_at": datetime.now(timezone.utc).isoformat()
}).eq("id", 55).execute()

print(f"Trade 55 forced closed: {res.data[0]['status']}")
