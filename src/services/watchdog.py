"""
TradeWatchdog service
=====================

Polls MetaApi for open positions and trade history to detect "silent exits"
when a position hits SL/TP on the broker but no exit webhook was received.

Runs inside the worker process on a timer.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Sequence

import requests

from config import get_settings

logger = logging.getLogger(__name__)


class TradeWatchdog:
    """Periodically syncs executed trades in Supabase with MetaApi positions."""

    BASE_URL = "https://mt-client-api-v1.new-york.agiliumtrade.ai"

    def __init__(self, supabase_client: Any | None = None) -> None:
        self.settings = get_settings()
        self.token = (self.settings.meta_api_token or "").strip()
        self.account_id = (self.settings.meta_api_account_id or "").strip()
        self.supabase = supabase_client

        if not self.token or not self.account_id:
            logger.warning(
                "TradeWatchdog disabled: META_API_TOKEN or META_API_ACCOUNT_ID missing.",
            )

    # ------------------------------------------------------------------ #
    # HTTP helpers
    # ------------------------------------------------------------------ #

    def _headers(self) -> Dict[str, str]:
        return {
            "auth-token": self.token,
            "Content-Type": "application/json",
        }

    def _get(self, path: str, params: Dict[str, Any] | None = None) -> Optional[Any]:
        """Wrapper around requests.get with basic error handling."""
        if not self.token or not self.account_id:
            return None

        url = f"{self.BASE_URL}{path}"
        try:
            resp = requests.get(url, headers=self._headers(), params=params, timeout=10)
        except Exception as exc:  # noqa: BLE001
            logger.error("TradeWatchdog GET %s failed: %s", url, exc)
            return None

        if resp.status_code != 200:
            logger.error(
                "TradeWatchdog GET %s failed: HTTP %s %s",
                url,
                resp.status_code,
                resp.text[:200],
            )
            return None

        try:
            return resp.json()
        except ValueError:
            logger.error("TradeWatchdog GET %s invalid JSON: %s", url, resp.text[:200])
            return None

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #

    def run_sync(self) -> None:
        """
        Sync executed trades in Supabase with MetaApi open positions.

        - Fetch all Supabase trades with status='executed' (LIVE only)
        - Fetch all open positions from MetaApi
        - For any executed trade whose broker_order_id is NOT in the open
          positions set, treat it as a "silent exit" and process it.
        """
        if not self.supabase:
            logger.debug("TradeWatchdog: Supabase client not available, skipping run.")
            return
        if not self.token or not self.account_id:
            # Already logged in __init__
            return

        try:
            resp = self.supabase.table("trading_signals").select("*").eq(
                "status", "executed",
            ).eq("mode", "LIVE").execute()
            executed_trades: Sequence[Dict[str, Any]] = resp.data or []
        except Exception as exc:  # noqa: BLE001
            logger.error("TradeWatchdog: failed to fetch executed trades: %s", exc)
            return

        if not executed_trades:
            return

        positions = self._get(
            f"/users/current/accounts/{self.account_id}/positions",
        )
        if positions is None:
            return

        # MetaApi returns an array of positions; extract their IDs as strings
        open_ids: set[str] = set()
        for pos in positions or []:
            pid = pos.get("id") or pos.get("positionId")
            if pid is not None:
                open_ids.add(str(pid))

        logger.debug(
            "TradeWatchdog: %s executed trades, %s open positions",
            len(executed_trades),
            len(open_ids),
        )

        for trade in executed_trades:
            broker_id = str(trade.get("broker_order_id") or "").strip()
            if not broker_id:
                continue
            if broker_id in open_ids:
                # Still open on broker; nothing to do
                continue

            # No longer open on broker side – process as silent exit
            try:
                self._process_closed_trade(trade, broker_id)
            except Exception as exc:  # noqa: BLE001
                logger.error(
                    "TradeWatchdog: failed to process closed trade %s (ticket %s): %s",
                    trade.get("id"),
                    broker_id,
                    exc,
                )

    # ------------------------------------------------------------------ #
    # Internal helpers
    # ------------------------------------------------------------------ #

    def _process_closed_trade(self, trade: Dict[str, Any], broker_id: str) -> None:
        """
        Inspect MetaApi deal history for the given broker position and sync PnL.

        - Find DEAL_ENTRY_OUT for matching positionId
        - Extract profit, swap, commission, and exit price
        - Update Supabase trading_signals row
        """
        if not self.supabase:
            return

        # Fetch recent deal history; using a broad startTime to be safe.
        params = {
            "startTime": "2024-01-01T00:00:00.000Z",
        }
        deals = self._get(
            f"/users/current/accounts/{self.account_id}/history-deals",
            params=params,
        )
        if not deals:
            logger.warning(
                "TradeWatchdog: no deals returned for account %s when inspecting ticket %s",
                self.account_id,
                broker_id,
            )
            return

        # Filter for exit deals for this position
        matching: List[Dict[str, Any]] = []
        for d in deals:
            pid = d.get("positionId")
            if pid is None:
                continue
            if str(pid) != str(broker_id):
                continue
            if d.get("entryType") != "DEAL_ENTRY_OUT":
                continue
            matching.append(d)

        if not matching:
            logger.warning(
                "TradeWatchdog: no DEAL_ENTRY_OUT found for ticket %s", broker_id,
            )
            return

        # Use the latest exit deal
        matching.sort(key=lambda d: d.get("time", ""))
        exit_deal = matching[-1]

        profit = float(exit_deal.get("profit", 0.0) or 0.0)
        swap = float(exit_deal.get("swap", 0.0) or 0.0)
        commission = float(exit_deal.get("commission", 0.0) or 0.0)
        total_pnl = profit + swap + commission
        exit_price = float(exit_deal.get("price", 0.0) or 0.0)

        outcome = "win" if total_pnl > 0 else "loss" if total_pnl < 0 else "breakeven"

        update_data = {
            "status": "closed",
            "pnl_usd": total_pnl,
            "outcome": outcome,
            "close_price": exit_price or None,
            "close_broker_order_id": broker_id,
            "notes": "Watchdog: Silent Exit (SL/TP)",
            "closed_at": datetime.now(timezone.utc).isoformat(),
        }

        alert_id = trade.get("id")
        if alert_id is None:
            logger.error(
                "TradeWatchdog: trade without id for ticket %s, skipping Supabase update",
                broker_id,
            )
            return

        try:
            self.supabase.table("trading_signals").update(update_data).eq(
                "id", alert_id,
            ).execute()
            logger.info(
                "TradeWatchdog: synced silent exit for alert #%s (ticket %s, pnl_usd=%.2f)",
                alert_id,
                broker_id,
                total_pnl,
            )
        except Exception as exc:  # noqa: BLE001
            logger.error(
                "TradeWatchdog: Supabase update failed for alert #%s: %s",
                alert_id,
                exc,
            )

