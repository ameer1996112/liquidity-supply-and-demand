"""
Broker Reconciliation Service

Periodically reconciles database trade states with broker (MetaAPI) truth.
Handles trades closed by broker-side SL/TP that didn't fire exit webhooks.

This prevents "ghost positions" where DB shows OPEN but broker already closed the trade.
"""


import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, Optional

from supabase import create_client, Client

from src.adapters.execution.meta_api_adapter import MetaApiAdapter

logger = logging.getLogger(__name__)


class BrokerReconciliation:
    """
    Reconciles DB trade states with broker positions.
    """

    def __init__(self, supabase_client: Client, meta_api: MetaApiAdapter, broker_profile_id: int):
        self.supabase = supabase_client
        self.meta_api = meta_api
        self.broker_profile_id = broker_profile_id

    def run_reconciliation(self) -> Dict[str, Any]:
        """
        Main reconciliation loop.

        Returns:
            Dict with reconciliation stats: closed_count, updated_ids, errors
        """
        stats = {
            "closed_count": 0,
            "updated_ids": [],
            "errors": [],
        }

        try:
            # 1. Fetch all DB trades marked as active/executed
            db_trades = self._get_active_db_trades()
            if not db_trades:
                logger.debug("No active trades in DB to reconcile")
                return stats

            # 2. Fetch open positions from broker
            broker_positions = self.meta_api.get_open_positions()
            broker_ticket_ids = {p.get("id") for p in broker_positions if p.get("id")}

            logger.info(
                "Broker reconciliation: DB has %d active trades, broker has %d open positions",
                len(db_trades),
                len(broker_positions),
            )

            # 3. For each DB trade, check if it still exists in broker
            for trade in db_trades:
                # FIX 1: Per-trade isolation — a bad trade must NOT crash the entire loop.
                # Log the error and continue to the next trade.
                try:
                    trade_id = trade.get("id")
                    broker_order_id = trade.get("broker_order_id")

                    if not broker_order_id:
                        logger.debug(f"Trade {trade_id}: no broker_order_id, skipping")
                        continue

                    # Check if this trade's position still exists in broker
                    # Note: broker_order_id in DB corresponds to position id in MetaAPI
                    str_ticket = str(broker_order_id)

                    if str_ticket not in broker_ticket_ids:
                        # Trade is no longer open in broker - it was closed by SL/TP
                        logger.info(f"Trade {trade_id}: ticket {broker_order_id} not in broker positions - closed externally")

                        # 4. Fetch the closed deal to get final PnL
                        closed_deal = self._fetch_closed_deal(trade)

                        if closed_deal:
                            # 5. Update DB with final trade state
                            self._update_trade_closed(trade, closed_deal)
                            stats["closed_count"] += 1
                            stats["updated_ids"].append(trade_id)
                            logger.info(
                                f"Reconciled trade {trade_id}: closed at {closed_deal.get('price')}, "
                                f"PnL={closed_deal.get('profit')}",
                            )
                        else:
                            # Couldn't find deal - mark as closed with estimated PnL
                            logger.warning(f"Could not fetch closed deal for trade {trade_id}, using current data")
                            self._update_trade_closed_fallback(trade)
                            stats["closed_count"] += 1
                            stats["updated_ids"].append(trade_id)
                    else:
                        logger.debug(f"Trade {trade_id}: ticket {broker_order_id} still open in broker")

                except Exception as trade_exc:
                    # Isolate the failure: log it and move on to the next trade.
                    logger.error(
                        f"Reconciliation error for trade {trade.get('id')} "
                        f"(broker_order_id={trade.get('broker_order_id')}): {trade_exc}"
                    )
                    stats["errors"].append(f"trade_{trade.get('id')}: {str(trade_exc)[:100]}")
                    continue

        except Exception as e:
            logger.error(f"Broker reconciliation failed: {e}")
            stats["errors"].append(str(e))

        return stats

    def _get_active_db_trades(self) -> list:
        """Fetch trades with status active/executed/OPEN from DB."""
        response = (
            self.supabase.table("trading_signals")
            .select("id, symbol, side, size, entry, filled_entry_price, sl, tp, status, pnl_usd, broker_order_id, closed_at, outcome")
            .in_("status", ["active", "executed", "ACTIVE", "EXECUTED", "OPEN", "open"])
            .eq("broker_profile_id", self.broker_profile_id)
            .execute()
        )
        return response.data or []

    def _fetch_closed_deal(self, trade: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Fetch the closed deal from broker history for a specific trade (INTERNAL)."""
        # Get recent deals — look back 7 days to cover trades held for several days.
        end_time = datetime.now(timezone.utc)
        start_time = end_time - timedelta(days=7)

        start_str = start_time.strftime("%Y-%m-%dT%H:%M:%SZ")
        end_str = end_time.strftime("%Y-%m-%dT%H:%M:%SZ")

        deals = self.meta_api.get_historical_deals(start_str, end_str)

        # Find deal matching our trade by broker_order_id (positionId or orderId)
        broker_order_id = str(trade.get("broker_order_id"))

        # FIX 2: Only match by strict ID — never fall back to symbol-only matching.
        # A symbol-only fallback would return the wrong deal if two positions of the
        # same symbol are open concurrently, corrupting PnL for both.
        for deal in deals:
            position_id = str(deal.get("positionId", ""))
            order_id = str(deal.get("orderId", ""))

            if position_id == broker_order_id or order_id == broker_order_id:
                if deal.get("entryType") == "DEAL_ENTRY_OUT":
                    return deal

        logger.warning(f"No closed deal found for trade {trade.get('id')} (ticket {broker_order_id})")
        return None

    def fetch_closing_deal(self, position_id: str, symbol: str, since_time: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """
        Public helper: Fetch DEAL_ENTRY_OUT for position since watermark.
        Used by: logic.py (instant), watchdog.py (background).
        """
        end_time = datetime.now(timezone.utc)
        if since_time:
            start_time = datetime.fromisoformat(since_time.replace("Z", "+00:00"))
        else:
            start_time = end_time - timedelta(hours=2)  # Default window

        start_str = start_time.strftime("%Y-%m-%dT%H:%M:%SZ")
        end_str = end_time.strftime("%Y-%m-%dT%H:%M:%SZ")

        deals = self.meta_api.get_historical_deals(start_str, end_str)

        # OPTIMIZED: positionId + DEAL_ENTRY_OUT + symbol
        for deal in deals:
            if (str(deal.get("positionId", "")) == position_id and 
                deal.get("entryType") == "DEAL_ENTRY_OUT" and
                deal.get("symbol", "").upper() == symbol.upper()):
                profit = float(deal.get("profit", 0))
                commission = float(deal.get("commission", 0))
                swap = float(deal.get("swap", 0))
                return {
                    "profit": profit,
                    "commission": commission,
                    "swap": swap,
                    "total_pnl": profit + commission + swap,
                    "exit_price": float(deal.get("price", 0)),
                    "exit_time": deal.get("time")
                }

        logger.debug(f"No closing deal for position {position_id}/{symbol} since {since_time or '2h'} ({len(deals)} deals)")
        return None

    @staticmethod
    def get_last_closed_timestamp(supabase_client) -> str:
        """Watermark: return most recent closed_at timestamp."""
        try:
            resp = supabase_client.table("trading_signals") \
                .select("closed_at").eq("status", "closed") \
                .order("closed_at", desc=True).limit(1).execute()
            return resp.data[0]["closed_at"] if resp.data else \
                   (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
        except:
            return (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()

    def _update_trade_closed(self, trade: Dict[str, Any], deal: Dict[str, Any]) -> None:
        """Update trade in DB with final closed state from broker deal."""

        # Extract PnL components from deal.
        # MT5 treats commission as a separate account-level item — the per-trade
        # profit shown in MT5 History is GROSS profit (before commission).
        # We store gross profit in pnl_usd to match what MT5 shows, and keep
        # commission/swap in their own columns for the account-level totals.
        profit = float(deal.get("profit", 0.0) or 0.0)
        commission = float(deal.get("commission", 0.0) or 0.0)
        swap = float(deal.get("swap", 0.0) or 0.0)

        # Determine outcome from gross profit (matching MT5 semantics)
        if profit > 0:
            outcome = "win"
        elif profit < 0:
            outcome = "loss"
        else:
            outcome = "breakeven"

        # Close price
        close_price = deal.get("price", trade.get("filled_entry_price", 0))

        # Closed at time
        closed_at = deal.get("time")
        if closed_at:
            if isinstance(closed_at, str):
                try:
                    closed_at = datetime.fromisoformat(closed_at.replace("Z", "+00:00"))
                except:
                    closed_at = datetime.now(timezone.utc)
        else:
            closed_at = datetime.now(timezone.utc)

        # Update DB — pnl_usd = gross profit (matches MT5 per-trade display)
        self.supabase.table("trading_signals").update({
            "status": "closed",
            "outcome": outcome,
            "pnl_usd": profit,
            "closed_at": closed_at.isoformat(),
            "exit_fill_price": close_price,
            "commission": commission,
            "swap": swap,
        }).eq("id", trade["id"]).execute()

        logger.info(
            f"Updated trade {trade['id']}: outcome={outcome}, gross_pnl={profit:.2f}, "
            f"commission={commission:.2f}, swap={swap:.2f}, "
            f"closed_at={closed_at.isoformat()}",
        )


    def _update_trade_closed_fallback(self, trade: Dict[str, Any]) -> None:
        """Update trade when we can't fetch deal details - use current DB data."""
        # Mark as closed with whatever PnL we have
        pnl = trade.get("pnl_usd") or trade.get("pnl") or 0.0

        if pnl > 0:
            outcome = "win"
        elif pnl < 0:
            outcome = "loss"
        else:
            outcome = "breakeven"

        self.supabase.table("trading_signals").update({
            "status": "closed",
            "outcome": outcome,
            "closed_at": datetime.now(timezone.utc).isoformat(),
        }).eq("id", trade["id"]).execute()

        logger.warning(f"Updated trade {trade['id']} (fallback): outcome={outcome}, pnl={pnl:.2f}")


def run_reconciliation_for_profile(
    supabase_url: str,
    supabase_key: str,
    broker_profile_id: int,
    meta_api_token: str,
    meta_api_account_id: str,
    meta_api_region: str = "london",
) -> Dict[str, Any]:
    """
    Standalone function to run reconciliation for a single broker profile.
    Use this from worker.py or cron.
    """
    supabase: Client = create_client(supabase_url, supabase_key)

    # Create MetaAPI adapter
    meta_api = MetaApiAdapter(
        account_id=meta_api_account_id,
        token=meta_api_token,
        region=meta_api_region,
    )

    reconciler = BrokerReconciliation(supabase, meta_api, broker_profile_id)
    return reconciler.run_reconciliation()
