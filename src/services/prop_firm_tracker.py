"""
Prop Firm Compliance Tracker
Calculates real-time drawdown with floating PnL included.

COMPREHENSIVE PROP FIRM MONITORING:
- Daily high water mark tracking
- Floating + closed PnL calculation
- Real-time drawdown percentages
- Days remaining in evaluation
- Consistency rule tracking

Integrates:
- MTMGuardian for real-time equity
- ConsistencyAnalyzer for daily profit distribution

Author: Trinity Engine v3.0
"""

from datetime import datetime, timezone, date, timedelta
from typing import Dict, Optional, List
from dataclasses import dataclass
import logging

import pytz

logger = logging.getLogger(__name__)

NY_TZ = pytz.timezone("America/New_York")

def get_ny_midnight_utc() -> datetime:
    """Return today's NY midnight as a UTC datetime."""
    now_ny = datetime.now(NY_TZ)
    midnight_ny = now_ny.replace(hour=0, minute=0, second=0, microsecond=0)
    return midnight_ny.astimezone(timezone.utc)


@dataclass
class PropFirmMetrics:
    """Real-time prop firm compliance metrics."""
    daily_start_balance: float
    daily_high_water_mark: float
    current_equity: float
    daily_pnl_closed: float
    daily_pnl_floating: float
    daily_pnl_total: float
    daily_drawdown_pct: float
    trailing_drawdown_pct: float
    daily_loss_limit_usd: float
    max_drawdown_limit_pct: float
    daily_loss_breach: bool
    drawdown_breach: bool
    days_remaining: Optional[int] = None
    consistency_ok: bool = True
    consistency_pct: float = 0.0


class PropFirmTracker:
    """Calculate real-time prop firm metrics with floating PnL."""

    def __init__(self, supabase_client, settings):
        self.supabase = supabase_client
        self.settings = settings

    def _get_live_balance(self, account_name: str) -> Optional[float]:
        """
        Fetch the most recent account balance from account_status_snapshots
        (populated by AccountSyncService from MetaAPI).

        Returns None if no recent snapshot exists.
        """
        try:
            from datetime import timedelta
            cutoff = (datetime.now(timezone.utc) - timedelta(hours=24)).isoformat()
            result = self.supabase.table("account_status_snapshots")\
                .select("balance, snapshot_time")\
                .eq("account_name", account_name)\
                .gte("snapshot_time", cutoff)\
                .order("snapshot_time", desc=True)\
                .limit(1)\
                .execute()
            if result.data:
                bal = float(result.data[0]["balance"])
                logger.info(
                    "PropFirmTracker: using live MetaAPI balance $%.2f for %s",
                    bal, account_name
                )
                return bal
        except Exception as e:
            logger.warning("PropFirmTracker: failed to fetch live balance for %s: %s", account_name, e)
        return None

    async def get_current_metrics(
        self,
        account_name: str = "default",
        evaluation_phase: str = "phase1"
    ) -> PropFirmMetrics:
        """
        Calculate real-time metrics including open positions.

        Args:
            account_name: Account identifier
            evaluation_phase: 'phase1', 'phase2', or 'funded'

        Returns:
            PropFirmMetrics with all compliance data
        """
        # 1. Get MTM data (includes floating PnL)
        from src.services.mtm_guardian import MTMGuardian

        mtm = MTMGuardian(self.supabase, self.settings)
        equity_data = mtm.get_real_time_equity(account_name)

        # 2. Get daily start balance from snapshot or settings
        today_start = get_ny_midnight_utc().isoformat()

        try:
            snapshot = self.supabase.table("prop_firm_metrics")\
                .select("daily_start_balance, daily_high_water_mark, max_historical_equity")\
                .eq("account_name", account_name)\
                .gte("snapshot_time", today_start)\
                .order("snapshot_time", desc=True)\
                .limit(1)\
                .execute()

            if snapshot.data:
                daily_start_balance = snapshot.data[0]["daily_start_balance"]
                daily_high_water_mark = snapshot.data[0].get("daily_high_water_mark", daily_start_balance)
                max_historical_equity = snapshot.data[0].get("max_historical_equity", daily_start_balance)
            else:
                # No prop_firm_metrics snapshot for today — try account_status_snapshots (MetaAPI live data)
                daily_start_balance = self._get_live_balance(account_name) or self.settings.account_balance
                daily_high_water_mark = daily_start_balance
                max_historical_equity = daily_start_balance
        except Exception as e:
            logger.error(f"Failed to fetch daily snapshot: {e}")
            daily_start_balance = self._get_live_balance(account_name) or self.settings.account_balance
            daily_high_water_mark = daily_start_balance
            max_historical_equity = daily_start_balance

        # 3. Extract PnL data from MTM
        daily_pnl_closed = equity_data["closed_pnl"]
        daily_pnl_floating = equity_data["floating_pnl"]
        daily_pnl_total = daily_pnl_closed + daily_pnl_floating
        current_equity = equity_data["current_equity"]

        # 4. Update high water mark if we reached new high today
        if current_equity > daily_high_water_mark:
            daily_high_water_mark = current_equity

        # 5. Update all-time high
        if current_equity > max_historical_equity:
            max_historical_equity = current_equity

        # 6. Calculate drawdowns
        # Daily drawdown: from high water mark to current
        daily_drawdown_pct = (
            (daily_high_water_mark - current_equity) / daily_start_balance * 100
            if daily_start_balance > 0 else 0
        )

        # Total drawdown: depends on evaluation phase
        starting_balance = self.settings.account_balance
        if evaluation_phase == "funded":
            # Funded: trailing HWM denominator
            trailing_drawdown_pct = (
                (max_historical_equity - current_equity) / max_historical_equity * 100
                if max_historical_equity > 0 else 0
            )
        else:
            # Phase 1 / Phase 2: initial starting balance denominator
            trailing_drawdown_pct = (
                (starting_balance - current_equity) / starting_balance * 100
                if starting_balance > 0 else 0
            )

        # 7. Get limits based on evaluation phase
        if evaluation_phase == "phase1":
            daily_loss_limit_usd = self.settings.phase1_max_daily_loss
            max_drawdown_limit_pct = self.settings.phase1_max_drawdown_pct
        elif evaluation_phase == "phase2":
            daily_loss_limit_usd = self.settings.phase2_max_daily_loss
            max_drawdown_limit_pct = self.settings.phase2_max_drawdown_pct
        else:  # funded
            daily_loss_limit_usd = self.settings.funded_max_daily_loss
            max_drawdown_limit_pct = self.settings.funded_max_drawdown_pct

        # 8. Check breaches
        daily_loss_breach = abs(daily_pnl_total) >= daily_loss_limit_usd if daily_pnl_total < 0 else False
        drawdown_breach = trailing_drawdown_pct >= max_drawdown_limit_pct

        # 9. Get consistency data
        consistency_ok = True
        consistency_pct = 0.0
        try:
            from src.services.consistency_analyzer import ConsistencyAnalyzer
            consistency = ConsistencyAnalyzer(self.supabase, self.settings)
            analysis = consistency.get_daily_profit_breakdown(account_name)
            consistency_ok = analysis["consistency_ok"]
            consistency_pct = analysis["best_day_pct"]
        except Exception as e:
            logger.error(f"Failed to get consistency data: {e}")

        # 10. Calculate days remaining
        days_remaining = None
        if self.settings.evaluation_mode and self.settings.evaluation_start_date:
            try:
                start = datetime.fromisoformat(self.settings.evaluation_start_date).date()
                days_elapsed = (date.today() - start).days

                if self.settings.evaluation_phase == "phase1":
                    max_days = 30  # FTMO Phase 1: 30 days
                elif self.settings.evaluation_phase == "phase2":
                    max_days = 60  # FTMO Phase 2: 60 days
                else:
                    max_days = None  # Funded accounts have no time limit

                if max_days:
                    days_remaining = max(max_days - days_elapsed, 0)
            except Exception as e:
                logger.error(f"Failed to calculate days remaining: {e}")

        return PropFirmMetrics(
            daily_start_balance=daily_start_balance,
            daily_high_water_mark=daily_high_water_mark,
            current_equity=current_equity,
            daily_pnl_closed=daily_pnl_closed,
            daily_pnl_floating=daily_pnl_floating,
            daily_pnl_total=daily_pnl_total,
            daily_drawdown_pct=daily_drawdown_pct,
            trailing_drawdown_pct=trailing_drawdown_pct,
            daily_loss_limit_usd=daily_loss_limit_usd,
            max_drawdown_limit_pct=max_drawdown_limit_pct,
            daily_loss_breach=daily_loss_breach,
            drawdown_breach=drawdown_breach,
            days_remaining=days_remaining,
            consistency_ok=consistency_ok,
            consistency_pct=consistency_pct,
        )

    async def save_snapshot(
        self,
        metrics: PropFirmMetrics,
        account_name: str = "default",
        broker_profile_id: Optional[int] = None
    ):
        """
        Save metrics snapshot to database.

        Args:
            metrics: PropFirmMetrics to save
            account_name: Account identifier
            broker_profile_id: Optional broker profile ID
        """
        # Calculate trades today
        try:
            ny_midnight = get_ny_midnight_utc().isoformat()
            trades_result = self.supabase.table("trading_signals") \
                .select("id") \
                .in_("status", ["closed", "CLOSED", "executed", "EXECUTED"]) \
                .gte("closed_at", ny_midnight) \
                .eq("account_name", account_name) \
                .execute()
            trades_today = len(trades_result.data) if trades_result.data else 0
        except Exception as e:
            logger.error(f"Failed to fetch trades_today: {e}")
            trades_today = 0

        try:
            self.supabase.table("prop_firm_metrics").insert({
                "account_name": account_name,
                "broker_profile_id": broker_profile_id,
                "evaluation_phase": self.settings.evaluation_phase,
                "daily_start_balance": metrics.daily_start_balance,
                "daily_high_water_mark": metrics.daily_high_water_mark,
                "daily_pnl_closed": metrics.daily_pnl_closed,
                "daily_pnl_floating": metrics.daily_pnl_floating,
                "daily_pnl_total": metrics.daily_pnl_total,
                "current_equity": metrics.current_equity,
                "max_historical_equity": metrics.daily_high_water_mark,  # Use current high as historical
                "daily_drawdown_pct": metrics.daily_drawdown_pct,
                "trailing_drawdown_pct": metrics.trailing_drawdown_pct,
                "daily_loss_limit_usd": metrics.daily_loss_limit_usd,
                "max_drawdown_limit_pct": metrics.max_drawdown_limit_pct,
                "daily_loss_breach": metrics.daily_loss_breach,
                "drawdown_breach": metrics.drawdown_breach,
                "trades_today": trades_today,
                "winning_trades_today": 0,
                "losing_trades_today": 0,
            }).execute()

            logger.info(f"Saved prop firm snapshot for {account_name}")
        except Exception as e:
            logger.error(f"Failed to save prop firm snapshot: {e}")
            raise

    def get_historical_snapshots(
        self,
        account_name: str = "default",
        days: int = 7
    ) -> List[Dict]:
        """
        Get historical snapshots for trend analysis.

        Args:
            account_name: Account identifier
            days: Number of days to fetch

        Returns:
            List of snapshot dictionaries ordered by time (newest first)
        """
        start_date = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()

        try:
            result = self.supabase.table("prop_firm_metrics")\
                .select("*")\
                .eq("account_name", account_name)\
                .gte("snapshot_time", start_date)\
                .order("snapshot_time", desc=True)\
                .execute()

            return result.data if result.data else []
        except Exception as e:
            logger.error(f"Failed to fetch historical snapshots: {e}")
            return []

    def get_daily_reset_needed(self, account_name: str = "default") -> bool:
        """
        Check if daily reset is needed (new trading day started).

        Returns:
            True if we need to create new daily starting balance snapshot
        """
        today_start = get_ny_midnight_utc().isoformat()

        try:
            snapshot = self.supabase.table("prop_firm_metrics")\
                .select("id")\
                .eq("account_name", account_name)\
                .gte("snapshot_time", today_start)\
                .limit(1)\
                .execute()

            return not bool(snapshot.data)
        except Exception as e:
            logger.error(f"Failed to check daily reset: {e}")
            return True

    async def perform_daily_reset(self, account_name: str = "default"):
        """
        Perform daily reset at 00:00 server time.

        Creates a new starting balance snapshot for the new trading day.
        """
        if not self.get_daily_reset_needed(account_name):
            return  # Already reset today

        # Get yesterday's closing equity
        from src.services.mtm_guardian import MTMGuardian

        mtm = MTMGuardian(self.supabase, self.settings)
        equity_data = mtm.get_real_time_equity(account_name)
        current_equity = equity_data["current_equity"]

        # Create new daily snapshot
        metrics = PropFirmMetrics(
            daily_start_balance=current_equity,
            daily_high_water_mark=current_equity,
            current_equity=current_equity,
            daily_pnl_closed=0.0,
            daily_pnl_floating=0.0,
            daily_pnl_total=0.0,
            daily_drawdown_pct=0.0,
            trailing_drawdown_pct=0.0,
            daily_loss_limit_usd=self.settings.phase1_max_daily_loss,
            max_drawdown_limit_pct=self.settings.phase1_max_drawdown_pct,
            daily_loss_breach=False,
            drawdown_breach=False,
        )

        await self.save_snapshot(metrics, account_name)
        logger.info(f"Daily reset performed for {account_name}: new balance ${current_equity:.2f}")
