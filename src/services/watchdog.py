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

    def _resolve_closed_trade(self, trade: Dict[str, Any], ticket_id: str) -> None:
        """
        Resolve a closed trade by looking up history-deals. DB stores broker_order_id
        which in MT5 is often the Order ID (entry order), not the Position ID.
        Use a 2-step lookup: (1) find entry deal by orderId → get positionId,
        (2) find exit deal by positionId and entryType OUT.
        """
        if not self.supabase:
            return

        # 1. Fetch history with wide time window (+24h end buffer for server TZ)
        now = datetime.now(timezone.utc)
        start_dt = now - timedelta(days=30)
        end_dt = now + timedelta(hours=24)
        start_str = start_dt.isoformat().replace("+00:00", "Z")
        end_str = end_dt.isoformat().replace("+00:00", "Z")

        raw = self._get_client(
            f"/users/current/accounts/{self.account_id}/history-deals/time/{start_str}/{end_str}",
        )
        if raw is None:
            logger.warning(
                "TradeWatchdog: no history response for account %s ticket %s",
                self.account_id,
                ticket_id,
            )
            return

        # API may return list or {"deals": [...]}
        if isinstance(raw, dict):
            deals = raw.get("deals") or []
        else:
            deals = raw if isinstance(raw, list) else []
        if not deals:
            logger.warning(
                "TradeWatchdog: no history deals for account %s ticket %s",
                self.account_id,
                ticket_id,
            )
            return

        # 2. Step 1 – Find ENTRY deal (orderId == broker_order_id) to get real Position ID
        real_position_id: Optional[str] = None
        for deal in deals:
            if str(deal.get("orderId")) == str(ticket_id):
                real_position_id = deal.get("positionId")
                if real_position_id is not None:
                    real_position_id = str(real_position_id)
                logger.info(
                    "TradeWatchdog: found Entry Deal: ID=%s PositionID=%s",
                    deal.get("id"),
                    real_position_id,
                )
                break

        if not real_position_id:
            logger.warning(
                "TradeWatchdog: could not link Order %s to a Position; assuming it IS the Position ID",
                ticket_id,
            )
            real_position_id = ticket_id

        # 3. Step 2 – Find EXIT deal for this position
        exit_types = ("DEAL_ENTRY_OUT", "DEAL_ENTRY_INOUT", "DEAL_ENTRY_OUT_BY")
        exit_deal: Optional[Dict[str, Any]] = None
        exit_candidates: List[Dict[str, Any]] = []
        for deal in deals:
            if str(deal.get("positionId")) != str(real_position_id):
                continue
            if deal.get("entryType") in exit_types:
                exit_candidates.append(deal)

        if exit_candidates:
            exit_candidates.sort(key=lambda d: d.get("time") or "")
            exit_deal = exit_candidates[-1]
            logger.info(
                "TradeWatchdog: found Exit Deal: ID=%s PnL=%s",
                exit_deal.get("id"),
                exit_deal.get("profit"),
            )

        if not exit_deal:
            logger.warning(
                "TradeWatchdog: Position %s has no Exit Deal yet (deals in window: %s)",
                real_position_id,
                len(deals),
            )
            return

        # 4. Calculate PnL and outcome
        profit = float(exit_deal.get("profit", 0.0) or 0.0)
        swap = float(exit_deal.get("swap", 0.0) or 0.0)
        commission = float(exit_deal.get("commission", 0.0) or 0.0)
        total_pnl = profit + swap + commission
        outcome = "win" if total_pnl > 0 else "loss" if total_pnl < 0 else "breakeven"
        price = float(exit_deal.get("price", 0.0) or exit_deal.get("closePrice") or 0.0)

        update_data = {
            "status": "closed",
            "pnl_usd": total_pnl,
            "outcome": outcome,
            "exit_price": price or None,
            "notes": "Auto-Resolved via Watchdog",
            "closed_at": datetime.now(timezone.utc).isoformat(),
        }

        alert_id = trade.get("id")
        if alert_id is None:
            logger.error(
                "TradeWatchdog: trade without id for ticket %s, skipping Supabase update",
                ticket_id,
            )
            return

        try:
            self.supabase.table("trading_signals").update(update_data).eq(
                "id", alert_id,
            ).execute()
            logger.info(
                "TradeWatchdog: synced silent exit for alert #%s (ticket %s, pnl_usd=%.2f)",
                alert_id,
                ticket_id,
                total_pnl,
            )
        except Exception as exc:  # noqa: BLE001
            logger.error(
                "TradeWatchdog: Supabase update failed for alert #%s: %s",
                alert_id,
                exc,
            )

