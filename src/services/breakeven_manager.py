"""
Breakeven Manager Service

Monitors open positions that have a Pine-computed be_trigger_price and moves
the stop loss to be_sl_price (+ configurable buffer) on the broker the moment
price crosses the trigger.

v1.1 Phase 9 additions:
- BE buffer: SL moves to entry + BREAKEVEN_BUFFER_PIPS instead of exact entry
- Trailing stop auto-activation: after BE fires, activates TrailingStopManager

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
    """Move SL to break-even (+ buffer) on the broker when price crosses the trigger level.

    After BE fires, automatically activates a trailing stop via TrailingStopManager
    if one is injected.
    """

    INDEX_KEYWORDS = ["NAS100", "US30", "SPX", "UK100", "GER", "FRA", "JPN225", "AUS200"]
    GOLD_KEYWORDS = ["XAU", "GOLD", "XAG", "SILVER"]

    def __init__(self, supabase_client, adapter=None, trailing_stop_manager=None):
        self.client = supabase_client
        self.adapter = adapter
        self.trailing_stop_manager = trailing_stop_manager  # Optional: auto-activate trail after BE

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

    def _get_pip_size(self, symbol: str) -> float:
        """Return pip size for the given symbol."""
        symbol_upper = symbol.upper()
        if any(kw in symbol_upper for kw in self.INDEX_KEYWORDS):
            return 1.0  # index points
        elif any(kw in symbol_upper for kw in self.GOLD_KEYWORDS):
            return 0.01
        elif "JPY" in symbol_upper:
            return 0.01
        else:
            return 0.0001  # standard forex

    def _get_be_buffer_pips(self) -> float:
        """Return the configured breakeven buffer in pips (default 3.0)."""
        try:
            from config import get_settings
            s = get_settings()
            return float(getattr(s, "breakeven_buffer_pips", 3.0))
        except Exception:
            return 3.0

    def _get_trail_distance(self, symbol: str) -> float:
        """Return trailing stop distance in pips/points for the given symbol."""
        try:
            from config import get_settings
            s = get_settings()
            symbol_upper = symbol.upper()
            if any(kw in symbol_upper for kw in self.INDEX_KEYWORDS):
                return float(getattr(s, "trail_distance_points_indices", 30.0))
            elif any(kw in symbol_upper for kw in self.GOLD_KEYWORDS):
                return float(getattr(s, "trail_distance_pips_gold", 50.0))
            else:
                return float(getattr(s, "trail_distance_pips_forex", 15.0))
        except Exception:
            return 15.0

    def _apply_be_buffer(self, be_sl_price: float, entry: float, side: str, symbol: str) -> float:
        """
        Shift be_sl_price by breakeven_buffer_pips above entry (buy) or below (sell).

        Only adjusts if the Pine-supplied be_sl_price is at or below entry for buys
        (or at/above entry for sells) — i.e. we never reduce a Pine-supplied profitable BE.
        """
        buffer_pips = self._get_be_buffer_pips()
        if buffer_pips <= 0:
            return be_sl_price

        pip_size = self._get_pip_size(symbol)
        buffer = buffer_pips * pip_size

        if side == "buy":
            adjusted = entry + buffer
            if be_sl_price < adjusted:
                logger.info(
                    "BreakevenManager: BE buffer applied +%.1f pips → sl %.5f → %.5f (%s buy)",
                    buffer_pips, be_sl_price, adjusted, symbol,
                )
                return adjusted
        else:  # sell
            adjusted = entry - buffer
            if be_sl_price > adjusted:
                logger.info(
                    "BreakevenManager: BE buffer applied +%.1f pips → sl %.5f → %.5f (%s sell)",
                    buffer_pips, be_sl_price, adjusted, symbol,
                )
                return adjusted

        return be_sl_price

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
        entry = float(row.get("entry") or 0)

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

        # Apply breakeven buffer (v1.1 Phase 9)
        if entry > 0:
            be_sl_price = self._apply_be_buffer(be_sl_price, entry, side, symbol)

        logger.info(
            "BreakevenManager: trigger hit for signal %s (%s %s) "
            "price=%.5f trigger=%.5f → moving SL to %.5f",
            signal_id, side, symbol, current_price, be_trigger_price, be_sl_price,
        )

        # Move SL on broker
        broker_ok = self._modify_broker_sl(broker_order_id, be_sl_price)

        # Always mark triggered in DB (even if broker call fails — avoids infinite retries)
        self._mark_triggered(signal_id, be_sl_price, broker_ok, row=row)

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

    def _mark_triggered(
        self,
        signal_id: int,
        new_sl: float,
        broker_ok: bool,
        row: Optional[Dict] = None,
    ) -> None:
        """Persist be_triggered=TRUE, update sl in the DB, and activate trailing stop."""
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

            # Auto-activate trailing stop (v1.1 Phase 9)
            if self.trailing_stop_manager and row and broker_ok:
                self._activate_trailing_stop(signal_id, row, new_sl)

        except Exception as exc:
            logger.error(
                "BreakevenManager: failed to mark signal %s as triggered: %s", signal_id, exc
            )

    def _activate_trailing_stop(self, signal_id: int, row: Dict, be_sl_price: float) -> None:
        """Activate trailing stop after breakeven fires (v1.1 Phase 9)."""
        try:
            from config import get_settings
            s = get_settings()

            symbol = row["symbol"]
            side = (row.get("side") or "").lower()
            entry = float(row.get("entry") or 0)

            if entry <= 0:
                logger.warning(
                    "BreakevenManager: cannot activate trailing stop for signal %s — no entry price",
                    signal_id,
                )
                return

            pip_size = self._get_pip_size(symbol)
            trail_pips = self._get_trail_distance(symbol)
            activation_pips = float(getattr(s, "trail_activation_pips", 0.0))

            # Compute activation threshold (None = trail starts immediately)
            activation_price: Optional[float] = None
            if activation_pips > 0:
                if side == "buy":
                    activation_price = entry + (activation_pips * pip_size)
                else:
                    activation_price = entry - (activation_pips * pip_size)

            ts_id = self.trailing_stop_manager.add_trailing_stop(
                signal_id=signal_id,
                symbol=symbol,
                side=side,
                trail_distance_pips=trail_pips,
                activation_price=activation_price,
                entry_price=entry,
            )

            if ts_id:
                logger.info(
                    "BreakevenManager: trailing stop activated for signal %s (%s %s) "
                    "trail=%.1f pips/pts, activation=%s",
                    signal_id, side, symbol, trail_pips,
                    f"{activation_price:.5f}" if activation_price else "immediate",
                )
                # Log trail_started lifecycle event
                try:
                    from src.services.trade_events import log_event
                    log_event(signal_id, "trail_started", "breakeven_manager", {
                        "trail_distance_pips": trail_pips,
                        "activation_price": activation_price,
                        "entry_price": entry,
                        "symbol": symbol,
                    })
                except Exception:
                    pass
            else:
                logger.warning(
                    "BreakevenManager: trailing stop activation returned no ID for signal %s",
                    signal_id,
                )

        except Exception as exc:
            logger.error(
                "BreakevenManager: trailing stop activation failed for signal %s: %s",
                signal_id, exc,
            )
