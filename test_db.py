import asyncio
import os
import sys

from src.adapters.supabase_api import get_api_supabase
from src.services.account_orchestrator import AccountOrchestrator

try:
    print("Testing DB connection...")
    sb = get_api_supabase()
    orch = AccountOrchestrator(sb)
    
    print("Fetching account_strategies...")
    accounts = sb.table("account_strategies").select("*").execute()
    print("All accounts in DB:")
    for a in accounts.data:
        print(f" - {a.get('id')}: {a.get('account_name')} (active={a.get('is_active')})")
        
    print("\nRunning get_account_comparison()...")
    comp = orch.get_account_comparison()
    print(f"Comparison returned {len(comp)} accounts.")
    for c in comp:
        print(f" - {c['account_name']}")

    for a in accounts.data:
        acc_name = a.get('account_name')
        if a.get('is_active'):
            print(f"\nTesting performance for {acc_name} directly...")
            try:
                perf = orch.get_account_performance(acc_name)
                if getattr(perf, 'account_name', None):
                    print(f"Success! {perf.account_name}")
                else:
                    print(f"Returned: {perf}")
            except Exception as e:
                print(f"Error fetching performance: {e}")

except Exception as e:
    import traceback
    traceback.print_exc()

