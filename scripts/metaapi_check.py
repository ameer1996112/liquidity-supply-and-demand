import asyncio
import os
from dotenv import load_dotenv

load_dotenv("/Users/ameeramer/dev/projects/galilsoftware/sources/trading/.env")

# Must append the codebase to the python path and use the real MetaApiAdapter
import sys
sys.path.append("/Users/ameeramer/dev/projects/galilsoftware/sources/trading")

from src.adapters.execution.meta_api_adapter import MetaApiAdapter

async def main():
    token = os.getenv("META_API_TOKEN")
    account_id = os.getenv("META_API_ACCOUNT_ID")
    if not token or not account_id:
        print("Missing MetaAPI token or account id")
        return

    print(f"Connecting to MetaAPI account {account_id}...")
    try:
        adapter = MetaApiAdapter(token=token, account_id=account_id, account_name="ACG-DEMO")
        # get_account_status is synchronous in the adapter? Let's check
        status = adapter.get_account_status()
        print("--- MetaAPI Status ---")
        print(status)
        
        positions = adapter.get_open_positions()
        print(f"\nOpen positions ({len(positions)}):")
        for p in positions:
            print(p)
            
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(main())
