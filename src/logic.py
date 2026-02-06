"""
Trade execution logic (Engine).
Save to Supabase, filter or notify, optional paper position. Used only by worker.
"""

import logging
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
) -> None:
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

        # 2) Live broker close via execution adapter (MetaApi) if enabled
        if getattr(s, "live_trading_enabled", False):
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
    should_forward, filter_reasons, _ = should_forward_alert(data)
    mode = "manual"
    if s.paper_trading_enabled and s.paper_auto_execute:
        paper_symbols = [x.strip() for x in s.paper_symbols.split(",") if x.strip()]
        if not paper_symbols or symbol in paper_symbols:
            pt = _get_paper_trader_instance()
            if len(pt.get_open_positions()) < s.paper_max_positions:
                mode = "paper"

    alert_id = save_alert(data, mode=mode, filter_reasons=filter_reasons if not should_forward else None)
    log_event(alert_id, "alert_saved", "logic", {"symbol": symbol, "mode": mode})

    if not should_forward:
        reason_str = "; ".join(filter_reasons)
        update_alert_status(alert_id, "filtered", notes=reason_str)
        logger.info("Alert #%s filtered: %s", alert_id, reason_str)
        return

    if mode == "paper" and not dry_run:
        pt = _get_paper_trader_instance()
        entry = float(data["entry"])
        sl = float(data["sl"])
        tp = float(data["tp"])
        size = float(data.get("size", 0.01))
        risk = abs(entry - sl)
        reward = abs(tp - entry)
        rr_ratio = reward / risk if risk > 0 else 0
        pt.open_position(alert_id, symbol, str(data["side"]).lower(), entry, sl, tp, size, rr_ratio)
        logger.info("Paper position #%s opened", alert_id)
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
                adapter = get_adapter(run_mode=s.run_mode, settings=s)
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

                # Risk-based position sizing: cap size to max allowed by balance
                sl_pips = risk  # raw price distance (used for logging)
                symbol_overrides = data.get("_symbol_overrides")
                max_lots = calculate_max_position_size(
                    payload=data,
                    account_balance=current_balance,
                    risk_percent=s.risk_percent,
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
                                client.table("trading_signals").update(update_payload).eq(
                                    "trade_key", trade_key
                                ).execute()
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
