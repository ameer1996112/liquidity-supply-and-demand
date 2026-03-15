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
from src.adapters.discord import send_discord, send_telegram, send_discord_async, send_telegram_async
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
    """Validate that the alert has required fields.

    NOTE: R:R filtering is disabled by default (min_rr_ratio=0) because
    the Pine Script strategy handles SL/TP rules directly.
    Set MIN_RR_RATIO > 0 in .env to re-enable backend R:R filtering.
    """
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
    # Only enforce if min_rr_ratio > 0 (disabled by default since Pine handles SL/TP)
    if min_rr > 0 and rr_ratio < min_rr:
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
        logger.info("Exit received: zone_id=%s, outcome=%s", data["zone_id"], data["outcome"])
        log_event(None, "exit_processed", "logic", {"zone_id": data["zone_id"], "outcome": data["outcome"]})

        # 2) Broker close: only for LIVE signals with live_trading_enabled
        # BUGFIX: fallback to settings run_mode (not "PAPER") so LIVE exits actually close the broker position
        exit_run_mode = str(data.get("run_mode", get_settings().run_mode)).upper()
        if exit_run_mode == "PAPER":
            # PAPER mode: no broker to confirm, update DB immediately
            update_alert_exit(data["zone_id"], exit_data, trade_key=trade_key)
            logger.info("PAPER exit — updating DB to CLOSED for zone_id=%s", data["zone_id"])
            try:
                # Mark the paper trade as closed in DB directly
                client = supabase_module.supabase
                if client:
                    close_payload = {
                        "status": "CLOSED",
                        "closed_at": datetime.now(timezone.utc).isoformat(),
                    }
                    if trade_key:
                        client.table("trading_signals").update(close_payload).eq("trade_key", trade_key).execute()
                    else:
                        client.table("trading_signals").update(close_payload).eq("zone_id", data["zone_id"]).execute()
            except Exception as e:
                logger.error("Failed to close paper trade in DB for zone_id=%s: %s", data["zone_id"], e)
        elif getattr(s, "live_trading_enabled", False):
            try:
                # Use profile-specific adapter when available (multi-account)
                adapter = get_adapter(run_mode=s.run_mode, settings=s, profile=profile)

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
                    # Still record exit telemetry even if broker close is skipped
                    update_alert_exit(data["zone_id"], exit_data, trade_key=trade_key)
                    return

                broker_order_id = alert.get("broker_order_id")
                if not broker_order_id:
                    logger.warning(
                        "No broker_order_id on alert %s; cannot send broker close.",
                        alert.get("id"),
                    )
                    # Still record exit telemetry
                    update_alert_exit(data["zone_id"], exit_data, trade_key=trade_key)
                    return

                # SAFEGUARD: Verify symbol matches to avoid closing the wrong MT5 position
                payload_symbol = str(data.get("symbol", "")).upper()
                alert_symbol = str(alert.get("symbol", "")).upper()
                if payload_symbol and alert_symbol and payload_symbol != alert_symbol:
                    logger.error(
                        "Symbol mismatch: exit payload symbol=%s but alert #%s symbol=%s — aborting broker close",
                        payload_symbol, alert["id"], alert_symbol,
                    )
                    update_alert_exit(data["zone_id"], exit_data, trade_key=trade_key)
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

                # BUGFIX: Only update DB to CLOSED AFTER broker close is confirmed
                if exec_result.status in ("filled", "submitted", "success"):
                    update_alert_exit(data["zone_id"], exit_data, trade_key=trade_key)
                    logger.info(
                        "✅ DB updated to CLOSED after confirmed broker close for zone_id=%s alert #%s ticket=%s",
                        data["zone_id"], alert["id"], broker_order_id,
                    )
                else:
                    logger.error(
                        "Broker close FAILED for zone_id=%s (status=%s) — DB NOT marked CLOSED; watchdog will retry",
                        data["zone_id"], exec_result.status,
                    )

# 🚀 OPTIMIZED Broker PnL Fetch (Watermark + 15min Instant Window)
                if exec_result.status in ("filled", "success") and hasattr(adapter, "get_historical_deals"):
                    try:
                        from src.services.broker_reconciliation import get_last_closed_timestamp
                        from datetime import timedelta
                        now = datetime.now(timezone.utc)
                        
                        # Instant prong: max 15min lookback for webhook closes
                        close_window_start = (now - timedelta(minutes=15)).isoformat()
                        # Watermark: DB's last closed_at (safety net)
                        watermark = get_last_closed_timestamp(supabase_module.supabase)
                        
                        # Use most recent (efficient + safe)
                        start_time = max(close_window_start, watermark)
                        end_time = now.isoformat()

                        logger.info("Fetching broker PnL since %s (watermark=%s)", start_time[:19], watermark[:19])

                        # Use new get_deals_by_position method for more efficient fetching
                        try:
                            deals = adapter.get_deals_by_position(broker_order_id)
                            if not deals:
                                logger.debug("get_deals_by_position returned empty, falling back to get_historical_deals")
                                deals = adapter.get_historical_deals(start_time, end_time)
                        except Exception:
                            logger.debug("get_deals_by_position not available, falling back to get_historical_deals")
                            deals = adapter.get_historical_deals(start_time, end_time)

                        deals = adapter.get_historical_deals(start_time, end_time)

                        # Process ALL exit deals for the position (DEAL_ENTRY_OUT)
                        total_pnl = 0.0
                        total_commission = 0.0
                        total_swap = 0.0
                        exit_deals = []
                        symbol = alert.get("symbol", "").upper()

                        for deal in deals:
                            if (str(deal.get("positionId", "")) == str(broker_order_id) and
                                deal.get("entryType") == "DEAL_ENTRY_OUT" and
                                str(deal.get("symbol", "")).upper() == symbol):
                                exit_deals.append(deal)
                                total_pnl += float(deal.get("profit", 0))
                                total_commission += float(deal.get("commission", 0))
                                total_swap += float(deal.get("swap", 0))

                        if exit_deals:
                            total_realized_pnl = total_pnl + total_commission + total_swap

                            logger.info(
                                "🚀 INSTANT Broker PnL #%s ticket=%s | Raw: P=$%.2f C=$%.2f S=$%.2f | "
                                "NET=$%.2f (vs TV $%.2f) | %d exit deals | Matches: %s",
                                alert["id"], broker_order_id,
                                total_pnl, total_commission, total_swap, total_realized_pnl,
                                exit_data.get("pnl_usd", 0), len(exit_deals),
                                "DEAL_ENTRY_OUT" if exit_deals[0].get("entryType") else exit_deals[0].get("entryType", "UNKNOWN")
                            )

                            # Update database with actual broker PnL (sum of all exit deals)
                            client = supabase_module.supabase
                            if client:
                                pnl_update = {
                                    "pnl_usd": total_realized_pnl,
                                    "pnl": total_realized_pnl,  # Also update pnl field
                                    "commission": total_commission,
                                    "swap": total_swap,
                                }
                                if trade_key:
                                    client.table("trading_signals").update(pnl_update).eq("trade_key", trade_key).execute()
                                else:
                                    client.table("trading_signals").update(pnl_update).eq("zone_id", data["zone_id"]).execute()

                                logger.info("Updated DB with broker actual PnL: $%.2f (sum of %d exit deals)", total_realized_pnl, len(exit_deals))
                        else:
                            logger.warning(
                                "Could not find any exit deals for broker_order_id=%s in recent history",
                                broker_order_id
                            )
                    except Exception as e:
                        logger.error("Failed to fetch/update actual broker PnL for alert #%s: %s", alert["id"], e)
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
    data["_signal_id"] = alert_id
    corr = data.get("_correlation_id")
    if corr and supabase_module.supabase:
        try:
            from src.services.ai_run_service import link_ai_run_to_signal
            link_ai_run_to_signal(supabase_module.supabase, corr, alert_id)
        except Exception:
            pass
    log_event(alert_id, "alert_saved", "logic", {"symbol": symbol, "mode": mode, "broker_profile_id": broker_profile_id})

    if not should_forward:
        reason_str = "; ".join(filter_reasons)
        update_alert_status(alert_id, "filtered", notes=reason_str)
        logger.info("Alert #%s filtered: %s", alert_id, reason_str)
        return

    if run_mode == "BACKTEST":
        # ── BACKTEST: imported historical data — save to DB only, no broker ──
        logger.info("BACKTEST signal #%s for %s — stored only, no execution", alert_id, symbol)
        try:
            supabase_module.init_supabase()
            client = supabase_module.supabase
            if client:
                client.table("trading_signals").update({
                    "status": "backtest",
                    "account_name": (profile.get("name") if profile else None) or "Backtest",
                }).eq("id", alert_id).execute()
            log_event(alert_id, "backtest_stored", "logic", {"symbol": symbol})
        except Exception as e:
            logger.error("Failed to update backtest status for alert #%s: %s", alert_id, e)
        return

    elif run_mode == "PAPER":
        # ── PAPER: simulate execution, skip broker ─────────────────────
        mock_broker_id = f"paper_{uuid.uuid4().hex[:8]}"
        logger.info("Simulating PAPER execution for %s (broker_id=%s)", symbol, mock_broker_id)
        try:
            supabase_module.init_supabase()
            client = supabase_module.supabase
            if client:
                paper_update = {
                    "status": "OPEN",
                    "broker_order_id": mock_broker_id,
                    "entry_time": datetime.now(timezone.utc).isoformat(),
                    "opened_at": datetime.now(timezone.utc).isoformat(),
                }
                if profile and profile.get("name"):
                    paper_update["account_name"] = profile["name"]
                else:
                    paper_update["account_name"] = "Paper"
                client.table("trading_signals").update(paper_update).eq("id", alert_id).execute()
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

                # Risk-based position sizing: DB broker_profiles > dynamic (UI) > .env
                _profile_risk = (profile.get("risk_pct") if profile else None)
                try:
                    from src.core.dynamic_config import get_dynamic_setting
                    _dynamic_risk = float(get_dynamic_setting("risk_percent", s.risk_percent))
                except Exception:
                    _dynamic_risk = s.risk_percent
                risk_pct = _profile_risk if (_profile_risk is not None and _profile_risk > 0) else _dynamic_risk

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

                # Read PropGuard risk multiplier (set by worker.py Step-Up Protocol)
                # Survival mode: 0.5x | Building buffer: 0.75x | Normal: 1.0x | Aggressive: 2.0x
                risk_multiplier = float(data.get("_risk_multiplier", 1.0))
                # Also apply time-based multiplier if present
                time_multiplier = float(data.get("_time_risk_multiplier", 1.0))
                effective_multiplier = risk_multiplier * time_multiplier
                if effective_multiplier != 1.0:
                    logger.info(
                        "Risk multipliers: prop_guard=%.2f, time=%.2f -> effective=%.2f",
                        risk_multiplier, time_multiplier, effective_multiplier,
                    )

                max_lots = calculate_max_position_size(
                    payload=data,
                    account_balance=current_balance,
                    risk_percent=risk_pct,
                    risk_multiplier=effective_multiplier,
                    symbol_overrides=symbol_overrides,
                )
                if size > max_lots:
                    logger.warning(
                        "Size %.4f exceeds risk limit %.4f (multiplier=%.2f) — capping to max",
                        size,
                        max_lots,
                        effective_multiplier,
                    )
                    size = max_lots
                size = round(size, 2)

                logger.info(
                    "Risk Calc: Balance=$%.2f Risk=%.1f%% Multiplier=%.2f SL_dist=%.5f -> MaxSize=%.4f, FinalSize=%.2f",
                    current_balance,
                    risk_pct,
                    effective_multiplier,
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
                broker_order_id = getattr(exec_result, "broker_order_id", None)

                if exec_result.status == "filled" and broker_order_id:
                    try:
                        supabase_module.init_supabase()
                        client = supabase_module.supabase
                        if client is None:
                            logger.error(
                                "Supabase client not initialized; cannot persist broker_order_id for alert #%s",
                                alert_id,
                            )
                        else:
                            account_name = getattr(
                                exec_result, "account_name", None
                            ) or (profile.get("name") if profile else None)
                            update_payload = {
                                "status": "OPEN",
                                "broker_order_id": str(broker_order_id),
                                "filled_entry_price": float(data.get("entry", 0.0)),
                                "entry_time": datetime.now(timezone.utc).isoformat(),
                                "opened_at": datetime.now(timezone.utc).isoformat(),
                            }
                            if account_name:
                                update_payload["account_name"] = account_name

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
                                "broker_order_id": str(broker_order_id),
                            })
                            logger.info(
                                "✅ Database Synced: Alert #%s linked to Ticket #%s",
                                alert_id,
                                broker_order_id,
                            )
                    except Exception as db_err:  # noqa: BLE001
                        logger.error(
                            "Failed to update broker_order_id for alert #%s: %s",
                            alert_id,
                            db_err,
                        )
                elif exec_result.status == "submitted" and broker_order_id:
                    # Mark as executed; PnL/outcome updated later on exit webhook
                    update_alert_status(alert_id, "OPEN")
                elif exec_result.status in ("filled", "submitted") and not broker_order_id:
                    logger.warning(
                        "Execution for alert #%s returned status=%s but no broker_order_id; marking execution_failed.",
                        alert_id,
                        exec_result.status,
                    )
                    update_alert_status(alert_id, "execution_failed", notes="Broker accepted order but returned no order ID")
            except Exception as e:  # noqa: BLE001
                logger.error("Execution adapter error for alert #%s: %s", alert_id, e)
                log_event(alert_id, "execution_failed", "logic", {"error": str(e)[:200]})
                update_alert_status(alert_id, "execution_failed", notes=f"Execution exception: {str(e)[:200]}")

    # Pass through AI ensemble result (if available) so Discord can render
    # the full brain decision matrix.
    # Phase 1 Optimization: Use async notifications to avoid blocking execution
    send_discord_async(data, alert_id, mode=mode, ai_result=ai_result)
    send_telegram_async(data, alert_id)


execute_trade = process_trade
