from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import requests

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from scripts.rd_concepts_pipeline.common import get_logger, redact
from scripts.rd_concepts_pipeline.config import get_settings

LOGGER = get_logger("rd_concepts.list_channels")
DISCORD_API = "https://discord.com/api/v10"
VISIBLE_CHANNEL_TYPES = {0, 5, 10, 11, 12, 15, 16}


def normalize_channel(raw: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": str(raw.get("id", "")),
        "name": str(raw.get("name", "")),
        "type": int(raw.get("type", -1)),
        "parent_id": raw.get("parent_id"),
    }


def fetch_channels() -> list[dict[str, Any]]:
    settings = get_settings()
    authorization = settings.require_discord_authorization()
    url = f"{DISCORD_API}/guilds/{settings.discord_server_id}/channels"
    response = requests.get(
        url,
        headers={"Authorization": authorization},
        timeout=settings.request_timeout_seconds,
    )
    if response.status_code >= 400:
        raise RuntimeError(
            redact(f"Discord channel list failed {response.status_code}: {response.text[:500]}")
        )
    channels = [normalize_channel(item) for item in response.json()]
    return [channel for channel in channels if channel["type"] in VISIBLE_CHANNEL_TYPES]


def main() -> int:
    parser = argparse.ArgumentParser(description="List visible Discord channels for RD Concepts.")
    parser.add_argument("--json", action="store_true", help="Print JSON instead of text.")
    args = parser.parse_args()
    try:
        channels = sorted(fetch_channels(), key=lambda item: item["name"])
    except (RuntimeError, ValueError, requests.RequestException, json.JSONDecodeError) as exc:
        print(f"error: {redact(str(exc))}", file=sys.stderr)
        return 1
    if args.json:
        print(json.dumps(channels, indent=2, sort_keys=True))
    else:
        for channel in channels:
            print(f"{channel['name']}: {channel['id']} (type={channel['type']})")
    LOGGER.info("Listed %s visible channels", len(channels))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
