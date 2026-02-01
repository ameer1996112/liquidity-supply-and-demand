#!/usr/bin/env python3
"""
Factory Reset Utility for Trading Bot Production Environment
============================================================
Wipes ALL data from persistence layers (Redis + Supabase) for clean smoke testing.

Usage:
    python scripts/reset_system.py

Requirements:
    - .env with REDIS_URL, SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY
    - Optional: DATABASE_URL for true TRUNCATE (else uses delete-all via Supabase REST API)

Safety: Script pauses and requires typing 'DELETE' to confirm.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

# Guard: Never run in test environment
if os.getenv("TRINITY_ENV") == "test":
    print("❌ reset_system.py is disabled when TRINITY_ENV=test (safety).")
    sys.exit(1)

# Load .env from project root or backend/
PROJECT_ROOT = Path(__file__).resolve().parent.parent
for env_file in [PROJECT_ROOT / ".env", PROJECT_ROOT / "backend" / ".env"]:
    if env_file.exists():
        try:
            from dotenv import load_dotenv

            load_dotenv(env_file)
            break
        except ImportError:
            pass

# ANSI / Rich-style output
RED = "\033[91m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
CYAN = "\033[96m"
BOLD = "\033[1m"
DIM = "\033[2m"
RESET = "\033[0m"

CONFIRM_WORD = "DELETE"


def _log(msg: str, style: str = "") -> None:
    """Print with optional ANSI style."""
    print(f"{style}{msg}{RESET}")


def _log_success(msg: str) -> None:
    _log(f"  ✅ {msg}", GREEN)


def _log_error(msg: str) -> None:
    _log(f"  ❌ {msg}", RED)


def _log_warn(msg: str) -> None:
    _log(f"  ⚠️  {msg}", YELLOW)


def _log_info(msg: str) -> None:
    _log(f"  ℹ️  {msg}", CYAN)


def _require_confirmation() -> bool:
    """Require user to type CONFIRM_WORD to proceed. Returns True iff confirmed."""
    _log("", "")
    _log(f"⚠️  {BOLD}DESTRUCTIVE OPERATION{RESET}", YELLOW)
    _log(f"You are about to wipe ALL data from Redis and Supabase.", YELLOW)
    _log("", "")
    try:
        response = input(
            f"{BOLD}Type '{CONFIRM_WORD}' to confirm destruction of all data: {RESET}"
        ).strip()
    except (EOFError, KeyboardInterrupt):
        _log("\nAborted (no input).", DIM)
        return False
    if response != CONFIRM_WORD:
        _log(f"\nExpected '{CONFIRM_WORD}'. Aborting.", RED)
        return False
    return True


def _wipe_redis() -> bool:
    """Flush Redis database. Returns True on success."""
    redis_url = os.getenv("REDIS_URL")
    if not redis_url:
        _log_error("REDIS_URL not set. Skipping Redis wipe.")
        return False

    try:
        import redis

        r = redis.from_url(redis_url, decode_responses=True)
        r.ping()
    except ImportError as e:
        _log_error(f"redis package not installed: {e}")
        _log_info("Install with: pip install redis")
        return False
    except Exception as e:
        _log_error(f"Redis connection failed: {e}")
        return False

    try:
        # Use flushdb for current DB only; flushall for all DBs.
        # flushdb is safer if Redis is shared; flushall clears everything.
        r.flushdb()
        _log_success("Redis: flushdb() — current database cleared (no ghost jobs).")
        return True
    except Exception as e:
        _log_error(f"Redis flush failed: {e}")
        return False


def _wipe_supabase() -> bool:
    """Truncate/delete all rows in trading_signals. Uses SERVICE_ROLE_KEY to bypass RLS."""
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_SERVICE_ROLE_KEY") or os.getenv("SUPABASE_KEY")

    if not url or not key:
        _log_error(
            "SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY (or SUPABASE_KEY) must be set."
        )
        return False

    # Prefer direct TRUNCATE via psycopg2 if DATABASE_URL is available
    db_url = os.getenv("DATABASE_URL") or os.getenv("SUPABASE_DB_URL")
    if db_url and _truncate_via_psycopg2(db_url):
        return True

    return _delete_all_via_supabase(url, key)


def _truncate_via_psycopg2(db_url: str) -> bool:
    """Hard TRUNCATE using direct PostgreSQL connection."""
    try:
        import psycopg2
    except ImportError:
        _log_warn("psycopg2 not installed. Falling back to Supabase REST delete.")
        return False

    try:
        conn = psycopg2.connect(db_url)
        conn.autocommit = True
        cur = conn.cursor()
        cur.execute("TRUNCATE TABLE public.trading_signals RESTART IDENTITY CASCADE;")
        cur.close()
        conn.close()
        _log_success("Database: TRUNCATE trading_signals (sequence reset).")
        return True
    except Exception as e:
        _log_error(f"Database TRUNCATE failed: {e}")
        return False


def _delete_all_via_supabase(url: str, key: str) -> bool:
    """Delete all rows via Supabase REST API (SERVICE_ROLE bypasses RLS)."""
    try:
        from supabase import create_client

        client = create_client(url, key)
    except ImportError as e:
        _log_error(f"supabase package not installed: {e}")
        _log_info("Install with: pip install supabase")
        return False
    except Exception as e:
        _log_error(f"Supabase client init failed: {e}")
        return False

    try:
        total_deleted = 0
        # Loop to handle PostgREST row limits (default ~1000 per request)
        while True:
            result = (
                client.table("trading_signals")
                .delete()
                .gte("id", 0)
                .execute()
            )
            deleted = result.data if result.data is not None else []
            n = len(deleted)
            total_deleted += n
            if n == 0:
                break

        _log_success(
            f"Database: Deleted all rows from trading_signals ({total_deleted} rows)."
        )
        _log_info(
            "Note: ID sequence not reset. For full TRUNCATE, set DATABASE_URL and install psycopg2-binary."
        )
        return True
    except Exception as e:
        _log_error(f"Supabase delete failed: {e}")
        _log_info(
            "Ensure SUPABASE_SERVICE_ROLE_KEY (not anon key) is set to bypass RLS."
        )
        return False


def _check_test_environment() -> bool:
    """Check if running in test environment. Returns True if safe to proceed."""
    trinity_env = os.getenv("TRINITY_ENV", "").lower()
    if trinity_env != "test":
        _log(f"❌ SAFETY CHECK FAILED: TRINITY_ENV must be 'test' to run destructive operations.", RED)
        _log(f"   Current TRINITY_ENV: '{trinity_env or '(not set)'}'", RED)
        _log(f"   Set TRINITY_ENV=test to proceed.", YELLOW)
        return False
    return True


def reset_system() -> int:
    """Execute full system reset. Returns 0 on success, 1 on failure."""
    _log("")
    _log(f"{BOLD}Factory Reset — Trading Bot{RESET}", CYAN)
    _log("Redis + Supabase data will be wiped.", DIM)
    _log("", "")

    # Safety check: refuse to run unless TRINITY_ENV == "test"
    if not _check_test_environment():
        return 1

    if not _require_confirmation():
        return 1

    _log("")
    _log(f"{BOLD}Executing reset...{RESET}", CYAN)

    redis_ok = _wipe_redis()
    db_ok = _wipe_supabase()

    _log("")
    if redis_ok and db_ok:
        _log(f"{BOLD}✅ Factory reset complete. Ready for smoke testing.{RESET}", GREEN)
        return 0
    if not redis_ok and not db_ok:
        _log(f"{BOLD}❌ Reset failed (Redis and DB). Check env and connectivity.{RESET}", RED)
        return 1
    _log(
        f"{BOLD}⚠️  Reset partially completed. Review output above.{RESET}",
        YELLOW,
    )
    return 1


if __name__ == "__main__":
    sys.exit(reset_system())
