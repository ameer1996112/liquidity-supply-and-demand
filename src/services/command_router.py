"""
CommandRouter — Two-way command handler for Discord and Telegram.

Supported commands:
  /close <signal_id>         — Close trade on broker via MetaAPI
  /move-sl <signal_id> <price> — Modify stop loss on broker
  /ack <alert_id>            — Acknowledge an operational alert
  /pause                     — Stop bot from taking new signals
  /resume                    — Resume bot
  /status                    — Current bot state + open positions summary

Security: only whitelisted user IDs (platform + user_id) may issue commands.
Unknown users are silently ignored.
"""

import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Callable, Awaitable

logger = logging.getLogger(__name__)


@dataclass
class CommandResult:
    success: bool
    message: str


class CommandRouter:
    def __init__(self, supabase, meta_api=None):
        """
        Args:
            supabase: Supabase client
            meta_api: MetaApiAdapter instance (optional — needed for /close and /move-sl)
        """
        self.supabase = supabase
        self.meta_api = meta_api

    # ─── Auth ────────────────────────────────────────────────────────────────

    def _is_allowed(self, platform: str, user_id: str) -> bool:
        """Check if user_id is in the notification_whitelist for this platform."""
        try:
            resp = (
                self.supabase.table("notification_whitelist")
                .select("id")
                .eq("platform", platform)
                .eq("user_id", str(user_id))
                .limit(1)
                .execute()
            )
            return len(resp.data) > 0
        except Exception:
            logger.exception("CommandRouter: whitelist check failed")
            return False

    # ─── Entry point ─────────────────────────────────────────────────────────

    async def handle(
        self,
        platform: str,
        user_id: str,
        text: str,
        reply_fn: Callable[[str], Awaitable[None]],
    ) -> None:
        """
        Handle an incoming message. Silently ignores unauthorized users.

        Args:
            platform: 'telegram' or 'discord'
            user_id:  platform-specific user identifier (string)
            text:     raw message text (e.g. '/close 42')
            reply_fn: async callable that sends a reply back to the user
        """
        if not self._is_allowed(platform, user_id):
            logger.debug("CommandRouter: ignoring unauthorized user %s on %s", user_id, platform)
            return

        text = text.strip()
        if not text.startswith("/"):
            return

        parts = text.lstrip("/").split()
        command = parts[0].lower()
        args = parts[1:]

        result = await self._dispatch(command, args)
        self._audit(platform, user_id, command, args, result)
        await reply_fn(result.message)

    # ─── Dispatcher ──────────────────────────────────────────────────────────

    async def _dispatch(self, command: str, args: list[str]) -> CommandResult:
        try:
            if command == "close":
                return await self._close(args)
            elif command == "move-sl":
                return await self._move_sl(args)
            elif command == "ack":
                return await self._ack(args)
            elif command == "pause":
                return await self._pause()
            elif command == "resume":
                return await self._resume()
            elif command == "status":
                return await self._status()
            else:
                return CommandResult(
                    success=False,
                    message=f"Unknown command: /{command}\nAvailable: /close, /move-sl, /ack, /pause, /resume, /status",
                )
        except Exception:
            logger.exception("CommandRouter: error in /%s", command)
            return CommandResult(success=False, message=f"/{command} failed due to an internal error.")

    # ─── Commands ─────────────────────────────────────────────────────────────

    async def _close(self, args: list[str]) -> CommandResult:
        if len(args) < 1:
            return CommandResult(success=False, message="Usage: /close <signal_id>")

        try:
            signal_id = int(args[0])
        except ValueError:
            return CommandResult(success=False, message="Signal ID must be a number.")

        # Fetch signal from DB
        resp = (
            self.supabase.table("trading_signals")
            .select("id, symbol, side, broker_order_id, broker_position_id, status")
            .eq("id", signal_id)
            .limit(1)
            .execute()
        )
        if not resp.data:
            return CommandResult(success=False, message=f"Signal #{signal_id} not found.")

        signal = resp.data[0]
        if signal["status"] not in ("open", "OPEN", "executed", "EXECUTED"):
            return CommandResult(
                success=False,
                message=f"Signal #{signal_id} is already {signal['status']} — cannot close.",
            )

        broker_order_id = signal.get("broker_position_id") or signal.get("broker_order_id")
        if not broker_order_id:
            return CommandResult(
                success=False,
                message=f"Signal #{signal_id} has no broker position ID — may not have been executed yet.",
            )

        if not self.meta_api:
            return CommandResult(success=False, message="MetaAPI adapter not available.")

        from src.adapters.execution.meta_api_adapter import CloseRequest

        result = self.meta_api.close_order(
            CloseRequest(
                client_order_id=str(signal_id),
                broker_order_id=str(broker_order_id),
                symbol=signal["symbol"],
                volume=None,
            )
        )

        if result.status == "filled":
            # Mark closed in DB
            self.supabase.table("trading_signals").update(
                {"status": "CLOSED", "closed_at": datetime.now(timezone.utc).isoformat()}
            ).eq("id", signal_id).execute()
            return CommandResult(
                success=True,
                message=f"✅ Signal #{signal_id} ({signal['symbol']} {signal['side']}) closed on broker.",
            )
        else:
            return CommandResult(
                success=False,
                message=f"❌ Failed to close #{signal_id}: {result.message}",
            )

    async def _move_sl(self, args: list[str]) -> CommandResult:
        if len(args) < 2:
            return CommandResult(success=False, message="Usage: /move-sl <signal_id> <new_sl_price>")

        try:
            signal_id = int(args[0])
            new_sl = float(args[1])
        except ValueError:
            return CommandResult(success=False, message="Signal ID must be integer, price must be number.")

        resp = (
            self.supabase.table("trading_signals")
            .select("id, symbol, side, broker_order_id, broker_position_id, status, sl")
            .eq("id", signal_id)
            .limit(1)
            .execute()
        )
        if not resp.data:
            return CommandResult(success=False, message=f"Signal #{signal_id} not found.")

        signal = resp.data[0]
        if signal["status"] not in ("open", "OPEN", "executed", "EXECUTED"):
            return CommandResult(
                success=False,
                message=f"Signal #{signal_id} is {signal['status']} — cannot modify.",
            )

        broker_order_id = signal.get("broker_position_id") or signal.get("broker_order_id")
        if not broker_order_id:
            return CommandResult(
                success=False,
                message=f"Signal #{signal_id} has no broker position ID.",
            )

        if not self.meta_api:
            return CommandResult(success=False, message="MetaAPI adapter not available.")

        result = self.meta_api.modify_position(position_id=str(broker_order_id), sl=new_sl)

        if result.status == "filled":
            old_sl = signal.get("sl")
            self.supabase.table("trading_signals").update({"sl": new_sl}).eq("id", signal_id).execute()
            return CommandResult(
                success=True,
                message=f"✅ SL moved for #{signal_id} ({signal['symbol']}): {old_sl} → {new_sl}",
            )
        else:
            return CommandResult(
                success=False,
                message=f"❌ Failed to move SL for #{signal_id}: {result.message}",
            )

    async def _ack(self, args: list[str]) -> CommandResult:
        if len(args) < 1:
            return CommandResult(success=False, message="Usage: /ack <alert_id>")

        try:
            alert_id = int(args[0])
        except ValueError:
            return CommandResult(success=False, message="Alert ID must be a number.")

        resp = (
            self.supabase.table("trading_alerts")
            .select("id, title, acknowledged_at")
            .eq("id", alert_id)
            .limit(1)
            .execute()
        )
        if not resp.data:
            return CommandResult(success=False, message=f"Alert #{alert_id} not found.")

        alert = resp.data[0]
        if alert["acknowledged_at"]:
            return CommandResult(success=True, message=f"Alert #{alert_id} was already acknowledged.")

        self.supabase.table("trading_alerts").update(
            {"acknowledged_at": datetime.now(timezone.utc).isoformat()}
        ).eq("id", alert_id).execute()

        return CommandResult(
            success=True,
            message=f"✅ Alert #{alert_id} acknowledged: {alert['title']}",
        )

    async def _pause(self) -> CommandResult:
        self.supabase.table("system_config").upsert(
            {"key": "bot_paused", "value": "true", "updated_at": datetime.now(timezone.utc).isoformat()}
        ).execute()
        return CommandResult(success=True, message="⏸️ Bot paused. No new signals will be executed until /resume.")

    async def _resume(self) -> CommandResult:
        self.supabase.table("system_config").upsert(
            {"key": "bot_paused", "value": "false", "updated_at": datetime.now(timezone.utc).isoformat()}
        ).execute()
        return CommandResult(success=True, message="▶️ Bot resumed. Signals will be executed normally.")

    async def _status(self) -> CommandResult:
        try:
            # Bot paused state
            paused_resp = (
                self.supabase.table("system_config")
                .select("value")
                .eq("key", "bot_paused")
                .limit(1)
                .execute()
            )
            is_paused = (
                paused_resp.data[0]["value"] == "true" if paused_resp.data else False
            )

            # Trading mode
            mode_resp = (
                self.supabase.table("system_config")
                .select("value")
                .eq("key", "trading_mode")
                .limit(1)
                .execute()
            )
            trading_mode = mode_resp.data[0]["value"] if mode_resp.data else "UNKNOWN"

            # Open positions count
            positions_resp = (
                self.supabase.table("trading_signals")
                .select("id", count="exact")
                .in_("status", ["open", "OPEN", "executed", "EXECUTED"])
                .execute()
            )
            open_count = positions_resp.count or 0

            # Recent unacknowledged alerts
            alerts_resp = (
                self.supabase.table("trading_alerts")
                .select("id", count="exact")
                .is_("acknowledged_at", "null")
                .execute()
            )
            unacked_alerts = alerts_resp.count or 0

            status_icon = "⏸️" if is_paused else "▶️"
            status_text = "PAUSED" if is_paused else "RUNNING"

            return CommandResult(
                success=True,
                message=(
                    f"{status_icon} Bot Status\n"
                    f"State: {status_text}\n"
                    f"Mode: {trading_mode}\n"
                    f"Open positions: {open_count}\n"
                    f"Unacknowledged alerts: {unacked_alerts}"
                ),
            )
        except Exception:
            logger.exception("CommandRouter: /status failed")
            return CommandResult(success=False, message="Could not retrieve status.")

    # ─── Audit log ───────────────────────────────────────────────────────────

    def _audit(
        self,
        platform: str,
        user_id: str,
        command: str,
        args: list[str],
        result: CommandResult,
    ) -> None:
        try:
            self.supabase.table("command_audit_log").insert(
                {
                    "platform": platform,
                    "user_id": str(user_id),
                    "command": command,
                    "args": " ".join(args) if args else None,
                    "result": result.message[:500],
                    "success": result.success,
                }
            ).execute()
        except Exception:
            logger.warning("CommandRouter: failed to write audit log", exc_info=True)
