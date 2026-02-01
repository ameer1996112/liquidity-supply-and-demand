"""
Server Hard Reset Script v1.0
=============================

Performs a factory reset of Railway infrastructure (Supabase & Redis).
Run this once to clear old conflicting signals.

WARNING: This deletes ALL live trading history!
"""

import os
import sys
from pathlib import Path
from dotenv import load_dotenv
from redis import Redis
from supabase import create_client

# Load Local Environment
_base = Path(__file__).resolve().parent.parent
for p in [_base / "backend" / ".env", _base / ".env"]:
    if p.exists():
        load_dotenv(dotenv_path=p)
        print(f"Loaded .env from: {p}")
        break

SUPA_URL = os.getenv("SUPABASE_URL")
SUPA_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY") or os.getenv("SUPABASE_KEY")
REDIS_URL = os.getenv("REDIS_URL")


def _check_test_environment() -> bool:
    """Check if running in test environment. Returns True if safe to proceed."""
    trinity_env = os.getenv("TRINITY_ENV", "").lower()
    if trinity_env != "test":
        print(f"SAFETY CHECK FAILED: TRINITY_ENV must be 'test' to run destructive operations.")
        print(f"  Current TRINITY_ENV: '{trinity_env or '(not set)'}'")
        print(f"  Set TRINITY_ENV=test to proceed.")
        return False
    return True


def hard_reset():
    print("INITIATING HARD SERVER RESET...")

    if not SUPA_URL or not REDIS_URL:
        print("Missing Credentials in .env")
        return False

    success = True

    # 1. WIPE REDIS (The Queue)
    try:
        r = Redis.from_url(REDIS_URL, decode_responses=True, socket_timeout=5)
        r.flushall()
        print("   Redis Queue FLUSHED.")
    except Exception as e:
        print(f"   Redis Flush Failed: {e}")
        success = False

    # 2. WIPE SUPABASE (The Ledger)
    try:
        supabase = create_client(SUPA_URL, SUPA_KEY)
        # Delete all records where ID > 0 (effectively all)
        supabase.table("trading_signals").delete().neq("id", 0).execute()
        print("   Supabase 'trading_signals' TRUNCATED.")
    except Exception as e:
        print(f"   Supabase Wipe Failed: {e}")
        success = False

    if success:
        print("\nSERVER CLEAN STATE ACHIEVED.")
    else:
        print("\nSERVER RESET COMPLETED WITH ERRORS.")

    return success


if __name__ == "__main__":
    print("\n" + "=" * 50)
    print("SERVER HARD RESET UTILITY")
    print("=" * 50)

    # Safety check: refuse to run unless TRINITY_ENV == "test"
    if not _check_test_environment():
        sys.exit(1)

    print(f"\nTarget Redis: {REDIS_URL[:30]}..." if REDIS_URL else "Redis: NOT CONFIGURED")
    print(f"Target Supabase: {SUPA_URL[:30]}..." if SUPA_URL else "Supabase: NOT CONFIGURED")
    print("")

    confirm = input("WARNING: This deletes ALL live trading history. Type 'DELETE' to confirm: ")
    if confirm == "DELETE":
        hard_reset()
    else:
        print("Aborted.")
        sys.exit(0)
