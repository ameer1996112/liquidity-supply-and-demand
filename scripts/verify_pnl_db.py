import os
from dotenv import load_dotenv
from supabase import create_client, Client

load_dotenv("/Users/ameeramer/dev/projects/galilsoftware/sources/trading/.env")

url: str = os.getenv("SUPABASE_URL")
key: str = os.getenv("SUPABASE_SERVICE_ROLE_KEY")

if not url or not key:
    print("Missing SUPABASE credentials")
    exit(1)

supabase: Client = create_client(url, key)

print("--- TRADING SIGNALS ---")
res = supabase.table("trading_signals").select("id, status, pnl, pnl_usd, side, size, entry, exit_fill_price, exit_price, run_mode, mode").in_("status", ["closed", "executed", "CLOSED", "EXECUTED"]).execute()

signals = res.data or []
print(f"Total closed signals: {len(signals)}")
total_pnl = 0
for s in signals:
    s_pnl = s.get("pnl_usd")
    if s_pnl is None:
        s_pnl = s.get("pnl")
        
    if s_pnl is not None:
        total_pnl += float(s_pnl)
    else:
        entry = s.get("entry")
        exit_val = s.get("exit_fill_price") or s.get("exit_price")
        size = s.get("size")
        if entry is not None and exit_val is not None and size is not None:
            diff = exit_val - entry if str(s.get("side")).lower() == 'buy' else entry - exit_val
            total_pnl += diff * size

print(f"Calculated Total PNL from trading_signals: {total_pnl}")

print("\n--- ACCOUNT STATUS SNAPSHOTS ---")
res = supabase.table("account_strategies").select("account_name, allocated_capital_usd").eq("is_active", True).execute()
accounts = res.data or []
print(f"Active accounts: {accounts}")

if accounts:
    for acct in accounts:
        name = acct.get("account_name")
        allocated = acct.get("allocated_capital_usd", 0)
        print(f"Account: {name}, Allocated: {allocated}")
        
        snaps = supabase.table("account_status_snapshots").select("balance, snapshot_time").eq("account_name", name).order("snapshot_time", desc=True).limit(5).execute()
        print(f"Recent snapshots: {snaps.data}")
else:
    print("No active accounts found")
