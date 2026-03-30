"""
NotificationService — Centralized notification formatting and dispatch.

All Discord/Telegram notifications go through here.
Fixes:
  - Correct entry/SL/TP: uses broker fill price when available, falls back to signal values
  - Correct lot size: uses signal.size (risk engine output), not recalculated in adapter
  - Correct R:R: calculated from actual entry/SL/TP values
  - Correct AI analysis: requires explicit ai_result dict, not silently dropped
  - Correct symbol: uses broker_symbol when set, falls back to signal symbol
  - Correct PnL on close: uses broker actual PnL (pnl_usd), not TradingView simulated
  - Notification routing: checks notification_routing table before dispatching
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Literal, Optional

logger = logging.getLogger(__name__)

NotificationColor = Literal["buy", "sell", "win", "loss", "breakeven", "warning", "critical", "info", "guard"]

COLOR_MAP: dict[NotificationColor, int] = {
    "buy":       0x00C853,  # Green
    "sell":      0xF44336,  # Red
    "win":       0x22C55E,  # Green
    "loss":      0xEF4444,  # Red
    "breakeven": 0x64748B,  # Slate
    "warning":   0xFACC15,  # Yellow
    "critical":  0xFF0000,  # Bright red
    "info":      0x3B82F6,  # Blue
    "guard":     0xFFA500,  # Orange
}


@dataclass
class NotificationPayload:
    type: Literal["signal", "close", "alert", "guard", "bug"]
    title: str
    fields: dict[str, str]       # ordered key-value pairs for embed fields
    color: NotificationColor
    description: str = ""
    footer: str = ""
    metadata: dict = field(default_factory=dict)
    signal_id: Optional[int] = None
    alert_id: Optional[int] = None


class NotificationService:
    def __init__(self, supabase=None):
        self.supabase = supabase
        self._routing_cache: dict[str, dict] | None = None
        self._routing_cache_ts: float = 0.0
        self._ROUTING_CACHE_TTL = 60.0  # seconds

    # ─── Public API ──────────────────────────────────────────────────────────

    def format_signal(
        self,
        signal: dict[str, Any],
        ai_result: Optional[dict[str, Any]] = None,
        mode: str = "manual",
    ) -> NotificationPayload:
        """
        Format a trade signal notification.

        Uses broker fill price when available (fill_price > entry).
        Uses signal.size for lot size (not recalculated).
        """
        signal_id = signal.get("id")
        symbol = self._resolve_symbol(signal)
        side = str(signal.get("side", "BUY")).upper()

        # Prefer broker fill price over TradingView entry
        entry = float(signal.get("fill_price") or signal.get("entry") or 0)
        sl = float(signal.get("sl") or 0)
        tp = float(signal.get("tp") or 0)

        # Prefer actual broker lot size from risk engine
        size = float(signal.get("size") or signal.get("lot_size") or 0)
        risk_usd = float(signal.get("risk_usd") or signal.get("risk_amount") or 0)

        pip_divisor = _get_pip_divisor(symbol)
        is_index = pip_divisor == 1.0
        unit_label = "pts" if is_index else "pips"

        sl_distance = abs(entry - sl) if entry and sl else 0
        tp_distance = abs(tp - entry) if tp and entry else 0
        sl_pips = sl_distance / pip_divisor if pip_divisor else 0
        tp_pips = tp_distance / pip_divisor if pip_divisor else 0
        rr_ratio = tp_distance / sl_distance if sl_distance > 0 else 0

        sl_display = _format_price_with_distance(sl, sl_pips, unit_label, is_index)
        tp_display = _format_price_with_distance(tp, tp_pips, unit_label, is_index)

        color: NotificationColor = "buy" if side == "BUY" else "sell"
        mode_prefix = "PAPER | " if mode == "paper" else ""
        emoji = "📈" if side == "BUY" else "📉"

        fields: dict[str, str] = {
            "Symbol":       f"**{symbol}**",
            "Side":         side,
            "R:R":          f"1:{rr_ratio:.2f}" if rr_ratio else "N/A",
            "Entry":        f"{entry:.5g}" if entry else "N/A",
            "Stop Loss":    sl_display if sl else "N/A",
            "Take Profit":  tp_display if tp else "N/A",
        }

        if size:
            fields["Lot Size"] = f"{size:.2f} lots"
        if risk_usd:
            fields["Risk"] = f"${risk_usd:.2f}"

        if signal.get("zone_id") is not None:
            fields["Zone ID"] = str(signal["zone_id"])
        if signal.get("zone_type"):
            zone_emoji = "🟢" if signal["zone_type"] == "demand" else "🔴"
            fields["Zone Type"] = f"{zone_emoji} {signal['zone_type'].upper()}"

        # AI analysis section
        ai_section = _format_ai_analysis(ai_result or signal.get("ai_reasoning"))
        if ai_section:
            fields["🧠 AI Analysis"] = ai_section

        return NotificationPayload(
            type="signal",
            title=f"{mode_prefix}{emoji} New {side} Signal — #{signal_id}",
            description=f"**{'Auto-executed (paper)' if mode == 'paper' else 'Execute manually'}**",
            fields=fields,
            color=color,
            footer=f"Signal #{signal_id} | /close {signal_id} to close",
            metadata={"symbol": symbol, "side": side, "mode": mode},
            signal_id=signal_id,
        )

    def format_close(
        self,
        signal: dict[str, Any],
        broker_deal: Optional[dict[str, Any]] = None,
    ) -> NotificationPayload:
        """
        Format a trade close notification.

        Prefers broker_deal (actual MetaAPI deal data) over DB values.
        broker_deal fields: profit, commission, swap, closePrice
        """
        signal_id = signal.get("id")
        symbol = self._resolve_symbol(signal)
        side = str(signal.get("side", "BUY")).upper()

        entry = float(signal.get("fill_price") or signal.get("entry") or 0)

        # Prefer broker actual PnL over TradingView simulated
        if broker_deal:
            raw_pnl = float(broker_deal.get("profit") or 0)
            commission = float(broker_deal.get("commission") or 0)
            swap = float(broker_deal.get("swap") or 0)
            pnl = raw_pnl + commission + swap
            exit_price = float(broker_deal.get("closePrice") or broker_deal.get("price") or signal.get("exit_price") or 0)
        else:
            pnl = float(signal.get("pnl_usd") or signal.get("pnl") or 0)
            commission = float(signal.get("commission") or 0)
            swap = float(signal.get("swap") or 0)
            exit_price = float(signal.get("exit_price") or 0)

        if pnl > 0:
            outcome = "WIN"
            color: NotificationColor = "win"
            emoji = "🟢"
        elif pnl < 0:
            outcome = "LOSS"
            color = "loss"
            emoji = "🔴"
        else:
            outcome = "BREAKEVEN"
            color = "breakeven"
            emoji = "⚪"

        pnl_sign = "+" if pnl >= 0 else ""
        fields: dict[str, str] = {
            "Outcome":    outcome,
            "PnL":        f"{pnl_sign}${pnl:.2f}",
            "Entry":      f"{entry:.5g}" if entry else "N/A",
            "Exit":       f"{exit_price:.5g}" if exit_price else "N/A",
        }
        if commission:
            fields["Commission"] = f"${commission:.2f}"
        if swap:
            fields["Swap"] = f"${swap:.2f}"

        return NotificationPayload(
            type="close",
            title=f"{emoji} Trade Closed — {symbol} {side}",
            fields=fields,
            color=color,
            metadata={"symbol": symbol, "side": side, "pnl": pnl, "outcome": outcome},
            signal_id=signal_id,
        )

    def format_alert(self, alert: dict[str, Any]) -> NotificationPayload:
        """Format an operational alert (drawdown, consecutive losses, etc.)."""
        severity = str(alert.get("severity", "info")).lower()
        color_map = {
            "critical": "critical",
            "error":    "critical",
            "warning":  "warning",
            "info":     "info",
        }
        color: NotificationColor = color_map.get(severity, "info")

        metadata = alert.get("metadata") or {}
        meta_lines = "\n".join(f"{k}: {v}" for k, v in metadata.items()) if metadata else ""

        fields: dict[str, str] = {
            "Severity": severity.upper(),
            "Type":     alert.get("alert_type", ""),
        }
        if alert.get("signal_id"):
            fields["Signal"] = f"#{alert['signal_id']}"
        if meta_lines:
            fields["Details"] = meta_lines

        return NotificationPayload(
            type="alert",
            title=alert.get("title", "Alert"),
            description=alert.get("message", ""),
            fields=fields,
            color=color,
            footer=f"Alert #{alert.get('id')} | /ack {alert.get('id')} to acknowledge",
            metadata=metadata,
            alert_id=alert.get("id"),
        )

    def format_guard(self, symbol: str, reason: str, signal_id: Optional[int] = None) -> NotificationPayload:
        """Format a guard/watchdog alert (late fill, circuit breaker, etc.)."""
        fields: dict[str, str] = {
            "Symbol": symbol,
            "Reason": reason,
        }
        if signal_id:
            fields["Signal"] = f"#{signal_id}"

        return NotificationPayload(
            type="guard",
            title=f"⚠️ Guard Alert — {symbol}",
            fields=fields,
            color="guard",
            signal_id=signal_id,
        )

    # ─── Routing ─────────────────────────────────────────────────────────────

    def get_routing(self, notification_type: str) -> dict[str, Any]:
        """
        Returns routing config for a notification type.
        Falls back to enabled on all channels if not in DB.
        """
        import time
        now = time.time()
        if self._routing_cache is None or (now - self._routing_cache_ts) > self._ROUTING_CACHE_TTL:
            self._routing_cache = self._load_routing()
            self._routing_cache_ts = now

        return self._routing_cache.get(
            notification_type,
            {"discord_enabled": True, "telegram_enabled": True, "discord_channel": "signals"},
        )

    def _load_routing(self) -> dict[str, dict]:
        if not self.supabase:
            return {}
        try:
            resp = self.supabase.table("notification_routing").select("*").execute()
            return {r["alert_type"]: r for r in (resp.data or [])}
        except Exception:
            logger.warning("NotificationService: failed to load routing config", exc_info=True)
            return {}

    # ─── Helpers ─────────────────────────────────────────────────────────────

    def _resolve_symbol(self, signal: dict[str, Any]) -> str:
        """Prefer broker_symbol over TradingView symbol."""
        return str(
            signal.get("broker_symbol") or signal.get("symbol") or "UNKNOWN"
        ).upper()


# ─── Module-level helpers ────────────────────────────────────────────────────

def _get_pip_divisor(symbol: str) -> float:
    symbol = symbol.upper()
    index_patterns = ["NAS", "US100", "NDX", "SPX", "US500", "DJI", "US30", "DAX", "FTSE", "NIK", "NAS100"]
    if any(p in symbol for p in index_patterns):
        return 1.0
    if "JPY" in symbol:
        return 0.01
    if "XAU" in symbol or "GOLD" in symbol:
        return 0.1
    if "BTC" in symbol or "ETH" in symbol:
        return 1.0
    return 0.0001


def _format_price_with_distance(price: float, distance: float, unit: str, is_index: bool) -> str:
    if not price:
        return "N/A"
    if is_index:
        return f"{price:.2f} ({distance:.1f} pts, {round(distance * 100):.0f} pips)"
    return f"{price:.5g} ({distance:.1f} {unit})"


def _format_ai_analysis(ai_result: Optional[dict]) -> Optional[str]:
    if not ai_result:
        return None
    decision = str(ai_result.get("decision", "")).upper()
    if not decision:
        return None

    try:
        rf_prob = float(ai_result.get("rf_prob") or ai_result.get("confidence") or 0) * 100
    except Exception:
        rf_prob = 0.0

    reason = str(ai_result.get("reason") or "N/A").strip()
    rules = ai_result.get("rules") or []

    lines = [
        f"**Decision:** {decision}",
        f"**Confidence:** {rf_prob:.1f}%",
        f"**Reason:** {reason}",
    ]
    if rules:
        lines.append(f"**RAG Wisdom:** {len(rules)} rules found:")
        for i, rule in enumerate(rules[:5], 1):
            snippet = str(rule).strip().replace("\n", " ")
            if len(snippet) > 300:
                snippet = snippet[:297] + "..."
            lines.append(f"{i}. {snippet}")

    return "\n".join(lines)
