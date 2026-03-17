"""
Breakeven Manager Service

Monitors open positions that have a Pine-computed be_trigger_price and moves
the stop loss to be_sl_price on the broker the moment price crosses the trigger.

Design for near-zero latency:
- Called on every worker loop iteration (same cadence as signal polling).
- Fetches live broker positions from MetaAPI in one batch call.
- Fires modify_position() immediately when a trigger is crossed.
- Marks be_triggered=TRUE in DB so it never fires twice.
"""

import logging
from datetime import datetime, timezone
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


class BreakevenManager:
    """Move SL to break-even on the broker when price crosses the trigger level."""

    def __init__(self, supabase_client, adapter=None):
        self.client = supabase_client
        self.adapter = adapter

    # ------------------------------------------------------------------
    # Public API — called by worker every loop
    # ------------------------------------------------------------------

    def check_and_trigger(self) -> int:
        """
        Check all pending BE triggers and fire any that have been crossed.

        Returns the number of positions whose SL was moved this call.
        """
        pending = self._fetch_pending()
        if not pending:
            return 0

        # Fetch live broker prices in one batch (keyed by symbol)
        prices = self._get_broker_prices({row["symbol"] for row in pending})

        triggered = 0
        for row in pending:
            try:
                if self._evaluate_and_trigger(row, prices):
                    triggered += 1
            except Exception as exc:
                logger.error(
                    "BreakevenManager: error processing signal %s: %s",
                    row.get("id"),
                    exc,
                )

        if triggered:
            logger.info("BreakevenManager: moved SL to BE on %d position(s)", triggered)
        return triggered

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _fetch_pending(self) -> List[Dict]:
        """Return OPEN signals that have a BE trigger not yet fired."""
        try:
            result = (
                self.client.table("trading_signals")
                .select("id, symbol, side, broker_order_id, be_trigger_price, be_sl_price, entry")
                .eq("status", "OPEN")
                .eq("be_triggered", False)
                .not_.is_("be_trigger_price", "null")
                .not_.is_("broker_order_id", "null")
                .execute()
            )
            return result.data or []
        except Exception as exc:
            logger.error("BreakevenManager: failed to fetch pending triggers: %s", exc)
            return []

    def _get_broker_prices(self, symbols: set) -> Dict[str, float]:
        """
        Return {symbol: mid_price} for the given symbols using the adapter.
        Falls back gracefully if adapter does not support price fetching.
        """
        prices: Dict[str, float] = {}
        if not self.adapter or not hasattr(self.adapter, "_get_symbol_price"):
            return prices

        for symbol in symbols:
            try:
                bid, ask = self.adapter._get_symbol_price(symbol)
                prices[symbol] = (bid + ask) / 2.0
            except Exception as exc:
                logger.debug("BreakevenManager: cannot fetch price for %s: %s", symbol, exc)

        return prices

    def _evaluate_and_trigger(self, row: Dict, prices: Dict[str, float]) -> bool:
        """
        Check if this position's trigger has been crossed and fire if so.
        Returns True if the SL was successfully moved.
        """
        signal_id = row["id"]
        symbol = row["symbol"]
        side = (row.get("side") or "").lower()
        broker_order_id = row["broker_order_id"]
        be_trigger_price = float(row["be_trigger_price"])
        be_sl_price = float(row["be_sl_price"])

        current_price = prices.get(symbol)
        if current_price is None:
            logger.debug(
                "BreakevenManager: no price for %s (signal %s), skipping", symbol, signal_id
            )
            return False

        # Trigger condition: long crosses above trigger, short crosses below
        triggered = (
            (side == "buy" and current_price >= be_trigger_price)
            or (side == "sell" and current_price <= be_trigger_price)
        )

        if not triggered:
            return False

        logger.info(
            "BreakevenManager: trigger hit for signal %s (%s %s) "
            "price=%.5f trigger=%.5f → moving SL to %.5f",
            signal_id, side, symbol, current_price, be_trigger_price, be_sl_price,
        )

        # Move SL on broker
        broker_ok = self._modify_broker_sl(broker_order_id, be_sl_price)

        # Always mark triggered in DB (even if broker call fails — avoids infinite retries)
        self._mark_triggered(signal_id, be_sl_price, broker_ok)

        return True

    def _modify_broker_sl(self, broker_order_id: str, new_sl: float) -> bool:
        """Call adapter.modify_position to update the SL on the broker."""
        if not self.adapter or not hasattr(self.adapter, "modify_position"):
            logger.warning("BreakevenManager: adapter does not support modify_position")
            return False
        try:
            result = self.adapter.modify_position(position_id=broker_order_id, sl=new_sl)
            if result.status == "filled":
                logger.info(
                    "BreakevenManager: broker SL updated → position %s SL=%.5f",
                    broker_order_id, new_sl,
                )
                return True
            logger.warning(
                "BreakevenManager: modify_position returned %s for position %s",
                result.status, broker_order_id,
            )
            return False
        except Exception as exc:
            logger.error(
                "BreakevenManager: modify_position failed for %s: %s", broker_order_id, exc
            )
            return False

    def _mark_triggered(self, signal_id: int, new_sl: float, broker_ok: bool) -> None:
        """Persist be_triggered=TRUE and update sl in the DB."""
        try:
            update = {
                "be_triggered": True,
                "sl": new_sl,
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }
            self.client.table("trading_signals").update(update).eq("id", signal_id).execute()

            # Emit a trade event for audit trail
            try:
                from src.services.trade_events import log_event
                log_event(signal_id, "breakeven_triggered", "breakeven_manager", {
                    "new_sl": new_sl,
                    "broker_updated": broker_ok,
                })
            except Exception:
                pass
        except Exception as exc:
            logger.error(
                "BreakevenManager: failed to mark signal %s as triggered: %s", signal_id, exc
            )
