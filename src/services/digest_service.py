import logging
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

class DigestService:
    def __init__(self, supabase):
        """
        :param supabase: Configured Supabase client for database interactions.
        """
        self.supabase = supabase

    def aggregate_daily_performance(self, hours_lookback: int = 24) -> Optional[Dict[str, dict]]:
        """
        Queries trading_signals from the past hours_lookback and aggregates metrics grouped by account.
        Returns None if zero trades found.
        Dict shape: { "Account Name": { "net_pnl": 12.3, "total_trades": 3, "win_rate_pct": 66.6, ... } }
        """
        now = datetime.now(timezone.utc)
        since_time = (now - timedelta(hours=hours_lookback)).isoformat()
        
        try:
            # Query the database
            response = (
                self.supabase.table("trading_signals")
                .select("account_name, pnl_usd, commission, swap")
                .in_("status", ["closed"])
                .gte("updated_at", since_time)
                .lte("updated_at", now.isoformat())
                .execute()
            )
            
            data = response.data
            if not data:
                logger.info("DigestService: Zero trades found in the lookback window. Silently exiting.")
                return None
                
            report: Dict[str, dict] = {}
            
            for row in data:
                acct = row.get("account_name") or "Unknown"
                
                # Treat missing as 0
                gross_pnl = float(row.get("pnl_usd") or 0.0)
                commission = float(row.get("commission") or 0.0)
                swap = float(row.get("swap") or 0.0)
                
                net_pnl = gross_pnl + commission + swap
                is_win = net_pnl > 0
                
                if acct not in report:
                    report[acct] = {
                        "net_pnl": 0.0,
                        "gross_pnl": 0.0,
                        "commission": 0.0,
                        "swap": 0.0,
                        "total_trades": 0,
                        "winning_trades": 0,
                        "best_trade_pnl": -float('inf'),
                        "worst_trade_pnl": float('inf'),
                        "win_rate_pct": 0.0
                    }
                
                metrics = report[acct]
                metrics["net_pnl"] += net_pnl
                metrics["gross_pnl"] += gross_pnl
                metrics["commission"] += commission
                metrics["swap"] += swap
                metrics["total_trades"] += 1
                
                if is_win:
                    metrics["winning_trades"] += 1
                    
                if net_pnl > metrics["best_trade_pnl"]:
                    metrics["best_trade_pnl"] = net_pnl
                    
                if net_pnl < metrics["worst_trade_pnl"]:
                    metrics["worst_trade_pnl"] = net_pnl

            # Second pass for final calculations
            for acct, metrics in report.items():
                metrics["win_rate_pct"] = (metrics["winning_trades"] / metrics["total_trades"]) * 100
                
                # Fix edge cases for infinity if there were 0 trades processed (shouldn't happen here)
                if metrics["total_trades"] == 0:
                    metrics["best_trade_pnl"] = 0.0
                    metrics["worst_trade_pnl"] = 0.0

            return report

        except Exception as e:
            logger.error(f"DigestService: Error aggregating daily performance - {e}", exc_info=True)
            return None
