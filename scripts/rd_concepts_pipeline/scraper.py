from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
import sys
import time
from typing import Any
from urllib.parse import urlparse

import requests

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from scripts.rd_concepts_pipeline.common import (
    ensure_dir,
    get_logger,
    now_iso,
    redact,
    safe_filename,
    write_jsonl,
)
from scripts.rd_concepts_pipeline.config import (
    PipelineSettings,
    configured_channels,
    get_settings,
)

IMAGE_CONTENT_PREFIX = "image/"
DISCORD_API = "https://discord.com/api/v10"
IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp", ".gif"}
MAX_RETRY_AFTER_SECONDS = 60.0
LOGGER = get_logger("rd_concepts.scraper")


def should_retry_status(status_code: int) -> bool:
    return status_code == 429 or 500 <= status_code <= 599


def build_image_filename(message_id: str, image: dict[str, str]) -> str:
    parsed = urlparse(image["url"])
    suffix = Path(parsed.path).suffix.lower()
    if suffix not in IMAGE_SUFFIXES:
        suffix = ".img"
    base = safe_filename(f"{message_id}_{image['source']}_{image['index']}")
    return f"{base}{suffix}"


def parse_retry_after(response: requests.Response) -> float:
    try:
        retry_after = response.json().get("retry_after", 1.0)
        parsed = float(retry_after)
    except (TypeError, ValueError, AttributeError, json.JSONDecodeError):
        return 1.0
    if not math.isfinite(parsed) or parsed < 0:
        return 1.0
    return min(parsed, MAX_RETRY_AFTER_SECONDS)


def request_json_with_retries(
    url: str,
    settings: PipelineSettings,
    params: dict[str, Any] | None = None,
) -> tuple[int, Any]:
    headers = {"Authorization": settings.require_discord_authorization()}
    last_error: requests.RequestException | None = None
    for attempt in range(1, settings.max_retries + 1):
        try:
            response = requests.get(
                url,
                headers=headers,
                params=params,
                timeout=settings.request_timeout_seconds,
            )
        except requests.RequestException as exc:
            last_error = exc
            if attempt < settings.max_retries:
                time.sleep(min(attempt * 2, 10))
                continue
            break
        if response.status_code == 429:
            retry_after = parse_retry_after(response)
            LOGGER.warning("Rate limited for %.2fs on %s", retry_after, redact(url))
            time.sleep(retry_after)
            continue
        if response.status_code == 403:
            return response.status_code, None
        if should_retry_status(response.status_code) and attempt < settings.max_retries:
            time.sleep(min(attempt * 2, 10))
            continue
        if response.status_code >= 400:
            raise RuntimeError(
                redact(
                    f"Discord request failed {response.status_code}: "
                    f"{response.text[:500]}"
                )
            )
        return response.status_code, response.json()
    if last_error is not None:
        raise RuntimeError(
            redact(f"Discord request exhausted retries: {url}: {last_error}")
        ) from last_error
    raise RuntimeError(redact(f"Discord request exhausted retries: {url}"))


def download_image(url: str, output_path: Path, settings: PipelineSettings) -> bool:
    ensure_dir(output_path.parent)
    for attempt in range(1, settings.max_retries + 1):
        try:
            response = requests.get(
                url,
                timeout=settings.request_timeout_seconds,
            )
        except requests.RequestException:
            if attempt < settings.max_retries:
                time.sleep(min(attempt * 2, 10))
                continue
            return False
        if response.status_code == 429:
            retry_after = parse_retry_after(response)
            time.sleep(retry_after)
            continue
        if should_retry_status(response.status_code) and attempt < settings.max_retries:
            time.sleep(min(attempt * 2, 10))
            continue
        if response.status_code >= 400:
            LOGGER.warning(
                "Image download failed %s for %s",
                response.status_code,
                redact(url),
            )
            return False
        output_path.write_bytes(response.content)
        return True
    return False


def extract_image_urls(message: dict[str, Any]) -> list[dict[str, str]]:
    images: list[dict[str, str]] = []
    for index, attachment in enumerate(message.get("attachments") or []):
        content_type = str(attachment.get("content_type", ""))
        url = attachment.get("url")
        if isinstance(url, str) and url and content_type.startswith(IMAGE_CONTENT_PREFIX):
            images.append({"source": "attachment", "index": str(index), "url": url})
    for index, embed in enumerate(message.get("embeds") or []):
        for key in ("image", "thumbnail"):
            url = (embed.get(key) or {}).get("url")
            if isinstance(url, str) and url:
                images.append({"source": f"embed_{key}", "index": str(index), "url": url})
    return images


def normalize_message(
    raw: dict[str, Any],
    channel_name: str,
    channel_id: str,
    image_paths: list[str],
) -> dict[str, Any]:
    author = raw.get("author") or {}
    message_id = str(raw.get("id", ""))
    return {
        "id": message_id,
        "channel": channel_name,
        "channel_id": channel_id,
        "timestamp": raw.get("timestamp"),
        "author": {
            "id": str(author.get("id", "")),
            "username": str(author.get("username", "")),
        },
        "content": raw.get("content", ""),
        "attachments": raw.get("attachments") or [],
        "embeds": raw.get("embeds") or [],
        "images": image_paths,
        "message_url": f"https://discord.com/channels/@me/{channel_id}/{message_id}",
        "raw": raw,
    }


def next_before_id(messages: list[dict[str, Any]]) -> str | None:
    if not messages:
        return None
    return str(messages[-1].get("id", "")) or None


def scrape_channel(
    channel_name: str,
    channel_id: str,
    settings: PipelineSettings,
    dry_run: bool = False,
) -> dict[str, Any]:
    channel_dir = settings.data_dir / "raw" / channel_name
    image_dir = channel_dir / "images"
    ensure_dir(image_dir)
    url = f"{DISCORD_API}/channels/{channel_id}/messages"
    before: str | None = None
    all_rows: list[dict[str, Any]] = []
    failures: list[dict[str, str]] = []
    page = 0

    while True:
        params = {"limit": settings.page_limit}
        if before:
            params["before"] = before
        status_code, messages = request_json_with_retries(url, settings, params=params)
        if status_code == 403:
            LOGGER.warning("Skipping %s: Discord returned 403", channel_name)
            write_jsonl(channel_dir / "messages.jsonl", [])
            manifest = {
                "channel": channel_name,
                "channel_id": channel_id,
                "status": "forbidden",
                "scraped_at": now_iso(),
                "message_count": 0,
                "image_failures": [],
            }
            (channel_dir / "manifest.json").write_text(
                json.dumps(manifest, indent=2, sort_keys=True),
                encoding="utf-8",
            )
            return manifest
        if not messages:
            break
        page += 1
        LOGGER.info("%s page %s fetched %s messages", channel_name, page, len(messages))
        for raw in messages:
            image_paths: list[str] = []
            for image in extract_image_urls(raw):
                filename = build_image_filename(str(raw.get("id", "")), image)
                output_path = image_dir / filename
                if (
                    dry_run
                    or output_path.exists()
                    or download_image(image["url"], output_path, settings)
                ):
                    image_paths.append(str(output_path))
                else:
                    failures.append(
                        {"message_id": str(raw.get("id", "")), "url": image["url"]}
                    )
            all_rows.append(normalize_message(raw, channel_name, channel_id, image_paths))
        before = next_before_id(messages)
        if dry_run:
            break

    write_jsonl(channel_dir / "messages.jsonl", all_rows)
    manifest = {
        "channel": channel_name,
        "channel_id": channel_id,
        "status": "ok",
        "scraped_at": now_iso(),
        "message_count": len(all_rows),
        "image_failures": failures,
    }
    (channel_dir / "manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Scrape RD Concepts Discord messages and images."
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Fetch one page per configured channel without downloading images.",
    )
    parser.add_argument("--channel", help="Only scrape one configured channel name.")
    args = parser.parse_args()
    settings = get_settings()
    channels = configured_channels(settings)
    if args.channel:
        channels = {args.channel: channels[args.channel]}
    summaries = [
        scrape_channel(name, channel_id, settings, dry_run=args.dry_run)
        for name, channel_id in channels.items()
    ]
    LOGGER.info("Scrape summary: %s", json.dumps(summaries, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
