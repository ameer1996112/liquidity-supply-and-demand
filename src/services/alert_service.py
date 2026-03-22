"""AlertService — centralized alert creation with pluggable notifiers.

Sprint 5.3: Operational alerting + external notifications (Discord, etc.).

This service writes into the ``trading_alerts`` table and then fans out the
created alert to any configured notifier backends. It is designed to be used
from both the worker (background checks) and API/background services.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Protocol, Sequence

import requests

from config import get_settings

logger = logging.getLogger(__name__)

_ALERTS_TABLE_MISSING_MSG = "Could not find the table"
_PGRST205 = "PGRST205"


def _is_table_missing(exc: BaseException) -> bool:
    """True if the exception indicates trading_alerts table is missing."""
    msg = str(exc)
    if _ALERTS_TABLE_MISSING_MSG in msg or _PGRST205 in msg:
        return True
    if getattr(exc, "args", None) and len(exc.args) > 0:
        first = exc.args[0]
        if isinstance(first, dict) and (
            first.get("code") == _PGRST205
            or _ALERTS_TABLE_MISSING_MSG in str(first.get("message", ""))
        ):
            return True
        if _ALERTS_TABLE_MISSING_MSG in str(first) or _PGRST205 in str(first):
            return True
    return False


@dataclass
class AlertPayload:
    """Lightweight alert DTO passed to notifiers."""

    alert_type: str
    severity: str
    title: str
    message: str
    metadata: Dict[str, Any]
    signal_id: Optional[int] = None
    correlation_id: Optional[str] = None
    created_at: Optional[str] = None
    id: Optional[int] = None


class AlertNotifier(Protocol):
    """Interface for pluggable alert notifiers."""

    def send(self, alert: AlertPayload) -> None:  # pragma: no cover - Protocol
        ...


class DiscordAlertNotifier:
    """Simple Discord webhook notifier for operational alerts.

    Uses a compact embed with severity-aware color and optional correlation link.
    """

    def __init__(self, webhook_url: Optional[str] = None) -> None:
        settings = get_settings()
        if webhook_url is not None:
            raw = webhook_url
        else:
            # Prefer dedicated alerts channel; fall back to main webhook
            raw = (
                getattr(settings, "discord_alerts_webhook_url", "")
                or getattr(settings, "discord_webhook_url", "")
            )
        self.webhook_url = (raw or "").strip()

    def send(self, alert: AlertPayload) -> None:
        if not self.webhook_url:
            return

        try:
            severity = (alert.severity or "info").lower()
            color_map = {
                "critical": 0xDC2626,  # red-600
                "error": 0xF97316,  # orange-500
                "warning": 0xFACC15,  # yellow-400
                "info": 0x3B82F6,  # blue-500
            }
            color = color_map.get(severity, 0x3B82F6)

            fields: List[Dict[str, Any]] = [
                {
                    "name": "Severity",
                    "value": severity.upper(),
                    "inline": True,
                },
                {
                    "name": "Type",
                    "value": alert.alert_type,
                    "inline": True,
                },
            ]

            if alert.signal_id is not None:
                fields.append(
                    {
                        "name": "Signal ID",
                        "value": f"#{alert.signal_id}",
                        "inline": True,
                    }
                )

            if alert.correlation_id:
                fields.append(
                    {
                        "name": "Correlation",
                        "value": alert.correlation_id,
                        "inline": False,
                    }
                )

            if alert.metadata:
                # Show a compact JSON-ish view (truncated) for quick context.
                try:
                    preview_items = []
                    for k, v in list(alert.metadata.items())[:8]:
                        preview_items.append(f"**{k}**={v}")
                    meta_preview = ", ".join(preview_items)
                except Exception:  # noqa: BLE001
                    meta_preview = ""
                if meta_preview:
                    if len(meta_preview) > 350:
                        meta_preview = meta_preview[:347].rstrip() + "..."
                    fields.append(
                        {
                            "name": "Metadata",
                            "value": meta_preview,
                            "inline": False,
                        }
                    )

            timestamp = (
                alert.created_at
                or datetime.now(timezone.utc).isoformat()
            )

            embed = {
                "title": alert.title or alert.alert_type,
                "description": alert.message or "",
                "color": color,
                "fields": fields,
                "timestamp": timestamp,
            }

            payload = {"embeds": [embed]}
            resp = requests.post(
                self.webhook_url,
                json=payload,
                timeout=5,
            )
            if resp.status_code not in (200, 204):
                logger.warning(
                    "DiscordAlertNotifier HTTP %s: %s",
                    resp.status_code,
                    (resp.text or "")[:200],
                )
        except Exception as exc:  # noqa: BLE001
            # Never raise from notifier — alerts must not break the core flow.
            logger.warning("DiscordAlertNotifier failed: %s", exc)


class TelegramAlertNotifier:
    """Telegram notifier for operational alerts.

    Mirrors DiscordAlertNotifier but sends a plain HTML message via Telegram Bot API.
    """

    def __init__(
        self,
        bot_token: Optional[str] = None,
        chat_id: Optional[str] = None,
    ) -> None:
        settings = get_settings()
        self.bot_token = (bot_token or getattr(settings, "telegram_bot_token", "") or "").strip()
        self.chat_id = (chat_id or getattr(settings, "telegram_chat_id", "") or "").strip()

    def send(self, alert: AlertPayload) -> None:
        if not self.bot_token or not self.chat_id:
            return

        try:
            severity = (alert.severity or "info").lower()
            severity_emoji = {
                "critical": "🔴",
                "error": "🟠",
                "warning": "🟡",
                "info": "🔵",
            }.get(severity, "🔵")

            lines = [
                f"{severity_emoji} <b>{alert.title}</b>",
                f"<i>{alert.alert_type.upper()} · {severity.upper()}</i>",
                "",
                alert.message or "",
            ]

            if alert.signal_id is not None:
                lines.append(f"Signal: <code>#{alert.signal_id}</code>")

            if alert.metadata:
                meta_parts = []
                for k, v in list(alert.metadata.items())[:6]:
                    meta_parts.append(f"  {k}: {v}")
                if meta_parts:
                    lines.append("\n" + "\n".join(meta_parts))

            text = "\n".join(lines)
            if len(text) > 4000:
                text = text[:3997] + "..."

            resp = requests.post(
                f"https://api.telegram.org/bot{self.bot_token}/sendMessage",
                json={"chat_id": self.chat_id, "text": text, "parse_mode": "HTML"},
                timeout=5,
            )
            if resp.status_code != 200:
                logger.warning(
                    "TelegramAlertNotifier HTTP %s: %s",
                    resp.status_code,
                    (resp.text or "")[:200],
                )
        except Exception as exc:  # noqa: BLE001
            logger.warning("TelegramAlertNotifier failed: %s", exc)


class AlertService:
    """Persist alerts to Supabase and fan out to notifiers."""

    def __init__(
        self,
        supabase_client: Any,
        notifiers: Optional[Sequence[AlertNotifier]] = None,
    ) -> None:
        self.supabase = supabase_client
        self._notifiers: List[AlertNotifier] = list(notifiers or [])

    def add_notifier(self, notifier: AlertNotifier) -> None:
        self._notifiers.append(notifier)

    def _notify(self, alert: AlertPayload) -> None:
        for notifier in list(self._notifiers):
            try:
                notifier.send(alert)
            except Exception as exc:  # noqa: BLE001
                logger.warning("Alert notifier %r failed: %s", notifier, exc)

    def create_alert(
        self,
        alert_type: str,
        severity: str,
        title: str,
        message: str,
        metadata: Optional[Dict[str, Any]] = None,
        *,
        signal_id: Optional[int] = None,
        correlation_id: Optional[str] = None,
        dedupe_minutes: int = 5,
    ) -> Optional[int]:
        """Insert alert into trading_alerts with simple recent deduplication.

        Deduplication window is keyed by ``alert_type`` to avoid spamming
        Discord / UI when a condition remains true for a while.
        """
        if not self.supabase:
            return None

        metadata = metadata or {}
        try:
            cutoff = (
                datetime.now(timezone.utc) - timedelta(minutes=dedupe_minutes)
            ).isoformat()
            existing = (
                self.supabase.table("trading_alerts")
                .select("id")
                .eq("alert_type", alert_type)
                .gte("created_at", cutoff)
                .limit(1)
                .execute()
            )
            if existing.data:
                return None
        except Exception as exc:  # noqa: BLE001
            if _is_table_missing(exc):
                logger.debug(
                    "AlertService: trading_alerts table not found "
                    "(run migrations/004_trading_alerts.sql): %s",
                    exc,
                )
                return None
            logger.error("AlertService: dedupe query failed: %s", exc)
            # Continue and attempt insert — better to over-alert than miss.

        row: Dict[str, Any] = {
            "alert_type": alert_type,
            "severity": severity,
            "title": title,
            "message": message,
            "metadata": metadata,
        }
        if signal_id is not None:
            row["signal_id"] = signal_id
        if correlation_id is not None:
            row["correlation_id"] = correlation_id

        try:
            resp = (
                self.supabase.table("trading_alerts")
                .insert(row)
                .execute()
            )
            created = None
            if resp.data:
                created = resp.data[0] if isinstance(resp.data, list) else resp.data
            alert = AlertPayload(
                alert_type=alert_type,
                severity=severity,
                title=title,
                message=message,
                metadata=metadata,
                signal_id=signal_id,
                correlation_id=correlation_id,
                id=(created or {}).get("id") if isinstance(created, dict) else None,
                created_at=(
                    (created or {}).get("created_at")
                    if isinstance(created, dict)
                    else None
                ),
            )
            logger.info("Alert created: [%s] %s", severity, title)
            if self._notifiers:
                self._notify(alert)
            return alert.id
        except Exception as exc:  # noqa: BLE001
            if _is_table_missing(exc):
                logger.debug(
                    "AlertService: trading_alerts table not found "
                    "(run migrations/004_trading_alerts.sql): %s",
                    exc,
                )
                return None
            logger.error("AlertService: failed to create alert: %s", exc)
            return None


def create_default_alert_service(
    supabase_client: Any,
) -> AlertService:
    """Factory used by worker and services to get an AlertService instance."""
    service = AlertService(supabase_client=supabase_client, notifiers=[])
    try:
        service.add_notifier(DiscordAlertNotifier())
    except Exception as exc:  # noqa: BLE001
        logger.warning("Failed to initialize DiscordAlertNotifier: %s", exc)
    try:
        service.add_notifier(TelegramAlertNotifier())
    except Exception as exc:  # noqa: BLE001
        logger.warning("Failed to initialize TelegramAlertNotifier: %s", exc)
    return service

