"""
Trade execution logic (Engine).
Save to Supabase, filter or notify, optional paper position. Used only by worker.
"""

import logging
from typing import Any, Dict, List, Tuple

from config import get_settings
import src.adapters.supabase as supabase_db
from src.adapters.discord import send_discord, send_telegram
from src.adapters.paper_trader import get_paper_trader

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

_paper_trader = None


def _get_paper_trader_instance():
    global _paper_trader
    if _paper_trader is None:
        supabase_db.init_supabase()
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


def process_trade(data: Dict[str, Any], dry_run: bool = False) -> None:
    supabase_db.init_supabase()
    db = supabase_db

    if data.get("event_type") == "exit":
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
        db.update_alert_exit(data["zone_id"], exit_data, trade_key=trade_key)
        logger.info("Exit recorded: zone_id=%s, outcome=%s", data["zone_id"], data["outcome"])
        return

    symbol = str(data.get("symbol", "")).upper()
    should_forward, filter_reasons, _ = should_forward_alert(data)
    s = get_settings()
    mode = "manual"
    if s.paper_trading_enabled and s.paper_auto_execute:
        paper_symbols = [x.strip() for x in s.paper_symbols.split(",") if x.strip()]
        if not paper_symbols or symbol in paper_symbols:
            pt = _get_paper_trader_instance()
            if len(pt.get_open_positions()) < s.paper_max_positions:
                mode = "paper"

    alert_id = db.save_alert(data, mode=mode, filter_reasons=filter_reasons if not should_forward else None)

    if not should_forward:
        reason_str = "; ".join(filter_reasons)
        db.update_alert_status(alert_id, "filtered", notes=reason_str)
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

    send_discord(data, alert_id, mode=mode)
    send_telegram(data, alert_id)


execute_trade = process_trade
