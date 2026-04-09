import json
import os
from src.adapters.supabase_api import get_api_supabase

def run():
    try:
        supabase = get_api_supabase()
        resp = supabase.table("trade_history").select("id, account_name, symbol, pnl_usd, entry_time").ilike("account_name", "%ACG%").execute()
        print(f"Total history trades: {len(resp.data)}")
        for row in resp.data:
            print(row)
    except Exception as e:
        print("ERROR:", e)

if __name__ == '__main__':
    run()
