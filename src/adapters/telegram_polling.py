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
_CONFLICT_RETRY_DELAY = 30  # longer backoff when another instance is polling (409)


class TelegramPoller:
    def __init__(self, supabase, meta_api=None):
        self.supabase = supabase
        self.meta_api = meta_api
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        # Track whether we've already warned about a 409 conflict in this
        # polling episode so we don't spam WARNING every 30 s.
        self._conflict_warned: bool = False

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

    def _delete_webhook(self, base_url: str) -> None:
        """Delete any registered Telegram webhook so long-polling can work."""
        try:
            resp = requests.get(f"{base_url}/deleteWebhook", timeout=10)
            if resp.ok:
                logger.info("TelegramPoller: webhook deleted (polling mode active)")
            else:
                logger.warning("TelegramPoller: deleteWebhook returned %s", resp.status_code)
        except Exception as exc:
            logger.warning("TelegramPoller: deleteWebhook failed: %s", exc)

    def _run(self) -> None:
        """Main polling loop — runs in background thread."""
        from src.services.command_router import CommandRouter

        router = CommandRouter(supabase=self.supabase, meta_api=self.meta_api)
        settings = get_settings()
        token = settings.telegram_bot_token
        base_url = f"https://api.telegram.org/bot{token}"
        offset = 0

        # Clear any registered webhook before starting long-polling.
        # A registered webhook and getUpdates cannot coexist — Telegram returns 409.
        self._delete_webhook(base_url)

        while not self._stop_event.is_set():
            try:
                updates = self._get_updates(base_url, offset)
            except requests.exceptions.HTTPError as exc:
                if exc.response is not None and exc.response.status_code == 409:
                    # Another instance is already polling. Back off and let it run.
                    # deleteWebhook won't help here — the conflict is between two pollers.
                    # Only log once as WARNING per conflict episode; subsequent retries
                    # are downgraded to DEBUG to avoid spamming logs every 30 s.
                    if not self._conflict_warned:
                        logger.warning(
                            "TelegramPoller: 409 Conflict — another instance is polling. "
                            "Retrying every %ds until resolved. Ensure only one worker instance is running.",
                            _CONFLICT_RETRY_DELAY,
                        )
                        self._conflict_warned = True
                    else:
                        logger.debug(
                            "TelegramPoller: still 409 — waiting for other poller to stop (retry in %ds)",
                            _CONFLICT_RETRY_DELAY,
                        )
                    time.sleep(_CONFLICT_RETRY_DELAY)
                else:
                    logger.warning("TelegramPoller: getUpdates failed, retrying in %ds", _RETRY_DELAY, exc_info=True)
                    time.sleep(_RETRY_DELAY)
                continue
            except Exception:
                logger.warning("TelegramPoller: getUpdates failed, retrying in %ds", _RETRY_DELAY, exc_info=True)
                time.sleep(_RETRY_DELAY)
                continue

            # A successful round of getUpdates means the conflict has ended — reset flag.
            if self._conflict_warned:
                logger.info("TelegramPoller: 409 conflict resolved — polling resumed normally.")
                self._conflict_warned = False

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
