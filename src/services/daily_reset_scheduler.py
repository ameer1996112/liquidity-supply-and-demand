"""
Daily Reset Scheduler
Automatically resets prop firm metrics at 00:00 UTC each day.

Integrated into worker.py main loop to run daily snapshot creation
without requiring external cron jobs.

Author: Trinity Engine v3.0
"""

import logging
from datetime import datetime, timezone
from typing import Optional

logger = logging.getLogger(__name__)


class DailyResetScheduler:
    """
    Schedules and executes daily reset at 00:00 UTC.

    Usage in worker.py:
        scheduler = DailyResetScheduler(supabase, settings)

        # In main loop:
        scheduler.check_and_execute_reset()
    """

    def __init__(self, supabase_client, settings):
        self.supabase = supabase_client
        self.settings = settings
        self._last_reset_date: Optional[str] = None

    def check_and_execute_reset(self) -> bool:
        """
        Check if daily reset is needed and execute if so.

        Returns:
            True if reset was performed, False otherwise
        """
        now = datetime.now(timezone.utc)
        today_date = now.date().isoformat()

        # Check if we already reset today
        if self._last_reset_date == today_date:
            return False

        # Only reset at or after midnight UTC
        # We check hour == 0 to ensure we're in the first hour of the new day
        if now.hour != 0:
            return False

        # Perform reset
        try:
            from src.services.prop_firm_tracker import PropFirmTracker

            tracker = PropFirmTracker(self.supabase, self.settings)

            # Get all active accounts
            # For single-account setup, just use default
            accounts = ["default"]

            # TODO: If multi-account, fetch from broker_profiles table:
            # try:
            #     profiles = self.supabase.table("broker_profiles")\
            #         .select("name")\
            #         .eq("enabled", True)\
            #         .execute()
            #     accounts = [p["name"] for p in profiles.data]
            # except:
            #     accounts = ["default"]

            for account_name in accounts:
                try:
                    import asyncio
                    asyncio.run(tracker.perform_daily_reset(account_name))
                    logger.info(f"✅ Daily reset completed for account: {account_name}")
                except Exception as e:
                    logger.error(f"Failed to reset account {account_name}: {e}")

            # Mark as completed for today
            self._last_reset_date = today_date

            # ── Pine streak rollup (adaptive trade limit) ──────────────
            # Updates the multi-day streak counter and clears today's intraday
            # trade state (wins/losses/risk_deployed) in Redis so the new day
            # starts clean.
            try:
                from src.services.pine_streak import rollup_day
                from src.adapters.redis_queue import get_redis as _get_redis_streak
                rollup_day(_get_redis_streak(), today_date)
                logger.info("📈 Pine streak rollup completed for %s", today_date)
            except Exception as streak_err:
                logger.warning("Pine streak rollup failed (non-fatal): %s", streak_err)
            # ───────────────────────────────────────────────────────────

            logger.info(f"🔄 Daily reset completed at {now.isoformat()}")
            return True

        except Exception as e:
            logger.error(f"Daily reset failed: {e}", exc_info=True)
            return False

    def force_reset_now(self, account_name: str = "default"):
        """
        Force immediate reset (for testing or manual intervention).

        Args:
            account_name: Account to reset
        """
        try:
            from src.services.prop_firm_tracker import PropFirmTracker
            import asyncio

            tracker = PropFirmTracker(self.supabase, self.settings)
            asyncio.run(tracker.perform_daily_reset(account_name))

            # Update last reset to prevent duplicate
            self._last_reset_date = datetime.now(timezone.utc).date().isoformat()

            logger.info(f"🔄 Manual reset completed for account: {account_name}")
            return True
        except Exception as e:
            logger.error(f"Manual reset failed: {e}", exc_info=True)
            return False
