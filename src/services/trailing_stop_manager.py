"""
Trailing Stop Manager Service

Automatically adjusts stop losses to follow favorable price movement.

Features:
- Activation price (wait until profit before trailing)
- Wait for breakeven option
- Configurable trail distance
- Automatic SL updates via broker adapter
"""

import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import List, Optional

logger = logging.getLogger(__name__)


@dataclass
class TrailingStop:
    """Represents an active trailing stop configuration."""
    id: int
    signal_id: int
    symbol: str
    side: str  # "buy" or "sell"
    trail_distance_pips: float
    activation_price: Optional[float]
    wait_for_breakeven: bool
    is_active: bool
    is_activated: bool
    current_sl: float
    highest_price_seen: Optional[float]
    lowest_price_seen: Optional[float]
    entry_price: float
    times_moved: int
    # R-ladder fields (added by migration 068)
    sl_distance_pips: Optional[float] = None
    r2_locked: bool = False
    r3_locked: bool = False


class TrailingStopManager:
    """Manages trailing stops for active positions."""

    PIP_SIZES = {
        "EURUSD": 0.0001, "GBPUSD": 0.0001, "USDJPY": 0.01,
        "USDCHF": 0.0001, "AUDUSD": 0.0001, "NZDUSD": 0.0001,
        "USDCAD": 0.0001, "EURJPY": 0.01, "GBPJPY": 0.01,
        "EURGBP": 0.0001, "AUDJPY": 0.01, "EURAUD": 0.0001,
        "XAUUSD": 0.01, "GOLD": 0.01,
    }

    def __init__(self, supabase_client, adapter=None):
        """
        Initialize trailing stop manager.

        Args:
            supabase_client: Supabase client for DB access
            adapter: Execution adapter for modifying SL on broker
        """
        self.client = supabase_client
        self.adapter = adapter

    def _get_pip_size(self, symbol: str) -> float:
        """Get pip size for a symbol."""
        symbol_clean = symbol.upper().replace(".", "")

        if symbol_clean in self.PIP_SIZES:
            return self.PIP_SIZES[symbol_clean]

        if "JPY" in symbol_clean:
            return 0.01
        return 0.0001

    def get_active_trailing_stops(self) -> List[TrailingStop]:
        """
        Fetch all active trailing stops with their position details.

        Returns:
            List of TrailingStop objects
        """
        try:
            # Join trailing_stops with trading_signals to get full position info
            result = self.client.table("trailing_stops").select(
                "*, trading_signals(symbol, side, entry, sl)"
            ).eq("is_active", True).execute()

            trailing_stops = []
            for row in result.data:
                signal = row.get("trading_signals")
                if not signal:
                    continue

                ts = TrailingStop(
                    id=row["id"],
                    signal_id=row["signal_id"],
                    symbol=signal["symbol"],
                    side=signal["side"].lower(),
                    trail_distance_pips=row["trail_distance_pips"],
                    activation_price=row.get("activation_price"),
                    wait_for_breakeven=row.get("wait_for_breakeven", False),
                    is_active=row["is_active"],
                    is_activated=row.get("is_activated", False),
                    current_sl=row["current_sl"],
                    highest_price_seen=row.get("highest_price_seen"),
                    lowest_price_seen=row.get("lowest_price_seen"),
                    entry_price=signal.get("entry", 0),
                    times_moved=row.get("times_moved", 0),
                    sl_distance_pips=row.get("sl_distance_pips"),
                    r2_locked=row.get("r2_locked", False),
                    r3_locked=row.get("r3_locked", False),
                )
                trailing_stops.append(ts)

            return trailing_stops

        except Exception as e:
            logger.error(f"Failed to fetch active trailing stops: {e}")
            return []

    def update_trailing_stops(self, current_prices: dict = None):
        """
        Update all active trailing stops based on current prices.

        Args:
            current_prices: Dict of {symbol: current_price} (if None, fetches from adapter)

        This should be called periodically (e.g., every minute) by the worker.
        """
        trailing_stops = self.get_active_trailing_stops()

        if not trailing_stops:
            logger.debug("No active trailing stops to update")
            return

        logger.info(f"Updating {len(trailing_stops)} trailing stops")

        for ts in trailing_stops:
            try:
                # Get current price
                if current_prices and ts.symbol in current_prices:
                    current_price = current_prices[ts.symbol]
                else:
                    current_price = self._get_current_price(ts)

                if current_price is None:
                    logger.warning(f"No price available for {ts.symbol}, skipping")
                    continue

                # Update trailing stop
                self._update_single_trailing_stop(ts, current_price)

            except Exception as e:
                logger.error(f"Failed to update trailing stop {ts.id}: {e}")

    def _get_current_price(self, ts: TrailingStop) -> Optional[float]:
        """Get current market price for a symbol."""
        if not self.adapter or not hasattr(self.adapter, "_get_symbol_price"):
            logger.warning("Adapter does not support price fetching")
            return None

        try:
            bid, ask = self.adapter._get_symbol_price(ts.symbol)

            # Use bid for sells, ask for buys
            if ts.side == "buy":
                return bid
            else:
                return ask

        except Exception as e:
            logger.error(f"Failed to get price for {ts.symbol}: {e}")
            return None

    def _check_r_ladder(self, ts: TrailingStop, current_price: float) -> None:
        """
        Check R-multiple milestones and lock in profit when hit.

        2R reached → move SL to entry + 1R (lock 1R profit)
        3R reached → move SL to entry + 2R (lock 2R profit)

        Only fires once per milestone (guarded by r2_locked / r3_locked).
        Skipped if sl_distance_pips is missing or zero.
        """
        if not ts.sl_distance_pips or ts.sl_distance_pips <= 0:
            return

        if ts.entry_price <= 0:
            return

        pip_size = self._get_pip_size(ts.symbol)
        sl_distance_price = ts.sl_distance_pips * pip_size

        if ts.side == "buy":
            r2_price = ts.entry_price + 2 * sl_distance_price
            r3_price = ts.entry_price + 3 * sl_distance_price

            if not ts.r3_locked and current_price >= r3_price:
                new_sl = ts.entry_price + 2 * sl_distance_price
                logger.info(
                    "R-Ladder [%s %s]: 3R hit at %.5f → locking SL at %.5f (2R profit)",
                    ts.symbol, ts.side, current_price, new_sl,
                )
                if new_sl > ts.current_sl:
                    self._move_stop_loss(ts, new_sl, r_milestone=3)
                self._lock_r_milestone(ts.id, milestone=3)

            elif not ts.r2_locked and current_price >= r2_price:
                new_sl = ts.entry_price + 1 * sl_distance_price
                logger.info(
                    "R-Ladder [%s %s]: 2R hit at %.5f → locking SL at %.5f (1R profit)",
                    ts.symbol, ts.side, current_price, new_sl,
                )
                if new_sl > ts.current_sl:
                    self._move_stop_loss(ts, new_sl, r_milestone=2)
                self._lock_r_milestone(ts.id, milestone=2)

        else:  # sell
            r2_price = ts.entry_price - 2 * sl_distance_price
            r3_price = ts.entry_price - 3 * sl_distance_price

            if not ts.r3_locked and current_price <= r3_price:
                new_sl = ts.entry_price - 2 * sl_distance_price
                logger.info(
                    "R-Ladder [%s %s]: 3R hit at %.5f → locking SL at %.5f (2R profit)",
                    ts.symbol, ts.side, current_price, new_sl,
                )
                if new_sl < ts.current_sl:
                    self._move_stop_loss(ts, new_sl, r_milestone=3)
                self._lock_r_milestone(ts.id, milestone=3)

            elif not ts.r2_locked and current_price <= r2_price:
                new_sl = ts.entry_price - 1 * sl_distance_price
                logger.info(
                    "R-Ladder [%s %s]: 2R hit at %.5f → locking SL at %.5f (1R profit)",
                    ts.symbol, ts.side, current_price, new_sl,
                )
                if new_sl < ts.current_sl:
                    self._move_stop_loss(ts, new_sl, r_milestone=2)
                self._lock_r_milestone(ts.id, milestone=2)

    def _lock_r_milestone(self, trailing_stop_id: int, milestone: int) -> None:
        """Persist r2_locked or r3_locked to DB to prevent double-firing."""
        column = f"r{milestone}_locked"
        try:
            self.client.table("trailing_stops").update({
                column: True,
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }).eq("id", trailing_stop_id).execute()
        except Exception as e:
            logger.error("Failed to set %s for trailing stop %s: %s", column, trailing_stop_id, e)

    def _update_single_trailing_stop(self, ts: TrailingStop, current_price: float):
        """
        Update a single trailing stop based on current price.

        Logic:
        1. Check if activation price has been hit (if set)
        2. Update highest/lowest price seen
        3. Calculate new SL
        4. Only move SL in favorable direction
        5. Update broker if SL changed
        """
        pip_size = self._get_pip_size(ts.symbol)

        # Wait for breakeven before activating?
        if ts.wait_for_breakeven and not ts.is_activated:
            if ts.side == "buy" and current_price >= ts.entry_price:
                logger.info(f"Trailing stop {ts.id} activated at breakeven")
                ts.is_activated = True
                self._mark_activated(ts.id)
            elif ts.side == "sell" and current_price <= ts.entry_price:
                logger.info(f"Trailing stop {ts.id} activated at breakeven")
                ts.is_activated = True
                self._mark_activated(ts.id)
            else:
                # Not yet at breakeven, skip
                return

        # Check activation price
        if ts.activation_price and not ts.is_activated:
            if ts.side == "buy" and current_price >= ts.activation_price:
                logger.info(f"Trailing stop {ts.id} activated at {current_price}")
                ts.is_activated = True
                self._mark_activated(ts.id)
            elif ts.side == "sell" and current_price <= ts.activation_price:
                logger.info(f"Trailing stop {ts.id} activated at {current_price}")
                ts.is_activated = True
                self._mark_activated(ts.id)
            else:
                # Activation price not hit yet
                return

        # R-ladder: lock in profit at 2R and 3R milestones
        self._check_r_ladder(ts, current_price)

        # Update highest/lowest price seen
        if ts.side == "buy":
            if ts.highest_price_seen is None or current_price > ts.highest_price_seen:
                ts.highest_price_seen = current_price
                self._update_price_seen(ts.id, "highest", current_price)

            # Calculate new SL (current price - trail distance)
            new_sl = current_price - (ts.trail_distance_pips * pip_size)

            # Only move SL up, never down
            if new_sl > ts.current_sl:
                self._move_stop_loss(ts, new_sl)

        else:  # sell
            if ts.lowest_price_seen is None or current_price < ts.lowest_price_seen:
                ts.lowest_price_seen = current_price
                self._update_price_seen(ts.id, "lowest", current_price)

            # Calculate new SL (current price + trail distance)
            new_sl = current_price + (ts.trail_distance_pips * pip_size)

            # Only move SL down, never up (for sells, lower SL = better)
            if new_sl < ts.current_sl:
                self._move_stop_loss(ts, new_sl)

    def _move_stop_loss(self, ts: TrailingStop, new_sl: float, r_milestone: Optional[int] = None):
        """
        Move stop loss to new level.

        Steps:
        1. Update broker (if adapter available)
        2. Update database
        3. Log the move
        """
        old_sl = ts.current_sl

        # Update broker
        broker_success = False
        if self.adapter and hasattr(self.adapter, "modify_position"):
            broker_order_id = self._get_broker_order_id(ts.signal_id)
            if broker_order_id:
                try:
                    result = self.adapter.modify_position(
                        position_id=broker_order_id,
                        sl=new_sl,
                    )
                    broker_success = result.status == "success"
                except Exception as e:
                    logger.error(f"Failed to update broker SL: {e}")

        # Update database (trading_signals + trailing_stops)
        try:
            # Update trading_signals.sl
            self.client.table("trading_signals").update(
                {"sl": new_sl}
            ).eq("id", ts.signal_id).execute()

            # Update trailing_stops record
            self.client.table("trailing_stops").update({
                "current_sl": new_sl,
                "updated_at": datetime.now(timezone.utc).isoformat(),
                "last_moved_at": datetime.now(timezone.utc).isoformat(),
                "times_moved": ts.times_moved + 1,
            }).eq("id", ts.id).execute()

            logger.info(
                f"Trailing stop {ts.id} ({ts.symbol}): Moved SL from {old_sl:.5f} to {new_sl:.5f} "
                f"(distance: {ts.trail_distance_pips} pips, times_moved: {ts.times_moved + 1})"
            )

            # Discord notification for R-milestone profit locks
            if r_milestone is not None:
                self._notify_r_milestone(ts, new_sl, r_milestone)

            # Log event
            try:
                from src.services.trade_events import log_event
                log_event(
                    ts.signal_id, "trailing_stop_moved", "trailing_stop_manager",
                    {
                        "old_sl": old_sl,
                        "new_sl": new_sl,
                        "trail_distance_pips": ts.trail_distance_pips,
                        "broker_updated": broker_success,
                        "r_milestone": r_milestone,
                    }
                )
            except Exception:
                pass

        except Exception as e:
            logger.error(f"Failed to update trailing stop in DB: {e}")

    def _notify_r_milestone(self, ts: TrailingStop, new_sl: float, milestone: int) -> None:
        """Send Discord notification when R-milestone profit is locked in."""
        try:
            from src.adapters.discord import send_discord_async
            from src.services.notification_service import NotificationPayload

            locked_r = milestone - 1  # at 2R we lock 1R; at 3R we lock 2R
            pip_size = self._get_pip_size(ts.symbol)
            locked_pips = abs(new_sl - ts.entry_price) / pip_size

            payload = NotificationPayload(
                title=f"🔒 {ts.symbol} — {locked_r}R Profit Locked",
                description=(
                    f"**{ts.side.upper()}** reached **{milestone}R**\n"
                    f"SL moved to **{new_sl:.5f}** (locking {locked_r}R / {locked_pips:.1f} pips profit)\n"
                    f"Entry: {ts.entry_price:.5f}"
                ),
                color=0x00FF88 if milestone == 2 else 0xFFAA00,
            )
            send_discord_async(payload, alert_id=0, mode="r_milestone")
        except Exception as e:
            logger.warning("R-milestone Discord notify failed (non-critical): %s", e)

    def _mark_activated(self, trailing_stop_id: int):
        """Mark a trailing stop as activated."""
        try:
            self.client.table("trailing_stops").update({
                "is_activated": True,
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }).eq("id", trailing_stop_id).execute()
        except Exception as e:
            logger.error(f"Failed to mark trailing stop {trailing_stop_id} as activated: {e}")

    def _update_price_seen(self, trailing_stop_id: int, field: str, price: float):
        """Update highest_price_seen or lowest_price_seen."""
        try:
            column = f"{field}_price_seen"
            self.client.table("trailing_stops").update({
                column: price,
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }).eq("id", trailing_stop_id).execute()
        except Exception as e:
            logger.error(f"Failed to update {field} price seen: {e}")

    def _get_broker_order_id(self, signal_id: int) -> Optional[str]:
        """Get broker_order_id for a signal."""
        try:
            result = self.client.table("trading_signals").select(
                "broker_order_id"
            ).eq("id", signal_id).single().execute()

            return result.data.get("broker_order_id") if result.data else None
        except Exception:
            return None

    def add_trailing_stop(
        self,
        signal_id: int,
        trail_distance_pips: float,
        activation_price: Optional[float] = None,
        wait_for_breakeven: bool = False,
        sl_distance_pips: Optional[float] = None,
    ) -> Optional[int]:
        """
        Add a trailing stop to an active position.

        Args:
            signal_id: ID of the trading signal
            trail_distance_pips: Distance to trail behind price (in pips)
            activation_price: Wait until price hits this before trailing starts
            wait_for_breakeven: Wait until position is profitable before trailing

        Returns:
            Trailing stop ID if successful, None otherwise
        """
        try:
            # Get position details
            signal = self.client.table("trading_signals").select(
                "id, symbol, side, sl, entry"
            ).eq("id", signal_id).single().execute()

            if not signal.data:
                logger.error(f"Signal {signal_id} not found")
                return None

            signal_data = signal.data
            current_sl = signal_data.get("sl")

            if not current_sl:
                logger.error(f"Signal {signal_id} has no SL set")
                return None

            # Create trailing stop record
            data = {
                "signal_id": signal_id,
                "trail_distance_pips": trail_distance_pips,
                "current_sl": current_sl,
                "is_active": True,
                "is_activated": False if (activation_price or wait_for_breakeven) else True,
            }

            if activation_price:
                data["activation_price"] = activation_price

            if wait_for_breakeven:
                data["wait_for_breakeven"] = True

            if sl_distance_pips is not None:
                data["sl_distance_pips"] = sl_distance_pips

            result = self.client.table("trailing_stops").insert(data).execute()

            if result.data:
                ts_id = result.data[0]["id"]
                logger.info(
                    f"Added trailing stop {ts_id} to signal {signal_id} "
                    f"(trail={trail_distance_pips} pips, activation={activation_price})"
                )

                # Log event
                try:
                    from src.services.trade_events import log_event
                    log_event(
                        signal_id, "trailing_stop_added", "ui",
                        {
                            "trail_distance_pips": trail_distance_pips,
                            "activation_price": activation_price,
                            "wait_for_breakeven": wait_for_breakeven,
                        }
                    )
                except Exception:
                    pass

                return ts_id

            return None

        except Exception as e:
            logger.error(f"Failed to add trailing stop: {e}")
            return None

    def remove_trailing_stop(self, trailing_stop_id: int) -> bool:
        """
        Remove (deactivate) a trailing stop.

        Args:
            trailing_stop_id: ID of the trailing stop

        Returns:
            True if successful
        """
        try:
            self.client.table("trailing_stops").update({
                "is_active": False,
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }).eq("id", trailing_stop_id).execute()

            logger.info(f"Removed trailing stop {trailing_stop_id}")
            return True

        except Exception as e:
            logger.error(f"Failed to remove trailing stop: {e}")
            return False
