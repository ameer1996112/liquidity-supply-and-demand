"""
Trade execution logic (Engine).
Extracted from trading_bot: Discord/Telegram, position sizing, filters, Supabase save/update.
Used only by worker.py. No Redis, no FastAPI.
"""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import requests

from backend.config import get_settings

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Lazy imports to avoid loading heavy deps in API
_supabase_db = None
_news_filter = None
_paper_trader = None


def _get_supabase_db():
    global _supabase_db
    if _supabase_db is None:
        from backend import supabase_db as m
        m.init_supabase()
        _supabase_db = m
    return _supabase_db


def _get_paper_trader():
    """In-memory only when db_path is None (no SQLite)."""
    global _paper_trader
    if _paper_trader is None:
        from backend.paper_trader import get_paper_trader
        # None = in-memory only (no SQLite)
        _paper_trader = get_paper_trader(None)
    return _paper_trader


def get_pip_divisor(symbol: str) -> float:
    symbol = symbol.upper()
    index_patterns = ["NAS", "US100", "NDX", "SPX", "US500", "DJI", "US30", "DAX", "FTSE", "NIK"]
    if any(p in symbol for p in index_patterns):
        return 1.0
    if "JPY" in symbol:
        return 0.01
    if "XAU" in symbol or "GOLD" in symbol:
        return get_settings().gold_pip_divisor
    return 0.0001


def calculate_position_size(
    sl_pips: float,
    symbol: str,
    account_balance: float = None,
    risk_percent: float = None,
) -> Dict[str, Any]:
    s = get_settings()
    account_balance = account_balance or s.account_balance
    risk_percent = risk_percent or s.risk_percent
    risk_amount = account_balance * (risk_percent / 100)
    symbol = symbol.upper()
    if "JPY" in symbol:
        pip_value_per_lot = 10.0
    elif "XAU" in symbol or "GOLD" in symbol:
        pip_value_per_lot = 1.0
    else:
        pip_value_per_lot = 10.0
    lots = (risk_amount / (sl_pips * pip_value_per_lot)) if sl_pips > 0 else 0.01
    lots = max(0.01, round(lots, 2))
    return {
        "lots": lots,
        "risk_amount": risk_amount,
        "sl_pips": sl_pips,
        "account_balance": account_balance,
        "risk_percent": risk_percent,
    }


def send_discord(data: Dict[str, Any], alert_id: int, mode: str = "manual") -> Tuple[bool, Optional[str]]:
    s = get_settings()
    if not s.discord_webhook_url:
        return False, "DISCORD_WEBHOOK_URL not configured"
    try:
        side = str(data["side"]).upper()
        emoji = "📈" if side == "BUY" else "📉"
        color = 0x3498DB if mode == "paper" else (0x00FF00 if side == "BUY" else 0xFF0000)
        mode_prefix = "🔵 PAPER | " if mode == "paper" else ""
        entry = float(data["entry"])
        sl = float(data["sl"])
        tp = float(data["tp"])
        risk = abs(entry - sl)
        reward = abs(tp - entry)
        rr_ratio = reward / risk if risk > 0 else 0
        symbol = str(data["symbol"]).upper()
        pip_divisor = get_pip_divisor(symbol)
        unit_label = "pts" if pip_divisor == 1.0 else "pips"
        sl_pips = abs(entry - sl) / pip_divisor
        tp_pips = abs(tp - entry) / pip_divisor
        position_info = calculate_position_size(sl_pips, symbol)
        fields = [
            {"name": "Symbol", "value": f"**{data['symbol']}**", "inline": True},
            {"name": "Type", "value": side, "inline": True},
            {"name": "R:R", "value": f"1:{rr_ratio:.2f}", "inline": True},
            {"name": "Entry", "value": str(data["entry"]), "inline": True},
            {"name": "Stop Loss", "value": f"{data['sl']} ({sl_pips:.1f} {unit_label})", "inline": True},
            {"name": "Take Profit", "value": f"{data['tp']} ({tp_pips:.1f} {unit_label})", "inline": True},
            {"name": "Suggested Size", "value": f"{position_info['lots']:.2f} lots", "inline": True},
            {"name": "Risk Amount", "value": f"${position_info['risk_amount']:.2f}", "inline": True},
        ]
        if data.get("zone_id") is not None:
            fields.append({"name": "Zone ID", "value": str(data["zone_id"]), "inline": True})
        if data.get("zone_type"):
            zone_emoji = "🟢" if data["zone_type"] == "demand" else "🔴"
            fields.append({"name": "Zone Type", "value": f"{zone_emoji} {data['zone_type'].upper()}", "inline": True})

        # AI Guardian analysis (if present)
        if data.get("ai_decision"):
            ai_emoji = "🤖✅" if data["ai_decision"] == "APPROVE" else "🤖⚠️"
            ai_confidence = data.get("ai_confidence", "N/A")
            fields.append({"name": "AI Guardian", "value": f"{ai_emoji} {data['ai_decision']} ({ai_confidence}%)", "inline": True})
        if data.get("ai_reasoning"):
            # Truncate reasoning for Discord embed field limit
            reasoning = data["ai_reasoning"][:200] + "..." if len(data.get("ai_reasoning", "")) > 200 else data["ai_reasoning"]
            fields.append({"name": "AI Analysis", "value": reasoning, "inline": False})

        embed = {
            "title": f"{mode_prefix}{emoji} New {side} Signal - #{alert_id}",
            "description": f"**{'Auto-executed (paper)' if mode == 'paper' else 'Execute manually'}** | Reply with outcome later",
            "color": color,
            "timestamp": datetime.utcnow().isoformat(),
            "fields": fields,
            "footer": {"text": f"Alert #{alert_id} | Update: /alert/{alert_id}/taken or /skipped"},
        }
        payload = {"content": f"@here **New Trade Signal #{alert_id}!**", "embeds": [embed]}
        r = requests.post(s.discord_webhook_url, json=payload, timeout=10)
        if r.status_code == 204:
            logger.info(f"Discord alert sent: #{alert_id} {data['symbol']} {side}")
            return True, None
        return False, f"HTTP {r.status_code}: {r.text[:200] if r.text else 'No response'}"
    except Exception as e:
        logger.error(f"Discord error: {e}")
        return False, str(e)


def send_telegram(data: Dict[str, Any], alert_id: int) -> bool:
    s = get_settings()
    if not s.telegram_bot_token or not s.telegram_chat_id:
        return False
    try:
        side = str(data["side"]).upper()
        emoji = "📈" if side == "BUY" else "📉"
        entry = float(data["entry"])
        sl = float(data["sl"])
        tp = float(data["tp"])
        risk = abs(entry - sl)
        reward = abs(tp - entry)
        rr_ratio = reward / risk if risk > 0 else 0
        symbol = str(data["symbol"]).upper()
        pip_divisor = get_pip_divisor(symbol)
        sl_pips = abs(entry - sl) / pip_divisor
        tp_pips = abs(tp - entry) / pip_divisor
        pos = calculate_position_size(sl_pips, symbol)
        # Build base text
        text = (
            f"{emoji} <b>NEW {side} SIGNAL #{alert_id}</b>\n\n"
            f"<b>Symbol:</b> {data['symbol']}\n<b>Entry:</b> {data['entry']}\n"
            f"<b>Stop Loss:</b> {data['sl']} ({sl_pips:.1f} pips)\n<b>Take Profit:</b> {data['tp']} ({tp_pips:.1f} pips)\n"
            f"<b>R:R:</b> 1:{rr_ratio:.2f}\n\n<b>Suggested Size:</b> {pos['lots']:.2f} lots\n<b>Risk:</b> ${pos['risk_amount']:.2f}"
        )

        # Add AI Guardian analysis if present
        if data.get("ai_decision"):
            ai_emoji = "🤖✅" if data["ai_decision"] == "APPROVE" else "🤖⚠️"
            ai_confidence = data.get("ai_confidence", "N/A")
            text += f"\n\n<b>AI Guardian:</b> {ai_emoji} {data['ai_decision']} ({ai_confidence}%)"
        if data.get("ai_reasoning"):
            reasoning = data["ai_reasoning"][:150] + "..." if len(data.get("ai_reasoning", "")) > 150 else data["ai_reasoning"]
            text += f"\n<i>{reasoning}</i>"

        text += "\n\nExecute manually, then update status."
        r = requests.post(
            f"https://api.telegram.org/bot{s.telegram_bot_token}/sendMessage",
            json={"chat_id": s.telegram_chat_id, "text": text, "parse_mode": "HTML"},
            timeout=10,
        )
        if r.status_code == 200:
            logger.info(f"Telegram alert sent: #{alert_id}")
            return True
        logger.error(f"Telegram failed: {r.text}")
        return False
    except Exception as e:
        logger.error(f"Telegram error: {e}")
        return False


def should_forward_alert(data: Dict[str, Any]) -> Tuple[bool, List[str], Dict[str, Any]]:
    """Returns (should_forward, reasons, debug_meta). No news/AI/swap for minimal version."""
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
    """
    Execute one trade payload: save to Supabase, filter or notify, optional paper position.
    Handles both entry and exit events. Called by worker only.
    When dry_run=True: save alert + Discord/Telegram only; no paper/live order.
    """
    db = _get_supabase_db()

    # Exit event: update Supabase and return
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
        logger.info(f"Exit recorded: zone_id={data['zone_id']}, outcome={data['outcome']}")
        return

    # Entry: validate
    symbol = str(data.get("symbol", "")).upper()
    should_forward, filter_reasons, _ = should_forward_alert(data)
    s = get_settings()
    mode = "manual"
    if s.paper_trading_enabled and s.paper_auto_execute:
        paper_symbols = [x.strip() for x in s.paper_symbols.split(",") if x.strip()]
        if not paper_symbols or symbol in paper_symbols:
            pt = _get_paper_trader()
            if len(pt.get_open_positions()) < s.paper_max_positions:
                mode = "paper"

    alert_id = db.save_alert(data, mode=mode, filter_reasons=filter_reasons if not should_forward else None)

    if not should_forward:
        reason_str = "; ".join(filter_reasons)
        db.update_alert_status(alert_id, "filtered", notes=reason_str)
        logger.info(f"Alert #{alert_id} filtered: {reason_str}")
        return

    if mode == "paper" and not dry_run:
        pt = _get_paper_trader()
        entry = float(data["entry"])
        sl = float(data["sl"])
        tp = float(data["tp"])
        size = float(data.get("size", 0.01))
        risk = abs(entry - sl)
        reward = abs(tp - entry)
        rr_ratio = reward / risk if risk > 0 else 0
        pt.open_position(alert_id, symbol, str(data["side"]).lower(), entry, sl, tp, size, rr_ratio)
        logger.info(f"Paper position #{alert_id} opened")
    elif dry_run:
        logger.info(f"DRY_RUN: Alert #{alert_id} saved, no order placed (LIVE_TRADING=false)")

    send_discord(data, alert_id, mode=mode)
    send_telegram(data, alert_id)


# Backward-compatible alias
execute_trade = process_trade
