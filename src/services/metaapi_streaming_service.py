"""
MetaApi Streaming Service — Real-time push-based trade monitoring.

Replaces the polling-based BackgroundSyncWorker for trade closure events.

Architecture:
  MetaApi WebSocket → SynchronizationListener.on_deal_added()
    → DEAL_ENTRY_OUT detected
    → Net PnL = profit + swap + commission
    → Update trading_signals WHERE broker_order_id = positionId AND status = 'OPEN'
    → Supabase Realtime auto-pushes DB change to frontend (no Socket.io needed)

DEV-39: Implement Real-Time MetaApi Streaming for Accurate PnL
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import Optional

logger = logging.getLogger(__name__)

# Global task handle — one streaming connection per process
_streaming_task: Optional[asyncio.Task] = None  # type: ignore[type-arg]


# ─────────────────────────────────────────────────────────────────────────────
# Internal deal handler
# ─────────────────────────────────────────────────────────────────────────────

class _DealHandler:
    """
    Processes MetaApi deal events and updates the database.

    Runs inside the asyncio event loop; uses run_in_executor for the
    synchronous Supabase client calls.
    """

    def __init__(self, supabase_client) -> None:  # type: ignore[no-untyped-def]
        self._sb = supabase_client

    async def handle_deal(self, deal: dict) -> None:
        """
        Entry point for each incoming deal event.

        Only processes DEAL_ENTRY_OUT events (position closures).
        """
        entry_type = deal.get("entryType") or deal.get("entry") or ""
        if entry_type != "DEAL_ENTRY_OUT":
            return  # skip entries/in-flight deals

        position_id = str(deal.get("positionId") or "").strip()
        if not position_id:
            logger.debug("MetaApi streaming: deal missing positionId, skipping: %s", deal)
            return

        profit = float(deal.get("profit") or 0)
        swap = float(deal.get("swap") or 0)
        commission = float(deal.get("commission") or 0)
        net_pnl = profit + swap + commission

        symbol = deal.get("symbol", "?")
        deal_id = deal.get("id", "?")

        logger.info(
            "[MetaApi Stream] Trade closed — deal=%s position=%s symbol=%s "
            "profit=%.2f swap=%.2f commission=%.2f → net_pnl=%.2f",
            deal_id, position_id, symbol, profit, swap, commission, net_pnl,
        )

        await asyncio.get_event_loop().run_in_executor(
            None,
            self._update_db_sync,
            position_id, net_pnl, profit, swap, commission,
        )

    def _update_db_sync(
        self,
        position_id: str,
        net_pnl: float,
        profit: float,
        swap: float,
        commission: float,
    ) -> None:
        """
        Synchronous Supabase write — called via run_in_executor.

        Updates the signal record matched by broker_order_id.
        The DB change triggers Supabase Realtime → frontend update.
        """
        now = datetime.now(timezone.utc).isoformat()
        try:
            result = (
                self._sb.table("trading_signals")
                .update(
                    {
                        "status": "CLOSED",
                        "pnl_usd": net_pnl,
                        "pnl": net_pnl,
                        "commission": commission,
                        "swap": swap,
                        "exit_time": now,
                        "updated_at": now,
                    }
                )
                .eq("broker_order_id", position_id)
                .eq("status", "OPEN")
                .execute()
            )
            rows = result.data or []
            if rows:
                logger.info(
                    "[MetaApi Stream] DB updated position=%s net_pnl=%.2f (%d row) "
                    "— Supabase Realtime will push to frontend",
                    position_id, net_pnl, len(rows),
                )
            else:
                logger.debug(
                    "[MetaApi Stream] No OPEN signal for position_id=%s "
                    "(may already be closed by Pine exit webhook or non-LIVE mode)",
                    position_id,
                )
        except Exception as exc:
            logger.error(
                "[MetaApi Stream] DB update failed for position=%s: %s",
                position_id, exc,
            )


# ─────────────────────────────────────────────────────────────────────────────
# Streaming connection coroutine
# ─────────────────────────────────────────────────────────────────────────────

async def _run_streaming(
    token: str,
    account_id: str,
    supabase_client,  # type: ignore[no-untyped-def]
) -> None:
    """
    Long-running coroutine — maintains persistent MetaApi streaming connection.
    Auto-reconnects on disconnect with exponential back-off (max 60s).
    """
    try:
        from metaapi_cloud_sdk import MetaApi, SynchronizationListener
    except ImportError:
        logger.error(
            "[MetaApi Stream] metaapi-cloud-sdk not installed. "
            "Run: pip install metaapi-cloud-sdk>=27.0.0"
        )
        return

    handler = _DealHandler(supabase_client)
    backoff = 5  # seconds, doubles on each failure up to 60

    class _Listener(SynchronizationListener):
        async def on_deal_added(
            self, instance_index: str, deal: dict
        ) -> None:
            await handler.handle_deal(deal)

        async def on_connected(
            self, instance_index: str, replicas: int
        ) -> None:
            logger.info(
                "[MetaApi Stream] Connected — instance=%s replicas=%d",
                instance_index, replicas,
            )

        async def on_disconnected(self, instance_index: str) -> None:
            logger.warning(
                "[MetaApi Stream] Disconnected — instance=%s", instance_index
            )

        async def on_synchronization_started(
            self,
            instance_index: str,
            specifications_updated: bool,
            positions_updated: bool,
            orders_updated: bool,
            synchronization_id: Optional[str] = None,
        ) -> None:
            logger.info(
                "[MetaApi Stream] Synchronization started — instance=%s", instance_index
            )

    listener = _Listener()

    while True:
        api = None
        connection = None
        try:
            logger.info(
                "[MetaApi Stream] Initializing streaming connection for account %s",
                account_id,
            )
            api = MetaApi(token)
            account = await api.metatrader_account_api.get_account(account_id)

            if account.state not in ("DEPLOYED", "DEPLOYING"):
                logger.info("[MetaApi Stream] Deploying account %s ...", account_id)
                await account.deploy()
            await account.wait_connected()

            connection = account.get_streaming_connection()
            connection.add_synchronization_listener(listener)
            await connection.connect()
            await connection.wait_synchronized()

            logger.info(
                "[MetaApi Stream] Synchronized. Listening for deal events on account %s",
                account_id,
            )
            backoff = 5  # reset on successful connection

            # Keep alive until cancelled or exception
            while True:
                await asyncio.sleep(30)

        except asyncio.CancelledError:
            logger.info("[MetaApi Stream] Task cancelled — shutting down cleanly")
            break

        except Exception as exc:
            logger.error(
                "[MetaApi Stream] Connection error: %s — reconnecting in %ds",
                exc, backoff,
            )
            await asyncio.sleep(backoff)
            backoff = min(backoff * 2, 60)

        finally:
            if connection is not None:
                try:
                    await connection.close()
                except Exception:
                    pass
            if api is not None:
                try:
                    api.close()
                except Exception:
                    pass


# ─────────────────────────────────────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────────────────────────────────────

def start_streaming(
    token: str,
    account_id: str,
    supabase_client,  # type: ignore[no-untyped-def]
) -> Optional["asyncio.Task[None]"]:
    """
    Spawn the MetaApi streaming connection as a background asyncio task.

    Call from FastAPI lifespan (async context). Returns the Task so the
    caller can cancel it on shutdown.
    """
    global _streaming_task

    if not token or not account_id:
        logger.warning(
            "[MetaApi Stream] META_API_TOKEN or META_API_ACCOUNT_ID not set — streaming disabled"
        )
        return None

    if _streaming_task and not _streaming_task.done():
        logger.warning("[MetaApi Stream] Already running — skipping duplicate start")
        return _streaming_task

    _streaming_task = asyncio.create_task(
        _run_streaming(token, account_id, supabase_client),
        name="metaapi-streaming",
    )
    logger.info(
        "[MetaApi Stream] Task started for account %s (task id: %s)",
        account_id, id(_streaming_task),
    )
    return _streaming_task


def stop_streaming() -> None:
    """Cancel the streaming task gracefully. Call from FastAPI shutdown."""
    global _streaming_task
    if _streaming_task and not _streaming_task.done():
        _streaming_task.cancel()
        logger.info("[MetaApi Stream] Streaming task cancelled")
    _streaming_task = None


def get_streaming_status() -> dict:
    """Return streaming task status for health-check endpoints."""
    if _streaming_task is None:
        return {"status": "not_started"}
    if _streaming_task.done():
        exc = _streaming_task.exception() if not _streaming_task.cancelled() else None
        return {
            "status": "cancelled" if _streaming_task.cancelled() else "stopped",
            "error": str(exc) if exc else None,
        }
    return {"status": "running"}
