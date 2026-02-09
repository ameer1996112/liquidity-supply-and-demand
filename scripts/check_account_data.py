#!/usr/bin/env python3
"""Check account data in database to debug frontend display issue."""

import os
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from supabase import create_client
from config import get_settings

def main():
    settings = get_settings()

    if not settings.supabase_url or not settings.supabase_key:
        print("❌ Supabase credentials not configured")
        return

    client = create_client(
        settings.supabase_url,
        settings.supabase_service_role_key or settings.supabase_key
    )

    print("=" * 80)
    print("ACCOUNT STRATEGIES TABLE")
    print("=" * 80)

    # Check account_strategies
    result = client.table("account_strategies").select("*").eq("is_active", True).execute()

    if not result.data:
        print("❌ No active accounts found in account_strategies table")
        return

    for account in result.data:
        print(f"\n📊 Account: {account.get('account_name')}")
        print(f"   Strategy: {account.get('strategy_type')}")
        print(f"   Allocated Capital: {account.get('allocated_capital_usd')} (type: {type(account.get('allocated_capital_usd')).__name__})")
        print(f"   Broker Profile ID: {account.get('broker_profile_id')}")
        print(f"   Meta API Account ID: {account.get('meta_api_account_id')}")
        print(f"   Risk %: {account.get('risk_percent')}")
        print(f"   Max Lot Size: {account.get('max_lot_size')}")
        print(f"   Pause Trading: {account.get('pause_trading')}")
        print(f"   Is Active: {account.get('is_active')}")

    print("\n" + "=" * 80)
    print("TRADING SIGNALS (RECENT 10)")
    print("=" * 80)

    # Check recent trading signals
    signals = client.table("trading_signals").select(
        "symbol, side, status, pnl_usd, outcome, account_name, created_at"
    ).order("created_at", desc=True).limit(10).execute()

    if signals.data:
        for sig in signals.data:
            print(f"\n   {sig.get('symbol')} {sig.get('side')} - Status: {sig.get('status')}")
            print(f"   Account: {sig.get('account_name')}")
            print(f"   PnL USD: {sig.get('pnl_usd')} (type: {type(sig.get('pnl_usd')).__name__})")
            print(f"   Outcome: {sig.get('outcome')}")
    else:
        print("   No recent trading signals found")

    print("\n" + "=" * 80)
    print("TEST API ENDPOINT")
    print("=" * 80)

    # Try to call the account orchestrator method directly
    try:
        from src.services.account_orchestrator import AccountOrchestrator

        orchestrator = AccountOrchestrator(client)

        print("\n🔍 Testing get_account_performance...")
        for account in result.data:
            account_name = account.get('account_name')
            perf = orchestrator.get_account_performance(account_name)

            if perf:
                print(f"   ✅ {account_name}: balance=${perf.balance:.2f}, trades={perf.total_trades}")
            else:
                print(f"   ❌ {account_name}: Failed to get performance")

        print("\n🔍 Testing get_account_comparison...")
        comparison = orchestrator.get_account_comparison()

        if comparison:
            print(f"   ✅ Found {len(comparison)} accounts in comparison")
            for acc in comparison:
                print(f"      - {acc.get('account_name')}: balance=${acc.get('balance'):.2f}")
        else:
            print("   ❌ No accounts returned from get_account_comparison()")

    except Exception as e:
        print(f"   ❌ Error testing API: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
