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
    image_url: Optional[str] = None
    account_name: Optional[str] = None
    bar_time: Optional[str] = None
    account_badge: str = "ACC: Unknown Account"
    status_line: Optional[str] = None
    sections: list[dict[str, Any]] = field(default_factory=list)


class NotificationService:
    def __init__(self, supabase=None):
        self.supabase = supabase
        self._routing_cache: dict[str, dict] | None = None
        self._routing_cache_ts: float = 0.0
        self._ROUTING_CACHE_TTL = 60.0  # seconds

    def _resolve_setup_image_url(
        self,
        signal: dict[str, Any],
        explicit_image_url: Optional[str] = None,
    ) -> Optional[str]:
        if explicit_image_url:
            return explicit_image_url

        setup_evidence = signal.get("setup_evidence")
        if isinstance(setup_evidence, dict):
            focus_image = setup_evidence.get("focus_image")
            if isinstance(focus_image, dict) and focus_image.get("url"):
                return str(focus_image["url"])

        image_url = signal.get("image_url")
        return str(image_url) if image_url else None

    def _build_setup_evidence_summary(self, signal: dict[str, Any]) -> Optional[dict[str, Any]]:
        setup_evidence = signal.get("setup_evidence")
        if not isinstance(setup_evidence, dict) or not setup_evidence:
            return None

        status = str(setup_evidence.get("status") or "missing").lower()
        focus_zone = setup_evidence.get("focus_zone")
        focus_zone_label = "No focus zone detected"
        if isinstance(focus_zone, dict) and focus_zone.get("label"):
            focus_zone_label = str(focus_zone["label"])

        return {
            "status": status,
            "status_label": f"Setup Evidence: {status.upper()}",
            "focus_zone_label": focus_zone_label,
            "has_image": bool(self._resolve_setup_image_url(signal)),
            "reason": str(setup_evidence.get("reason") or ""),
        }

    # ─── Public API ──────────────────────────────────────────────────────────

    def format_signal(
        self,
        signal: dict[str, Any],
        ai_result: Optional[dict[str, Any]] = None,
        mode: str = "manual",
        account_name: Optional[str] = None,
        image_url: Optional[str] = None,
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

        # Resolve image_url — prefer explicit param, fallback to signal dict
        resolved_image_url = self._resolve_setup_image_url(signal, image_url)

        # Resolve account name
        resolved_account = _resolve_account_name(account_name, signal)

        # Resolve bar_time
        bar_time_raw = signal.get("bar_time") or signal.get("signal_time")
        session = _derive_session(bar_time_raw)
        bar_time_display = None
        if bar_time_raw:
            try:
                dt = datetime.fromisoformat(str(bar_time_raw).replace("Z", "+00:00"))
                bar_time_display = dt.strftime("%H:%M UTC")
            except Exception:
                bar_time_display = str(bar_time_raw)

        _ai_raw = ai_result or signal.get("ai_reasoning")
        decision = ""
        rf_prob = 0.0
        reason = ""
        if _ai_raw:
            decision = str(_ai_raw.get("decision", "")).upper()
            if decision:
                try:
                    rf_prob = float(_ai_raw.get("rf_prob") or _ai_raw.get("confidence") or 0) * 100
                except Exception:
                    rf_prob = 0.0
                reason = str(_ai_raw.get("reason") or "").strip()

        trade_fields: dict[str, str] = {
            "Symbol": symbol,
            "Side": side,
            "Entry": f"{entry:.5g}" if entry else "N/A",
            "Stop Loss": sl_display if sl else "N/A",
            "Take Profit": tp_display if tp else "N/A",
            "R:R": f"1:{rr_ratio:.2f}" if rr_ratio else "N/A",
        }

        risk_fields: dict[str, str] = {}
        if size:
            risk_fields["Lot Size"] = f"{size:.2f} lots"
        if risk_usd:
            risk_fields["Risk"] = f"${risk_usd:.2f}"
        if signal.get("zone_type"):
            risk_fields["Zone"] = str(signal["zone_type"]).title()
        if signal.get("zone_id") is not None:
            risk_fields["Zone ID"] = str(signal["zone_id"])

        ai_fields: dict[str, str] = {}
        if decision:
            ai_fields["AI"] = decision
            ai_fields["Confidence"] = f"{rf_prob:.1f}%"
            if reason:
                ai_fields["Reason"] = reason

        context_fields: dict[str, str] = {}
        if session:
            context_fields["Session"] = session
        if bar_time_display:
            context_fields["Bar Time"] = bar_time_display
        if signal_id:
            context_fields["Signal"] = f"#{signal_id}"
        strategy_badge = _format_strategy_badge(signal)
        if strategy_badge:
            context_fields["Strategy"] = strategy_badge

        sections: list[dict[str, Any]] = [{"name": "Trade", "fields": trade_fields}]
        if risk_fields:
            sections.append({"name": "Risk", "fields": risk_fields})
        if ai_fields:
            sections.append({"name": "AI", "fields": ai_fields})
        if context_fields:
            sections.append({"name": "Context", "fields": context_fields})

        fields = _flatten_sections(sections)
        fields["Account"] = resolved_account

        metadata = {"symbol": symbol, "side": side, "mode": mode, "ai_result": _ai_raw or {}}
        setup_evidence_summary = self._build_setup_evidence_summary(signal)
        if setup_evidence_summary:
            metadata["setup_evidence_summary"] = setup_evidence_summary

        return NotificationPayload(
            type="signal",
            title=f"[{strategy_badge}] {side} Signal - {symbol}" if strategy_badge else f"{side} Signal - {symbol}",
            description="Auto-executed (paper)" if mode == "paper" else "Execute manually",
            fields=fields,
            color=color,
            footer=f"Signal #{signal_id} | /close {signal_id} to close",
            metadata=metadata,
            signal_id=signal_id,
            image_url=resolved_image_url,
            account_name=resolved_account,
            bar_time=bar_time_raw,
            account_badge=f"ACC: {resolved_account}",
            status_line=_build_status_line(mode, signal),
            sections=sections,
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
        resolved_account = _resolve_account_name(None, signal)

        summary_fields: dict[str, str] = {
            "Outcome":    outcome,
            "PnL":        f"{pnl_sign}${pnl:.2f}",
            "Entry":      f"{entry:.5g}" if entry else "N/A",
            "Exit":       f"{exit_price:.5g}" if exit_price else "N/A",
        }
        if commission:
            summary_fields["Commission"] = f"${commission:.2f}"
        if swap:
            summary_fields["Swap"] = f"${swap:.2f}"

        risk_usd = float(signal.get("risk_usd") or signal.get("risk_amount") or 0)
        if risk_usd > 0:
            r_multiple = pnl / risk_usd
            sign = "+" if r_multiple >= 0 else ""
            summary_fields["R Multiple"] = f"{sign}{r_multiple:.2f}R"

        sections: list[dict[str, Any]] = [{"name": "Summary", "fields": summary_fields}]
        context_fields: dict[str, str] = {}
        if signal_id:
            context_fields["Signal"] = f"#{signal_id}"
        strategy_badge = _format_strategy_badge(signal)
        if strategy_badge:
            context_fields["Strategy"] = strategy_badge
        if context_fields:
            sections.append({"name": "Context", "fields": context_fields})

        metadata = {"symbol": symbol, "side": side, "pnl": pnl, "outcome": outcome}
        setup_evidence_summary = self._build_setup_evidence_summary(signal)
        if setup_evidence_summary:
            metadata["setup_evidence_summary"] = setup_evidence_summary

        return NotificationPayload(
            type="close",
            title=f"[{strategy_badge}] Trade Closed - {symbol} {side}" if strategy_badge else f"Trade Closed - {symbol} {side}",
            fields=_flatten_sections(sections),
            color=color,
            metadata=metadata,
            signal_id=signal_id,
            image_url=self._resolve_setup_image_url(signal),
            account_name=resolved_account,
            account_badge=f"ACC: {resolved_account}",
            sections=sections,
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
        resolved_account = _resolve_account_name(None, alert)

        summary_fields: dict[str, str] = {
            "Severity": severity.upper(),
            "Type":     alert.get("alert_type", ""),
        }
        if alert.get("signal_id"):
            summary_fields["Signal"] = f"#{alert['signal_id']}"
        if meta_lines:
            summary_fields["Details"] = meta_lines

        sections = [{"name": "Summary", "fields": summary_fields}]

        return NotificationPayload(
            type="alert",
            title=alert.get("title", "Alert"),
            description=alert.get("message", ""),
            fields=_flatten_sections(sections),
            color=color,
            footer=f"Alert #{alert.get('id')} | /ack {alert.get('id')} to acknowledge",
            metadata=metadata,
            alert_id=alert.get("id"),
            account_name=resolved_account,
            account_badge=f"ACC: {resolved_account}",
            sections=sections,
        )

    def format_guard(
        self,
        symbol: str,
        reason: str,
        signal_id: Optional[int] = None,
        account_name: Optional[str] = None,
    ) -> NotificationPayload:
        """Format a guard/watchdog alert (late fill, circuit breaker, etc.)."""
        resolved_account = _resolve_account_name(account_name, {})
        fields: dict[str, str] = {
            "Symbol": symbol,
            "Reason": reason,
        }
        if signal_id:
            fields["Signal"] = f"#{signal_id}"

        sections = [{"name": "Summary", "fields": fields}]

        return NotificationPayload(
            type="guard",
            title=f"Guard Alert - {symbol}",
            fields=fields,
            color="guard",
            signal_id=signal_id,
            account_name=resolved_account,
            account_badge=f"ACC: {resolved_account}",
            sections=sections,
        )

    def format_digest(self, account_name: str, stats: dict) -> NotificationPayload:
        """
        Formats a daily performance digest payload for Discord and Telegram.
        
        stats: Dictionary containing net_pnl, win_rate_pct, total_trades, etc.
        """
        net_pnl = stats.get("net_pnl", 0.0)
        win_rate = stats.get("win_rate_pct", 0.0)
        total_trades = stats.get("total_trades", 0)
        best_trade = stats.get("best_trade_pnl", 0.0)
        worst_trade = stats.get("worst_trade_pnl", 0.0)
        
        is_profitable = net_pnl > 0
        color: NotificationColor = "buy" if is_profitable else "sell"
        if net_pnl == 0:
            color = "info"
            
        emoji = "🎯" if is_profitable else "📊"
        
        def format_currency(val: float) -> str:
            sign = "+" if val >= 0 else "-"
            return f"{sign}${abs(val):.2f}"

        fields = {
            "Net PnL": format_currency(net_pnl),
            "Win Rate": f"{win_rate:.1f}% ({stats.get('winning_trades', 0)}/{total_trades})",
            "Best Trade": format_currency(best_trade),
            "Worst Trade": format_currency(worst_trade),
            "Gross PnL": format_currency(stats.get("gross_pnl", 0.0)),
            "Commissions": format_currency(stats.get("commission", 0.0)),
        }
        
        if stats.get("swap"):
            fields["Swap"] = format_currency(stats.get("swap", 0.0))

        return NotificationPayload(
            type="info",
            title=f"{emoji} Daily Performance Report",
            fields=fields,
            color=color,
            account_name=account_name,
            account_badge=f"ACC: {_resolve_account_name(account_name, {})}",
            sections=[{"name": "Summary", "fields": fields}],
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


def _resolve_account_name(explicit_account: Optional[str], payload_source: dict[str, Any]) -> str:
    return str(
        explicit_account
        or payload_source.get("account_name")
        or payload_source.get("account")
        or "Unknown Account"
    )


def _build_status_line(mode: str, source: dict[str, Any]) -> Optional[str]:
    mode_label = "Paper" if mode == "paper" else "Live" if mode == "live" else "Manual"
    venue = source.get("firm_name") or source.get("broker_name") or source.get("broker")
    parts = [mode_label]
    if venue:
        parts.append(str(venue))
    return " | ".join(parts)


def _flatten_sections(sections: list[dict[str, Any]]) -> dict[str, str]:
    flattened: dict[str, str] = {}
    for section in sections:
        for key, value in section["fields"].items():
            flattened[key] = value
    return flattened


def _format_price_with_distance(price: float, distance: float, unit: str, is_index: bool) -> str:
    if not price:
        return "N/A"
    if is_index:
        return f"{price:.2f} ({distance:.1f} pts, {round(distance * 100):.0f} pips)"
    return f"{price:.5g} ({distance:.1f} {unit})"


def _format_strategy_badge(signal: dict[str, Any]) -> str:
    strategy_id = str(signal.get("strategy_id") or "").strip()
    if not strategy_id:
        return ""
    strategy_version = str(signal.get("strategy_version") or "?").strip()
    return f"{strategy_id}@{strategy_version}"


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


def _derive_session(bar_time_iso: Optional[str]) -> Optional[str]:
    """Derive trading session from bar_time UTC hour."""
    if not bar_time_iso:
        return None
    try:
        dt = datetime.fromisoformat(str(bar_time_iso).replace("Z", "+00:00"))
        hour = dt.astimezone(timezone.utc).hour
        if 0 <= hour < 8:
            return "🌏 Asian"
        if 8 <= hour < 13:
            return "🇬🇧 London"
        if 13 <= hour < 16:
            return "🌐 London/NY Overlap"
        if 16 <= hour < 21:
            return "🇺🇸 New York"
        return "🌙 Off-hours"
    except Exception:
        return None
