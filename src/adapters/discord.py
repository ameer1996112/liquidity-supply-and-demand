"""Discord and Telegram alert adapter."""

import logging
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

import requests

from config import get_settings

logger = logging.getLogger(__name__)

# ═══════════════════════════════════════════════════════════════════════════
# Phase 1 Latency Optimization: Background notification executor
# Sends Discord/Telegram alerts in background threads to avoid blocking execution
# ═══════════════════════════════════════════════════════════════════════════
_notification_executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="NotificationAsync")


_CURRENCY_FLAG_MAP: dict[str, str] = {
    "EUR": "eu", "GBP": "gb", "USD": "us", "JPY": "jp",
    "CAD": "ca", "AUD": "au", "NZD": "nz", "CHF": "ch",
    "NAS": "us", "SPX": "us", "DJI": "us", "US3": "us",
}


def _get_symbol_thumbnail_url(symbol: str, image_url: Optional[str] = None) -> Optional[str]:
    """Return thumbnail URL: chart screenshot → currency flag → None."""
    if image_url:
        return image_url
    symbol = symbol.upper()
    for prefix, code in _CURRENCY_FLAG_MAP.items():
        if symbol.startswith(prefix):
            return f"https://flagcdn.com/w80/{code}.png"
    return None


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
) -> Tuple[bool, Optional[str], Optional[str], Optional[str]]:
    """Send a trade signal embed to Discord.

    Returns (success, error, message_id, channel_id).
    message_id and channel_id are populated when DISCORD_BOT_TOKEN is set
    (requires ?wait=true which returns the full message object).
    """
    s = get_settings()
    if not s.discord_webhook_url:
        return False, "DISCORD_WEBHOOK_URL not configured"
    try:
        side = str(data.get("side", "")).upper()
        emoji = "📈" if side == "BUY" else "📉"
        color = 0x3498DB if mode == "paper" else (0x00FF00 if side == "BUY" else 0xFF0000)
        mode_prefix = "🔵 PAPER | " if mode == "paper" else ""
        entry = float(data.get("entry") or 0)
        sl = float(data.get("sl") or 0)
        tp = float(data.get("tp") or 0)
        risk = abs(entry - sl)
        reward = abs(tp - entry)
        rr_ratio = reward / risk if risk > 0 else 0
        symbol = str(data.get("symbol", "")).upper()
        pip_divisor = get_pip_divisor(symbol)
        unit_label = "pts" if pip_divisor == 1.0 else "pips"
        sl_pips = abs(entry - sl) / pip_divisor if pip_divisor else 0
        tp_pips = abs(tp - entry) / pip_divisor if pip_divisor else 0
        # For indices (pts): also show TradingView-style pips (1 pip = 0.01 pt) so Discord matches TV
        is_index = pip_divisor == 1.0
        sl_display = f"{sl} ({sl_pips:.1f} pts, {round(sl_pips * 100):.0f} pips)" if is_index else f"{sl} ({sl_pips:.1f} {unit_label})"
        tp_display = f"{tp} ({tp_pips:.1f} pts, {round(tp_pips * 100):.0f} pips)" if is_index else f"{tp} ({tp_pips:.1f} {unit_label})"
        position_info = calculate_position_size(sl_pips, symbol)
        fields = [
            {"name": "Symbol", "value": f"**{symbol}**", "inline": True},
            {"name": "Type", "value": side, "inline": True},
            {"name": "R:R", "value": f"1:{rr_ratio:.2f}", "inline": True},
            {"name": "Entry", "value": str(entry), "inline": True},
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

        # New: rich AI Brain analysis section.
        # If the worker didn't pass ai_result explicitly, fall back to
        # any structured reasoning payload attached to the data.
        if ai_result is None:
            ai_result = data.get("ai_reasoning")

        if ai_result:
            decision = str(ai_result.get("decision", "NO_GO")).upper()
            try:
                rf_prob = float(ai_result.get("rf_prob", 0.0)) * 100.0
            except Exception:
                rf_prob = 0.0
            reason = str(ai_result.get("reason", "") or "N/A").strip()
            rules = ai_result.get("rules") or []
            rule_count = len(rules)

            # Build a multi-line summary of the top few rules so you can
            # see the full reasoning, not just a single truncated line.
            wisdom_lines: List[str] = []
            for idx, rule in enumerate(rules[:5], start=1):
                snippet = str(rule).strip().replace("\n", " ")
                # Keep each bullet under control for Discord's field limits
                if len(snippet) > 300:
                    snippet = snippet[:297].rstrip() + "..."
                wisdom_lines.append(f"{idx}. {snippet}")

            wisdom_body = "No matching rules." if not wisdom_lines else "\n".join(wisdom_lines)

            ai_lines = [
                f"**Decision:** {decision} (Shadow Mode)",
                f"**Confidence:** {rf_prob:.1f}%",
                f"**Reason:** {reason}",
                f"**RAG Wisdom:** {rule_count} rules found:",
                wisdom_body,
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
        # Use ?wait=true to get the message object back (needed for thread creation)
        url = s.discord_webhook_url.rstrip("?&") + "?wait=true"
        r = requests.post(url, json=payload, timeout=10)
        if r.status_code == 200:
            msg = r.json()
            message_id = str(msg.get("id", ""))
            channel_id = str(msg.get("channel_id", ""))
            logger.info(f"Discord alert sent: #{alert_id} {data['symbol']} {side} msg={message_id}")
            return True, None, message_id or None, channel_id or None
        # Fallback: some proxies/older setups return 204 without wait
        if r.status_code == 204:
            logger.info(f"Discord alert sent: #{alert_id} {data['symbol']} {side}")
            return True, None, None, None
        return False, f"HTTP {r.status_code}: {r.text[:200] if r.text else 'No response'}", None, None
    except Exception as e:
        logger.error(f"Discord error: {e}")
        return False, str(e), None, None


def send_telegram(data: Dict[str, Any], alert_id: int) -> Tuple[bool, Optional[int]]:
    """Send a trade signal to Telegram. Returns (success, message_id)."""
    s = get_settings()
    if not s.telegram_bot_token or not s.telegram_chat_id:
        return False, None
    try:
        side = str(data.get("side", "")).upper()
        emoji = "📈" if side == "BUY" else "📉"
        entry = float(data.get("entry") or 0)
        sl = float(data.get("sl") or 0)
        tp = float(data.get("tp") or 0)
        risk = abs(entry - sl)
        reward = abs(tp - entry)
        rr_ratio = reward / risk if risk > 0 else 0
        symbol = str(data.get("symbol", "")).upper()
        pip_divisor = get_pip_divisor(symbol)
        sl_pips = abs(entry - sl) / pip_divisor if pip_divisor else 0
        tp_pips = abs(tp - entry) / pip_divisor if pip_divisor else 0
        pos = calculate_position_size(sl_pips, symbol)
        text = (
            f"{emoji} <b>NEW {side} SIGNAL #{alert_id}</b>\n\n"
            f"<b>Symbol:</b> {symbol}\n<b>Entry:</b> {entry}\n"
            f"<b>Stop Loss:</b> {sl} ({sl_pips:.1f} pips)\n<b>Take Profit:</b> {tp} ({tp_pips:.1f} pips)\n"
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
            msg_id = r.json().get("result", {}).get("message_id")
            logger.info(f"Telegram alert sent: #{alert_id} msg_id={msg_id}")
            return True, msg_id
        logger.error(f"Telegram failed: {r.text}")
        return False, None
    except Exception as e:
        logger.error(f"Telegram error: {e}")
        return False, None


# ═══════════════════════════════════════════════════════════════════════════
# Guard / Watchdog Notifications
# Lightweight Discord embeds that do NOT require trade fields (sl, tp, entry).
# Use these for late-fill alerts, circuit-breaker notices, etc.
# ═══════════════════════════════════════════════════════════════════════════

def send_guard_notification(signal_id: Any, symbol: str, reason: str) -> Tuple[bool, Optional[str]]:
    """Send a lightweight Discord embed for guard/watchdog events (no trade fields needed)."""
    s = get_settings()
    # Prefer dedicated alerts channel; fall back to main webhook
    webhook_url = (
        getattr(s, "discord_alerts_webhook_url", "")
        or s.discord_webhook_url
    )
    if not webhook_url:
        return False, "DISCORD_WEBHOOK_URL not configured"
    try:
        embed = {
            "title": f"⚠️ Guard Alert — {symbol} (#{signal_id})",
            "description": reason,
            "color": 0xFFA500,  # orange
            "timestamp": datetime.utcnow().isoformat(),
            "footer": {"text": f"Signal #{signal_id}"},
        }
        payload = {"embeds": [embed]}
        r = requests.post(webhook_url, json=payload, timeout=10)
        if r.status_code in (200, 204):
            return True, None
        # 404 = webhook deleted/invalid — tag the error so async wrapper can downgrade log level
        if r.status_code == 404:
            return False, f"WEBHOOK_NOT_FOUND: {r.text[:100] if r.text else 'no body'}"
        return False, f"HTTP {r.status_code}: {r.text[:200] if r.text else 'No response'}"
    except Exception as e:
        logger.error(f"Discord guard notification error: {e}")
        return False, str(e)


def send_guard_notification_async(signal_id: Any, symbol: str, reason: str) -> None:
    """Non-blocking version of send_guard_notification."""
    s = get_settings()
    if not getattr(s, "async_notifications", False):
        send_guard_notification(signal_id, symbol, reason)
        return

    def _send():
        try:
            success, error = send_guard_notification(signal_id, symbol, reason)
            if not success:
                # Downgrade 404 (stale webhook) from WARNING to DEBUG — it's a config
                # issue, not a runtime crash, and fires on every watchdog cycle otherwise.
                if error and error.startswith("WEBHOOK_NOT_FOUND"):
                    logger.debug(
                        "Background Discord guard skipped: webhook URL is invalid/deleted. "
                        "Update DISCORD_WEBHOOK_URL in .env. (%s)", error
                    )
                else:
                    logger.warning(f"Background Discord guard notification failed: {error}")
        except Exception as e:
            logger.error(f"Background Discord guard notification crashed: {e}")

    _notification_executor.submit(_send)


def send_bug_alert(title: str, description: str, jira_key: Optional[str] = None) -> Tuple[bool, Optional[str]]:
    """Send a high-priority bug alert embed to Discord."""
    s = get_settings()
    webhook_url = (
        getattr(s, "discord_alerts_webhook_url", "")
        or s.discord_webhook_url
    )
    if not webhook_url:
        return False, "DISCORD_WEBHOOK_URL not configured"
    try:
        embed_title = f"🚨 SYSTEM EXCEPTION — {jira_key}" if jira_key else f"🚨 SYSTEM EXCEPTION — {title}"
        safe_desc = description[:4000] + "\n...[truncated]" if len(description) > 4000 else description

        embed = {
            "title": embed_title,
            "description": f"```python\n{safe_desc}\n```",
            "color": 0xFF0000,
            "timestamp": datetime.utcnow().isoformat(),
            "footer": {"text": "Autonomous Error-to-Ticket Pipeline"},
        }
        payload = {"embeds": [embed]}
        r = requests.post(webhook_url, json=payload, timeout=10)
        if r.status_code in (200, 204):
            return True, None
        return False, f"HTTP {r.status_code}: {r.text[:200] if r.text else 'No response'}"
    except Exception as e:
        logger.error(f"Discord bug alert error: {e}")
        return False, str(e)


def send_bug_alert_async(title: str, description: str, jira_key: Optional[str] = None) -> None:
    """Non-blocking version of send_bug_alert."""
    s = get_settings()
    if not getattr(s, "async_notifications", False):
        send_bug_alert(title, description, jira_key)
        return

    def _send():
        try:
            success, error = send_bug_alert(title, description, jira_key)
            if not success:
                logger.warning(f"Background Discord bug alert failed: {error}")
        except Exception as e:
            logger.error(f"Background Discord bug alert crashed: {e}")

    _notification_executor.submit(_send)


# ═══════════════════════════════════════════════════════════════════════════
# Async Notification Wrappers (Phase 1 Latency Optimization)
# These functions submit notifications to background threads to avoid blocking
# the critical execution path. Use these in worker.py instead of sync versions.
# ═══════════════════════════════════════════════════════════════════════════

def send_discord_async(
    data: Dict[str, Any],
    alert_id: int,
    mode: str = "manual",
    ai_result: Optional[Dict[str, Any]] = None,
) -> None:
    """
    Send Discord notification in background thread (non-blocking).

    Returns immediately without waiting for HTTP response.
    Logs errors in background if notification fails.
    """
    s = get_settings()
    if not getattr(s, "async_notifications", False):
        # Async notifications disabled - use synchronous version
        send_discord(data, alert_id, mode, ai_result)
        return

    def _send():
        try:
            success, error, _, __ = send_discord(data, alert_id, mode, ai_result)
            if not success:
                logger.warning(f"Background Discord notification failed: {error}")
        except Exception as e:
            logger.error(f"Background Discord notification crashed: {e}")

    _notification_executor.submit(_send)
    logger.debug(f"Discord notification queued in background for alert #{alert_id}")


def send_telegram_async(data: Dict[str, Any], alert_id: int) -> None:
    """
    Send Telegram notification in background thread (non-blocking).

    Returns immediately without waiting for HTTP response.
    Logs errors in background if notification fails.
    """
    s = get_settings()
    if not getattr(s, "async_notifications", False):
        # Async notifications disabled - use synchronous version
        send_telegram(data, alert_id)
        return

    def _send():
        try:
            success, _ = send_telegram(data, alert_id)
            if not success:
                logger.warning(f"Background Telegram notification failed for alert #{alert_id}")
        except Exception as e:
            logger.error(f"Background Telegram notification crashed: {e}")

    _notification_executor.submit(_send)
    logger.debug(f"Telegram notification queued in background for alert #{alert_id}")


# ═══════════════════════════════════════════════════════════════════════════
# Discord Thread-per-Trade
# Requires DISCORD_BOT_TOKEN. Each signal gets its own thread for fill +
# close updates. Falls back silently if bot token is not configured.
# ═══════════════════════════════════════════════════════════════════════════

def create_discord_thread(channel_id: str, message_id: str, thread_name: str) -> Optional[str]:
    """Create a Discord thread from a message using the Bot API. Returns thread_id or None."""
    s = get_settings()
    bot_token = (getattr(s, "discord_bot_token", "") or "").strip()
    if not bot_token:
        return None
    try:
        r = requests.post(
            f"https://discord.com/api/v10/channels/{channel_id}/messages/{message_id}/threads",
            headers={
                "Authorization": f"Bot {bot_token}",
                "Content-Type": "application/json",
            },
            json={"name": thread_name[:100], "auto_archive_duration": 10080},  # 7 days
            timeout=10,
        )
        if r.status_code == 201:
            thread_id = str(r.json().get("id", ""))
            logger.info(f"Discord thread created: {thread_id} for message {message_id}")
            return thread_id or None
        logger.warning(f"create_discord_thread HTTP {r.status_code}: {r.text[:200]}")
        return None
    except Exception as exc:
        logger.warning(f"create_discord_thread failed: {exc}")
        return None


def post_to_discord_thread(thread_id: str, embed: Dict[str, Any]) -> bool:
    """Post an embed to an existing Discord thread via webhook + thread_id param."""
    s = get_settings()
    webhook_url = (s.discord_webhook_url or "").strip()
    if not webhook_url or not thread_id:
        return False
    try:
        url = f"{webhook_url.rstrip('?&')}?wait=true&thread_id={thread_id}"
        r = requests.post(url, json={"embeds": [embed]}, timeout=10)
        return r.status_code in (200, 204)
    except Exception as exc:
        logger.warning(f"post_to_discord_thread failed: {exc}")
        return False


def post_close_to_thread_async(
    thread_id: str,
    symbol: str,
    side: str,
    pnl_usd: Optional[float],
    outcome: str,
    entry_price: Optional[float] = None,
    close_price: Optional[float] = None,
) -> None:
    """Post a trade close summary to an existing Discord thread (non-blocking)."""
    def _post():
        try:
            pnl = pnl_usd or 0.0
            outcome_upper = (outcome or "").upper()
            if outcome_upper == "WIN" or pnl > 0:
                color = 0x22C55E   # green
                icon = "🟢"
            elif outcome_upper == "LOSS" or pnl < 0:
                color = 0xEF4444   # red
                icon = "🔴"
            else:
                color = 0x94A3B8   # slate (breakeven)
                icon = "⚪"

            pnl_str = f"+${pnl:.2f}" if pnl >= 0 else f"-${abs(pnl):.2f}"
            fields: List[Dict[str, Any]] = [
                {"name": "Outcome", "value": outcome_upper or "CLOSED", "inline": True},
                {"name": "PnL", "value": pnl_str, "inline": True},
            ]
            if entry_price is not None:
                fields.append({"name": "Entry", "value": str(entry_price), "inline": True})
            if close_price is not None:
                fields.append({"name": "Exit", "value": str(close_price), "inline": True})

            embed = {
                "title": f"{icon} Trade Closed — {symbol.upper()} {side.upper()}",
                "color": color,
                "fields": fields,
                "timestamp": datetime.utcnow().isoformat(),
            }
            post_to_discord_thread(thread_id, embed)
        except Exception as exc:
            logger.warning(f"post_close_to_thread_async failed: {exc}")

    _notification_executor.submit(_post)


def send_discord_and_thread_async(
    data: Dict[str, Any],
    alert_id: int,
    mode: str = "manual",
    ai_result: Optional[Dict[str, Any]] = None,
    supabase_client: Any = None,
) -> None:
    """Send signal embed + create Discord thread, store IDs to DB (non-blocking).

    Drop-in replacement for send_discord_async in the main signal path.
    If DISCORD_BOT_TOKEN is not configured, behaves identically to send_discord_async.
    """
    def _send():
        try:
            success, error, message_id, channel_id = send_discord(data, alert_id, mode, ai_result)
            if not success:
                logger.warning(f"Background Discord notification failed: {error}")
                return

            if not message_id or not channel_id:
                return  # No IDs returned (204 path or bot token not needed)

            # Persist message_id
            if supabase_client:
                try:
                    supabase_client.table("trading_signals").update(
                        {"discord_message_id": message_id}
                    ).eq("id", alert_id).execute()
                except Exception as db_exc:
                    logger.warning(f"Could not store discord_message_id: {db_exc}")

            # Create thread if bot token configured
            thread_name = f"{data.get('symbol', '').upper()} {str(data.get('side', '')).upper()} #{alert_id}"
            thread_id = create_discord_thread(channel_id, message_id, thread_name)
            if not thread_id:
                return

            # Persist thread_id
            if supabase_client:
                try:
                    supabase_client.table("trading_signals").update(
                        {"discord_thread_id": thread_id}
                    ).eq("id", alert_id).execute()
                except Exception as db_exc:
                    logger.warning(f"Could not store discord_thread_id: {db_exc}")

            # If trade was already filled by the time we post (common in auto-execute flow),
            # post a fill confirmation inside the thread immediately.
            if supabase_client:
                try:
                    rec = supabase_client.table("trading_signals").select(
                        "status, broker_order_id, filled_entry_price"
                    ).eq("id", alert_id).maybe_single().execute()
                    if rec and rec.data:
                        status = str(rec.data.get("status", "")).upper()
                        if status == "OPEN":
                            broker_id = rec.data.get("broker_order_id", "")
                            entry = rec.data.get("filled_entry_price") or data.get("entry")
                            fill_embed = {
                                "title": "✅ Order Filled",
                                "description": f"Broker ticket: `{broker_id}`",
                                "color": 0x22C55E,
                                "fields": [
                                    {"name": "Entry", "value": str(entry or ""), "inline": True},
                                ],
                                "timestamp": datetime.utcnow().isoformat(),
                            }
                            post_to_discord_thread(thread_id, fill_embed)
                except Exception as fill_exc:
                    logger.debug(f"Discord fill thread update skipped: {fill_exc}")

        except Exception as e:
            logger.error(f"Background Discord+thread notification crashed: {e}")

    _notification_executor.submit(_send)
    logger.debug(f"Discord+thread notification queued in background for alert #{alert_id}")


# ═══════════════════════════════════════════════════════════════════════════
# Telegram Reply-per-Trade
# Stores the original signal message_id so fill/close updates are posted
# as replies, keeping each trade's history in one conversation thread.
# ═══════════════════════════════════════════════════════════════════════════

def post_telegram_close_reply_async(
    telegram_message_id: int,
    symbol: str,
    side: str,
    pnl_usd: Optional[float],
    outcome: str,
    entry_price: Optional[float] = None,
    close_price: Optional[float] = None,
) -> None:
    """Reply to the original Telegram signal message with a close summary (non-blocking)."""
    def _post():
        s = get_settings()
        if not s.telegram_bot_token or not s.telegram_chat_id:
            return
        try:
            pnl = pnl_usd or 0.0
            outcome_upper = (outcome or "").upper()
            if outcome_upper == "WIN" or pnl > 0:
                icon = "🟢"
                pnl_str = f"+${pnl:.2f}"
            elif outcome_upper == "LOSS" or pnl < 0:
                icon = "🔴"
                pnl_str = f"-${abs(pnl):.2f}"
            else:
                icon = "⚪"
                pnl_str = f"${pnl:.2f}"

            lines = [
                f"{icon} <b>Trade Closed — {symbol.upper()} {side.upper()}</b>",
                f"<b>Outcome:</b> {outcome_upper or 'CLOSED'}",
                f"<b>PnL:</b> {pnl_str}",
            ]
            if entry_price is not None:
                lines.append(f"<b>Entry:</b> {entry_price}")
            if close_price is not None:
                lines.append(f"<b>Exit:</b> {close_price}")

            requests.post(
                f"https://api.telegram.org/bot{s.telegram_bot_token}/sendMessage",
                json={
                    "chat_id": s.telegram_chat_id,
                    "text": "\n".join(lines),
                    "parse_mode": "HTML",
                    "reply_to_message_id": telegram_message_id,
                },
                timeout=10,
            )
        except Exception as exc:
            logger.warning(f"post_telegram_close_reply_async failed: {exc}")

    _notification_executor.submit(_post)


def send_telegram_and_store_async(
    data: Dict[str, Any],
    alert_id: int,
    supabase_client: Any = None,
) -> None:
    """Send Telegram signal and store message_id to DB for later reply threading (non-blocking)."""
    def _send():
        try:
            success, msg_id = send_telegram(data, alert_id)
            if not success or not msg_id:
                return
            if supabase_client:
                try:
                    supabase_client.table("trading_signals").update(
                        {"telegram_message_id": msg_id}
                    ).eq("id", alert_id).execute()
                except Exception as db_exc:
                    logger.warning(f"Could not store telegram_message_id: {db_exc}")
        except Exception as e:
            logger.error(f"Background Telegram+store notification crashed: {e}")

    _notification_executor.submit(_send)
    logger.debug(f"Telegram+store notification queued in background for alert #{alert_id}")


# ═══════════════════════════════════════════════════════════════════════════
# NotificationPayload dispatch — DEV-73
# Renders NotificationPayload to Discord embed or Telegram HTML and dispatches.
# ═══════════════════════════════════════════════════════════════════════════

from src.services.notification_service import NotificationPayload, COLOR_MAP, _format_ai_analysis  # noqa: E402


def _section_to_embed_field(section: dict[str, Any]) -> dict[str, Any]:
    body = "\n".join(f"**{key}:** {value}" for key, value in section["fields"].items())
    return {
        "name": section["name"],
        "value": body,
        "inline": section["name"] in {"Trade", "Risk", "Context", "Summary"},
    }


def _setup_evidence_field(summary: Optional[dict[str, Any]]) -> Optional[dict[str, Any]]:
    if not summary:
        return None

    screenshot_state = "attached" if summary.get("has_image") else "not attached"
    lines = [
        str(summary.get("status_label") or "Setup Evidence"),
        f"Zone: {summary.get('focus_zone_label') or 'No focus zone detected'}",
        f"Screenshot: {screenshot_state}",
    ]
    if summary.get("reason"):
        lines.append(f"Note: {summary['reason']}")

    return {
        "name": "Setup Evidence",
        "value": "\n".join(lines),
        "inline": False,
    }


def _payload_to_discord_embed(payload: NotificationPayload) -> dict:
    """Render a NotificationPayload as a premium Discord embed dict."""
    color = COLOR_MAP.get(payload.color, 0x3B82F6)

    sections = payload.sections or [{"name": "Summary", "fields": payload.fields}]
    fields = [_section_to_embed_field(section) for section in sections]
    setup_field = _setup_evidence_field((payload.metadata or {}).get("setup_evidence_summary"))
    if setup_field:
        fields.append(setup_field)

    embed: dict = {
        "title": payload.title,
        "color": color,
        "timestamp": datetime.utcnow().isoformat(),
        "fields": fields,
    }

    author_name = payload.account_badge
    if (not author_name or author_name == "ACC: Unknown Account") and payload.account_name:
        author_name = f"ACC: {payload.account_name}"
    embed["author"] = {"name": author_name or "ACC: Unknown Account"}

    # Thumbnail (top-right small): currency flag when no chart; omit if chart present
    # Full-width image (bottom): chart screenshot when image_url set
    symbol = (payload.metadata or {}).get("symbol", "")
    if payload.image_url:
        embed["image"] = {"url": payload.image_url}
    else:
        flag_url = _get_symbol_thumbnail_url(symbol)
        if flag_url:
            embed["thumbnail"] = {"url": flag_url}

    description_parts = []
    if payload.status_line:
        description_parts.append(payload.status_line)
    if payload.description:
        description_parts.append(payload.description)
    if description_parts:
        embed["description"] = "\n".join(description_parts)
    if payload.footer:
        embed["footer"] = {"text": payload.footer}

    return embed


def _payload_to_telegram_html(payload: NotificationPayload) -> str:
    """Render a NotificationPayload as a premium Telegram HTML string."""
    
    def clean(val: str) -> str:
        return str(val).replace("**", "")

    title = clean(payload.title)
    if "GUILD" in title.upper() or "ALERT" in title.upper():
        header_emoji = "⚠️"
    elif "BUY" in title.upper() or "WIN" in title.upper():
        header_emoji = "🟢"
    elif "SELL" in title.upper() or "LOSS" in title.upper():
        header_emoji = "🔴"
    else:
        header_emoji = "🚨"

    lines = [
        f"<b>{clean(payload.account_badge or 'ACC: Unknown Account')}</b>",
        f"{header_emoji} <b>{title.upper()}</b>",
    ]
    if payload.status_line:
        lines.append(f"<i>{clean(payload.status_line)}</i>")
    if payload.description:
        lines.append(clean(payload.description))

    lines.append("")

    sections = payload.sections or [{"name": "Summary", "fields": payload.fields}]
    for section in sections:
        lines.append(f"<b>{clean(section['name'])}</b>")
        section_lines = [
            f"<b>{clean(key)}:</b> <code>{clean(value)}</code>"
            for key, value in section["fields"].items()
        ]
        lines.append("<blockquote>" + "\n".join(section_lines) + "</blockquote>")
        lines.append("")

    if payload.footer:
        lines.append(f"\n<i>{clean(payload.footer)}</i>")

    return "\n".join(lines)


def _payload_to_telegram_setup_caption(payload: NotificationPayload) -> str:
    summary = (payload.metadata or {}).get("setup_evidence_summary") or {}
    lines = ["Setup Evidence"]

    focus_zone_label = summary.get("focus_zone_label")
    if focus_zone_label:
        lines.append(str(focus_zone_label))

    status_label = summary.get("status_label")
    if status_label:
        lines.append(str(status_label))

    reason = summary.get("reason")
    if reason:
        lines.append(str(reason))

    return "\n".join(lines)


def dispatch_payload(
    payload: NotificationPayload,
    supabase_client=None,
    notification_service=None,
) -> None:
    """
    Dispatch a NotificationPayload to Discord and/or Telegram.
    Respects notification_routing table via notification_service.
    Runs synchronously — wrap in _notification_executor.submit() for async.
    """
    s = get_settings()

    # Check routing
    routing = {"discord_enabled": True, "telegram_enabled": True, "discord_channel": "signals"}
    if notification_service:
        try:
            routing = notification_service.get_routing(payload.type)
        except Exception:
            pass

    # Discord
    if routing.get("discord_enabled", True) and s.discord_webhook_url:
        discord_channel = routing.get("discord_channel", "signals")
        if discord_channel == "alerts":
            webhook_url = getattr(s, "discord_alerts_webhook_url", "") or s.discord_webhook_url
        else:
            webhook_url = s.discord_webhook_url

        try:
            embed = _payload_to_discord_embed(payload)
            r = requests.post(
                webhook_url.rstrip("?&") + "?wait=true",
                json={"embeds": [embed]},
                timeout=10,
            )
            if r.status_code in (200, 204):
                msg_id = r.json().get("id") if r.status_code == 200 else None
                channel_id = r.json().get("channel_id") if r.status_code == 200 else None
                if msg_id and supabase_client and payload.signal_id:
                    try:
                        supabase_client.table("trading_signals").update(
                            {"discord_message_id": str(msg_id)}
                        ).eq("id", payload.signal_id).execute()
                    except Exception:
                        pass
                # Post full AI reasoning to thread when bot token is configured
                if (
                    msg_id
                    and channel_id
                    and payload.type == "signal"
                    and getattr(s, "discord_bot_token", "")
                ):
                    ai_result = (payload.metadata or {}).get("ai_result")
                    if ai_result:
                        full_ai = _format_ai_analysis(ai_result)
                        if full_ai:
                            thread_id = create_discord_thread(
                                channel_id,
                                msg_id,
                                f"AI Analysis — Signal #{payload.signal_id}",
                            )
                            if thread_id:
                                ai_embed = {
                                    "title": "🧠 Full AI Analysis",
                                    "description": full_ai,
                                    "color": 0x5865F2,
                                    "timestamp": datetime.utcnow().isoformat(),
                                }
                                post_to_discord_thread(thread_id, ai_embed)
                logger.info("dispatch_payload: Discord sent (%s)", payload.title)
            else:
                logger.warning("dispatch_payload: Discord failed HTTP %s", r.status_code)
        except Exception:
            logger.error("dispatch_payload: Discord error", exc_info=True)

    # Telegram
    if routing.get("telegram_enabled", True) and s.telegram_bot_token and s.telegram_chat_id:
        try:
            text = _payload_to_telegram_html(payload)
            if payload.image_url:
                requests.post(
                    f"https://api.telegram.org/bot{s.telegram_bot_token}/sendMessage",
                    json={"chat_id": s.telegram_chat_id, "text": text, "parse_mode": "HTML"},
                    timeout=10,
                )
                r = requests.post(
                    f"https://api.telegram.org/bot{s.telegram_bot_token}/sendPhoto",
                    json={
                        "chat_id": s.telegram_chat_id,
                        "photo": payload.image_url,
                        "caption": _payload_to_telegram_setup_caption(payload),
                    },
                    timeout=10,
                )
            else:
                r = requests.post(
                    f"https://api.telegram.org/bot{s.telegram_bot_token}/sendMessage",
                    json={"chat_id": s.telegram_chat_id, "text": text, "parse_mode": "HTML"},
                    timeout=10,
                )
            if r.status_code == 200:
                msg_id = r.json().get("result", {}).get("message_id")
                if msg_id and supabase_client and payload.signal_id:
                    try:
                        supabase_client.table("trading_signals").update(
                            {"telegram_message_id": msg_id}
                        ).eq("id", payload.signal_id).execute()
                    except Exception:
                        pass
                logger.info("dispatch_payload: Telegram sent (%s)", payload.title)
            else:
                logger.warning("dispatch_payload: Telegram failed HTTP %s", r.status_code)
        except Exception:
            logger.error("dispatch_payload: Telegram error", exc_info=True)


def dispatch_payload_async(
    payload: NotificationPayload,
    supabase_client=None,
    notification_service=None,
) -> None:
    """Non-blocking version of dispatch_payload."""
    s = get_settings()
    if not getattr(s, "async_notifications", False):
        dispatch_payload(payload, supabase_client, notification_service)
        return

    def _send():
        dispatch_payload(payload, supabase_client, notification_service)

    _notification_executor.submit(_send)


# ═══════════════════════════════════════════════════════════════════════════
# Chart screenshot delivery: edit existing messages with chart image
# ═══════════════════════════════════════════════════════════════════════════

def edit_discord_message_with_chart(
    channel_id: str,
    message_id: str,
    chart_png: bytes,
    signal_id: int,
) -> bool:
    """
    Edit a Discord message to attach a chart screenshot image.
    Uses Discord Bot API (requires DISCORD_BOT_TOKEN).
    Returns True on success.
    """
    s = get_settings()
    bot_token = getattr(s, "discord_bot_token", "")
    if not bot_token or not channel_id or not message_id:
        return False

    try:
        import json as _json

        url = f"https://discord.com/api/v10/channels/{channel_id}/messages/{message_id}"
        headers = {"Authorization": f"Bot {bot_token}"}

        # First fetch the existing message to preserve the embed
        get_resp = requests.get(url, headers=headers, timeout=10)
        if get_resp.status_code != 200:
            logger.warning("Failed to fetch Discord message for chart edit: HTTP %s", get_resp.status_code)
            return False

        existing = get_resp.json()
        embeds = existing.get("embeds", [])

        # Add chart as the embed image via attachment
        if embeds:
            embeds[0]["image"] = {"url": "attachment://chart.png"}

        # PATCH with multipart: embed + file
        payload_json = _json.dumps({"embeds": embeds})
        files = {
            "payload_json": (None, payload_json, "application/json"),
            "files[0]": ("chart.png", chart_png, "image/png"),
        }
        patch_resp = requests.patch(url, headers=headers, files=files, timeout=15)

        if patch_resp.status_code == 200:
            logger.info("Chart attached to Discord message %s for signal #%s", message_id, signal_id)
            return True
        else:
            logger.warning(
                "Discord chart edit failed HTTP %s: %s",
                patch_resp.status_code, patch_resp.text[:200] if patch_resp.text else "",
            )
            return False
    except Exception:
        logger.error("Discord chart edit error for signal #%s", signal_id, exc_info=True)
        return False


def send_telegram_chart(
    chart_png: bytes,
    signal_id: int,
    reply_to_message_id: Optional[int] = None,
) -> bool:
    """
    Send a chart screenshot as a Telegram photo.
    Sends as reply to the original signal message if reply_to_message_id is provided.
    Returns True on success.
    """
    s = get_settings()
    if not s.telegram_bot_token or not s.telegram_chat_id:
        return False

    try:
        url = f"https://api.telegram.org/bot{s.telegram_bot_token}/sendPhoto"
        data = {
            "chat_id": s.telegram_chat_id,
            "caption": f"📊 Trade Setup Chart — Signal #{signal_id}",
        }
        if reply_to_message_id:
            data["reply_to_message_id"] = reply_to_message_id

        files = {"photo": ("chart.png", chart_png, "image/png")}
        r = requests.post(url, data=data, files=files, timeout=15)

        if r.status_code == 200:
            logger.info("Chart sent to Telegram for signal #%s", signal_id)
            return True
        else:
            logger.warning("Telegram chart send failed HTTP %s: %s", r.status_code, r.text[:200])
            return False
    except Exception:
        logger.error("Telegram chart send error for signal #%s", signal_id, exc_info=True)
        return False


def send_chart_to_channels_async(
    chart_png: bytes,
    signal_id: int,
    supabase_client=None,
) -> None:
    """
    Non-blocking: send chart to Discord and Telegram in background.
    Fetches message IDs from DB, then edits Discord / sends Telegram photo.
    """
    def _send():
        try:
            discord_msg_id = None
            telegram_msg_id = None

            if supabase_client and signal_id:
                try:
                    rec = (
                        supabase_client.table("trading_signals")
                        .select("discord_message_id, telegram_message_id")
                        .eq("id", signal_id)
                        .maybe_single()
                        .execute()
                    )
                    if rec and rec.data:
                        discord_msg_id = rec.data.get("discord_message_id")
                        telegram_msg_id = rec.data.get("telegram_message_id")
                except Exception:
                    logger.warning("Could not fetch message IDs for chart delivery, signal #%s", signal_id)

            # Discord: need channel_id -- extract from webhook URL or use bot token
            s = get_settings()
            if discord_msg_id and getattr(s, "discord_bot_token", ""):
                # We need channel_id. Try fetching it via the bot API.
                try:
                    # Parse channel from webhook URL (format: .../webhooks/{id}/{token})
                    # Or use the signals channel ID if configured
                    channel_id = getattr(s, "discord_signals_channel_id", "")
                    if channel_id:
                        edit_discord_message_with_chart(channel_id, discord_msg_id, chart_png, signal_id)
                except Exception:
                    logger.warning("Discord chart edit skipped -- no channel_id for signal #%s", signal_id)

            # Telegram: send as reply
            if telegram_msg_id:
                send_telegram_chart(chart_png, signal_id, reply_to_message_id=int(telegram_msg_id))
            else:
                # No reply target -- send standalone
                send_telegram_chart(chart_png, signal_id)

        except Exception:
            logger.error("Chart channel delivery error for signal #%s", signal_id, exc_info=True)

    _notification_executor.submit(_send)
