from __future__ import annotations

from typing import Any

IMAGE_CONTENT_PREFIX = "image/"


def extract_image_urls(message: dict[str, Any]) -> list[dict[str, str]]:
    images: list[dict[str, str]] = []
    for index, attachment in enumerate(message.get("attachments") or []):
        content_type = str(attachment.get("content_type", ""))
        url = str(attachment.get("url", ""))
        if url and content_type.startswith(IMAGE_CONTENT_PREFIX):
            images.append({"source": "attachment", "index": str(index), "url": url})
    for index, embed in enumerate(message.get("embeds") or []):
        for key in ("image", "thumbnail"):
            url = str((embed.get(key) or {}).get("url", ""))
            if url:
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
