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
import time
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

    def _get_with_retry(
        self,
        base_url: str,
        path: str,
        params: Optional[Dict[str, Any]] = None,
        max_attempts: int = 3,
    ) -> Optional[requests.Response]:
        """GET with retries (1s, 2s backoff) on timeout/5xx. Returns Response or None."""
        if not self.token or not self.account_id:
            return None
        url = f"{base_url}{path}"
        for attempt in range(max_attempts):
            try:
                resp = requests.get(url, headers=self._headers(), params=params, timeout=10)
            except (requests.exceptions.Timeout, requests.exceptions.ConnectionError, OSError) as exc:
                logger.warning("TradeWatchdog GET %s attempt %s failed: %s", url[:80], attempt + 1, exc)
                if attempt < max_attempts - 1:
                    time.sleep(1.0 + attempt)
                continue
            if 500 <= resp.status_code < 600 and attempt < max_attempts - 1:
                logger.warning("TradeWatchdog GET %s HTTP %s; retrying", url[:80], resp.status_code)
                time.sleep(1.0 + attempt)
                continue
            return resp
        return None

    def _get_client(self, path: str, params: Optional[Dict[str, Any]] = None) -> Optional[Any]:
        """GET wrapper against the MetaApi client API (positions, etc.)."""
        resp = self._get_with_retry(self.client_base_url, path, params)
        if resp is None or resp.status_code != 200:
            if resp is not None:
                logger.error(
                    "TradeWatchdog client GET %s failed: HTTP %s %s",
                    f"{self.client_base_url}{path}"[:80],
                    resp.status_code,
                    resp.text[:200],
                )
            return None
        try:
            return resp.json()
        except ValueError:
            logger.error("TradeWatchdog client GET invalid JSON: %s", resp.text[:200])
            return None

    def _get_stats(self, path: str, params: Optional[Dict[str, Any]] = None) -> Optional[Any]:
        """GET wrapper against the MetaStats API (history-deals)."""
        if not self.token or not self.account_id:
            return None
        resp = self._get_with_retry(self.stats_base_url, path, params)
        if resp is None or resp.status_code != 200:
            if resp is not None:
                logger.error(
                    "TradeWatchdog stats GET %s failed: HTTP %s %s",
                    f"{self.stats_base_url}{path}"[:80],
                    resp.status_code,
                    resp.text[:200],
                )
            return None
        try:
            return resp.json()
        except ValueError:
            logger.error("TradeWatchdog stats GET invalid JSON: %s", resp.text[:200])
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
            from src.core.circuit_breaker import is_metaapi_circuit_open
            if is_metaapi_circuit_open():
                logger.debug("TradeWatchdog: circuit breaker open, skipping sync")
                return
        except Exception:  # noqa: BLE001
            pass

        try:
            # FIX 3: Include all active statuses — logic.py writes 'OPEN' on fill,
            # but legacy/partial paths may write 'executed'/'active'. Include them all
            # so the watchdog can detect silent exits regardless of the write path.
            resp = (
                self.supabase.table("trading_signals")
                .select("*")
                .eq("run_mode", "LIVE")
                .in_("status", ["executed", "OPEN", "active", "ACTIVE", "open"])
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
        Chain-link lookup: DB stores broker_order_id (Order ID / Entry Ticket);
        MetaTrader history groups deals by Position ID. Find Entry Deal first to
        get real Position ID, then find Exit Deal by that Position ID.
        """
        if not self.supabase:
            return

        # 1. Fetch history: path-based URL, start 30 days ago, end now+24h (broker TZ buffer)
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

        # 2. Step 1: Find real Position ID (entry lookup)
        real_position_id: Optional[str] = None
        for deal in deals:
            if str(deal.get("orderId")) == str(ticket_id):
                pos = deal.get("positionId")
                real_position_id = str(pos) if pos is not None else None
                logger.info(
                    "🔗 Linked Order %s to Position %s",
                    ticket_id,
                    real_position_id,
                )
                break

        if not real_position_id:
            logger.warning(
                "TradeWatchdog: no entry order found for %s; assuming it IS the Position ID",
                ticket_id,
            )
            real_position_id = ticket_id

        # 3. Step 2: Find exit deal for this position
        exit_types = ("DEAL_ENTRY_OUT", "DEAL_ENTRY_INOUT", "DEAL_ENTRY_OUT_BY")
        exit_candidates: List[Dict[str, Any]] = []
        for deal in deals:
            if str(deal.get("positionId")) != str(real_position_id):
                continue
            if deal.get("entryType") in exit_types:
                exit_candidates.append(deal)

        if not exit_candidates:
            logger.warning(
                "TradeWatchdog: Position %s has no Exit Deal (deals in window: %s)",
                real_position_id,
                len(deals),
            )
            return

        exit_candidates.sort(key=lambda d: d.get("time") or "")
        exit_deal = exit_candidates[-1]

        # 4. Step 3: Update database
        profit = float(exit_deal.get("profit", 0.0) or 0.0)
        swap = float(exit_deal.get("swap", 0.0) or 0.0)
        commission = float(exit_deal.get("commission", 0.0) or 0.0)
        total_pnl = profit + swap + commission
        outcome = "win" if total_pnl > 0 else "loss" if total_pnl < 0 else "breakeven"
        exit_fill_price = float(exit_deal.get("price", 0.0) or exit_deal.get("closePrice") or 0.0)
        exit_time = datetime.now(timezone.utc).isoformat()

        alert_id = trade.get("id")
        if alert_id is None:
            logger.error(
                "TradeWatchdog: trade without id for ticket %s, skipping update",
                ticket_id,
            )
            return

        # Schema uses exit_price and closed_at (frontend/DB); map exit_fill_price → exit_price, exit_time → closed_at
        update_data = {
            "status": "closed",
            "pnl_usd": total_pnl,
            "outcome": outcome,
            "exit_price": exit_fill_price or None,
            "closed_at": exit_time,
            "notes": "Auto-Resolved via Watchdog",
        }

        try:
            self.supabase.table("trading_signals").update(update_data).eq(
                "id", alert_id,
            ).execute()
            logger.info(
                "✅ Auto-Resolved: PnL=$%.2f (%s)",
                total_pnl,
                outcome,
            )
            # Sprint 4.3: Create reflection on close (when MEMORY_ENABLED)
            try:
                from src.services.reflection_service import create_reflection_on_close_safe
                merged = {**trade, **update_data}
                create_reflection_on_close_safe(self.supabase, alert_id, merged)
            except Exception:  # noqa: BLE001
                pass
        except Exception as exc:  # noqa: BLE001
            logger.error(
                "TradeWatchdog: Supabase update failed for alert #%s: %s",
                alert_id,
                exc,
            )

    # ------------------------------------------------------------------ #
    # Phase 11: Late Fill Detection
    # ------------------------------------------------------------------ #

    def check_late_fills(self) -> int:
        """
        Scan PENDING/OPEN signals that still have no broker_order_id after
        >TCA_LATENCY_THRESHOLD_MS milliseconds (default 30s).

        When a late fill is detected:
        - Logs a trade_event: 'late_fill_alert'
        - Emits a Discord/Telegram notification (via existing async notify path)

        Returns the number of late-fill alerts fired this call.
        """
        if not self.supabase:
            return 0

        try:
            threshold_ms = int(
                getattr(self.settings, "tca_latency_threshold_ms", 30000)
            )
            threshold_s = threshold_ms / 1000.0

            from datetime import datetime, timedelta, timezone
            cutoff = (datetime.now(timezone.utc) - timedelta(seconds=threshold_s)).isoformat()

            resp = (
                self.supabase.table("trading_signals")
                .select("id, symbol, side, entry, created_at")
                .in_("status", ["PENDING", "pending", "queued"])
                .is_("broker_order_id", "null")
                .lt("created_at", cutoff)
                .limit(20)
                .execute()
            )
            late_signals = resp.data or []
        except Exception as exc:
            logger.debug("TradeWatchdog.check_late_fills: fetch failed: %s", exc)
            return 0

        alerted = 0
        for sig in late_signals:
            signal_id = sig.get("id")
            symbol = sig.get("symbol", "?")
            try:
                # Log trade_event for audit trail
                try:
                    from src.services.trade_events import log_event
                    log_event(signal_id, "late_fill_alert", "watchdog", {
                        "symbol": symbol,
                        "side": sig.get("side"),
                        "threshold_seconds": threshold_s,
                        "created_at": sig.get("created_at"),
                    })
                except Exception:
                    pass

                # Fire Discord alert
                try:
                    from src.adapters.discord import send_discord_async
                    send_discord_async(
                        {
                            "symbol": symbol,
                            "side": sig.get("side", ""),
                            "entry": sig.get("entry", 0),
                            "_guard_reason": (
                                f"🕐 Late Fill Alert: signal #{signal_id} ({symbol}) "
                                f"has no broker confirmation after {threshold_s:.0f}s"
                            ),
                            "_guard_blocked": False,
                        },
                        alert_id=signal_id,
                        mode="guard_blocked",
                    )
                except Exception:
                    pass

                logger.warning(
                    "TradeWatchdog: LATE FILL — signal #%s (%s) still PENDING "
                    "after %.0fs (no broker_order_id). Possible execution failure.",
                    signal_id, symbol, threshold_s,
                )
                alerted += 1
            except Exception as exc:
                logger.debug("TradeWatchdog.check_late_fills: error on signal %s: %s", signal_id, exc)

        return alerted



