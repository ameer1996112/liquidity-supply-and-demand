"""
Background Sync Worker for Multi-Account Manager

Syncs account BALANCE / EQUITY / CONNECTION STATUS from MetaAPI at regular intervals.
Uses APScheduler for job scheduling and optional Redis for caching.

DEPRECATION NOTICE (DEV-39):
  Trade closure events and Net PnL updates are now handled in real-time by
  MetaApiStreamingService (src/services/metaapi_streaming_service.py).
  This worker is kept only for account balance/equity snapshots
  (account_status_snapshots table) — it no longer handles position sync.

Author: Claude Code
Created: 2026-02-09
"""

import logging
import time
from datetime import datetime, timezone
from typing import Dict, Any, Optional
from supabase import Client

logger = logging.getLogger(__name__)


class BackgroundSyncWorker:
    """
    Background worker for automatic account synchronization.

    Features:
    - Auto-sync all active accounts at configurable intervals
    - Optional Redis caching (30s TTL) for account data
    - Health check endpoint data
    - Graceful shutdown support
    """

    def __init__(
        self,
        supabase_client: Client,
        sync_interval_seconds: int = 60,
        redis_client: Optional[Any] = None,
        cache_ttl_seconds: int = 30,
    ):
        self.sb = supabase_client
        self.sync_interval = sync_interval_seconds
        self.redis = redis_client
        self.cache_ttl = cache_ttl_seconds
        self.scheduler = None
        self.is_running = False
        self.last_sync_time = None
        self.last_sync_status = "not_started"
        self.total_syncs = 0
        self.successful_syncs = 0
        self.failed_syncs = 0

    def start(self):
        """
        Start the background sync worker.

        Initializes APScheduler and schedules the sync job.
        """
        if self.is_running:
            logger.warning("Background sync worker is already running")
            return

        try:
            from apscheduler.schedulers.background import BackgroundScheduler
            from apscheduler.triggers.interval import IntervalTrigger

            self.scheduler = BackgroundScheduler()

            # Add sync job
            self.scheduler.add_job(
                func=self._sync_all_accounts,
                trigger=IntervalTrigger(seconds=self.sync_interval),
                id="account_sync_job",
                name="Sync all active accounts",
                replace_existing=True,
                max_instances=1,  # Prevent overlapping runs
            )

            self.scheduler.start()
            self.is_running = True

            logger.info(
                f"Background sync worker started. Interval: {self.sync_interval}s, "
                f"Cache TTL: {self.cache_ttl}s, Redis: {'enabled' if self.redis else 'disabled'}"
            )

        except Exception as e:
            logger.error(f"Failed to start background sync worker: {e}")
            raise

    def stop(self):
        """
        Stop the background sync worker gracefully.
        """
        if not self.is_running:
            return

        try:
            if self.scheduler:
                self.scheduler.shutdown(wait=True)
                logger.info("Background sync worker stopped")
            self.is_running = False

        except Exception as e:
            logger.error(f"Error stopping background sync worker: {e}")

    def _sync_all_accounts(self):
        """
        Sync all active accounts (called by scheduler).
        """
        from src.services.account_sync_service import AccountSyncService

        sync_start = time.time()
        self.total_syncs += 1

        try:
            logger.debug("Starting scheduled account sync...")

            sync_service = AccountSyncService(self.sb)
            results = sync_service.sync_all_active_accounts()

            success_count = sum(1 for v in results.values() if v)
            failed_count = len(results) - success_count

            # Update stats
            self.last_sync_time = datetime.now(timezone.utc)
            self.last_sync_status = "success" if failed_count == 0 else "partial"
            self.successful_syncs += 1 if failed_count == 0 else 0
            self.failed_syncs += 1 if failed_count > 0 else 0

            sync_duration = time.time() - sync_start

            logger.debug(
                "Scheduled sync complete: %d/%d accounts synced in %.2fs",
                success_count, len(results), sync_duration,
            )

            # Update cache if Redis is available
            if self.redis:
                try:
                    cache_key = "background_sync:last_run"
                    cache_data = {
                        "last_sync_time": self.last_sync_time.isoformat(),
                        "status": self.last_sync_status,
                        "accounts_synced": success_count,
                        "accounts_failed": failed_count,
                        "duration_seconds": sync_duration,
                    }
                    self.redis.setex(
                        cache_key,
                        self.cache_ttl,
                        str(cache_data)
                    )
                except Exception as e:
                    logger.warning(f"Failed to update Redis cache: {e}")

        except Exception as e:
            self.last_sync_status = "error"
            self.failed_syncs += 1
            logger.error(f"Scheduled sync failed: {e}")

    def get_health_status(self) -> Dict[str, Any]:
        """
        Get health check data for monitoring.

        Returns:
            Dict with worker status, last sync info, and stats
        """
        return {
            "worker_status": "running" if self.is_running else "stopped",
            "last_sync_time": self.last_sync_time.isoformat() if self.last_sync_time else None,
            "last_sync_status": self.last_sync_status,
            "sync_interval_seconds": self.sync_interval,
            "total_syncs": self.total_syncs,
            "successful_syncs": self.successful_syncs,
            "failed_syncs": self.failed_syncs,
            "success_rate": (
                self.successful_syncs / self.total_syncs * 100
                if self.total_syncs > 0
                else 0
            ),
            "redis_cache_enabled": self.redis is not None,
            "cache_ttl_seconds": self.cache_ttl,
        }

    def get_cached_account_data(self, account_name: str) -> Optional[Dict[str, Any]]:
        """
        Get cached account data from Redis (if available).

        Returns None if cache miss or Redis not configured.
        """
        if not self.redis:
            return None

        try:
            cache_key = f"account_data:{account_name}"
            cached = self.redis.get(cache_key)

            if cached:
                import json
                return json.loads(cached)

            return None

        except Exception as e:
            logger.warning(f"Failed to get cached data for {account_name}: {e}")
            return None

    def cache_account_data(
        self,
        account_name: str,
        data: Dict[str, Any],
        ttl_override: Optional[int] = None
    ):
        """
        Cache account data in Redis.

        Args:
            account_name: Account identifier
            data: Account data to cache
            ttl_override: Optional TTL override (seconds)
        """
        if not self.redis:
            return

        try:
            import json
            cache_key = f"account_data:{account_name}"
            ttl = ttl_override or self.cache_ttl

            self.redis.setex(
                cache_key,
                ttl,
                json.dumps(data)
            )

            logger.debug(f"Cached account data for {account_name} (TTL: {ttl}s)")

        except Exception as e:
            logger.warning(f"Failed to cache data for {account_name}: {e}")


# Global worker instance
_worker: Optional[BackgroundSyncWorker] = None


def get_background_worker() -> Optional[BackgroundSyncWorker]:
    """
    Get the global background worker instance.

    Returns None if not initialized.
    """
    return _worker


def initialize_background_worker(
    supabase_client: Client,
    sync_enabled: bool = True,
    sync_interval_seconds: int = 60,
    redis_client: Optional[Any] = None,
    cache_ttl_seconds: int = 30,
) -> Optional[BackgroundSyncWorker]:
    """
    Initialize and start the background sync worker.

    Args:
        supabase_client: Supabase client instance
        sync_enabled: Whether to enable background sync
        sync_interval_seconds: Sync interval in seconds
        redis_client: Optional Redis client for caching
        cache_ttl_seconds: Cache TTL in seconds

    Returns:
        Worker instance if enabled, None otherwise
    """
    global _worker

    if not sync_enabled:
        logger.info("Background sync is disabled (ACCOUNT_SYNC_ENABLED=false)")
        return None

    if _worker is not None:
        logger.warning("Background worker already initialized")
        return _worker

    try:
        _worker = BackgroundSyncWorker(
            supabase_client=supabase_client,
            sync_interval_seconds=sync_interval_seconds,
            redis_client=redis_client,
            cache_ttl_seconds=cache_ttl_seconds,
        )

        _worker.start()

        return _worker

    except Exception as e:
        logger.error(f"Failed to initialize background worker: {e}")
        return None


def shutdown_background_worker():
    """
    Shutdown the background sync worker gracefully.
    """
    global _worker

    if _worker:
        _worker.stop()
        _worker = None
