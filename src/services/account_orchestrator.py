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


def _derive_account_type(profile: dict) -> str:
    """Derive account_type string from evaluation_mode + evaluation_phase."""
    if not profile.get("evaluation_mode"):
        return "personal"
    phase = profile.get("evaluation_phase", "phase1")
    if phase == "funded":
        return "funded"
    return "evaluation"


def _coerce_amount(value: object) -> Optional[float]:
    """Return a float for non-empty numeric values, otherwise None."""
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


@dataclass
class AccountPerformance:
    """Performance metrics for an account."""
    account_name: str
    balance: float
    equity: float
    daily_pnl: float
    daily_pnl_pct: float
    win_rate: float
    sharpe_ratio: float
    max_drawdown_pct: float
    profit_factor: float
    total_trades: int
    active_positions: int
    # Live broker data
    free_margin: Optional[float] = None
    margin_used: Optional[float] = None
    margin_level_pct: Optional[float] = None
    # Account config
    provider: Optional[str] = None
    account_type: Optional[str] = None
    strategy_type: Optional[str] = None
    connection_status: Optional[str] = None
    last_sync_time: Optional[str] = None
    server_name: Optional[str] = None
    platform_type: Optional[str] = None
    leverage: Optional[int] = None
    # Risk config
    risk_percent: Optional[float] = None
    min_rr_ratio: Optional[float] = None
    max_lot_size: Optional[float] = None
    max_positions: Optional[int] = None
    pause_trading: Optional[bool] = None


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

    def _fetch_live_profile_snapshot(self, profile: dict) -> dict:
        """
        Best-effort live account snapshot for broker-profile-only cards.

        These profiles can exist in broker_profiles before an account_strategies row
        is created, but we still want the dashboard to show real broker balance/equity
        instead of a placeholder card.
        """
        result = {
            "balance": _coerce_amount(profile.get("starting_balance")),
            "equity": _coerce_amount(profile.get("starting_balance")),
            "free_margin": None,
            "margin_used": 0.0,
            "margin_level_pct": None,
            "open_positions": 0,
            "server_name": None,
            "platform_type": profile.get("venue"),
            "leverage": None,
            "last_sync_time": None,
            "connection_status": profile.get("connection_status", "unknown"),
        }

        try:
            from src.adapters.execution.router import resolve_profile_adapter

            profile_id = profile.get("id")
            profile_for_adapter = dict(profile)
            if profile_id is not None and (
                not profile_for_adapter.get("token")
                or not (
                    profile_for_adapter.get("meta_api_account_id")
                    or profile_for_adapter.get("account_id")
                )
            ):
                full_profile_resp = (
                    self.client.table("broker_profiles")
                    .select("*")
                    .eq("id", profile_id)
                    .single()
                    .execute()
                )
                if full_profile_resp and full_profile_resp.data:
                    profile_for_adapter.update(full_profile_resp.data)

            adapter = resolve_profile_adapter(profile_for_adapter)
            if adapter and hasattr(adapter, "get_account_information"):
                account_info = adapter.get_account_information()
                if account_info:
                    live_balance = _coerce_amount(account_info.get("balance"))
                    live_equity = _coerce_amount(account_info.get("equity"))
                    result["balance"] = live_balance if live_balance is not None else result["balance"]
                    result["equity"] = live_equity if live_equity is not None else result["equity"]
                    result["free_margin"] = float(
                        account_info.get("freeMargin")
                        or account_info.get("free_margin")
                        or 0
                    )
                    result["margin_used"] = float(account_info.get("margin", 0))
                    if result["free_margin"] and result["margin_used"] and result["margin_used"] > 0:
                        result["margin_level_pct"] = (
                            (result["free_margin"] + result["margin_used"]) / result["margin_used"]
                        ) * 100
                    result["server_name"] = account_info.get("server") or account_info.get("broker")
                    result["platform_type"] = account_info.get("platform", result["platform_type"])
                    result["leverage"] = (
                        int(account_info.get("leverage"))
                        if account_info.get("leverage")
                        else None
                    )
                    result["connection_status"] = "connected"
                    logger.info(
                        "Fetched live data for standalone profile %s: balance=$%.2f, equity=$%.2f",
                        profile.get("name") or profile.get("id"),
                        result["balance"] or 0.0,
                        result["equity"] or 0.0,
                    )
            if adapter and hasattr(adapter, "get_open_positions"):
                open_positions = adapter.get_open_positions()
                if isinstance(open_positions, list):
                    result["open_positions"] = len(open_positions)

            snapshot_resp = (
                self.client.table("account_status_snapshots")
                .select("snapshot_time")
                .eq("broker_profile_id", profile.get("id"))
                .order("snapshot_time", desc=True)
                .limit(1)
                .execute()
            )
            snapshot_rows = snapshot_resp.data if snapshot_resp else None
            if snapshot_rows:
                result["last_sync_time"] = snapshot_rows[0].get("snapshot_time")
        except Exception as exc:
            logger.warning(
                "Failed to fetch live data for standalone profile %s: %s",
                profile.get("name") or profile.get("id"),
                exc,
            )

        return result

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

            # Get CLOSED trades only for metrics (match by account_name OR broker_profile_id for legacy trades)
            start_date = (datetime.now(timezone.utc) - timedelta(days=lookback_days)).isoformat()
            closed_statuses = ["closed", "CLOSED", "executed", "EXECUTED"]

            # Strategy: Try account_name filter; if 0 results and broker_profile_id exists, also get trades by broker_profile_id
            trades_query = self.client.table("trading_signals").select(
                "pnl_usd, pnl_r, outcome, created_at"
            ).gte("created_at", start_date).eq("account_name", account_name).in_("status", closed_statuses)

            trades_result = trades_query.execute()
            trades = list(trades_result.data or [])

            # If no trades found by account_name and broker_profile_id exists, query by broker_profile_id (legacy trades)
            if len(trades) == 0 and broker_profile_id:
                fallback_query = self.client.table("trading_signals").select(
                    "pnl_usd, pnl_r, outcome, created_at"
                ).gte("created_at", start_date).eq("broker_profile_id", broker_profile_id).is_("account_name", "null").in_("status", closed_statuses)

                fallback_result = fallback_query.execute()
                trades.extend(fallback_result.data or [])
                logger.info(f"Found {len(fallback_result.data or [])} legacy closed trades for {account_name} via broker_profile_id")

            # Calculate metrics from closed trades only
            total_trades = len(trades)
            wins = [t for t in trades if t.get("outcome") == "win" or (t.get("pnl_usd") is not None and float(t.get("pnl_usd") or 0) > 0)]
            losses = [t for t in trades if t.get("outcome") == "loss" or (t.get("pnl_usd") is not None and float(t.get("pnl_usd") or 0) < 0)]
            decided = len(wins) + len(losses)
            win_rate = len(wins) / decided if decided > 0 else 0.0

            # Daily PnL (handle None values from database)
            today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0).isoformat()
            try:
                daily_pnl = sum(
                    float(t.get("pnl_usd") or 0)
                    for t in trades
                    if (t.get("created_at") or "") >= today_start
                )
            except Exception as e:
                logger.error(f"Error calculating daily_pnl: {e}")
                daily_pnl = 0.0

            # ── Override daily_pnl with MetaAPI balance diff (more accurate) ──
            # Uses account_status_snapshots: current_balance − last_balance_before_today
            try:
                start_snap = self.client.table("account_status_snapshots") \
                    .select("balance") \
                    .eq("account_name", account_name) \
                    .lt("snapshot_time", today_start) \
                    .order("snapshot_time", desc=True) \
                    .limit(1) \
                    .execute()

                current_snap = self.client.table("account_status_snapshots") \
                    .select("balance") \
                    .eq("account_name", account_name) \
                    .order("snapshot_time", desc=True) \
                    .limit(1) \
                    .execute()

                if start_snap.data and current_snap.data:
                    start_bal = float(start_snap.data[0]["balance"])
                    curr_bal = float(current_snap.data[0]["balance"])
                    daily_pnl = curr_bal - start_bal
                    logger.info(
                        "daily_pnl from MetaAPI snapshots for %s: "
                        "start=$%.2f current=$%.2f diff=$%.2f",
                        account_name, start_bal, curr_bal, daily_pnl,
                    )
            except Exception as _snap_pnl_err:
                logger.warning(
                    "Failed to compute daily_pnl from snapshots for %s: %s",
                    account_name, _snap_pnl_err,
                )

            # Get real balance and live data from broker (not static allocated capital)
            configured_balance = _coerce_amount(account_data.get("allocated_capital_usd"))
            profile = None
            starting_balance = None
            balance = configured_balance or 0.0
            equity = balance  # Default: equity = balance
            free_margin = None
            margin_used = None
            margin_level_pct = None
            server_name = None
            platform_type = None
            leverage = None
            connection_status = "not_configured"
            last_sync_time = None

            # Try to fetch real account data from MetaApi if broker_profile_id exists
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
                        starting_balance = _coerce_amount(profile.get("starting_balance"))
                        if balance <= 0 and starting_balance is not None:
                            balance = starting_balance
                            equity = starting_balance
                        adapter = get_adapter(profile=profile, settings=get_settings())

                        # Fetch real account info from broker
                        if hasattr(adapter, "get_account_information"):
                            account_info = adapter.get_account_information()
                            if account_info:
                                live_balance = _coerce_amount(account_info.get("balance"))
                                live_equity = _coerce_amount(account_info.get("equity"))
                                balance = live_balance if live_balance is not None else balance
                                equity = live_equity if live_equity is not None else balance
                                free_margin = float(account_info.get("freeMargin") or account_info.get("free_margin") or 0)
                                margin_used = float(account_info.get("margin", 0))
                                if free_margin and margin_used and margin_used > 0:
                                    margin_level_pct = ((free_margin + margin_used) / margin_used) * 100
                                server_name = account_info.get("server") or account_info.get("broker")
                                platform_type = account_info.get("platform", "MetaTrader")
                                leverage = int(account_info.get("leverage", 0)) if account_info.get("leverage") else None
                                connection_status = "connected"
                                logger.info(f"Fetched live data for {account_name}: balance=${balance:.2f}, equity=${equity:.2f}")
                        
                        # Get last sync time from account_status_snapshots
                        try:
                            snapshot = self.client.table("account_status_snapshots").select("snapshot_time").eq(
                                "broker_profile_id", broker_profile_id
                            ).order("snapshot_time", desc=True).limit(1).maybe_single().execute()
                            if snapshot.data:
                                last_sync_time = snapshot.data.get("snapshot_time")
                        except Exception:
                            pass

                except Exception as e:
                    logger.warning(f"Failed to fetch live data for {account_name}: {e}")
                    connection_status = "error"

            # Fallback: try account_status_snapshots (populated by AccountSyncService from MetaAPI)
            if configured_balance is not None and balance == configured_balance:
                try:
                    cutoff = (datetime.now(timezone.utc) - timedelta(hours=24)).isoformat()
                    snap = self.client.table("account_status_snapshots")\
                        .select("balance, equity, snapshot_time")\
                        .eq("account_name", account_name)\
                        .gte("snapshot_time", cutoff)\
                        .order("snapshot_time", desc=True)\
                        .limit(1)\
                        .execute()
                    if snap.data:
                        balance = float(snap.data[0]["balance"])
                        equity = float(snap.data[0]["equity"])
                        last_sync_time = snap.data[0].get("snapshot_time")
                        connection_status = "synced"
                        logger.info(
                            "AccountOrchestrator: using snapshot balance $%.2f for %s",
                            balance, account_name
                        )
                except Exception as snap_err:
                    logger.warning(
                        "AccountOrchestrator: failed to fetch account_status_snapshots for %s: %s",
                        account_name, snap_err
                    )

            if balance <= 0 and starting_balance is not None:
                balance = starting_balance
                equity = starting_balance

            daily_pnl_pct = (daily_pnl / balance * 100) if balance > 0 else 0.0

            # Profit factor (gross wins / gross losses)
            profit_factor = 0.0
            if wins and losses:
                gross_wins = sum(float(t.get("pnl_usd") or 0) for t in wins)
                gross_losses = abs(sum(float(t.get("pnl_usd") or 0) for t in losses))
                profit_factor = gross_wins / gross_losses if gross_losses > 0 else (gross_wins if gross_wins > 0 else 0.0)

            # Sharpe ratio (simplified)
            if len(trades) > 5:
                returns = [float(t.get("pnl_r") or 0) for t in trades if t.get("pnl_r")]
                if returns:
                    try:
                        import numpy as np
                        mean_return = float(np.mean(returns))
                        std_return = float(np.std(returns))
                        sharpe_ratio = (mean_return / std_return) if std_return > 0 else 0.0
                    except (ImportError, Exception) as e:
                        logger.warning(f"Sharpe calc failed: {e}")
                        sharpe_ratio = 0.0
                else:
                    sharpe_ratio = 0.0
            else:
                sharpe_ratio = 0.0

            # Max drawdown (simplified - would need equity curve)
            max_drawdown_pct = 0.0  # TODO: Calculate from equity curve

            # Active positions (open/active only — executed/closed are terminal states)
            open_statuses = ["active", "ACTIVE", "open", "OPEN"]

            if broker_profile_id:
                active_by_name = self.client.table("trading_signals").select(
                    "id", count="exact"
                ).eq("account_name", account_name).in_("status", open_statuses).execute()

                active_by_profile = self.client.table("trading_signals").select(
                    "id", count="exact"
                ).eq("broker_profile_id", broker_profile_id).is_("account_name", "null").in_("status", open_statuses).execute()

                active_positions = (active_by_name.count or 0) + (active_by_profile.count or 0)
            else:
                active_result = self.client.table("trading_signals").select(
                    "id", count="exact"
                ).eq("account_name", account_name).in_("status", open_statuses).execute()
                active_positions = active_result.count or 0

            return AccountPerformance(
                account_name=account_name,
                balance=balance,
                equity=equity,
                daily_pnl=daily_pnl,
                daily_pnl_pct=daily_pnl_pct,
                win_rate=win_rate,
                sharpe_ratio=sharpe_ratio,
                max_drawdown_pct=max_drawdown_pct,
                profit_factor=profit_factor,
                total_trades=total_trades,
                active_positions=active_positions,
                # Live broker data
                free_margin=free_margin,
                margin_used=margin_used,
                margin_level_pct=margin_level_pct,
                # Account config
                provider=account_data.get("provider"),
                account_type=account_data.get("account_type"),
                strategy_type=account_data.get("strategy_type"),
                connection_status=connection_status,
                last_sync_time=last_sync_time,
                server_name=server_name,
                platform_type=platform_type,
                leverage=leverage,
                # Risk config
                risk_percent=account_data.get("risk_percent"),
                min_rr_ratio=account_data.get("min_rr_ratio"),
                max_lot_size=account_data.get("max_lot_size"),
                max_positions=account_data.get("max_positions"),
                pause_trading=account_data.get("pause_trading"),
            )

        except Exception as e:
            from src.adapters.supabase_api import is_supabase_connection_error, reset_api_supabase
            if is_supabase_connection_error(e):
                logger.warning("Supabase connection error in get_account_performance, re-raising for retry")
                reset_api_supabase()
                raise
            logger.exception(f"Failed to get account performance for {account_name}: {e}")
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
            from src.adapters.supabase_api import is_supabase_connection_error, reset_api_supabase
            if is_supabase_connection_error(e):
                logger.warning("Supabase connection error in suggest_capital_allocation, re-raising for retry")
                reset_api_supabase()
                raise
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
            # Fetch all accounts (active and archived soft-deleted)
            all_accounts = self.client.table("account_strategies").select("*").execute()
            account_rows = all_accounts.data or []
            known_names = {a["account_name"] for a in account_rows}

            # Also surface active broker profiles that have not been promoted into
            # account_strategies yet. These are still live trading accounts and
            # should appear in the overview so multi-account activation is visible.
            try:
                all_broker_profiles = self.client.table("broker_profiles").select(
                    "id,name,venue,connection_status,run_mode,is_active,selected_for_trading,"
                    "evaluation_mode,evaluation_phase,prop_firm_name,starting_balance"
                ).execute().data or []
            except Exception:
                all_broker_profiles = []

            broker_profile_ids = {
                profile.get("id") for profile in all_broker_profiles if profile.get("id") is not None
            }
            active_selected_profile_ids = {
                profile.get("id") for profile in all_broker_profiles
                if profile.get("id") is not None
                and profile.get("is_active", True)
                and profile.get("selected_for_trading") is True
            }
            broker_profiles = [
                profile for profile in all_broker_profiles
                if profile.get("id") in active_selected_profile_ids
            ]

            def _account_is_enabled(account: dict) -> bool:
                if not account.get("is_active", True):
                    return False
                broker_profile_id = account.get("broker_profile_id")
                if broker_profile_id is None:
                    return True
                if broker_profile_id in broker_profile_ids:
                    return broker_profile_id in active_selected_profile_ids
                return True

            active_accounts = [a for a in account_rows if _account_is_enabled(a)]
            archived_accounts = [a for a in account_rows if not _account_is_enabled(a)]

            # Find orphaned accounts: have trades in trading_signals but no account_strategies row
            try:
                orphan_rows = self.client.table("trading_signals").select("account_name").not_.is_(
                    "account_name", "null"
                ).execute()
                orphan_names = {
                    r["account_name"] for r in (orphan_rows.data or [])
                    if r.get("account_name") and r["account_name"] not in known_names
                    and r["account_name"] not in ("default", "")
                }
            except Exception:
                orphan_names = set()

            comparison = []

            def _build_active_entry(account):
                perf = self.get_account_performance(account["account_name"])
                if not perf:
                    return None
                profit_factor = 0.0
                avg_win = 0.0
                avg_loss = 0.0
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
                return {
                    "account_name": account["account_name"],
                    "account_type": perf.account_type or account.get("account_type", "Personal"),
                    "strategy_type": account.get("strategy_type", "BALANCED"),
                    "connection_status": perf.connection_status or "unknown",
                    "status": perf.connection_status or "unknown",
                    "balance": perf.balance,
                    "equity": perf.equity,
                    "free_margin": perf.free_margin,
                    "margin_used": perf.margin_used or 0.0,
                    "margin_level_pct": perf.margin_level_pct,
                    "floating_pnl": 0.0,
                    "realized_pnl_today": perf.daily_pnl,
                    "daily_pnl": perf.daily_pnl,
                    "daily_pnl_pct": perf.daily_pnl_pct,
                    "win_rate": perf.win_rate,
                    "sharpe_ratio": perf.sharpe_ratio,
                    "max_drawdown_pct": perf.max_drawdown_pct,
                    "open_positions": perf.active_positions,
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
                    "last_sync_time": perf.last_sync_time,
                    "server_name": perf.server_name,
                    "platform_type": perf.platform_type,
                    "leverage": perf.leverage,
                    "created_at": account.get("created_at"),
                    "updated_at": account.get("updated_at"),
                    "is_active": bool(account.get("is_active", True)),
                    "selected_for_trading": bool(
                        account.get("selected_for_trading", True)
                    ),
                    "is_archived": False,
                }

            def _build_profile_entry(profile):
                """Build a lightweight entry for active broker profiles without strategy rows."""
                account_name = profile.get("name") or f"Profile-{profile.get('id')}"
                if account_name in known_names:
                    return None
                live_data = self._fetch_live_profile_snapshot(profile)
                return {
                    "account_name": account_name,
                    "account_type": _derive_account_type(profile),
                    "strategy_type": "BROKER_PROFILE",
                    "connection_status": live_data["connection_status"],
                    "status": live_data["connection_status"],
                    "balance": live_data["balance"],
                    "equity": live_data["equity"],
                    "free_margin": live_data["free_margin"],
                    "margin_used": live_data["margin_used"],
                    "margin_level_pct": live_data["margin_level_pct"],
                    "floating_pnl": 0.0,
                    "realized_pnl_today": 0.0,
                    "daily_pnl": 0.0,
                    "daily_pnl_pct": 0.0,
                    "win_rate": 0.0,
                    "sharpe_ratio": None,
                    "max_drawdown_pct": None,
                    "open_positions": live_data["open_positions"],
                    "active_positions": live_data["open_positions"],
                    "total_trades": 0,
                    "profit_factor": 0.0,
                    "avg_win_usd": 0.0,
                    "avg_loss_usd": 0.0,
                    "risk_percent": 0.0,
                    "max_positions": 0,
                    "max_lot_size": 0.0,
                    "min_rr_ratio": 0.0,
                    "allocated_capital_usd": 0.0,
                    "pause_trading": False,
                    "broker_profile_id": profile.get("id"),
                    "last_sync_time": live_data["last_sync_time"],
                    "server_name": live_data["server_name"],
                    "platform_type": live_data["platform_type"],
                    "leverage": live_data["leverage"],
                    "created_at": None,
                    "updated_at": None,
                    "is_active": bool(profile.get("is_active", True)),
                    "selected_for_trading": bool(profile.get("selected_for_trading", True)),
                    "is_archived": False,
                }

            def _build_archived_entry(account_name, account_row=None):
                """Build a minimal entry for archived/orphaned accounts with trade history only."""
                try:
                    # Query by account_name first
                    trades = self.client.table("trading_signals").select(
                        "pnl_usd, outcome, created_at"
                    ).eq("account_name", account_name).not_.is_("pnl_usd", "null").execute().data or []

                    # If no trades found by account_name, try broker_profile_id fallback
                    if not trades and account_row and account_row.get("broker_profile_id"):
                        broker_profile_id = account_row["broker_profile_id"]
                        fallback = self.client.table("trading_signals").select(
                            "pnl_usd, outcome, created_at"
                        ).eq("broker_profile_id", broker_profile_id).not_.is_("pnl_usd", "null").execute().data or []
                        trades = fallback

                    total_trades = len(trades)
                    wins = [float(t["pnl_usd"]) for t in trades if t.get("outcome") == "win" and t.get("pnl_usd")]
                    losses = [abs(float(t["pnl_usd"])) for t in trades if t.get("outcome") == "loss" and t.get("pnl_usd")]
                    win_rate = len(wins) / total_trades * 100 if total_trades > 0 else 0.0
                except Exception:
                    total_trades = 0
                    wins = []
                    losses = []
                    win_rate = 0.0
                return {
                    "account_name": account_name,
                    "account_type": (account_row or {}).get("account_type", "Personal"),
                    "strategy_type": (account_row or {}).get("strategy_type", "BALANCED"),
                    "connection_status": "archived",
                    "status": "archived",
                    "balance": None,
                    "equity": None,
                    "free_margin": None,
                    "margin_used": 0.0,
                    "margin_level_pct": None,
                    "floating_pnl": 0.0,
                    "realized_pnl_today": 0.0,
                    "daily_pnl": 0.0,
                    "daily_pnl_pct": 0.0,
                    "win_rate": win_rate,
                    "sharpe_ratio": None,
                    "max_drawdown_pct": None,
                    "open_positions": 0,
                    "active_positions": 0,
                    "total_trades": total_trades,
                    "profit_factor": sum(wins) / sum(losses) if losses else 0.0,
                    "avg_win_usd": sum(wins) / len(wins) if wins else 0.0,
                    "avg_loss_usd": sum(losses) / len(losses) if losses else 0.0,
                    "allocated_capital_usd": (account_row or {}).get("allocated_capital_usd", 0),
                    "broker_profile_id": (account_row or {}).get("broker_profile_id"),
                    "created_at": (account_row or {}).get("created_at"),
                    "updated_at": (account_row or {}).get("updated_at"),
                    "pause_trading": True,
                    "is_active": False,
                    "selected_for_trading": False,
                    "is_archived": True,
                }

            # Active accounts
            for account in active_accounts:
                entry = _build_active_entry(account)
                if entry:
                    comparison.append(entry)

            # Standalone active broker profiles
            for profile in broker_profiles:
                entry = _build_profile_entry(profile)
                if entry:
                    comparison.append(entry)

            # Archived (soft-deleted) accounts from account_strategies
            for account in archived_accounts:
                comparison.append(_build_archived_entry(account["account_name"], account))

            # Truly orphaned accounts (hard-deleted but have trades)
            for name in sorted(orphan_names):
                comparison.append(_build_archived_entry(name))

            return comparison

        except Exception as e:
            logger.error(f"Failed to get account comparison: {e}")
            return []
