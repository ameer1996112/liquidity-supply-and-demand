"""
TradeWatchdog
=============

Background service that polls MetaApi and Supabase to detect "silent exits":
positions that have been closed on the broker (SL/TP hit) without an explicit
exit webhook reaching the backend. When such a position is detected, the
watchdog resolves its PnL from broker history and updates the corresponding
row in the `trading_signals` table.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Sequence

import requests

from config import get_settings

logger = logging.getLogger(__name__)


class TradeWatchdog:
    """
    Periodically compares Supabase trades vs MetaApi positions to detect trades
    that have closed on the broker without an exit webhook, then syncs their
    PnL and status in Supabase.
    """

    def __init__(self, supabase_client: Optional[Any] = None) -> None:
        self.settings = get_settings()
        self.token = (self.settings.meta_api_token or "").strip()
        self.account_id = (self.settings.meta_api_account_id or "").strip()
        region = (getattr(self.settings, "meta_api_region", "new-york") or "new-york").strip()
        # mt-client API (positions)
        self.client_base_url = f"https://mt-client-api-v1.{region}.agiliumtrade.ai"
        # MetaStats API (history-deals)
        self.stats_base_url = f"https://metastats-api-v1.{region}.agiliumtrade.ai"
        self.supabase = supabase_client

        if not self.token or not self.account_id:
            logger.warning(
                "TradeWatchdog disabled: META_API_TOKEN or META_API_ACCOUNT_ID missing.",
            )
        else:
            logger.info(
                "TradeWatchdog using MetaApi region '%s' (client=%s, stats=%s)",
                region,
                self.client_base_url,
                self.stats_base_url,
            )

    # ------------------------------------------------------------------ #
    # HTTP helpers
    # ------------------------------------------------------------------ #

    def _headers(self) -> Dict[str, str]:
        return {
            "auth-token": self.token,
            "Content-Type": "application/json",
        }

    def _get_client(self, path: str, params: Optional[Dict[str, Any]] = None) -> Optional[Any]:
        """GET wrapper against the MetaApi client API (positions, etc.)."""
        if not self.token or not self.account_id:
            return None

        url = f"{self.client_base_url}{path}"
        try:
            resp = requests.get(url, headers=self._headers(), params=params, timeout=10)
        except Exception as exc:  # noqa: BLE001
            logger.error("TradeWatchdog client GET %s failed: %s", url, exc)
            return None

        if resp.status_code != 200:
            logger.error(
                "TradeWatchdog client GET %s failed: HTTP %s %s",
                url,
                resp.status_code,
                resp.text[:200],
            )
            return None

        try:
            return resp.json()
        except ValueError:
            logger.error("TradeWatchdog client GET %s invalid JSON: %s", url, resp.text[:200])
            return None

    def _get_stats(self, path: str, params: Optional[Dict[str, Any]] = None) -> Optional[Any]:
        """GET wrapper against the MetaStats API (history-deals)."""
        if not self.token or not self.account_id:
            return None

        url = f"{self.stats_base_url}{path}"
        try:
            resp = requests.get(url, headers=self._headers(), params=params, timeout=10)
        except Exception as exc:  # noqa: BLE001
            logger.error("TradeWatchdog stats GET %s failed: %s", url, exc)
            return None

        if resp.status_code != 200:
            logger.error(
                "TradeWatchdog stats GET %s failed: HTTP %s %s",
                url,
                resp.status_code,
                resp.text[:200],
            )
            return None

        try:
            return resp.json()
        except ValueError:
            logger.error("TradeWatchdog stats GET %s invalid JSON: %s", url, resp.text[:200])
            return None

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #

    def run_sync(self) -> None:
        """
        Main entry point.

        1. Fetch trades from Supabase where:
           - run_mode = 'LIVE'
           - status   = 'executed'
        2. Fetch open positions from MetaApi.
        3. For any Supabase trade whose broker_order_id is NOT present in the
           list of open positions, treat it as a "silent exit" and resolve PnL
           from MetaApi history.
        """
        if not self.supabase:
            return
        if not self.token or not self.account_id:
            return

        try:
            resp = (
                self.supabase.table("trading_signals")
                .select("*")
                .eq("run_mode", "LIVE")
                .eq("status", "executed")
            ).execute()
            executed_trades: Sequence[Dict[str, Any]] = resp.data or []
        except Exception as exc:  # noqa: BLE001
            logger.error("TradeWatchdog: failed to fetch executed trades: %s", exc)
            return

        if not executed_trades:
            return

        positions = self._get_client(
            f"/users/current/accounts/{self.account_id}/positions",
        )
        if positions is None:
            return

        # Build a set of currently-open broker tickets
        open_ids: set[str] = set()
        for pos in positions or []:
            pid = pos.get("id") or pos.get("positionId")
            if pid is not None:
                open_ids.add(str(pid))

        for trade in executed_trades:
            broker_id = str(trade.get("broker_order_id") or "").strip()
            if not broker_id:
                continue
            if broker_id in open_ids:
                # Still open on broker; nothing to do yet.
                continue

            # Position is no longer in open positions – resolve as silent exit.
            try:
                self._resolve_closed_trade(trade, broker_id)
            except Exception as exc:  # noqa: BLE001
                logger.error(
                    "TradeWatchdog: failed to resolve closed trade %s (ticket %s): %s",
                    trade.get("id"),
                    broker_id,
                    exc,
                )

    # ------------------------------------------------------------------ #
    # Internal helpers
    # ------------------------------------------------------------------ #

    def _resolve_closed_trade(self, trade: Dict[str, Any], position_id: str) -> None:
        """
        Given a Supabase trade and its broker positionId, query MetaApi
        history-deals and update the trade with PnL and exit information.
        """
        if not self.supabase:
            return

        # Look back 30 days in history. We use the MetaApi client REST
        # `history-deals/time` endpoint which accepts ISO8601 timestamps.
        now = datetime.now(timezone.utc)
        start = now - timedelta(days=30)
        start_str = start.isoformat().replace("+00:00", "Z")
        end_str = now.isoformat().replace("+00:00", "Z")

        deals = self._get_client(
            f"/users/current/accounts/{self.account_id}/history-deals/time/{start_str}/{end_str}",
        )
        if not deals:
            logger.warning(
                "TradeWatchdog: no historical trades payload for account %s when inspecting ticket %s",
                self.account_id,
                position_id,
            )
            return

        # Client history-deals returns an array of MetatraderDeal objects.
        if not isinstance(deals, list) or not deals:
            logger.warning(
                "TradeWatchdog: no history deals returned for account %s when inspecting ticket %s",
                self.account_id,
                position_id,
            )
            return

        # Find exit deal(s) for this positionId.
        matching: List[Dict[str, Any]] = []
        for d in deals:
            pid = d.get("positionId")
            if pid is None:
                continue
            if str(pid) != str(position_id):
                continue
            matching.append(d)

        if not matching:
            logger.warning(
                "TradeWatchdog: no DEAL_ENTRY_OUT found for ticket %s", position_id,
            )
            return

        # Use the latest trade (by close time if available).
        matching.sort(key=lambda d: d.get("closeTime") or d.get("time") or "")
        exit_deal = matching[-1]

        profit = float(exit_deal.get("profit", 0.0) or 0.0)
        # MetaStats trades response already includes net profit, so swap/commission
        # are either baked in or absent; treat them as zero if missing.
        swap = float(exit_deal.get("swap", 0.0) or 0.0)
        commission = float(exit_deal.get("commission", 0.0) or 0.0)
        total_pnl = profit + swap + commission

        price = float(
            exit_deal.get("closePrice")
            or exit_deal.get("price", 0.0)
            or 0.0,
        )
        outcome = "win" if total_pnl > 0 else "loss" if total_pnl < 0 else "breakeven"

        update_data = {
            "status": "closed",
            "pnl_usd": total_pnl,
            "outcome": outcome,
            "exit_price": price or None,
            # `close_broker_order_id` column may not exist in older schemas;
            # we keep the update compatible by omitting it.
            "notes": "Auto-Resolved via Watchdog",
            "closed_at": datetime.now(timezone.utc).isoformat(),
        }

        alert_id = trade.get("id")
        if alert_id is None:
            logger.error(
                "TradeWatchdog: trade without id for ticket %s, skipping Supabase update",
                position_id,
            )
            return

        try:
            self.supabase.table("trading_signals").update(update_data).eq(
                "id", alert_id,
            ).execute()
            logger.info(
                "TradeWatchdog: synced silent exit for alert #%s (ticket %s, pnl_usd=%.2f)",
                alert_id,
                position_id,
                total_pnl,
            )
        except Exception as exc:  # noqa: BLE001
            logger.error(
                "TradeWatchdog: Supabase update failed for alert #%s: %s",
                alert_id,
                exc,
            )

