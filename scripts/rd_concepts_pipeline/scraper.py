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
from scripts.rd_concepts_pipeline.list_channels import fetch_channels

IMAGE_CONTENT_PREFIX = "image/"
DISCORD_API = "https://discord.com/api/v10"
IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp", ".gif"}
FILE_SUFFIXES = {
    ".csv",
    ".doc",
    ".docx",
    ".html",
    ".pdf",
    ".ppt",
    ".pptx",
    ".txt",
    ".xls",
    ".xlsm",
    ".xlsx",
}
MESSAGE_CHANNEL_TYPES = {0, 5, 10, 11, 12}
MAX_RETRY_AFTER_SECONDS = 60.0
LOGGER = get_logger("rd_concepts.scraper")
DEFAULT_TRADING_KEYWORDS = [
    "EURUSD",
    "GBPUSD",
    "AUDUSD",
    "NZDUSD",
    "USDJPY",
    "EURJPY",
    "GBPJPY",
    "NZDJPY",
    "AUDJPY",
    "USDCAD",
    "USDCHF",
    "XAUUSD",
    "GOLD",
    "NAS100",
    "US30",
    "LONG",
    "SHORT",
    "BUY",
    "SELL",
    "BULLISH",
    "BEARISH",
    "ENTRY",
    "TP",
    "SL",
    "STOP",
    "TARGET",
    "SETUP",
    "CONFLUENCE",
    "LIQUIDITY",
    "SWEEP",
    "BOS",
    "CHOCH",
    "DISPLACEMENT",
    "IMBALANCE",
    "FVG",
    "FAIR VALUE GAP",
    "ORDER BLOCK",
    "DEMAND",
    "SUPPLY",
    "MECHANICAL",
    "FORECAST",
    "BACKTEST",
    "BACKTESTING",
    "SPREADSHEET",
    "SHEET",
    "LIQUIDITY DISTANCE",
    "DISTANCES",
    "NEWS",
    "TP RULE",
    "PDF",
    "XLSX",
    "CSV",
]
DEFAULT_EDUCATION_KEYWORDS = [
    "RULE",
    "RULES",
    "SETUP",
    "ENTRY",
    "CONFLUENCE",
    "STRUCTURE",
    "MECHANICAL",
    "ANALYSIS",
    "CONDITION",
    "MUST",
    "ALWAYS",
    "NEVER",
    "5M",
    "30M",
    "EMA",
    "FIB",
    "LIQUIDITY",
    "LIQUIDITY DISTANCE",
    "DISTANCE",
    "DISTANCES",
    "BOS",
    "CHOCH",
    "SWEEP",
    "DISPLACEMENT",
    "IMBALANCE",
    "OB",
    "ORDER BLOCK",
    "FAIR VALUE GAP",
    "FVG",
    "PD ARRAY",
    "TP",
    "STOP LOSS",
    "NEWS",
    "BACKTEST",
    "BACKTESTING",
    "SPREADSHEET",
    "SHEET",
    "XLSX",
    "CSV",
    "PDF",
    "WEBINAR",
    "MENTORING",
]


def should_retry_status(status_code: int) -> bool:
    return status_code == 429 or 500 <= status_code <= 599


def build_image_filename(message_id: str, image: dict[str, str]) -> str:
    parsed = urlparse(image["url"])
    suffix = Path(parsed.path).suffix.lower()
    if suffix not in IMAGE_SUFFIXES:
        suffix = ".img"
    base = safe_filename(f"{message_id}_{image['source']}_{image['index']}")
    return f"{base}{suffix}"


def build_file_filename(message_id: str, file_item: dict[str, str]) -> str:
    suffix = Path(file_item.get("filename", "")).suffix.lower()
    if suffix not in FILE_SUFFIXES:
        suffix = Path(urlparse(file_item["url"]).path).suffix.lower()
    if suffix not in FILE_SUFFIXES:
        suffix = ".bin"
    stem = Path(file_item.get("filename", "")).stem or f"{file_item['source']}_{file_item['index']}"
    base = safe_filename(f"{message_id}_{stem}")
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


def download_file(url: str, output_path: Path, settings: PipelineSettings) -> bool:
    ensure_dir(output_path.parent)
    for attempt in range(1, settings.max_retries + 1):
        try:
            response = requests.get(url, timeout=settings.request_timeout_seconds)
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
                "File download failed %s for %s",
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


def extract_file_urls(message: dict[str, Any]) -> list[dict[str, str]]:
    files: list[dict[str, str]] = []
    for index, attachment in enumerate(message.get("attachments") or []):
        content_type = str(attachment.get("content_type", ""))
        url = attachment.get("url")
        filename = str(attachment.get("filename") or "")
        suffix = Path(filename).suffix.lower()
        if not isinstance(url, str) or not url:
            continue
        if content_type.startswith(IMAGE_CONTENT_PREFIX):
            continue
        if suffix in FILE_SUFFIXES or content_type:
            files.append(
                {
                    "source": "attachment",
                    "index": str(index),
                    "url": url,
                    "filename": filename,
                    "content_type": content_type,
                }
            )
    return files


def normalize_keyword_filters(values: list[str] | None) -> list[str]:
    keywords: list[str] = []
    seen: set[str] = set()
    for value in values or []:
        for part in value.split(","):
            keyword = part.strip()
            key = keyword.casefold()
            if keyword and key not in seen:
                keywords.append(keyword)
                seen.add(key)
    return keywords


def build_discovered_channel_map(
    channels: list[dict[str, Any]],
) -> dict[str, str]:
    discovered: dict[str, str] = {}
    for channel in channels:
        if channel.get("type") not in MESSAGE_CHANNEL_TYPES:
            continue
        channel_id = str(channel.get("id") or "")
        if not channel_id:
            continue
        base_name = safe_filename(str(channel.get("name") or channel_id))
        channel_name = base_name
        if channel_name in discovered:
            channel_name = f"{base_name}_{channel_id}"
        discovered[channel_name] = channel_id
    return dict(sorted(discovered.items()))


def message_search_text(message: dict[str, Any]) -> str:
    parts = [str(message.get("content") or "")]
    for attachment in message.get("attachments") or []:
        for key in ("filename", "description", "title"):
            value = attachment.get(key)
            if value:
                parts.append(str(value))
    for embed in message.get("embeds") or []:
        for key in ("title", "description", "url"):
            value = embed.get(key)
            if value:
                parts.append(str(value))
        footer = embed.get("footer") or {}
        if footer.get("text"):
            parts.append(str(footer["text"]))
        author = embed.get("author") or {}
        if author.get("name"):
            parts.append(str(author["name"]))
        for field in embed.get("fields") or []:
            if field.get("name"):
                parts.append(str(field["name"]))
            if field.get("value"):
                parts.append(str(field["value"]))
    return "\n".join(parts)


def message_matches_keywords(
    message: dict[str, Any],
    keywords: list[str],
    mode: str = "any",
) -> bool:
    if not keywords:
        return True
    haystack = message_search_text(message).casefold()
    checks = [keyword.casefold() in haystack for keyword in keywords]
    if mode == "all":
        return all(checks)
    return any(checks)


def should_keep_message(
    message: dict[str, Any],
    keywords: list[str],
    mode: str,
    include_image_only: bool,
    image_urls: list[dict[str, str]],
    include_file_only: bool = False,
    file_urls: list[dict[str, str]] | None = None,
) -> bool:
    if message_matches_keywords(message, keywords, mode):
        return True
    if include_image_only and bool(image_urls):
        return True
    return include_file_only and bool(file_urls)


def normalize_message(
    raw: dict[str, Any],
    channel_name: str,
    channel_id: str,
    image_paths: list[str],
    file_paths: list[str] | None = None,
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
        "files": file_paths or [],
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
    keyword_filters: list[str] | None = None,
    keyword_mode: str = "any",
    include_image_only: bool = False,
    include_file_only: bool = False,
    max_pages: int | None = None,
    max_messages: int | None = None,
    download_images: bool = True,
    download_files: bool = False,
) -> dict[str, Any]:
    channel_dir = settings.data_dir / "raw" / channel_name
    image_dir = channel_dir / "images"
    file_dir = channel_dir / "files"
    ensure_dir(image_dir)
    url = f"{DISCORD_API}/channels/{channel_id}/messages"
    before: str | None = None
    all_rows: list[dict[str, Any]] = []
    failures: list[dict[str, str]] = []
    keywords = keyword_filters or []
    page = 0
    fetched_count = 0
    skipped_count = 0

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
        fetched_count += len(messages)
        kept_this_page = 0
        for raw in messages:
            image_urls = extract_image_urls(raw)
            file_urls = extract_file_urls(raw)
            if not should_keep_message(
                raw,
                keywords,
                keyword_mode,
                include_image_only,
                image_urls,
                include_file_only=include_file_only,
                file_urls=file_urls,
            ):
                skipped_count += 1
                continue
            image_paths: list[str] = []
            file_paths: list[str] = []
            for image in image_urls:
                filename = build_image_filename(str(raw.get("id", "")), image)
                output_path = image_dir / filename
                if (
                    dry_run
                    or not download_images
                    or output_path.exists()
                    or download_image(image["url"], output_path, settings)
                ):
                    if dry_run or download_images:
                        image_paths.append(str(output_path))
                else:
                    failures.append(
                        {"message_id": str(raw.get("id", "")), "url": image["url"]}
                    )
            for file_item in file_urls:
                filename = build_file_filename(str(raw.get("id", "")), file_item)
                output_path = file_dir / filename
                if (
                    dry_run
                    or not download_files
                    or output_path.exists()
                    or download_file(file_item["url"], output_path, settings)
                ):
                    if dry_run or download_files:
                        file_paths.append(str(output_path))
                else:
                    failures.append(
                        {"message_id": str(raw.get("id", "")), "url": file_item["url"]}
                    )
            all_rows.append(
                normalize_message(
                    raw,
                    channel_name,
                    channel_id,
                    image_paths,
                    file_paths=file_paths,
                )
            )
            kept_this_page += 1
            if max_messages is not None and len(all_rows) >= max_messages:
                break
        LOGGER.info(
            "%s page %s fetched %s messages, kept %s",
            channel_name,
            page,
            len(messages),
            kept_this_page,
        )
        before = next_before_id(messages)
        if (
            dry_run
            or (max_pages is not None and page >= max_pages)
            or (max_messages is not None and len(all_rows) >= max_messages)
        ):
            break

    write_jsonl(channel_dir / "messages.jsonl", all_rows)
    manifest = {
        "channel": channel_name,
        "channel_id": channel_id,
        "status": "ok",
        "scraped_at": now_iso(),
        "message_count": len(all_rows),
        "fetched_message_count": fetched_count,
        "skipped_message_count": skipped_count,
        "keyword_filters": keywords,
        "keyword_mode": keyword_mode,
        "include_image_only": include_image_only,
        "include_file_only": include_file_only,
        "max_pages": max_pages,
        "max_messages": max_messages,
        "download_images": download_images,
        "download_files": download_files,
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
    parser.add_argument(
        "--all-visible-channels",
        action="store_true",
        help="Discover and scan all visible message channels in the server.",
    )
    parser.add_argument(
        "--trading-only",
        action="store_true",
        help="Keep only messages matching the built-in trading keyword list.",
    )
    parser.add_argument(
        "--education-only",
        action="store_true",
        help="Keep only messages matching the built-in education/rules/backtesting keyword list.",
    )
    parser.add_argument(
        "--keyword",
        action="append",
        default=[],
        help="Keep messages matching this keyword or comma-separated keywords. Repeatable.",
    )
    parser.add_argument(
        "--keyword-mode",
        choices=("any", "all"),
        default="any",
        help="Use any keyword match or require all keyword matches.",
    )
    parser.add_argument(
        "--include-image-only",
        action="store_true",
        help="With keyword filtering, also keep messages that only contain images.",
    )
    parser.add_argument(
        "--include-file-only",
        action="store_true",
        help="With keyword filtering, also keep messages that only contain files.",
    )
    parser.add_argument("--max-pages", type=int, help="Stop each channel after N pages.")
    parser.add_argument(
        "--max-messages",
        type=int,
        help="Stop each channel after saving N kept messages.",
    )
    parser.add_argument(
        "--no-images",
        action="store_true",
        help="Save matching messages without downloading image files.",
    )
    parser.add_argument(
        "--download-files",
        action="store_true",
        help="Download non-image attachments such as PDFs, CSVs, and spreadsheets.",
    )
    args = parser.parse_args()
    if args.max_pages is not None and args.max_pages < 1:
        parser.error("--max-pages must be 1 or greater")
    if args.max_messages is not None and args.max_messages < 1:
        parser.error("--max-messages must be 1 or greater")
    if args.channel and args.all_visible_channels:
        parser.error("--channel cannot be combined with --all-visible-channels")
    keyword_filters = normalize_keyword_filters(args.keyword)
    if args.trading_only:
        keyword_filters = normalize_keyword_filters(
            [*DEFAULT_TRADING_KEYWORDS, *keyword_filters]
        )
    if args.education_only:
        keyword_filters = normalize_keyword_filters(
            [*DEFAULT_EDUCATION_KEYWORDS, *keyword_filters]
        )
    if (
        args.all_visible_channels
        and not keyword_filters
        and not args.include_image_only
        and not args.include_file_only
    ):
        parser.error(
            "--all-visible-channels requires --keyword, --trading-only, "
            "--education-only, --include-image-only, or --include-file-only"
        )
    settings = get_settings()
    channels = (
        build_discovered_channel_map(fetch_channels())
        if args.all_visible_channels
        else configured_channels(settings)
    )
    if args.channel:
        channels = {args.channel: channels[args.channel]}
    summaries = [
        scrape_channel(
            name,
            channel_id,
            settings,
            dry_run=args.dry_run,
            keyword_filters=keyword_filters,
            keyword_mode=args.keyword_mode,
            include_image_only=args.include_image_only,
            include_file_only=args.include_file_only,
            max_pages=args.max_pages,
            max_messages=args.max_messages,
            download_images=not args.no_images,
            download_files=args.download_files,
        )
        for name, channel_id in channels.items()
    ]
    LOGGER.info("Scrape summary: %s", json.dumps(summaries, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
