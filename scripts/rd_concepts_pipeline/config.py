from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
import os
from typing import Mapping

from dotenv import load_dotenv


DEFAULT_CHANNELS: dict[str, str] = {
    "5m-charts-mechanical": "1240929130980053052",
    "main-pairs": "1249703205894361109",
    "5m-charts-analysis": "1485539713011028029",
    "alt-pairs": "1351594896611344415",
    "30m-signals": "1160558866807922729",
    "5m-signals": "1400356518070583428",
    "6-months-chat": "1341700060609642546",
    "wins": "1162800326915666041",
    "webinars-and-extras": "1169627155798446172",
    "market-breakdowns": "1246790498304262164",
    "daily-forecast": "1219165120622493756",
    "rules": "1160559454849351720",
    "watch-first": "1163500988162916462",
    "webinar-questions": "1211048857908285460",
    "mechanical-style-lives": "1481266322150133892",
    "analysis-style-lives": "1404330713544790066",
    "tp-and-news-rules": "1162008394551537665",
    "backtest-charts": "1253261006776303617",
    "1-to-1-mentoring-open": "1234804480176820284",
    "liquidity-distances": "1324438480134340679",
    "30-day-challenge-1": "1402195445002014801",
    "30-day-challenge-2": "1480811504852008981",
}

INCOMPLETE_CHANNEL_VALUES = {"", "PASTE_ID", "MISSING", "UNKNOWN"}
PACKAGE_ENV_PATH = Path(__file__).with_name(".env")


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
    load_dotenv(PACKAGE_ENV_PATH)
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
        name: channel_id.strip()
        for name, channel_id in settings.channels.items()
        if channel_id.strip() not in INCOMPLETE_CHANNEL_VALUES
    }
