import os
from dotenv import load_dotenv
from supabase import create_client, Client

load_dotenv("/Users/ameeramer/dev/projects/galilsoftware/sources/trading/.env")

url: str = os.getenv("SUPABASE_URL")
key: str = os.getenv("SUPABASE_SERVICE_ROLE_KEY")

supabase: Client = create_client(url, key)

res = supabase.table("trading_signals").select("id, symbol, side, size, sl, tp, pnl, pnl_usd, created_at, exit_price, entry").order("created_at", desc=True).limit(20).execute()

for s in res.data:
    print(f"{s['created_at']} | {s['symbol']} {s['side']} {s['size']} | PNL: {s.get('pnl_usd') or s.get('pnl')} | Entry: {s.get('entry')} Exit: {s.get('exit_price')}")
