from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
import os
from typing import Mapping

from dotenv import load_dotenv


DEFAULT_CHANNELS: dict[str, str] = {
    "5m-charts-mechanical": "1240929130980053052",
    "main-pairs": "PASTE_ID",
    "5m-charts-analysis": "PASTE_ID",
    "alt-pairs": "PASTE_ID",
    "30m-signals": "PASTE_ID",
    "5m-signals": "PASTE_ID",
    "6-months-chat": "PASTE_ID",
    "wins": "PASTE_ID",
    "webinars-and-extras": "PASTE_ID",
    "market-breakdowns": "PASTE_ID",
    "daily-forecast": "PASTE_ID",
}

INCOMPLETE_CHANNEL_VALUES = {"", "PASTE_ID", "MISSING", "UNKNOWN"}


@dataclass(frozen=True)
class PipelineSettings:
    discord_authorization: str
    discord_server_id: str
    data_dir: Path = Path("data/rd_concepts")
    channels: Mapping[str, str] = field(default_factory=lambda: DEFAULT_CHANNELS.copy())
    request_timeout_seconds: int = 30
    max_retries: int = 3
    page_limit: int = 100

    def require_discord_authorization(self) -> str:
        if not self.discord_authorization.strip():
            raise ValueError("RD_DISCORD_AUTHORIZATION is required for Discord API calls")
        return self.discord_authorization.strip()


def get_settings() -> PipelineSettings:
    load_dotenv()
    return PipelineSettings(
        discord_authorization=os.getenv("RD_DISCORD_AUTHORIZATION", ""),
        discord_server_id=os.getenv("RD_DISCORD_SERVER_ID", "1160558784314343484"),
        data_dir=Path(os.getenv("RD_DATA_DIR", "data/rd_concepts")),
        channels=DEFAULT_CHANNELS.copy(),
        request_timeout_seconds=int(os.getenv("RD_REQUEST_TIMEOUT_SECONDS", "30")),
        max_retries=int(os.getenv("RD_MAX_RETRIES", "3")),
        page_limit=int(os.getenv("RD_PAGE_LIMIT", "100")),
    )


def configured_channels(settings: PipelineSettings) -> dict[str, str]:
    return {
        name: channel_id
        for name, channel_id in settings.channels.items()
        if channel_id.strip() not in INCOMPLETE_CHANNEL_VALUES
    }
