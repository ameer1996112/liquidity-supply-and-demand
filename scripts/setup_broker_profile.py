#!/usr/bin/env python3
"""
Setup broker profile for FTMO-Demo-50K account.

This script:
1. Creates a broker_profile record with Meta API credentials
2. Links the account_strategies record to the broker_profile
"""

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

    # Get account name from command line or use default
    if len(sys.argv) > 1:
        account_name = sys.argv[1]
    else:
        # List available accounts
        accounts = client.table("account_strategies").select("account_name, is_active").execute()
        if accounts.data:
            print("=" * 80)
            print("AVAILABLE ACCOUNTS")
            print("=" * 80)
            for acc in accounts.data:
                status = "✅" if acc.get("is_active") else "❌"
                print(f"  {status} {acc.get('account_name')}")
            print("\nUsage: python scripts/setup_broker_profile.py <account_name>")
            print(f"Example: python scripts/setup_broker_profile.py {accounts.data[0].get('account_name')}")
            return
        else:
            print("❌ No accounts found in database")
            return

    print("=" * 80)
    print("BROKER PROFILE SETUP")
    print("=" * 80)

    # Get current account data
    account_result = client.table("account_strategies").select("*").eq(
        "account_name", account_name
    ).execute()

    if not account_result.data:
        print(f"❌ Account {account_name} not found")
        return

    account = account_result.data[0]

    meta_api_account_id = account.get("meta_api_account_id")
    meta_api_token_env_key = account.get("meta_api_token_env_key")

    print(f"\n📊 Current Account: {account_name}")
    print(f"   Meta API Account ID: {meta_api_account_id}")
    print(f"   Meta API Token Env Key: {meta_api_token_env_key}")
    print(f"   Broker Profile ID: {account.get('broker_profile_id')}")

    if not meta_api_account_id:
        print("\n❌ No Meta API Account ID found in account_strategies")
        print("\n📝 To fix this, you need to add the Meta API Account ID to your database:")
        print("\n   Option 1: Update via Supabase Dashboard")
        print(f"      1. Go to Supabase > Table Editor > account_strategies")
        print(f"      2. Find row with account_name = '{account_name}'")
        print(f"      3. Set meta_api_account_id = '<your-metaapi-account-id>'")
        print(f"      4. Set meta_api_token_env_key = 'META_API_TOKEN'")
        print("\n   Option 2: Update via SQL")
        print(f"      UPDATE account_strategies")
        print(f"      SET meta_api_account_id = '<your-metaapi-account-id>',")
        print(f"          meta_api_token_env_key = 'META_API_TOKEN'")
        print(f"      WHERE account_name = '{account_name}';")
        print("\n   Then run this script again.")
        return

    # Check if token env key is set
    if not meta_api_token_env_key:
        print("\n⚠️  Warning: meta_api_token_env_key is not set")
        print("   This should be the NAME of the env var (e.g., 'META_API_TOKEN')")
        print("   NOT the actual token value")

        # Suggest a value
        suggested_key = "META_API_TOKEN"
        print(f"\n   Suggested: {suggested_key}")
        print(f"   Then add the actual JWT token to Railway env vars as {suggested_key}")

    # Check if broker profile already exists for this Meta API account
    existing_profile = client.table("broker_profiles").select("*").eq(
        "meta_api_account_id", meta_api_account_id
    ).execute()

    if existing_profile.data:
        profile = existing_profile.data[0]
        profile_id = profile.get("id")
        print(f"\n✅ Broker profile already exists: ID={profile_id}")

        # Update account to link to this profile
        if account.get("broker_profile_id") != profile_id:
            print(f"\n🔗 Linking account to broker profile...")
            client.table("account_strategies").update({
                "broker_profile_id": profile_id
            }).eq("account_name", account_name).execute()
            print(f"   ✅ Updated account_strategies.broker_profile_id = {profile_id}")
        else:
            print(f"   ✅ Account already linked to profile")

        return

    # Create new broker profile
    print(f"\n🆕 Creating new broker profile...")

    profile_data = {
        "name": f"{account_name} MetaAPI",
        "meta_api_account_id": meta_api_account_id,
        "token_env_key": meta_api_token_env_key or "META_API_TOKEN",
        "risk_pct": account.get("risk_percent", 1.0),
        "max_positions": account.get("max_positions", 3),
        "run_mode": "LIVE",  # or "PAPER" based on your setup
        "is_active": True,
    }

    try:
        profile_result = client.table("broker_profiles").insert(profile_data).execute()

        if not profile_result.data:
            print("❌ Failed to create broker profile")
            return

        profile_id = profile_result.data[0].get("id")
        print(f"   ✅ Created broker profile: ID={profile_id}")

        # Update account to link to this profile
        print(f"\n🔗 Linking account to broker profile...")
        client.table("account_strategies").update({
            "broker_profile_id": profile_id
        }).eq("account_name", account_name).execute()
        print(f"   ✅ Updated account_strategies.broker_profile_id = {profile_id}")

        # If meta_api_token_env_key was empty, update it
        if not meta_api_token_env_key:
            client.table("account_strategies").update({
                "meta_api_token_env_key": "META_API_TOKEN"
            }).eq("account_name", account_name).execute()
            print(f"   ✅ Updated account_strategies.meta_api_token_env_key = META_API_TOKEN")

        print("\n" + "=" * 80)
        print("✅ SETUP COMPLETE!")
        print("=" * 80)
        print("\n⚠️  IMPORTANT: Make sure you have added the Meta API JWT token to Railway:")
        print("   1. Go to Railway > Project > Variables")
        print("   2. Add: META_API_TOKEN = <your-jwt-token-here>")
        print("   3. Redeploy the backend")
        print("\n📝 The account should now appear in the frontend after backend restart")

    except Exception as e:
        print(f"❌ Error creating broker profile: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
