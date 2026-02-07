"""
Trade execution logic (Engine).
Save to Supabase, filter or notify, optional paper position. Used only by worker.
"""

import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Tuple, Optional

from config import get_settings
from src.adapters.supabase import (
    init_supabase,
    save_alert,
    update_alert_exit,
    update_alert_status,
    get_alert_by_zone_id,
    get_alert_by_trade_key,
)
from src.adapters.discord import send_discord, send_telegram
from src.adapters.paper_trader import get_paper_trader
from src.adapters.execution.interfaces import OrderRequest, CloseRequest
from src.adapters.execution.router import get_adapter
from src.core.risk_engine import calculate_max_position_size
from src.adapters import supabase as supabase_module
from src.services.trade_events import log_event
from src.services.execution_engine import ExecutionEngine

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

_paper_trader = None


def _get_paper_trader_instance():
    global _paper_trader
    if _paper_trader is None:
        init_supabase()
        _paper_trader = get_paper_trader(None)
    return _paper_trader


def should_forward_alert(data: Dict[str, Any]) -> Tuple[bool, List[str], Dict[str, Any]]:
    reasons = []
    debug_meta: Dict[str, Any] = {}
    if data.get("entry") is None or data.get("sl") is None or data.get("tp") is None:
        return True, ["Test: Unresolved placeholders"], {"test_mode": True}
    try:
        entry = float(data["entry"])
        sl = float(data["sl"])
        tp = float(data["tp"])
    except (ValueError, TypeError):
        return True, ["Test: Invalid entry/SL/TP"], {"test_mode": True}
    risk = abs(entry - sl)
    reward = abs(tp - entry)
    rr_ratio = reward / risk if risk > 0 else 0
    debug_meta["rr_ratio"] = rr_ratio
    min_rr = get_settings().min_rr_ratio
    if rr_ratio < min_rr:
        reasons.append(f"R:R {rr_ratio:.2f} below minimum ({min_rr})")
    if reasons:
        return False, reasons, debug_meta
    return True, ["OK"], debug_meta


def process_trade(
    data: Dict[str, Any],
    dry_run: bool = False,
    ai_result: Optional[Dict[str, Any]] = None,
    profile: Optional[Dict[str, Any]] = None,
) -> None:
    """
    Execute one trade. When profile is set (multi-account), save one row per profile
    and use that profile's token/account_id/risk_pct for execution.
    """
    init_supabase()
    s = get_settings()

    if data.get("event_type") == "exit":
        # 1) Update Supabase with exit telemetry (existing behavior)
        exit_data = {
            "outcome": data["outcome"],
            "close_price": data["close_price"],
            "close_time": data.get("close_time"),
            "exit_time": data.get("exit_time"),
            "entry_time": data.get("entry_time"),
            "pnl_r": data.get("pnl_r", 0),
            "pnl_usd": data.get("pnl_usd"),
            "exit_type": data["exit_type"],
            "mae_pips": data["mae_pips"],
            "bars_held": data["bars_held"],
        }
        trade_key = (data.get("trade_key") or "").strip()
        update_alert_exit(data["zone_id"], exit_data, trade_key=trade_key)
        logger.info("Exit recorded: zone_id=%s, outcome=%s", data["zone_id"], data["outcome"])
        log_event(None, "exit_processed", "logic", {"zone_id": data["zone_id"], "outcome": data["outcome"]})

        # 2) Broker close: only for LIVE signals with live_trading_enabled
        exit_run_mode = str(data.get("run_mode", "PAPER")).upper()
        if exit_run_mode == "PAPER":
            logger.info("PAPER exit — skipping broker close for zone_id=%s", data["zone_id"])
        elif getattr(s, "live_trading_enabled", False):
            try:
                adapter = get_adapter(run_mode=s.run_mode, settings=s)

                alert = None
                if trade_key:
                    alert = get_alert_by_trade_key(trade_key)
                if not alert:
                    alert = get_alert_by_zone_id(data["zone_id"])

                if not alert:
                    logger.warning(
                        "No alert found for exit: zone_id=%s trade_key=%s (skipping broker close)",
                        data["zone_id"],
                        trade_key,
                    )
                    return

                broker_order_id = alert.get("broker_order_id")
                if not broker_order_id:
                    logger.warning(
                        "No broker_order_id on alert %s; cannot send broker close.",
                        alert.get("id"),
                    )
                    return

                close_req = CloseRequest(
                    client_order_id=str(trade_key or f"alert-{alert['id']}"),
                    signal_id=alert["id"],
                    symbol=alert["symbol"],
                    close_price=data.get("close_price"),
                    outcome=data.get("outcome"),
                    alert_id=alert["id"],
                    broker_order_id=str(broker_order_id),
                    notes="exit_webhook",
                    side=str(alert.get("side", "")).lower(),
                    size=float(alert.get("size", 0.0)),
                )

                exec_result = adapter.close_order(close_req)
                logger.info(
                    "Broker exit result for alert #%s: status=%s message=%s",
                    alert["id"],
                    exec_result.status,
                    exec_result.message,
                )
            except Exception as e:  # noqa: BLE001
                logger.error("Broker close failed for zone_id=%s: %s", data["zone_id"], e)

        return

    symbol = str(data.get("symbol", "")).upper()
    run_mode = str(data.get("run_mode", "PAPER")).upper()
    logger.info("Signal: %s | Mode: %s", symbol, run_mode)

    should_forward, filter_reasons, _ = should_forward_alert(data)
    mode = "paper" if run_mode == "PAPER" else "manual"

    broker_profile_id = profile.get("id") if profile and profile.get("id") is not None else None
    alert_id = save_alert(
        data,
        mode=mode,
        filter_reasons=filter_reasons if not should_forward else None,
        broker_profile_id=broker_profile_id,
    )
    log_event(alert_id, "alert_saved", "logic", {"symbol": symbol, "mode": mode, "broker_profile_id": broker_profile_id})

    if not should_forward:
        reason_str = "; ".join(filter_reasons)
        update_alert_status(alert_id, "filtered", notes=reason_str)
        logger.info("Alert #%s filtered: %s", alert_id, reason_str)
        return

    if run_mode == "PAPER":
        # ── PAPER: simulate execution, skip broker ─────────────────────
        mock_broker_id = f"paper_{uuid.uuid4().hex[:8]}"
        logger.info("Simulating PAPER execution for %s (broker_id=%s)", symbol, mock_broker_id)
        try:
            supabase_module.init_supabase()
            client = supabase_module.supabase
            if client:
                client.table("trading_signals").update({
                    "status": "executed",
                    "broker_order_id": mock_broker_id,
                    "entry_time": datetime.now(timezone.utc).isoformat(),
                }).eq("id", alert_id).execute()
            log_event(alert_id, "paper_executed", "logic", {
                "broker_order_id": mock_broker_id, "symbol": symbol,
            })
        except Exception as e:
            logger.error("Failed to update paper broker_order_id for alert #%s: %s", alert_id, e)
    elif dry_run:
        logger.info("DRY_RUN: Alert #%s saved, no order placed", alert_id)
    else:
        # Live execution path (MetaApi / other adapters via router)
        if not getattr(s, "live_trading_enabled", False):
            logger.info(
                "LIVE_TRADING disabled in settings; skipping live execution for alert #%s",
                alert_id,
            )
        else:
            try:
                adapter = get_adapter(run_mode=s.run_mode, settings=s, profile=profile)
                entry = float(data["entry"])
                sl = float(data["sl"])
                tp = float(data["tp"])
                size = float(data.get("size", 0.01))
                risk = abs(entry - sl)
                reward = abs(tp - entry)
                rr_ratio = reward / risk if risk > 0 else 0.0

                # Force-fetch latest balance from broker for risk sizing
                current_balance = s.account_balance
                current_equity = s.account_balance
                if hasattr(adapter, "get_account_information"):
                    try:
                        account_info = adapter.get_account_information()
                        fetched_balance = account_info.get("balance", 0.0)
                        fetched_equity = account_info.get("equity", 0.0)
                        if fetched_balance > 0:
                            current_balance = fetched_balance
                        if fetched_equity > 0:
                            current_equity = fetched_equity
                    except Exception as acct_err:  # noqa: BLE001
                        logger.warning(
                            "Failed to fetch live balance, falling back to config: %s",
                            acct_err,
                        )

                # Risk-based position sizing: use profile risk_pct when in multi-account
                risk_pct = (profile.get("risk_pct") if profile else None) or s.risk_percent

                # ── Kelly Criterion Position Sizing ────────────────────
                if s.kelly_enabled and supabase:
                    try:
                        from src.services.position_optimizer import PositionOptimizer

                        # Fetch historical performance stats
                        mode_filter = profile.get("run_mode") if profile else s.run_mode

                        # Get closed trades for win rate calculation
                        stats_query = (
                            supabase.table("trading_signals")
                            .select("pnl_r, outcome")
                            .eq("mode", mode_filter)
                            .in_("outcome", ["win", "loss"])
                            .order("created_at", desc=True)
                            .limit(100)
                        )

                        stats_result = stats_query.execute()

                        if stats_result.data and len(stats_result.data) >= 20:
                            wins = [t for t in stats_result.data if t.get("outcome") == "win"]
                            losses = [t for t in stats_result.data if t.get("outcome") == "loss"]

                            win_rate = len(wins) / len(stats_result.data) if stats_result.data else 0.6
                            avg_win_r = sum(t.get("pnl_r", 0) for t in wins) / len(wins) if wins else 2.0
                            avg_loss_r = abs(sum(t.get("pnl_r", 0) for t in losses) / len(losses)) if losses else 1.0

                            # Calculate Kelly-adjusted risk
                            optimizer = PositionOptimizer()
                            kelly_risk_pct = optimizer.suggest_position_size(
                                base_risk_pct=risk_pct,
                                win_rate=win_rate,
                                avg_win_r=avg_win_r,
                                kelly_fraction=s.kelly_fraction,
                                use_kelly=True,
                            )

                            logger.info(
                                "Kelly sizing: win_rate=%.2f, avg_win=%.2fR, "
                                "base=%.2f%%, kelly=%.2f%%",
                                win_rate, avg_win_r, risk_pct, kelly_risk_pct,
                            )

                            risk_pct = kelly_risk_pct

                        else:
                            logger.info("Insufficient trade history for Kelly (%d trades), using base risk", len(stats_result.data) if stats_result.data else 0)

                    except Exception as kelly_err:
                        logger.warning("Kelly Criterion failed, using base risk: %s", kelly_err)

                sl_pips = risk  # raw price distance (used for logging)
                symbol_overrides = data.get("_symbol_overrides")
                max_lots = calculate_max_position_size(
                    payload=data,
                    account_balance=current_balance,
                    risk_percent=risk_pct,
                    symbol_overrides=symbol_overrides,
                )
                if size > max_lots:
                    logger.warning(
                        "Size %.4f exceeds risk limit %.4f — capping to max",
                        size,
                        max_lots,
                    )
                    size = max_lots
                size = round(size, 2)

                logger.info(
                    "Risk Calc: Balance=$%.2f Risk=%.1f%% SL_dist=%.5f -> MaxSize=%.4f, FinalSize=%.2f",
                    current_balance,
                    s.risk_percent,
                    sl_pips,
                    max_lots,
                    size,
                )

                trade_key = (data.get("trade_key") or "").strip()

                order_req = OrderRequest(
                    client_order_id=str(trade_key or f"alert-{alert_id}"),
                    signal_id=alert_id,
                    symbol=symbol,
                    side=str(data.get("side", "")).lower(),
                    size=size,
                    entry=entry,
                    sl=sl,
                    tp=tp,
                    alert_id=alert_id,
                    rr_ratio=rr_ratio,
                )

                # Use Execution Engine for TCA tracking
                # Prepare signal data for TCA analysis
                signal_data = {
                    "created_at": data.get("bar_time") or datetime.now(timezone.utc).isoformat(),
                    "symbol": symbol,
                    "side": data.get("side"),
                    "entry": entry,
                    "sl": sl,
                    "tp": tp,
                }

                # Initialize Supabase client if needed
                supabase_module.init_supabase()
                client = supabase_module.supabase

                if client and s.tca_enabled:
                    # Use execution engine with TCA tracking
                    execution_engine = ExecutionEngine(client, s)
                    exec_result = execution_engine.execute_with_tca(
                        order_request=order_req,
                        signal_data=signal_data,
                        adapter=adapter,
                        profile=profile
                    )
                else:
                    # Fallback to direct adapter call (TCA disabled or no DB)
                    exec_result = adapter.submit_order(order_req)

                logger.info(
                    "Execution result for alert #%s: status=%s broker_order_id=%s message=%s",
                    alert_id,
                    exec_result.status,
                    exec_result.broker_order_id,
                    exec_result.message,
                )

                # CRITICAL: Force update broker_order_id when filled so exit logic can close it later
                if exec_result.status == "filled":
                    try:
                        supabase_module.init_supabase()
                        client = supabase_module.supabase
                        if client is None:
                            logger.error(
                                "Supabase client not initialized; cannot persist broker_order_id for alert #%s",
                                alert_id,
                            )
                        else:
                            update_payload = {
                                "status": "executed",
                                "broker_order_id": str(exec_result.broker_order_id),
                                "filled_entry_price": float(data.get("entry", 0.0)),
                                "entry_time": datetime.now(timezone.utc).isoformat(),
                            }

                            if trade_key:
                                q = client.table("trading_signals").update(update_payload).eq("trade_key", trade_key)
                                if broker_profile_id is not None:
                                    q = q.eq("broker_profile_id", broker_profile_id)
                                else:
                                    q = q.is_("broker_profile_id", "null")
                                q.execute()
                            else:
                                client.table("trading_signals").update(update_payload).eq(
                                    "id", alert_id
                                ).execute()

                            log_event(alert_id, "execution_filled", "logic", {
                                "broker_order_id": str(exec_result.broker_order_id),
                            })
                            logger.info(
                                "✅ Database Synced: Alert #%s linked to Ticket #%s",
                                alert_id,
                                exec_result.broker_order_id,
                            )
                    except Exception as db_err:  # noqa: BLE001
                        logger.error(
                            "Failed to update broker_order_id for alert #%s: %s",
                            alert_id,
                            db_err,
                        )
                elif exec_result.status == "submitted":
                    # Mark as executed; PnL/outcome updated later on exit webhook
                    update_alert_status(alert_id, "executed")
            except Exception as e:  # noqa: BLE001
                logger.error("Execution adapter error for alert #%s: %s", alert_id, e)
                log_event(alert_id, "execution_failed", "logic", {"error": str(e)[:200]})

    # Pass through AI ensemble result (if available) so Discord can render
    # the full brain decision matrix.
    send_discord(data, alert_id, mode=mode, ai_result=ai_result)
    send_telegram(data, alert_id)


execute_trade = process_trade
