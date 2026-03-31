import json
import os
from src.adapters.supabase_api import get_api_supabase

def run():
    try:
        supabase = get_api_supabase()
        resp = supabase.table("broker_profiles").update({"profit_target": 5000}).ilike("name", "%ACG%").execute()
        print("Updated DB manually:", resp.data)
    except Exception as e:
        print("ERROR:", e)

if __name__ == '__main__':
    run()
