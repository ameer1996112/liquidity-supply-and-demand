import json

from scripts.rd_concepts_pipeline import scraper
from scripts.rd_concepts_pipeline.config import PipelineSettings
from scripts.rd_concepts_pipeline.scraper import (
    build_image_filename,
    extract_image_urls,
    next_before_id,
    normalize_message,
    should_retry_status,
)


def test_extract_image_urls_from_attachments_and_embeds() -> None:
    message = {
        "id": "42",
        "attachments": [
            {"id": "a1", "url": "https://cdn/x.png", "content_type": "image/png"},
            {"id": "a2", "url": "https://cdn/readme.txt", "content_type": "text/plain"},
        ],
        "embeds": [
            {"image": {"url": "https://cdn/embed.jpg"}},
            {"thumbnail": {"url": "https://cdn/thumb.webp"}},
        ],
    }

    assert [item["url"] for item in extract_image_urls(message)] == [
        "https://cdn/x.png",
        "https://cdn/embed.jpg",
        "https://cdn/thumb.webp",
    ]


def test_extract_image_urls_skips_none_and_empty_urls() -> None:
    message = {
        "id": "43",
        "attachments": [
            {"id": "a1", "url": None, "content_type": "image/png"},
            {"id": "a2", "url": "", "content_type": "image/png"},
            {"id": "a3", "url": "https://cdn/valid.png", "content_type": "image/png"},
        ],
        "embeds": [
            {"image": {"url": None}},
            {"thumbnail": {"url": ""}},
            {"image": {"url": "https://cdn/embed-valid.jpg"}},
        ],
    }

    assert [item["url"] for item in extract_image_urls(message)] == [
        "https://cdn/valid.png",
        "https://cdn/embed-valid.jpg",
    ]


def test_normalize_message_preserves_required_fields() -> None:
    raw = {
        "id": "100",
        "timestamp": "2026-05-08T08:00:00+00:00",
        "author": {"id": "7", "username": "mentor"},
        "content": "EURUSD long from demand",
        "attachments": [],
        "embeds": [],
    }

    normalized = normalize_message(raw, "main-pairs", "123", [])

    assert normalized["id"] == "100"
    assert normalized["channel"] == "main-pairs"
    assert normalized["author"] == {"id": "7", "username": "mentor"}
    assert normalized["content"] == "EURUSD long from demand"
    assert normalized["images"] == []
    assert normalized["message_url"].endswith("/123/100")


def test_next_before_id_uses_last_message_id() -> None:
    assert next_before_id([{"id": "3"}, {"id": "2"}]) == "2"
    assert next_before_id([]) is None


def test_build_image_filename_uses_message_source_and_extension() -> None:
    filename = build_image_filename(
        "123",
        {"source": "embed_image", "index": "0", "url": "https://cdn/chart.png?x=1"},
    )
    assert filename == "123_embed_image_0.png"


def test_should_retry_status_marks_rate_limits_and_server_errors() -> None:
    assert should_retry_status(429) is True
    assert should_retry_status(500) is True
    assert should_retry_status(403) is False


def test_scrape_channel_persists_forbidden_manifest(monkeypatch, tmp_path) -> None:
    settings = PipelineSettings(
        discord_authorization="token",
        discord_server_id="guild-123",
        data_dir=tmp_path,
        channels={"forbidden-channel": "channel-123"},
    )

    def fake_request_json_with_retries(url, settings, params=None):
        return 403, None

    monkeypatch.setattr(
        scraper,
        "request_json_with_retries",
        fake_request_json_with_retries,
    )

    manifest = scraper.scrape_channel("forbidden-channel", "channel-123", settings)
    channel_dir = tmp_path / "raw" / "forbidden-channel"
    manifest_path = channel_dir / "manifest.json"
    messages_path = channel_dir / "messages.jsonl"

    assert manifest["channel"] == "forbidden-channel"
    assert manifest["channel_id"] == "channel-123"
    assert manifest["status"] == "forbidden"
    assert manifest["scraped_at"]
    assert manifest["message_count"] == 0
    assert manifest["image_failures"] == []
    assert messages_path.exists()
    assert messages_path.read_text(encoding="utf-8") == ""
    assert json.loads(manifest_path.read_text(encoding="utf-8")) == manifest
