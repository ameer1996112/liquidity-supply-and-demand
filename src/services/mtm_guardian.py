"""
Mark-to-Market (MTM) Guardian
Real-time position monitoring with floating PnL tracking.

CRITICAL: This prevents prop firm failures by tracking OPEN position losses
that the standard kill switch misses (which only counts closed trades).

Author: Trinity Engine v3.0
"""

import logging
from typing import Dict, List, Tuple, Optional
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


class MTMGuardian:
    """
    Monitors all open positions and calculates real-time equity.
    Engages kill switch if floating losses push daily drawdown beyond limit.

    PROP FIRM PROTECTION:
    - FTMO/MyFundedFX fail at -5% daily loss
    - Standard kill switch at -4% only counts CLOSED trades
    - Open positions with -$250 floating loss can push you over -5%
    - This guard prevents that scenario by including floating PnL

    Usage:
        guardian = MTMGuardian(supabase, settings)
        should_kill, reason = guardian.check_kill_switch()

        if should_kill:
            # Engage kill switch
            redis.set("trading:kill_switch", "1")
    """

    def __init__(self, supabase_client, settings, *, starting_balance: float | None = None):
        self.supabase = supabase_client
        self.settings = settings
        self._starting_balance_override = starting_balance
        self._last_check_time = {}   # per-account cache timestamps
        self._cached_equity = {}     # per-account equity caches
        self._cache_ttl_seconds = getattr(settings, "mtm_cache_ttl_seconds", 10)

    def _apply_account_filter(self, query, account_name=None, broker_profile_id=None):
        """Add account isolation filters to a Supabase query."""
        if broker_profile_id is not None:
            query = query.eq("broker_profile_id", broker_profile_id)
        elif account_name and account_name != "default":
            query = query.eq("account_name", account_name)
        return query

    def get_real_time_equity(
        self,
        account_name: str = "default",
        broker_profile_id: int | None = None,
    ) -> Dict[str, float]:
        """
        Calculate current equity including floating PnL from open positions.

        Args:
            account_name: Account identifier for multi-account setups
            broker_profile_id: Optional broker profile id for account isolation

        Returns:
            {
                'starting_balance': float,
                'closed_pnl': float,
                'floating_pnl': float,
                'current_equity': float,
                'daily_drawdown_pct': float,
                'position_details': List[Dict],
                'timestamp': str,
            }
        """
        now = datetime.now(timezone.utc)
        cache_key = f"{account_name}:{broker_profile_id}"

        # Use cache if fresh (avoid excessive market data calls)
        last_time = self._last_check_time.get(cache_key)
        cached = self._cached_equity.get(cache_key)
        if (last_time and
            (now - last_time).total_seconds() < self._cache_ttl_seconds and
            cached):
            return cached

        # 1. Get starting balance for today
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0).isoformat()

        # 2. Calculate closed PnL — scoped to this account
        try:
            q = self.supabase.table("trading_signals")\
                .select("pnl_usd")\
                .in_("status", ["closed", "CLOSED", "executed", "EXECUTED"])\
                .gte("created_at", today_start)
            q = self._apply_account_filter(q, account_name, broker_profile_id)
            closed_trades = q.execute()

            closed_pnl = sum(float(t.get("pnl_usd", 0)) for t in closed_trades.data) if closed_trades.data else 0.0
        except Exception as e:
            logger.error(f"Failed to fetch closed PnL: {e}")
            closed_pnl = 0.0

        # 3. Calculate floating PnL from active positions — scoped to this account
        try:
            q = self.supabase.table("trading_signals")\
                .select("id, symbol, side, entry, size, filled_entry_price, sl, tp")\
                .in_("status", ["active", "executed"])
            q = self._apply_account_filter(q, account_name, broker_profile_id)
            open_positions = q.execute()
        except Exception as e:
            logger.error(f"Failed to fetch open positions: {e}")
            open_positions = None

        floating_pnl = 0.0
        position_details = []

        if open_positions and open_positions.data:
            from src.adapters.market_data import get_current_price

            for pos in open_positions.data:
                try:
                    current_price = get_current_price(pos["symbol"])
                    entry = pos.get("filled_entry_price") or pos.get("entry", 0)
                    size = pos.get("size", 0)

                    # ✅ Guard: Ensure both entry and current_price are valid (> 0)
                    # This prevents massive phantom losses if yfinance returns 0 (market closed or error)
                    # or if the entry price is missing from the signal payload.
                    if current_price <= 0 or entry <= 0:
                        logger.warning(
                            "MTM SKIP: Invalid price for %s (entry=%s, current=%s). Skipping calculation.",
                            pos["symbol"], entry, current_price
                        )
                        continue

                    side = pos["side"].lower()
                    symbol = pos["symbol"]

                    # Get pip values (reuse from risk_engine logic)
                    if "JPY" in symbol:
                        pip_size = 0.01
                        pip_value_per_lot = 1000.0
                    elif "XAU" in symbol or "GOLD" in symbol:
                        pip_size = 0.01
                        pip_value_per_lot = 100.0
                    else:
                        pip_size = 0.0001
                        pip_value_per_lot = 10.0

                    # Calculate PnL
                    if side == "buy":
                        price_diff = current_price - entry
                    else:
                        price_diff = entry - current_price

                    pips = price_diff / pip_size
                    pnl = pips * pip_value_per_lot * size
                    floating_pnl += pnl

                    position_details.append({
                        "id": pos["id"],
                        "symbol": symbol,
                        "side": side,
                        "entry": entry,
                        "current": current_price,
                        "pnl": round(pnl, 2),
                        "pnl_pips": round(pips, 1),
                        "size": size,
                    })

                except Exception as e:
                    logger.error(f"MTM calculation error for position {pos.get('id')}: {e}")

        # 4. Calculate total equity and drawdown
        starting_balance = self._starting_balance_override or self.settings.account_balance
        current_equity = starting_balance + closed_pnl + floating_pnl

        # Daily drawdown percentage
        daily_drawdown_pct = ((starting_balance - current_equity) / starting_balance) * 100 if starting_balance > 0 else 0

        result = {
            "starting_balance": starting_balance,
            "closed_pnl": round(closed_pnl, 2),
            "floating_pnl": round(floating_pnl, 2),
            "current_equity": round(current_equity, 2),
            "daily_drawdown_pct": round(daily_drawdown_pct, 2),
            "position_details": position_details,
            "timestamp": now.isoformat(),
        }

        # Update per-account cache
        self._cached_equity[cache_key] = result
        self._last_check_time[cache_key] = now

        return result

    def check_kill_switch(
        self,
        account_name: str = "default",
        broker_profile_id: int | None = None,
    ) -> Tuple[bool, str]:
        """
        Check if kill switch should engage based on real-time equity.

        Args:
            account_name: Account identifier
            broker_profile_id: Optional broker profile id for account isolation

        Returns:
            (should_engage, reason)
        """
        equity_data = self.get_real_time_equity(account_name, broker_profile_id=broker_profile_id)

        kill_threshold_pct = getattr(self.settings, "trinity_max_daily_loss_pct", 4.0)
        daily_dd_pct = equity_data["daily_drawdown_pct"]

        if daily_dd_pct >= kill_threshold_pct:
            reason = (
                f"MTM Kill Switch: Daily drawdown {daily_dd_pct:.2f}% >= {kill_threshold_pct}% "
                f"(Closed: ${equity_data['closed_pnl']:.2f}, Floating: ${equity_data['floating_pnl']:.2f})"
            )
            return True, reason

        # Warning zone: 80% of limit
        warning_threshold = kill_threshold_pct * 0.8
        if daily_dd_pct >= warning_threshold:
            logger.warning(
                f"⚠️ MTM WARNING: Daily drawdown {daily_dd_pct:.2f}% approaching limit ({kill_threshold_pct}%)"
            )

        return False, "MTM Guardian: OK"

    def get_position_summary(self, account_name: str = "default") -> Dict:
        """
        Get summary of all open positions with live PnL.

        Returns:
            {
                'total_positions': int,
                'floating_pnl': float,
                'largest_winner': float,
                'largest_loser': float,
                'positions': List[Dict],
            }
        """
        equity_data = self.get_real_time_equity(account_name)

        position_pnls = [p["pnl"] for p in equity_data["position_details"]]

        return {
            "total_positions": len(equity_data["position_details"]),
            "floating_pnl": equity_data["floating_pnl"],
            "largest_winner": max(position_pnls) if position_pnls else 0,
            "largest_loser": min(position_pnls) if position_pnls else 0,
            "positions": equity_data["position_details"],
        }

    def get_at_risk_positions(self, risk_threshold_pct: float = 50.0) -> List[Dict]:
        """
        Get positions that have lost >50% of their risk (approaching stop loss).

        Args:
            risk_threshold_pct: Percentage of initial risk (50 = halfway to SL)

        Returns:
            List of positions at risk
        """
        equity_data = self.get_real_time_equity()
        at_risk = []

        for pos in equity_data["position_details"]:
            if pos["pnl"] < 0:  # Only check losing positions
                # Calculate distance to SL as percentage
                try:
                    query = self.supabase.table("trading_signals")\
                        .select("sl, entry")\
                        .eq("id", pos["id"])\
                        .single()\
                        .execute()

                    if query.data:
                        entry = query.data.get("entry")
                        sl = query.data.get("sl")
                        current = pos["current"]

                        if entry and sl:
                            # Calculate % of distance to SL
                            total_risk = abs(entry - sl)
                            current_loss = abs(entry - current) if pos["side"] == "buy" else abs(current - entry)
                            pct_to_sl = (current_loss / total_risk) * 100 if total_risk > 0 else 0

                            if pct_to_sl >= risk_threshold_pct:
                                at_risk.append({
                                    **pos,
                                    "pct_to_sl": round(pct_to_sl, 1),
                                    "sl": sl,
                                })
                except Exception as e:
                    logger.error(f"Failed to check risk for position {pos['id']}: {e}")

        return at_risk
