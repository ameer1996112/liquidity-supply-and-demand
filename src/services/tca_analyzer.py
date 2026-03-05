"""
Transaction Cost Analysis (TCA) Analyzer Service

Calculates execution quality metrics including:
- Slippage (pips and basis points)
- Implementation shortfall
- Spread costs
- Latency metrics
- Aggregate TCA reports

Author: AI Trading System - TCA Module
Date: 2026-02-07
"""

import logging
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class TCAMetrics:
    """Aggregate TCA metrics for a time period"""
    total_trades: int
    avg_slippage_pips: float
    avg_slippage_bps: float
    total_slippage_cost_usd: float
    avg_spread_cost_usd: float
    avg_execution_time_ms: float
    worst_slippage_pips: float
    best_slippage_pips: float
    median_slippage_pips: float = 0.0
    total_spread_cost_usd: float = 0.0


@dataclass
class SlippageBySymbol:
    """Slippage metrics grouped by symbol"""
    symbol: str
    avg_slippage_pips: float
    trade_count: int
    total_cost_usd: float
    worst_slippage_pips: float


@dataclass
class LatencyBreakdown:
    """Latency statistics"""
    avg_signal_to_submit_ms: float
    avg_submit_to_fill_ms: float
    avg_total_execution_ms: float
    p95_latency_ms: float
    p99_latency_ms: float
    median_latency_ms: float


class TCAAnalyzer:
    """Analyze transaction costs and execution quality"""

    # Pip sizes for common forex pairs
    PIP_SIZES = {
        "EURUSD": 0.0001,
        "GBPUSD": 0.0001,
        "USDJPY": 0.01,
        "USDCHF": 0.0001,
        "AUDUSD": 0.0001,
        "NZDUSD": 0.0001,
        "USDCAD": 0.0001,
        "EURJPY": 0.01,
        "GBPJPY": 0.01,
        "EURGBP": 0.0001,
        "AUDJPY": 0.01,
        "EURAUD": 0.0001,
        "EURCHF": 0.0001,
        "AUDCAD": 0.0001,
        "GBPAUD": 0.0001,
        "GBPCAD": 0.0001,
        "GOLD": 0.01,  # XAUUSD
        "XAUUSD": 0.01,
    }

    def __init__(self, supabase_client):
        self.client = supabase_client

    def _get_pip_size(self, symbol: str) -> float:
        """Get pip size for a symbol"""
        # Normalize symbol (remove any prefixes/suffixes)
        symbol_clean = symbol.upper().replace(".", "")

        # Direct lookup
        if symbol_clean in self.PIP_SIZES:
            return self.PIP_SIZES[symbol_clean]

        # Check if symbol contains known pairs
        for known_symbol, pip_size in self.PIP_SIZES.items():
            if known_symbol in symbol_clean:
                return pip_size

        # Default to 0.0001 for most forex pairs
        if "JPY" in symbol_clean:
            return 0.01
        return 0.0001

    def calculate_slippage(
        self,
        intended_price: float,
        fill_price: float,
        side: str,
        symbol: str
    ) -> Dict[str, float]:
        """
        Calculate slippage in pips and basis points.

        Slippage convention:
        - Positive slippage = favorable fill (better than expected)
        - Negative slippage = unfavorable fill (worse than expected, cost)

        For BUY orders:
            - Filled lower than intended = positive (good)
            - Filled higher than intended = negative (cost)

        For SELL orders:
            - Filled higher than intended = positive (good)
            - Filled lower than intended = negative (cost)
        """
        if intended_price == 0 or fill_price == 0:
            return {
                "slippage_pips": 0.0,
                "slippage_bps": 0.0,
            }

        pip_size = self._get_pip_size(symbol)

        # Calculate slippage based on direction
        if side.lower() == "buy":
            # BUY: filled lower = good, filled higher = bad
            slippage_pips = (intended_price - fill_price) / pip_size
        else:  # sell
            # SELL: filled higher = good, filled lower = bad
            slippage_pips = (fill_price - intended_price) / pip_size

        # Calculate basis points (always absolute value for percentage)
        slippage_bps = abs((fill_price - intended_price) / intended_price) * 10000

        return {
            "slippage_pips": slippage_pips,
            "slippage_bps": slippage_bps,
        }

    def calculate_implementation_shortfall(
        self,
        arrival_price: float,
        fill_price: float,
        side: str
    ) -> float:
        """
        Calculate implementation shortfall (price impact).

        Measures how much the price moved against us from signal arrival
        to execution. Always a cost (positive number).
        """
        if side.lower() == "buy":
            # BUY: if price went up, we paid more
            return max(0, fill_price - arrival_price)
        else:  # sell
            # SELL: if price went down, we received less
            return max(0, arrival_price - fill_price)

    def get_daily_tca_summary(
        self,
        days: int = 1,
        run_mode: Optional[str] = None
    ) -> TCAMetrics:
        """
        Get aggregate TCA metrics for the last N days.

        Args:
            days: Number of days to look back
            run_mode: Filter by LIVE or PAPER (None = all)

        Returns:
            TCAMetrics dataclass with aggregated statistics
        """
        try:
            # Calculate date range
            end_date = datetime.now(timezone.utc)
            start_date = end_date - timedelta(days=days)

            # Build query
            query = self.client.table("tca_execution_metrics").select("*").gte(
                "signal_created_at", start_date.isoformat()
            ).lte("signal_created_at", end_date.isoformat())

            # Filter by run_mode if specified
            # Note: We need to join with trading_signals to get run_mode
            # For now, fetch all and filter in memory
            response = query.execute()
            records = response.data

            if not records:
                return TCAMetrics(
                    total_trades=0,
                    avg_slippage_pips=0.0,
                    avg_slippage_bps=0.0,
                    total_slippage_cost_usd=0.0,
                    avg_spread_cost_usd=0.0,
                    avg_execution_time_ms=0.0,
                    worst_slippage_pips=0.0,
                    best_slippage_pips=0.0,
                )

            # Calculate aggregates
            total_trades = len(records)
            slippages = [r.get("slippage_pips", 0) or 0 for r in records]
            slippage_bps_list = [r.get("slippage_bps", 0) or 0 for r in records]
            slippage_costs = [r.get("slippage_usd", 0) or 0 for r in records]
            spread_costs = [r.get("spread_cost_usd", 0) or 0 for r in records]
            execution_times = [r.get("total_execution_ms", 0) or 0 for r in records]

            # Filter out None/null values
            slippages = [s for s in slippages if s is not None]
            slippage_bps_list = [s for s in slippage_bps_list if s is not None]
            slippage_costs = [s for s in slippage_costs if s is not None]
            spread_costs = [s for s in spread_costs if s is not None]
            execution_times = [t for t in execution_times if t is not None and t > 0]

            return TCAMetrics(
                total_trades=total_trades,
                avg_slippage_pips=sum(slippages) / len(slippages) if slippages else 0.0,
                avg_slippage_bps=sum(slippage_bps_list) / len(slippage_bps_list) if slippage_bps_list else 0.0,
                total_slippage_cost_usd=sum(slippage_costs),
                avg_spread_cost_usd=sum(spread_costs) / len(spread_costs) if spread_costs else 0.0,
                avg_execution_time_ms=sum(execution_times) / len(execution_times) if execution_times else 0.0,
                worst_slippage_pips=min(slippages) if slippages else 0.0,  # Most negative = worst
                best_slippage_pips=max(slippages) if slippages else 0.0,  # Most positive = best
                median_slippage_pips=sorted(slippages)[len(slippages) // 2] if slippages else 0.0,
                total_spread_cost_usd=sum(spread_costs),
            )

        except Exception as e:
            logger.error(f"Failed to get TCA summary: {e}")
            return TCAMetrics(
                total_trades=0,
                avg_slippage_pips=0.0,
                avg_slippage_bps=0.0,
                total_slippage_cost_usd=0.0,
                avg_spread_cost_usd=0.0,
                avg_execution_time_ms=0.0,
                worst_slippage_pips=0.0,
                best_slippage_pips=0.0,
            )

    def get_slippage_by_symbol(
        self,
        days: int = 30,
        run_mode: Optional[str] = None
    ) -> List[SlippageBySymbol]:
        """
        Get slippage metrics grouped by symbol.

        Args:
            days: Number of days to look back
            run_mode: Filter by LIVE or PAPER (None = all)

        Returns:
            List of SlippageBySymbol objects
        """
        try:
            # Calculate date range
            end_date = datetime.now(timezone.utc)
            start_date = end_date - timedelta(days=days)

            # Fetch TCA metrics with signal data
            query = self.client.table("tca_execution_metrics").select(
                "*,trading_signals(symbol,run_mode)"
            ).gte("signal_created_at", start_date.isoformat()).lte(
                "signal_created_at", end_date.isoformat()
            )

            response = query.execute()
            records = response.data

            if not records:
                return []

            # Group by symbol
            symbol_data: Dict[str, List[Dict]] = {}
            for record in records:
                signal = record.get("trading_signals")
                if not signal:
                    continue

                symbol = signal.get("symbol", "UNKNOWN")
                record_run_mode = signal.get("run_mode")

                # Filter by run_mode if specified
                if run_mode and record_run_mode != run_mode:
                    continue

                if symbol not in symbol_data:
                    symbol_data[symbol] = []
                symbol_data[symbol].append(record)

            # Calculate aggregates per symbol
            results = []
            for symbol, symbol_records in symbol_data.items():
                slippages = [r.get("slippage_pips", 0) or 0 for r in symbol_records]
                costs = [r.get("slippage_usd", 0) or 0 for r in symbol_records]

                results.append(SlippageBySymbol(
                    symbol=symbol,
                    avg_slippage_pips=sum(slippages) / len(slippages) if slippages else 0.0,
                    trade_count=len(symbol_records),
                    total_cost_usd=sum(costs),
                    worst_slippage_pips=min(slippages) if slippages else 0.0,
                ))

            # Sort by trade count (most traded first)
            results.sort(key=lambda x: x.trade_count, reverse=True)
            return results

        except Exception as e:
            from src.adapters.supabase_api import is_supabase_connection_error, reset_api_supabase
            if is_supabase_connection_error(e):
                logger.warning("Supabase connection error in get_slippage_by_symbol, re-raising for retry")
                reset_api_supabase()
                raise
            logger.error(f"Failed to get slippage by symbol: {e}")
            return []

    def get_slippage_by_hour(
        self,
        days: int = 7
    ) -> Dict[int, float]:
        """
        Get average slippage by hour of day (0-23).

        Helps identify which trading hours have best/worst execution quality.

        Args:
            days: Number of days to look back

        Returns:
            Dictionary mapping hour (0-23) to avg slippage (pips)
        """
        try:
            # Calculate date range
            end_date = datetime.now(timezone.utc)
            start_date = end_date - timedelta(days=days)

            # Fetch records
            response = self.client.table("tca_execution_metrics").select(
                "slippage_pips,signal_created_at"
            ).gte("signal_created_at", start_date.isoformat()).lte(
                "signal_created_at", end_date.isoformat()
            ).execute()

            records = response.data

            if not records:
                return {}

            # Group by hour
            hour_data: Dict[int, List[float]] = {h: [] for h in range(24)}
            for record in records:
                slippage = record.get("slippage_pips")
                timestamp_str = record.get("signal_created_at")

                if slippage is None or timestamp_str is None:
                    continue

                # Parse timestamp and extract hour
                timestamp = datetime.fromisoformat(timestamp_str.replace("Z", "+00:00"))
                hour = timestamp.hour

                hour_data[hour].append(slippage)

            # Calculate averages
            result = {}
            for hour, slippages in hour_data.items():
                if slippages:
                    result[hour] = sum(slippages) / len(slippages)

            return result

        except Exception as e:
            logger.error(f"Failed to get slippage by hour: {e}")
            return {}

    def get_latency_breakdown(
        self,
        days: int = 7
    ) -> LatencyBreakdown:
        """
        Get latency statistics with percentiles.

        Args:
            days: Number of days to look back

        Returns:
            LatencyBreakdown dataclass
        """
        try:
            # Calculate date range
            end_date = datetime.now(timezone.utc)
            start_date = end_date - timedelta(days=days)

            # Fetch latency metrics
            response = self.client.table("tca_execution_metrics").select(
                "signal_to_submit_ms,submit_to_fill_ms,total_execution_ms"
            ).gte("signal_created_at", start_date.isoformat()).lte(
                "signal_created_at", end_date.isoformat()
            ).execute()

            records = response.data

            if not records:
                return LatencyBreakdown(
                    avg_signal_to_submit_ms=0.0,
                    avg_submit_to_fill_ms=0.0,
                    avg_total_execution_ms=0.0,
                    p95_latency_ms=0.0,
                    p99_latency_ms=0.0,
                    median_latency_ms=0.0,
                )

            # Extract metrics
            signal_to_submit = [r.get("signal_to_submit_ms", 0) or 0 for r in records if r.get("signal_to_submit_ms")]
            submit_to_fill = [r.get("submit_to_fill_ms", 0) or 0 for r in records if r.get("submit_to_fill_ms")]
            total_execution = [r.get("total_execution_ms", 0) or 0 for r in records if r.get("total_execution_ms")]

            # Calculate percentiles
            def percentile(data: List[float], p: float) -> float:
                if not data:
                    return 0.0
                sorted_data = sorted(data)
                index = int(len(sorted_data) * p)
                return sorted_data[min(index, len(sorted_data) - 1)]

            return LatencyBreakdown(
                avg_signal_to_submit_ms=sum(signal_to_submit) / len(signal_to_submit) if signal_to_submit else 0.0,
                avg_submit_to_fill_ms=sum(submit_to_fill) / len(submit_to_fill) if submit_to_fill else 0.0,
                avg_total_execution_ms=sum(total_execution) / len(total_execution) if total_execution else 0.0,
                p95_latency_ms=percentile(total_execution, 0.95),
                p99_latency_ms=percentile(total_execution, 0.99),
                median_latency_ms=percentile(total_execution, 0.50),
            )

        except Exception as e:
            from src.adapters.supabase_api import is_supabase_connection_error, reset_api_supabase
            if is_supabase_connection_error(e):
                logger.warning("Supabase connection error in get_latency_breakdown, re-raising for retry")
                reset_api_supabase()
                raise
            logger.error(f"Failed to get latency breakdown: {e}")
            return LatencyBreakdown(
                avg_signal_to_submit_ms=0.0,
                avg_submit_to_fill_ms=0.0,
                avg_total_execution_ms=0.0,
                p95_latency_ms=0.0,
                p99_latency_ms=0.0,
                median_latency_ms=0.0,
            )

    def detect_high_slippage_alert(
        self,
        slippage_pips: float,
        threshold: float = 3.0
    ) -> bool:
        """
        Check if slippage exceeds threshold for alerting.

        Args:
            slippage_pips: Slippage in pips (negative = cost)
            threshold: Alert threshold (absolute value)

        Returns:
            True if slippage is worse than threshold
        """
        return abs(slippage_pips) > threshold
