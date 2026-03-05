"""
Consistency Analyzer
Enforces prop firm consistency rules: best day can't dominate total profit.

CRITICAL: FTMO/MyFundedFX consistency rule states:
"Your best trading day cannot exceed 40% of your total profit."

Example Violation:
- Total profit: $500 over 10 days
- Day 8 profit: $300 (60% of total) → FTMO REJECTION

This analyzer prevents violations by:
1. Tracking daily profits in real-time
2. Simulating "what if this trade wins" scenarios
3. Throttling/blocking trades that would cause violations

Author: Trinity Engine v3.0
"""

from datetime import datetime, timezone, timedelta
from typing import Dict, List, Tuple, Optional
import logging

logger = logging.getLogger(__name__)


class ConsistencyAnalyzer:
    """
    Tracks daily profits and enforces consistency rules.

    FTMO Rule: Best trading day profit <= 40% of total profit
    MyFundedFX Rule: Best trading day <= 50% of total profit
    """

    def __init__(self, supabase_client, settings, consistency_limit_pct: float = 40.0):
        """
        Initialize consistency analyzer.

        Args:
            supabase_client: Supabase client for database access
            settings: App settings
            consistency_limit_pct: Maximum % of total profit from single day (default: 40%)
        """
        self.supabase = supabase_client
        self.settings = settings
        self.consistency_limit_pct = consistency_limit_pct

    # ── Account-scoped query helper ────────────────────────────────
    def _apply_account_filter(self, query, account_name=None, broker_profile_id=None):
        """Add account isolation filters to a Supabase query."""
        if broker_profile_id is not None:
            query = query.eq("broker_profile_id", broker_profile_id)
        elif account_name and account_name != "default":
            query = query.eq("account_name", account_name)
        return query

    def get_daily_profit_breakdown(
        self,
        account_name: str = "default",
        lookback_days: int = 30,
        broker_profile_id: Optional[int] = None,
    ) -> Dict:
        """
        Get profit breakdown by day for consistency analysis.

        Args:
            account_name: Account identifier
            lookback_days: How many days to analyze (default: 30)
            broker_profile_id: Optional broker profile id for account isolation

        Returns:
            {
                'total_profit': float,  # Sum of all profitable days
                'total_loss': float,    # Sum of all losing days
                'net_profit': float,    # total_profit + total_loss
                'daily_profits': Dict[str, float],  # Date -> PnL mapping
                'best_day_profit': float,
                'worst_day_loss': float,
                'best_day_pct': float,  # Best day as % of total profit
                'consistency_ok': bool,
                'days_traded': int,
            }
        """
        start_date = (datetime.now(timezone.utc) - timedelta(days=lookback_days)).isoformat()

        # Get all closed trades — scoped to this account
        try:
            query = self.supabase.table("trading_signals")\
                .select("pnl_usd, created_at")\
                .in_("status", ["closed", "CLOSED"])\
                .gte("created_at", start_date)\
                .order("created_at", desc=False)
            query = self._apply_account_filter(query, account_name, broker_profile_id)
            trades = query.execute()
        except Exception as e:
            logger.error(f"Failed to fetch trades for consistency analysis: {e}")
            return self._empty_result()

        if not trades.data:
            return self._empty_result()

        # Group by day
        daily_profits = {}
        for trade in trades.data:
            pnl = float(trade.get("pnl_usd", 0))
            trade_date = datetime.fromisoformat(trade["created_at"].replace("Z", "+00:00"))
            day_key = trade_date.date().isoformat()

            if day_key not in daily_profits:
                daily_profits[day_key] = 0
            daily_profits[day_key] += pnl

        # Calculate metrics
        total_profit = sum(p for p in daily_profits.values() if p > 0)  # Only count profitable days
        total_loss = sum(p for p in daily_profits.values() if p < 0)    # Only count losing days
        net_profit = total_profit + total_loss

        best_day_profit = max(daily_profits.values()) if daily_profits else 0
        worst_day_loss = min(daily_profits.values()) if daily_profits else 0

        # Best day as percentage of total profit (FTMO metric)
        best_day_pct = (best_day_profit / total_profit * 100) if total_profit > 0 else 0

        consistency_ok = best_day_pct <= self.consistency_limit_pct

        return {
            "total_profit": round(total_profit, 2),
            "total_loss": round(total_loss, 2),
            "net_profit": round(net_profit, 2),
            "daily_profits": {k: round(v, 2) for k, v in daily_profits.items()},
            "best_day_profit": round(best_day_profit, 2),
            "worst_day_loss": round(worst_day_loss, 2),
            "best_day_pct": round(best_day_pct, 2),
            "consistency_limit_pct": self.consistency_limit_pct,
            "consistency_ok": consistency_ok,
            "days_traded": len([p for p in daily_profits.values() if p != 0]),
        }

    def check_trade_consistency_risk(
        self,
        expected_profit: float,
        account_name: str = "default",
        broker_profile_id: Optional[int] = None,
    ) -> Tuple[bool, str, float]:
        """
        Check if taking this trade (if it wins) would violate consistency rule.

        SMART THROTTLING:
        - 0-35%: Full risk (1.0x multiplier)
        - 35-38%: Warning zone, reduce risk to 75% (0.75x multiplier)
        - 38-40%: Danger zone, reduce risk to 50% (0.5x multiplier)
        - >40%: Hard block (0.0x multiplier)

        Args:
            expected_profit: Expected profit if trade hits TP (entry to TP distance * size)
            account_name: Account identifier
            broker_profile_id: Optional broker profile id for account isolation

        Returns:
            (should_allow, reason, risk_multiplier)
        """
        analysis = self.get_daily_profit_breakdown(account_name, broker_profile_id=broker_profile_id)

        # Get today's profit so far
        today = datetime.now(timezone.utc).date().isoformat()
        today_profit = analysis["daily_profits"].get(today, 0)

        # Simulate if this trade wins
        simulated_today_profit = today_profit + expected_profit
        simulated_total_profit = analysis["total_profit"] + max(expected_profit, 0)

        if simulated_total_profit > 0:
            simulated_best_day_pct = (simulated_today_profit / simulated_total_profit * 100)
        else:
            simulated_best_day_pct = 0

        # Decision logic
        if simulated_best_day_pct > self.consistency_limit_pct:
            # HARD BLOCK: Would violate consistency rule
            return False, (
                f"Consistency violation risk: If this trade wins, today would be "
                f"{simulated_best_day_pct:.1f}% of total profit (FTMO limit: {self.consistency_limit_pct}%). "
                f"Trade blocked to preserve consistency."
            ), 0.0

        elif simulated_best_day_pct > 38.0:
            # DANGER ZONE: Very close to limit, reduce risk to 50%
            return True, (
                f"Consistency danger zone: Today would be {simulated_best_day_pct:.1f}% of total profit "
                f"(limit: {self.consistency_limit_pct}%). Reducing risk to 50%."
            ), 0.5

        elif simulated_best_day_pct > 35.0:
            # WARNING ZONE: Approaching limit, reduce risk to 75%
            return True, (
                f"Consistency warning: Today would be {simulated_best_day_pct:.1f}% of total profit "
                f"(limit: {self.consistency_limit_pct}%). Reducing risk to 75%."
            ), 0.75

        else:
            # SAFE ZONE: Full risk
            return True, "Consistency OK", 1.0

    def get_safe_target_distance(
        self,
        entry: float,
        current_risk_usd: float,
        account_name: str = "default"
    ) -> Optional[float]:
        """
        Calculate the maximum TP distance that keeps consistency safe.

        Returns:
            Maximum profit in USD that won't violate consistency, or None if unlimited
        """
        analysis = self.get_daily_profit_breakdown(account_name)

        if analysis["total_profit"] <= 0:
            return None  # No consistency risk yet

        today = datetime.now(timezone.utc).date().isoformat()
        today_profit = analysis["daily_profits"].get(today, 0)

        # Calculate max additional profit before hitting 40% limit
        max_today_profit = analysis["total_profit"] * (self.consistency_limit_pct / 100)
        remaining_room = max_today_profit - today_profit

        if remaining_room <= 0:
            return 0  # Already at or over limit

        return remaining_room

    def _empty_result(self) -> Dict:
        """Return empty result structure."""
        return {
            "total_profit": 0,
            "total_loss": 0,
            "net_profit": 0,
            "daily_profits": {},
            "best_day_profit": 0,
            "worst_day_loss": 0,
            "best_day_pct": 0,
            "consistency_limit_pct": self.consistency_limit_pct,
            "consistency_ok": True,
            "days_traded": 0,
        }

    def get_consistency_dashboard_data(self, account_name: str = "default") -> Dict:
        """
        Get formatted data for dashboard display.

        Returns:
            {
                'status': 'safe' | 'warning' | 'danger' | 'violated',
                'best_day_pct': float,
                'remaining_capacity_pct': float,
                'best_day_profit': float,
                'total_profit': float,
                'days_traded': int,
            }
        """
        analysis = self.get_daily_profit_breakdown(account_name)

        # Determine status
        if analysis["best_day_pct"] > self.consistency_limit_pct:
            status = "violated"
        elif analysis["best_day_pct"] > 38:
            status = "danger"
        elif analysis["best_day_pct"] > 35:
            status = "warning"
        else:
            status = "safe"

        remaining_capacity_pct = self.consistency_limit_pct - analysis["best_day_pct"]

        return {
            "status": status,
            "best_day_pct": analysis["best_day_pct"],
            "remaining_capacity_pct": max(remaining_capacity_pct, 0),
            "best_day_profit": analysis["best_day_profit"],
            "total_profit": analysis["total_profit"],
            "days_traded": analysis["days_traded"],
            "consistency_limit_pct": self.consistency_limit_pct,
        }
