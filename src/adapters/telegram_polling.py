"""
Telegram long-polling loop for two-way command handling.

Runs as a background thread inside the worker process.
Polls Telegram for new messages and forwards them to CommandRouter.

Usage:
    poller = TelegramPoller(supabase=sb, meta_api=adapter)
    poller.start()   # starts background thread
    poller.stop()    # signals shutdown
"""

import asyncio
import logging
import threading
import time
from typing import Optional

import requests

from config.settings import get_settings

logger = logging.getLogger(__name__)

_POLL_TIMEOUT = 30    # long-poll timeout in seconds
_RETRY_DELAY = 5      # seconds to wait after a failed poll before retrying


class TelegramPoller:
    def __init__(self, supabase, meta_api=None):
        self.supabase = supabase
        self.meta_api = meta_api
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()

    def start(self) -> None:
        """Start the polling loop in a background daemon thread."""
        settings = get_settings()
        if not settings.telegram_bot_token:
            logger.warning("TelegramPoller: TELEGRAM_BOT_TOKEN not set — polling disabled")
            return

        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._run,
            name="TelegramPoller",
            daemon=True,
        )
        self._thread.start()
        logger.info("TelegramPoller: started")

    def stop(self) -> None:
        """Signal the polling loop to stop."""
        self._stop_event.set()
        logger.info("TelegramPoller: stop requested")

    # ─── Internal ────────────────────────────────────────────────────────────

    def _run(self) -> None:
        """Main polling loop — runs in background thread."""
        from src.services.command_router import CommandRouter

        router = CommandRouter(supabase=self.supabase, meta_api=self.meta_api)
        settings = get_settings()
        token = settings.telegram_bot_token
        base_url = f"https://api.telegram.org/bot{token}"
        offset = 0

        while not self._stop_event.is_set():
            try:
                updates = self._get_updates(base_url, offset)
            except Exception:
                logger.warning("TelegramPoller: getUpdates failed, retrying in %ds", _RETRY_DELAY, exc_info=True)
                time.sleep(_RETRY_DELAY)
                continue

            for update in updates:
                update_id = update.get("update_id", 0)
                offset = max(offset, update_id + 1)

                message = update.get("message") or update.get("edited_message")
                if not message:
                    continue

                text = message.get("text", "").strip()
                if not text.startswith("/"):
                    continue

                chat_id = str(message["chat"]["id"])
                user_id = str(message["from"]["id"])

                asyncio.run(
                    router.handle(
                        platform="telegram",
                        user_id=user_id,
                        text=text,
                        reply_fn=lambda reply_text, _chat_id=chat_id, _token=token: self._send_reply(
                            _token, _chat_id, reply_text
                        ),
                    )
                )

    def _get_updates(self, base_url: str, offset: int) -> list[dict]:
        resp = requests.get(
            f"{base_url}/getUpdates",
            params={"offset": offset, "timeout": _POLL_TIMEOUT, "allowed_updates": ["message"]},
            timeout=_POLL_TIMEOUT + 5,
        )
        resp.raise_for_status()
        data = resp.json()
        if not data.get("ok"):
            logger.warning("TelegramPoller: getUpdates not ok: %s", data)
            return []
        return data.get("result", [])

    def _send_reply(self, token: str, chat_id: str, text: str) -> None:
        try:
            requests.post(
                f"https://api.telegram.org/bot{token}/sendMessage",
                json={"chat_id": chat_id, "text": text, "parse_mode": "HTML"},
                timeout=10,
            )
        except Exception:
            logger.warning("TelegramPoller: failed to send reply", exc_info=True)
