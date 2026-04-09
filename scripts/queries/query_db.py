import json
import os
from src.adapters.supabase_api import get_api_supabase

def run():
    try:
        supabase = get_api_supabase()
        resp = supabase.table("broker_profiles").select("name, consistency_enabled, profit_target").ilike("name", "%ACG%").execute()
        print(json.dumps(resp.data, indent=2))
    except Exception as e:
        print("ERROR:", e)
        print("ERROR:", e)
        print("ERROR:", e)
        print("ERROR:", e)
        print("ERROR:", e)
        print("ERROR:", e)

if __name__ == '__main__':
    run()
