import asyncio
import os
import json
from src.adapters.supabase_api import get_api_supabase
from src.api_prop_firm_v1 import get_challenge_status

async def run():
    supabase = get_api_supabase()
    res = await get_challenge_status("ACG-DEMO-2", supabase)
    print(json.dumps(res, indent=2))

if __name__ == "__main__":
    asyncio.run(run())
