#!/usr/bin/env python3
"""
Quick one-off script to correct the PnL for trades that were previously
reconciled with commission folded into pnl_usd. Resets them to OPEN so
the next reconciliation re-syncs them with the correct gross profit value.

Usage:
    source venv/bin/activate && PYTHONPATH=. python3 scripts/reset_and_resync.py
"""
import os
import logging
from dotenv import load_dotenv
from supabase import create_client, Client
from src.services.broker_reconciliation import run_reconciliation_for_profile
from src.core.broker_profiles import get_active_profiles
from config import get_settings

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Trade IDs that were reconciled with wrong pnl (commission included in pnl_usd)
TRADES_TO_CORRECT = [200, 192]

def main():
    load_dotenv()
    settings = get_settings()
    supabase: Client = create_client(
        settings.supabase_url,
        settings.supabase_service_role_key or settings.supabase_key
    )

    # Step 1: Reset the trades back to OPEN so reconciliation picks them up again
    logger.info(f"Resetting trades {TRADES_TO_CORRECT} to OPEN for re-sync...")
    for trade_id in TRADES_TO_CORRECT:
        supabase.table("trading_signals").update({
            "status": "OPEN",
            "pnl_usd": None,
            "commission": None,
            "swap": None,
            "exit_fill_price": None,
            "outcome": None,
            "closed_at": None,
        }).eq("id", trade_id).execute()
        logger.info(f"  Reset trade {trade_id} -> OPEN")

    # Step 2: Re-run reconciliation to get correct gross PnL values
    logger.info("Running reconciliation to re-sync with correct gross PnL values...")
    profiles = get_active_profiles()
    for profile in profiles:
        if profile.get("run_mode") == "PAPER":
            continue
        result = run_reconciliation_for_profile(
            supabase_url=settings.supabase_url,
            supabase_key=settings.supabase_service_role_key or settings.supabase_key,
            broker_profile_id=profile.get("id", 0),
            meta_api_token=profile.get("token", ""),
            meta_api_account_id=profile.get("meta_api_account_id", ""),
            meta_api_region=getattr(settings, "meta_api_region", "london"),
        )
        logger.info(
            f"Profile {profile.get('name')}: {result.get('closed_count', 0)} closed, "
            f"{len(result.get('errors', []))} errors"
        )
        for err in result.get("errors", []):
            logger.error(f"  Error: {err}")

    logger.info("Done. Check your dashboard for correct PnL values.")

if __name__ == "__main__":
    main()
