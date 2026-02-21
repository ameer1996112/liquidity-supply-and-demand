import sys
import os

# Ensure the module can find src
sys.path.append(os.path.abspath(os.path.dirname(__file__)))

from src.adapters.supabase import init_supabase

print("Attempting to connect via adapter...")
try:
    client = init_supabase()
    
    # Try an authenticated call
    resp = client.table("trading_signals").select("id").limit(1).execute()
    print("Success! Fetch returned: ", resp.data)
except Exception as e:
    print("Connection failed:", e)

