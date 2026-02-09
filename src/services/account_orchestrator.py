"""
Multi-Account Orchestration

Features:
- Capital allocation across accounts
- Trade copying (master → slave)
- Account performance tracking
- Strategy assignment per account
"""

import logging
from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class AccountPerformance:
    """Performance metrics for an account."""
    account_name: str
    balance: float
    daily_pnl: float
    daily_pnl_pct: float
    win_rate: float
    sharpe_ratio: float
    max_drawdown_pct: float
    total_trades: int
    active_positions: int


@dataclass
class AllocationRecommendation:
    """Capital allocation recommendation for an account."""
    account_name: str
    current_balance: float
    suggested_allocation_usd: float
    change_usd: float
    change_pct: float
    reason: str
    performance_score: float


@dataclass
class AllocationPlan:
    """Complete capital allocation plan across all accounts."""
    total_capital: float
    total_allocated: float
    unallocated: float
    recommendations: List[AllocationRecommendation]
    expected_portfolio_sharpe: float


class AccountOrchestrator:
    """Manages multi-account capital allocation and strategy assignment."""

    def __init__(self, supabase_client):
        """
        Initialize account orchestrator.

        Args:
            supabase_client: Supabase client
        """
        self.client = supabase_client

    def get_account_performance(
        self,
        account_name: str,
        lookback_days: int = 30
    ) -> Optional[AccountPerformance]:
        """
        Calculate performance metrics for an account.

        Args:
            account_name: Name of the account
            lookback_days: Days to look back for metrics

        Returns:
            AccountPerformance object or None
        """
        try:
            # Get account strategy config
            account = self.client.table("account_strategies").select("*").eq(
                "account_name", account_name
            ).eq("is_active", True).single().execute()

            if not account.data:
                logger.warning(f"Account {account_name} not found")
                return None

            account_data = account.data
            broker_profile_id = account_data.get("broker_profile_id")

            # Get trades for this account
            start_date = (datetime.now(timezone.utc) - timedelta(days=lookback_days)).isoformat()

            trades_query = self.client.table("trading_signals").select(
                "pnl_usd, pnl_r, outcome, created_at"
            ).gte("created_at", start_date)

            if broker_profile_id:
                trades_query = trades_query.eq("broker_profile_id", broker_profile_id)

            trades_result = trades_query.execute()
            trades = trades_result.data or []

            # Calculate metrics
            total_trades = len(trades)
            wins = [t for t in trades if t.get("outcome") == "win"]
            losses = [t for t in trades if t.get("outcome") == "loss"]
            win_rate = len(wins) / total_trades if total_trades > 0 else 0.0

            # Daily PnL (handle None values from database)
            today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0).isoformat()
            daily_pnl = sum(
                float(t.get("pnl_usd") or 0)
                for t in trades
                if t.get("created_at", "") >= today_start
            )

            # Get real balance from broker (not static allocated capital)
            balance = float(account_data.get("allocated_capital_usd") or 0)  # Fallback

            # Try to fetch real balance from MetaApi if broker_profile_id exists
            if broker_profile_id:
                try:
                    from src.adapters.execution.router import get_adapter
                    from config import get_settings

                    # Get broker profile details
                    profile_query = self.client.table("broker_profiles").select("*").eq(
                        "id", broker_profile_id
                    ).single().execute()

                    if profile_query.data:
                        profile = profile_query.data
                        adapter = get_adapter(profile=profile, settings=get_settings())

                        # Fetch real account info from broker
                        if hasattr(adapter, "get_account_information"):
                            account_info = adapter.get_account_information()
                            if account_info and "balance" in account_info:
                                balance = float(account_info["balance"])
                                logger.info(f"Fetched real balance for {account_name}: ${balance:.2f}")
                except Exception as e:
                    logger.warning(f"Failed to fetch real balance for {account_name}, using allocated capital: {e}")

            daily_pnl_pct = (daily_pnl / balance * 100) if balance > 0 else 0.0

            # Sharpe ratio (simplified)
            if len(trades) > 5:
                returns = [float(t.get("pnl_r") or 0) for t in trades if t.get("pnl_r")]
                if returns:
                    import numpy as np
                    mean_return = np.mean(returns)
                    std_return = np.std(returns)
                    sharpe_ratio = (mean_return / std_return) if std_return > 0 else 0.0
                else:
                    sharpe_ratio = 0.0
            else:
                sharpe_ratio = 0.0

            # Max drawdown (simplified - would need equity curve)
            max_drawdown_pct = 0.0  # TODO: Calculate from equity curve

            # Active positions
            active_query = self.client.table("trading_signals").select(
                "id", count="exact"
            ).in_("status", ["active", "executed"])

            if broker_profile_id:
                active_query = active_query.eq("broker_profile_id", broker_profile_id)

            active_result = active_query.execute()
            active_positions = active_result.count or 0

            return AccountPerformance(
                account_name=account_name,
                balance=balance,
                daily_pnl=daily_pnl,
                daily_pnl_pct=daily_pnl_pct,
                win_rate=win_rate,
                sharpe_ratio=sharpe_ratio,
                max_drawdown_pct=max_drawdown_pct,
                total_trades=total_trades,
                active_positions=active_positions,
            )

        except Exception as e:
            logger.error(f"Failed to get account performance for {account_name}: {e}")
            return None

    def suggest_capital_allocation(
        self,
        total_available_capital: float,
        optimization_goal: str = "maximize_sharpe"
    ) -> AllocationPlan:
        """
        Suggest optimal capital allocation across all accounts.

        Args:
            total_available_capital: Total capital to allocate
            optimization_goal: 'maximize_sharpe', 'maximize_return', 'minimize_risk'

        Returns:
            AllocationPlan with recommendations
        """
        try:
            # Get all active accounts
            accounts = self.client.table("account_strategies").select("*").eq(
                "is_active", True
            ).execute()

            if not accounts.data:
                logger.warning("No active accounts found")
                return AllocationPlan(
                    total_capital=total_available_capital,
                    total_allocated=0.0,
                    unallocated=total_available_capital,
                    recommendations=[],
                    expected_portfolio_sharpe=0.0,
                )

            # Get performance for each account
            account_performances = []
            for account in accounts.data:
                perf = self.get_account_performance(account["account_name"])
                if perf:
                    account_performances.append(perf)

            if not account_performances:
                logger.warning("No account performance data available")
                return AllocationPlan(
                    total_capital=total_available_capital,
                    total_allocated=0.0,
                    unallocated=total_available_capital,
                    recommendations=[],
                    expected_portfolio_sharpe=0.0,
                )

            # Score each account
            scored_accounts = []
            for perf in account_performances:
                # Calculate performance score
                if optimization_goal == "maximize_sharpe":
                    score = perf.sharpe_ratio * perf.win_rate
                elif optimization_goal == "maximize_return":
                    score = perf.daily_pnl_pct * perf.win_rate
                elif optimization_goal == "minimize_risk":
                    score = (1.0 - perf.max_drawdown_pct) * perf.win_rate
                else:
                    score = perf.sharpe_ratio * perf.win_rate

                # Penalize accounts with few trades or low win rate
                if perf.total_trades < 10:
                    score *= 0.5  # Reduce allocation for unproven accounts
                if perf.win_rate < 0.4:
                    score *= 0.3  # Heavy penalty for losing accounts

                scored_accounts.append((perf, max(score, 0.001)))  # Avoid division by zero

            # Sort by score (highest first)
            scored_accounts.sort(key=lambda x: x[1], reverse=True)

            # Allocate proportionally to scores
            total_score = sum(score for _, score in scored_accounts)
            recommendations = []

            for perf, score in scored_accounts:
                allocation_pct = score / total_score
                allocation_usd = total_available_capital * allocation_pct

                # Minimum allocation (don't allocate less than $1k to avoid dust)
                if allocation_usd < 1000:
                    allocation_usd = 0.0

                change_usd = allocation_usd - perf.balance
                change_pct = (change_usd / perf.balance * 100) if perf.balance > 0 else 0.0

                reason = self._build_allocation_reason(perf, allocation_pct, optimization_goal)

                recommendations.append(AllocationRecommendation(
                    account_name=perf.account_name,
                    current_balance=perf.balance,
                    suggested_allocation_usd=allocation_usd,
                    change_usd=change_usd,
                    change_pct=change_pct,
                    reason=reason,
                    performance_score=score,
                ))

            total_allocated = sum(r.suggested_allocation_usd for r in recommendations)
            unallocated = total_available_capital - total_allocated

            # Estimate portfolio Sharpe (weighted average)
            expected_sharpe = 0.0
            if total_allocated > 0:
                for rec in recommendations:
                    weight = rec.suggested_allocation_usd / total_allocated
                    # Find matching performance
                    matching_perf = next(
                        (p for p, _ in scored_accounts if p.account_name == rec.account_name),
                        None
                    )
                    if matching_perf:
                        expected_sharpe += weight * matching_perf.sharpe_ratio

            return AllocationPlan(
                total_capital=total_available_capital,
                total_allocated=total_allocated,
                unallocated=unallocated,
                recommendations=recommendations,
                expected_portfolio_sharpe=expected_sharpe,
            )

        except Exception as e:
            logger.exception("Failed to suggest capital allocation: %s", e)
            return AllocationPlan(
                total_capital=total_available_capital,
                total_allocated=0.0,
                unallocated=total_available_capital,
                recommendations=[],
                expected_portfolio_sharpe=0.0,
            )

    def _build_allocation_reason(
        self,
        perf: AccountPerformance,
        allocation_pct: float,
        optimization_goal: str
    ) -> str:
        """Build human-readable allocation reason."""
        reasons = []

        if perf.sharpe_ratio > 1.5:
            reasons.append(f"High Sharpe ratio ({perf.sharpe_ratio:.2f})")
        if perf.win_rate > 0.65:
            reasons.append(f"Strong win rate ({perf.win_rate:.0%})")
        if perf.total_trades < 10:
            reasons.append("Limited track record")
        if perf.win_rate < 0.45:
            reasons.append("Underperforming")

        if not reasons:
            reasons.append(f"Allocation: {allocation_pct:.0%}")

        return " | ".join(reasons)

    def execute_allocation(self, recommendation: AllocationRecommendation) -> bool:
        """
        Execute a capital allocation change.

        Args:
            recommendation: AllocationRecommendation object

        Returns:
            True if successful

        Note: This updates the database. Actual capital transfer
        would need to be done manually or via broker API.
        """
        try:
            # Update account_strategies table
            self.client.table("account_strategies").update({
                "allocated_capital_usd": recommendation.suggested_allocation_usd,
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }).eq("account_name", recommendation.account_name).execute()

            # Log to capital_allocation_history
            self.client.table("capital_allocation_history").insert({
                "account_name": recommendation.account_name,
                "previous_allocation_usd": recommendation.current_balance,
                "new_allocation_usd": recommendation.suggested_allocation_usd,
                "change_usd": recommendation.change_usd,
                "allocation_reason": recommendation.reason,
                "automated": False,
            }).execute()

            logger.info(
                f"Executed allocation for {recommendation.account_name}: "
                f"${recommendation.current_balance:.0f} → ${recommendation.suggested_allocation_usd:.0f} "
                f"({recommendation.change_usd:+.0f})"
            )

            return True

        except Exception as e:
            logger.error(f"Failed to execute allocation: {e}")
            return False

    def get_account_comparison(self) -> List[Dict]:
        """
        Get side-by-side comparison of all accounts with comprehensive metrics.

        Returns:
            List of account comparison dicts with full metrics
        """
        try:
            accounts = self.client.table("account_strategies").select("*").eq(
                "is_active", True
            ).execute()

            comparison = []
            for account in accounts.data or []:
                perf = self.get_account_performance(account["account_name"])

                if perf:
                    # Calculate additional metrics
                    profit_factor = 0.0
                    avg_win = 0.0
                    avg_loss = 0.0

                    # Get recent trades for profit factor
                    try:
                        broker_profile_id = account.get("broker_profile_id")
                        trades_query = self.client.table("trading_signals").select(
                            "pnl_usd, pnl_r, outcome"
                        ).limit(100)

                        if broker_profile_id:
                            trades_query = trades_query.eq("broker_profile_id", broker_profile_id)

                        trades = trades_query.execute().data or []

                        wins = [float(t.get("pnl_usd") or 0) for t in trades if t.get("outcome") == "win" and t.get("pnl_usd")]
                        losses = [abs(float(t.get("pnl_usd") or 0)) for t in trades if t.get("outcome") == "loss" and t.get("pnl_usd")]

                        if wins:
                            avg_win = sum(wins) / len(wins)
                        if losses:
                            avg_loss = sum(losses) / len(losses)
                        if avg_loss > 0:
                            profit_factor = sum(wins) / sum(losses) if losses else 0.0
                    except Exception as e:
                        logger.warning(f"Failed to calculate profit metrics for {account['account_name']}: {e}")

                    comparison.append({
                        "account_name": account["account_name"],
                        "strategy_type": account.get("strategy_type", "BALANCED"),
                        "balance": perf.balance,
                        "equity": perf.balance,  # TODO: Get actual equity from broker
                        "daily_pnl": perf.daily_pnl,
                        "daily_pnl_pct": perf.daily_pnl_pct,
                        "win_rate": perf.win_rate,
                        "sharpe_ratio": perf.sharpe_ratio,
                        "max_drawdown_pct": perf.max_drawdown_pct,
                        "active_positions": perf.active_positions,
                        "total_trades": perf.total_trades,
                        "profit_factor": profit_factor,
                        "avg_win_usd": avg_win,
                        "avg_loss_usd": avg_loss,
                        "risk_percent": account.get("risk_percent", 0.5),
                        "max_positions": account.get("max_positions", 3),
                        "max_lot_size": account.get("max_lot_size", 10.0),
                        "min_rr_ratio": account.get("min_rr_ratio", 2.0),
                        "allocated_capital_usd": account.get("allocated_capital_usd", 0),
                        "pause_trading": account.get("pause_trading", False),
                        "broker_profile_id": account.get("broker_profile_id"),
                        "created_at": account.get("created_at"),
                        "updated_at": account.get("updated_at"),
                    })

            return comparison

        except Exception as e:
            logger.error(f"Failed to get account comparison: {e}")
            return []
