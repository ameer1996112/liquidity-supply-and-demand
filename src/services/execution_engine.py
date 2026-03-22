"""
Execution Engine with Transaction Cost Analysis (TCA)

Wraps execution adapter calls with TCA metric capture:
- Pre-execution market conditions (bid/ask/spread/ATR)
- Execution timing (latency metrics)
- Post-execution slippage calculation
- Threshold alerts (high slippage/latency)

Author: AI Trading System - TCA Module
Date: 2026-02-07
"""

import logging
import time
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from src.adapters.execution.interfaces import ExecutionResult, OrderRequest
from src.adapters.market_data import get_market_snapshot
from src.services.tca_analyzer import TCAAnalyzer

logger = logging.getLogger(__name__)


class ExecutionEngine:
    """
    Smart execution wrapper with TCA tracking.

    Captures:
    - Market conditions at execution (bid/ask/spread/volatility)
    - Execution latency (signal → submit → fill)
    - Slippage (intended vs actual fill price)
    - Cost analysis (slippage + spread costs)
    - Alert generation (threshold violations)
    """

    def __init__(self, supabase_client, settings, alert_service=None):
        self.client = supabase_client
        self.settings = settings
        self.tca_analyzer = TCAAnalyzer(supabase_client)
        self._alert_service = alert_service  # Optional AlertService for Discord/Telegram fanout

    def execute_with_tca(
        self,
        order_request: OrderRequest,
        signal_data: Dict[str, Any],
        adapter: Any,
        profile: Optional[Dict] = None,
        pre_fetched_market: Optional[Dict] = None,
    ) -> ExecutionResult:
        """
        Execute order with full TCA tracking.

        Args:
            order_request: OrderRequest with trade details
            signal_data: Original signal payload with metadata
            adapter: Execution adapter (MetaAPI, DryRun, etc.)
            profile: Optional broker profile for multi-account
            pre_fetched_market: Optional pre-fetched market snapshot dict with keys
                bid/ask/spread_pips/atr. When provided, skips the external
                get_market_snapshot() HTTP call on the hot path (OPT-4).

        Returns:
            ExecutionResult from adapter

        Side Effects:
            - Inserts record into tca_execution_metrics table
            - Creates trading_alert if thresholds exceeded
        """
        # Skip TCA if disabled
        if not getattr(self.settings, "tca_enabled", True):
            return adapter.submit_order(order_request)

        # Extract key data
        symbol = order_request.symbol
        intended_price = order_request.entry
        signal_id = order_request.signal_id or order_request.alert_id
        broker_profile_id = profile.get("id") if profile else None

        # Parse signal creation timestamp
        signal_created_at = signal_data.get("created_at")
        if isinstance(signal_created_at, str):
            signal_created_at = datetime.fromisoformat(signal_created_at.replace("Z", "+00:00"))
        elif signal_created_at is None:
            signal_created_at = datetime.now(timezone.utc)

        # Step 1: Submit order FIRST (latency-critical), then build market snapshot.
        # OPT-4: If the caller provides a pre-fetched snapshot, use it and skip the
        # external get_market_snapshot() call entirely. Otherwise fall back to it
        # after the order is submitted (so it runs off the hot path).
        order_submitted_at = datetime.now(timezone.utc)
        submit_start = time.time()

        try:
            exec_result = adapter.submit_order(order_request)
        except Exception as e:
            logger.error(f"Order submission failed: {e}")
            exec_result = ExecutionResult(
                status="failed",
                message=str(e),
                client_order_id=order_request.client_order_id,
            )

        submit_duration_ms = int((time.time() - submit_start) * 1000)
        order_filled_at = datetime.now(timezone.utc)

        # Build market snapshot — prefer pre-fetched (zero cost), fall back to live call
        if pre_fetched_market:
            market = pre_fetched_market
        else:
            try:
                market = get_market_snapshot(symbol)
            except Exception as e:
                logger.warning(f"Failed to get market snapshot: {e}")
                market = {
                    "bid": 0.0,
                    "ask": 0.0,
                    "spread_pips": 0.0,
                    "atr": 0.0,
                }

        # Step 3: Calculate latency metrics
        signal_to_submit_ms = int(
            (order_submitted_at - signal_created_at).total_seconds() * 1000
        ) if signal_created_at else None

        submit_to_fill_ms = int(
            (order_filled_at - order_submitted_at).total_seconds() * 1000
        )

        total_execution_ms = (signal_to_submit_ms or 0) + submit_to_fill_ms

        # Step 4: Calculate slippage (if fill price available)
        actual_fill_price = None
        slippage_pips = None
        slippage_bps = None
        slippage_usd = 0.0

        if exec_result.status in ["filled", "submitted"]:
            # Get actual fill price from ExecutionResult (if available)
            actual_fill_price = getattr(exec_result, "actual_fill_price", None)

            # Fallback: use intended price if actual not available
            if actual_fill_price is None or actual_fill_price == 0:
                actual_fill_price = intended_price

            # Calculate slippage
            if actual_fill_price and intended_price:
                slippage_metrics = self.tca_analyzer.calculate_slippage(
                    intended_price=intended_price,
                    fill_price=actual_fill_price,
                    side=order_request.side,
                    symbol=symbol
                )
                slippage_pips = slippage_metrics["slippage_pips"]
                slippage_bps = slippage_metrics["slippage_bps"]

                # Calculate slippage cost in USD
                pip_value_usd = self._get_pip_value_usd(
                    symbol=symbol,
                    lot_size=order_request.size
                )
                slippage_usd = abs(slippage_pips) * pip_value_usd

        # Step 5: Calculate spread cost
        spread_cost_usd = 0.0
        if market.get("spread_pips"):
            pip_value_usd = self._get_pip_value_usd(
                symbol=symbol,
                lot_size=order_request.size
            )
            spread_cost_usd = market["spread_pips"] * pip_value_usd

        # Step 6: Calculate implementation shortfall (if available)
        implementation_shortfall = None
        if actual_fill_price and intended_price:
            implementation_shortfall = self.tca_analyzer.calculate_implementation_shortfall(
                arrival_price=intended_price,
                fill_price=actual_fill_price,
                side=order_request.side
            )

        # Step 7: Check alert thresholds
        slippage_threshold = getattr(self.settings, "tca_slippage_threshold_pips", 3.0)
        latency_threshold = getattr(self.settings, "tca_latency_threshold_ms", 30000)
        bot_latency_threshold = getattr(self.settings, "tca_bot_latency_threshold_ms", 10000)
        broker_latency_threshold = getattr(self.settings, "tca_broker_latency_threshold_ms", 20000)

        exceeds_slippage = False
        exceeds_latency = False
        exceeds_bot_latency = False
        exceeds_broker_latency = False

        if slippage_pips is not None:
            exceeds_slippage = self.tca_analyzer.detect_high_slippage_alert(
                slippage_pips=slippage_pips,
                threshold=slippage_threshold
            )

        if total_execution_ms > latency_threshold:
            exceeds_latency = True

        # Separate bot vs broker latency detection
        if signal_to_submit_ms and signal_to_submit_ms > bot_latency_threshold:
            exceeds_bot_latency = True

        if submit_to_fill_ms > broker_latency_threshold:
            exceeds_broker_latency = True

        # Step 8: Persist TCA metrics to database
        tca_record = {
            "signal_id": signal_id,
            "broker_profile_id": broker_profile_id,
            "intended_entry_price": float(intended_price) if intended_price else None,
            "actual_fill_price": float(actual_fill_price) if actual_fill_price else None,
            "slippage_pips": float(slippage_pips) if slippage_pips is not None else None,
            "slippage_bps": float(slippage_bps) if slippage_bps is not None else None,
            "slippage_usd": float(slippage_usd),
            "bid_price": float(market.get("bid", 0)),
            "ask_price": float(market.get("ask", 0)),
            "spread_pips": float(market.get("spread_pips", 0)),
            "spread_cost_usd": float(spread_cost_usd),
            "volatility_atr": float(market.get("atr", 0)),
            "signal_to_submit_ms": signal_to_submit_ms,
            "submit_to_fill_ms": submit_to_fill_ms,
            "total_execution_ms": total_execution_ms,
            "execution_method": "market",
            "order_type": order_request.side,
            "executed_volume": float(order_request.size),
            "implementation_shortfall": float(implementation_shortfall) if implementation_shortfall else None,
            "arrival_price": float(intended_price) if intended_price else None,
            "signal_created_at": signal_created_at.isoformat(),
            "order_submitted_at": order_submitted_at.isoformat(),
            "order_filled_at": order_filled_at.isoformat(),
            "exceeds_slippage_threshold": exceeds_slippage,
            "exceeds_latency_threshold": exceeds_latency,
        }

        try:
            self.client.table("tca_execution_metrics").insert(tca_record).execute()
            logger.info(f"TCA metrics persisted for signal_id={signal_id}")
        except Exception as e:
            logger.error(f"Failed to persist TCA metrics: {e}")
            # Don't fail the trade if TCA persistence fails

        # Step 9: Create alerts if thresholds exceeded
        if exceeds_slippage:
            self._create_tca_alert(
                signal_id=signal_id,
                alert_type="high_slippage",
                severity="warning",
                message=f"High slippage: {slippage_pips:.1f} pips on {symbol} "
                        f"(threshold: {slippage_threshold} pips). Cost: ${slippage_usd:.2f}"
            )

        # Separate alerts for bot vs broker latency
        if exceeds_bot_latency:
            self._create_tca_alert(
                signal_id=signal_id,
                alert_type="high_bot_latency",
                severity="warning",
                message=f"High bot processing latency: {signal_to_submit_ms}ms on {symbol} "
                        f"(threshold: {bot_latency_threshold}ms). Check guard rail performance."
            )

        if exceeds_broker_latency:
            self._create_tca_alert(
                signal_id=signal_id,
                alert_type="high_broker_latency",
                severity="info",  # Info since we can't control broker speed
                message=f"High broker execution latency: {submit_to_fill_ms}ms on {symbol} "
                        f"(threshold: {broker_latency_threshold}ms). MetaAPI/broker may be slow."
            )

        # Legacy total latency alert (kept for backward compatibility)
        if exceeds_latency and not (exceeds_bot_latency or exceeds_broker_latency):
            self._create_tca_alert(
                signal_id=signal_id,
                alert_type="high_latency",
                severity="warning",
                message=f"High total execution latency: {total_execution_ms}ms on {symbol} "
                        f"(threshold: {latency_threshold}ms)"
            )

        # Step 10: Return original execution result
        return exec_result

    def _get_pip_value_usd(self, symbol: str, lot_size: float) -> float:
        """
        Calculate USD value of 1 pip for this symbol/position.

        Uses the same logic as risk_engine.py for consistency.
        """
        # Pip value per standard lot (100k units for forex)
        if "JPY" in symbol.upper():
            pip_value_per_lot = 1000.0  # 0.01 pip size * 100k units / 100
        elif "XAU" in symbol.upper() or "GOLD" in symbol.upper():
            pip_value_per_lot = 100.0
        else:
            pip_value_per_lot = 10.0  # Standard for most forex pairs

        return pip_value_per_lot * lot_size

    def _create_tca_alert(
        self,
        signal_id: int,
        alert_type: str,
        severity: str,
        message: str
    ):
        """Create trading alert for TCA threshold violations, with Discord/Telegram fanout."""
        title = f"Execution Quality: {alert_type.replace('_', ' ').title()}"
        metadata = {"source": "tca_engine", "signal_id": signal_id}

        # Use AlertService if available (sends to Discord/Telegram)
        if self._alert_service is not None:
            try:
                self._alert_service.create_alert(
                    alert_type=alert_type,
                    severity=severity,
                    title=title,
                    message=message,
                    metadata=metadata,
                    signal_id=signal_id,
                    dedupe_minutes=30,
                )
                logger.warning(f"TCA alert created via AlertService: {alert_type} for signal_id={signal_id}")
                return
            except Exception as e:
                logger.error(f"AlertService.create_alert failed for TCA alert: {e}")

        # Fallback: direct insert (no Discord/Telegram)
        try:
            alert = {
                "signal_id": signal_id,
                "alert_type": alert_type,
                "severity": severity,
                "title": title,
                "message": message,
                "metadata": metadata,
            }
            self.client.table("trading_alerts").insert(alert).execute()
            logger.warning(f"TCA alert created (direct): {alert_type} for signal_id={signal_id}")
        except Exception as e:
            logger.error(f"Failed to create TCA alert: {e}")
