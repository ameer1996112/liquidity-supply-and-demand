#!/usr/bin/env python3
import os
import logging
from dotenv import load_dotenv
from supabase import create_client, Client
from src.services.broker_reconciliation import run_reconciliation_for_profile
from src.core.broker_profiles import get_active_profiles
from config import get_settings

# Configure logging to see the reconciliation steps
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def main():
    load_dotenv()
    
    settings = get_settings()
    supabase: Client = create_client(settings.supabase_url, settings.supabase_service_role_key or settings.supabase_key)
    
    logger.info("Starting manual broker reconciliation for all active profiles...")
    
    profiles = get_active_profiles()
    
    total_closed = 0
    total_errors = 0
    
    for profile in profiles:
        if profile.get("run_mode") == "PAPER":
            logger.info(f"Skipping paper profile: {profile.get('name')}")
            continue
            
        logger.info(f"Reconciling profile: {profile.get('name')} (ID: {profile.get('id')})")
        
        try:
            result = run_reconciliation_for_profile(
                supabase_url=settings.supabase_url,
                supabase_key=settings.supabase_service_role_key or settings.supabase_key,
                broker_profile_id=profile.get("id", 0),
                meta_api_token=profile.get("token", ""),
                meta_api_account_id=profile.get("meta_api_account_id", ""),
                meta_api_region=getattr(settings, "meta_api_region", "london"),
            )
            
            closed = result.get("closed_count", 0)
            errors = result.get("errors", [])
            
            logger.info(f"Profile {profile.get('name')} results: {closed} trades closed, {len(errors)} errors")
            if errors:
                for err in errors:
                    logger.error(f"  Error: {err}")
            
            total_closed += closed
            total_errors += len(errors)
            
        except Exception as e:
            logger.error(f"Failed to reconcile profile {profile.get('name')}: {e}")
            total_errors += 1
            
    logger.info(f"Manual sync complete. Total trades closed: {total_closed}. Total errors: {total_errors}.")

if __name__ == "__main__":
    main()
