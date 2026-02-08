"""
Evaluation Progress Tracker for FTMO/PropFirm Challenges

Tracks challenge rules (profit targets, drawdown limits, trading days, consistency)
and calculates current progress from closed trades.

Author: Claude Code
Created: 2026-02-09
"""

import logging
from datetime import datetime, timedelta, timezone
from typing import Dict, Any, Optional, List
from supabase import Client

logger = logging.getLogger(__name__)


class EvaluationTracker:
    """
    Service for tracking FTMO/prop firm evaluation progress.

    Features:
    - Get/Update evaluation rules (profit target, DD limits, min trading days)
    - Calculate current progress from trading_signals table
    - Check rule violations (daily loss, max DD, consistency)
    - Automatic status updates (active -> passed/failed)
    """

    def __init__(self, supabase_client: Client):
        self.sb = supabase_client

    def get_evaluation(self, account_name: str) -> Optional[Dict[str, Any]]:
        """
        Get evaluation progress for an account.

        Returns None if no evaluation is configured.
        """
        try:
            result = (
                self.sb.table("evaluation_progress")
                .select("*")
                .eq("account_name", account_name)
                .maybe_single()
                .execute()
            )

            if not result.data:
                logger.info(f"No evaluation found for {account_name}")
                return None

            return result.data

        except Exception as e:
            logger.error(f"Failed to get evaluation for {account_name}: {e}")
            raise

    def create_or_update_evaluation(
        self,
        account_name: str,
        profit_target_usd: float,
        daily_loss_limit_pct: float,
        max_drawdown_pct: float,
        min_trading_days: int = 0,
        consistency_max_day_pct: Optional[float] = None,
    ) -> Dict[str, Any]:
        """
        Create or update evaluation rules for an account.

        Args:
            account_name: Account identifier
            profit_target_usd: Total profit required to pass (e.g., 10000 for $10k target)
            daily_loss_limit_pct: Max daily loss as % of starting balance (e.g., 5.0 for 5%)
            max_drawdown_pct: Max drawdown from peak equity (e.g., 10.0 for 10%)
            min_trading_days: Minimum number of trading days required
            consistency_max_day_pct: Max % of total profit from any single day (e.g., 0.40 for 40%)

        Returns:
            Created/updated evaluation record
        """
        try:
            # Check if eval exists
            existing = self.get_evaluation(account_name)

            payload = {
                "account_name": account_name,
                "profit_target_usd": profit_target_usd,
                "daily_loss_limit_pct": daily_loss_limit_pct,
                "max_drawdown_pct": max_drawdown_pct,
                "min_trading_days": min_trading_days,
                "consistency_max_day_pct": consistency_max_day_pct,
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }

            if existing:
                # Update existing
                logger.info(f"Updating evaluation rules for {account_name}")
                result = (
                    self.sb.table("evaluation_progress")
                    .update(payload)
                    .eq("account_name", account_name)
                    .execute()
                )
            else:
                # Create new
                logger.info(f"Creating evaluation for {account_name}")
                payload["status"] = "active"
                payload["current_profit_usd"] = 0.0
                payload["current_dd_pct"] = 0.0
                payload["daily_loss_today_pct"] = 0.0
                payload["days_traded"] = 0
                payload["largest_day_profit_pct"] = 0.0
                payload["largest_day_profit_usd"] = 0.0
                result = self.sb.table("evaluation_progress").insert(payload).execute()

            return result.data[0] if result.data else payload

        except Exception as e:
            logger.error(f"Failed to create/update evaluation for {account_name}: {e}")
            raise

    def calculate_progress(self, account_name: str) -> Dict[str, Any]:
        """
        Calculate current evaluation progress from closed trades.

        Returns:
            Updated evaluation record with current stats
        """
        try:
            # Get evaluation rules
            eval_data = self.get_evaluation(account_name)
            if not eval_data:
                raise ValueError(f"No evaluation configured for {account_name}")

            # Get account's starting balance
            account_info = (
                self.sb.table("account_strategies")
                .select("balance")
                .eq("account_name", account_name)
                .single()
                .execute()
            )
            starting_balance = account_info.data.get("balance", 10000)

            # Get all closed trades for this account
            trades = (
                self.sb.table("trading_signals")
                .select("exit_price, pnl_usd, exit_time, created_at")
                .eq("account_name", account_name)
                .not_.is_("exit_price", "null")
                .not_.is_("pnl_usd", "null")
                .order("exit_time", desc=False)
                .execute()
            )

            if not trades.data:
                logger.info(f"No closed trades for {account_name}, progress = 0")
                return eval_data

            # Calculate metrics
            total_profit = sum(t.get("pnl_usd", 0) for t in trades.data)

            # Group by day to find largest day profit and daily loss violations
            trades_by_day: Dict[str, List[float]] = {}
            for trade in trades.data:
                exit_time = trade.get("exit_time")
                if not exit_time:
                    continue
                day_key = exit_time[:10]  # YYYY-MM-DD
                pnl = trade.get("pnl_usd", 0)
                if day_key not in trades_by_day:
                    trades_by_day[day_key] = []
                trades_by_day[day_key].append(pnl)

            days_traded = len(trades_by_day)

            # Find largest day profit
            largest_day_usd = 0.0
            daily_profits = [sum(pnls) for pnls in trades_by_day.values()]
            if daily_profits:
                largest_day_usd = max(daily_profits)

            largest_day_pct = (largest_day_usd / total_profit * 100) if total_profit > 0 else 0

            # Calculate today's loss (for daily loss limit check)
            today = datetime.now(timezone.utc).date().isoformat()
            today_pnl = sum(trades_by_day.get(today, []))
            daily_loss_today_pct = abs(today_pnl / starting_balance * 100) if today_pnl < 0 else 0

            # Calculate current drawdown (simplified - from peak equity)
            # Track running equity and find max DD
            running_equity = starting_balance
            peak_equity = starting_balance
            max_dd_pct = 0.0

            for trade in trades.data:
                pnl = trade.get("pnl_usd", 0)
                running_equity += pnl
                if running_equity > peak_equity:
                    peak_equity = running_equity
                current_dd = (peak_equity - running_equity) / peak_equity * 100 if peak_equity > 0 else 0
                max_dd_pct = max(max_dd_pct, current_dd)

            # Check for rule violations
            status = eval_data.get("status", "active")
            failure_reason = None

            if status == "active":
                # Check daily loss limit
                if daily_loss_today_pct > eval_data["daily_loss_limit_pct"]:
                    status = "failed"
                    failure_reason = f"Daily loss limit exceeded: {daily_loss_today_pct:.2f}% > {eval_data['daily_loss_limit_pct']}%"

                # Check max drawdown
                elif max_dd_pct > eval_data["max_drawdown_pct"]:
                    status = "failed"
                    failure_reason = f"Max drawdown exceeded: {max_dd_pct:.2f}% > {eval_data['max_drawdown_pct']}%"

                # Check consistency rule (if configured)
                elif eval_data.get("consistency_max_day_pct") and total_profit > 0:
                    max_allowed_pct = eval_data["consistency_max_day_pct"] * 100
                    if largest_day_pct > max_allowed_pct:
                        status = "failed"
                        failure_reason = f"Consistency rule violated: largest day was {largest_day_pct:.1f}% of total profit (max {max_allowed_pct}%)"

                # Check if target reached
                elif total_profit >= eval_data["profit_target_usd"]:
                    if days_traded >= eval_data["min_trading_days"]:
                        status = "passed"
                    else:
                        logger.info(f"{account_name}: Profit target reached but only {days_traded}/{eval_data['min_trading_days']} days traded")

            # Update database
            update_payload = {
                "current_profit_usd": total_profit,
                "current_dd_pct": max_dd_pct,
                "daily_loss_today_pct": daily_loss_today_pct,
                "days_traded": days_traded,
                "largest_day_profit_pct": largest_day_pct,
                "largest_day_profit_usd": largest_day_usd,
                "status": status,
                "failure_reason": failure_reason,
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }

            if status in ("passed", "failed") and not eval_data.get("completed_at"):
                update_payload["completed_at"] = datetime.now(timezone.utc).isoformat()

            result = (
                self.sb.table("evaluation_progress")
                .update(update_payload)
                .eq("account_name", account_name)
                .execute()
            )

            logger.info(
                f"Evaluation progress updated for {account_name}: "
                f"profit=${total_profit:.2f} ({total_profit/eval_data['profit_target_usd']*100:.1f}% of target), "
                f"DD={max_dd_pct:.2f}%, days={days_traded}, status={status}"
            )

            return result.data[0] if result.data else update_payload

        except Exception as e:
            logger.error(f"Failed to calculate progress for {account_name}: {e}")
            raise

    def delete_evaluation(self, account_name: str) -> bool:
        """
        Delete evaluation configuration for an account.

        Returns:
            True if deleted, False if not found
        """
        try:
            result = (
                self.sb.table("evaluation_progress")
                .delete()
                .eq("account_name", account_name)
                .execute()
            )

            deleted = len(result.data) > 0
            if deleted:
                logger.info(f"Deleted evaluation for {account_name}")
            else:
                logger.info(f"No evaluation found to delete for {account_name}")

            return deleted

        except Exception as e:
            logger.error(f"Failed to delete evaluation for {account_name}: {e}")
            raise

    def get_all_active_evaluations(self) -> List[Dict[str, Any]]:
        """
        Get all active evaluations across all accounts.

        Useful for batch processing / daily cron jobs.
        """
        try:
            result = (
                self.sb.table("evaluation_progress")
                .select("*")
                .eq("status", "active")
                .execute()
            )

            return result.data or []

        except Exception as e:
            logger.error(f"Failed to get active evaluations: {e}")
            raise

    def recalculate_all_active(self) -> Dict[str, Any]:
        """
        Recalculate progress for all active evaluations.

        Returns:
            Summary dict with success/failure counts
        """
        active_evals = self.get_all_active_evaluations()

        results = {
            "total": len(active_evals),
            "success": 0,
            "failed": 0,
            "errors": []
        }

        for eval_data in active_evals:
            account_name = eval_data["account_name"]
            try:
                self.calculate_progress(account_name)
                results["success"] += 1
            except Exception as e:
                results["failed"] += 1
                results["errors"].append({
                    "account_name": account_name,
                    "error": str(e)
                })
                logger.error(f"Failed to recalculate {account_name}: {e}")

        logger.info(
            f"Batch recalculation complete: {results['success']}/{results['total']} successful, "
            f"{results['failed']} failed"
        )

        return results
