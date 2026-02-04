"""Discord and Telegram alert adapter."""

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

import requests

from config import get_settings

logger = logging.getLogger(__name__)


def get_pip_divisor(symbol: str) -> float:
    s = get_settings()
    symbol = symbol.upper()
    index_patterns = ["NAS", "US100", "NDX", "SPX", "US500", "DJI", "US30", "DAX", "FTSE", "NIK"]
    if any(p in symbol for p in index_patterns):
        return 1.0
    if "JPY" in symbol:
        return 0.01
    if "XAU" in symbol or "GOLD" in symbol:
        return s.gold_pip_divisor
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


def send_discord(
    data: Dict[str, Any],
    alert_id: int,
    mode: str = "manual",
    ai_result: Optional[Dict[str, Any]] = None,
) -> Tuple[bool, Optional[str]]:
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
        # For indices (pts): also show TradingView-style pips (1 pip = 0.01 pt) so Discord matches TV
        is_index = pip_divisor == 1.0
        sl_display = f"{data['sl']} ({sl_pips:.1f} pts, {round(sl_pips * 100):.0f} pips)" if is_index else f"{data['sl']} ({sl_pips:.1f} {unit_label})"
        tp_display = f"{data['tp']} ({tp_pips:.1f} pts, {round(tp_pips * 100):.0f} pips)" if is_index else f"{data['tp']} ({tp_pips:.1f} {unit_label})"
        position_info = calculate_position_size(sl_pips, symbol)
        fields = [
            {"name": "Symbol", "value": f"**{data['symbol']}**", "inline": True},
            {"name": "Type", "value": side, "inline": True},
            {"name": "R:R", "value": f"1:{rr_ratio:.2f}", "inline": True},
            {"name": "Entry", "value": str(data["entry"]), "inline": True},
            {"name": "Stop Loss", "value": sl_display, "inline": True},
            {"name": "Take Profit", "value": tp_display, "inline": True},
            {"name": "Suggested Size", "value": f"{position_info['lots']:.2f} lots", "inline": True},
            {"name": "Risk Amount", "value": f"${position_info['risk_amount']:.2f}", "inline": True},
        ]
        if data.get("zone_id") is not None:
            fields.append({"name": "Zone ID", "value": str(data["zone_id"]), "inline": True})
        if data.get("zone_type"):
            zone_emoji = "🟢" if data["zone_type"] == "demand" else "🔴"
            fields.append({"name": "Zone Type", "value": f"{zone_emoji} {data['zone_type'].upper()}", "inline": True})

        # Optional: legacy inline AI flags on the card (still supported)
        if data.get("ai_decision"):
            ai_emoji = "🤖✅" if str(data["ai_decision"]).upper() == "GO" else "🤖⚠️"
            ai_confidence = data.get("ai_confidence", "N/A")
            fields.append(
                {
                    "name": "AI Gate",
                    "value": f"{ai_emoji} {data['ai_decision']} ({ai_confidence}%)",
                    "inline": True,
                }
            )

        # New: rich AI Brain analysis section when ai_result is provided
        if ai_result:
            decision = str(ai_result.get("decision", "NO_GO")).upper()
            try:
                rf_prob = float(ai_result.get("rf_prob", 0.0)) * 100.0
            except Exception:
                rf_prob = 0.0
            reason = str(ai_result.get("reason", "") or "N/A").strip()
            rules = ai_result.get("rules") or []
            rule_count = len(rules)
            top_snippet = ""
            if rules:
                top_snippet = str(rules[0]).replace("\n", " ")
                if len(top_snippet) > 200:
                    top_snippet = top_snippet[:197].rstrip() + "..."

            ai_lines = [
                f"**Decision:** {decision} (Shadow Mode)",
                f"**Confidence:** {rf_prob:.1f}%",
                f"**Reason:** {reason}",
                f"**RAG Wisdom:** {rule_count} rules found."
                + (f' Top advice: \"{top_snippet}\"' if top_snippet else ""),
            ]
            fields.append(
                {
                    "name": "🧠 AI Analysis",
                    "value": "\n".join(ai_lines),
                    "inline": False,
                }
            )

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
        text = (
            f"{emoji} <b>NEW {side} SIGNAL #{alert_id}</b>\n\n"
            f"<b>Symbol:</b> {data['symbol']}\n<b>Entry:</b> {data['entry']}\n"
            f"<b>Stop Loss:</b> {data['sl']} ({sl_pips:.1f} pips)\n<b>Take Profit:</b> {data['tp']} ({tp_pips:.1f} pips)\n"
            f"<b>R:R:</b> 1:{rr_ratio:.2f}\n\n<b>Suggested Size:</b> {pos['lots']:.2f} lots\n<b>Risk:</b> ${pos['risk_amount']:.2f}"
        )
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
