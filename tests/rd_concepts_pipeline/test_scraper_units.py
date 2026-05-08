import json

import requests

from scripts.rd_concepts_pipeline import scraper
from scripts.rd_concepts_pipeline.config import PipelineSettings
from scripts.rd_concepts_pipeline.scraper import (
    build_image_filename,
    extract_image_urls,
    next_before_id,
    normalize_message,
    should_retry_status,
)


class FakeResponse:
    def __init__(
        self,
        status_code: int,
        payload=None,
        text: str = "",
        content: bytes = b"",
        headers: dict[str, str] | None = None,
        chunks: list[bytes] | None = None,
        json_exc: Exception | None = None,
    ) -> None:
        self.status_code = status_code
        self._payload = payload
        self.text = text
        self.content = content
        self.headers = headers or {}
        self._chunks = chunks
        self._json_exc = json_exc

    def json(self):
        if self._json_exc is not None:
            raise self._json_exc
        return self._payload

    def iter_content(self, chunk_size=1):
        if self._chunks is not None:
            yield from self._chunks
            return
        for index in range(0, len(self.content), chunk_size):
            yield self.content[index : index + chunk_size]


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


def test_parse_retry_after_clamps_unsafe_values() -> None:
    assert scraper.parse_retry_after(
        FakeResponse(429, payload={"retry_after": -1})
    ) == 1.0
    assert scraper.parse_retry_after(
        FakeResponse(429, payload={"retry_after": "NaN"})
    ) == 1.0
    assert scraper.parse_retry_after(
        FakeResponse(429, payload={"retry_after": 9999})
    ) == 60.0


def test_download_image_does_not_send_authorization_header(monkeypatch, tmp_path) -> None:
    settings = PipelineSettings(
        discord_authorization="secret-token",
        discord_server_id="guild-123",
        data_dir=tmp_path,
    )
    seen_headers = []

    def fake_get(url, **kwargs):
        seen_headers.append(kwargs.get("headers"))
        assert kwargs["stream"] is True
        return FakeResponse(200, content=b"image-bytes")

    monkeypatch.setattr(scraper.requests, "get", fake_get)

    assert scraper.download_image(
        "https://images.example/chart.png",
        tmp_path / "chart.png",
        settings,
    )
    assert seen_headers == [None]


def test_download_image_rejects_non_image_content_type(monkeypatch, tmp_path) -> None:
    settings = PipelineSettings(
        discord_authorization="secret-token",
        discord_server_id="guild-123",
        data_dir=tmp_path,
    )

    def fake_get(url, **kwargs):
        return FakeResponse(
            200,
            content=b"not-image",
            headers={"content-type": "text/html; charset=utf-8"},
        )

    monkeypatch.setattr(scraper.requests, "get", fake_get)

    output_path = tmp_path / "chart.png"
    assert (
        scraper.download_image("https://images.example/chart.png", output_path, settings)
        is False
    )
    assert not output_path.exists()
    assert not output_path.with_name("chart.png.part").exists()


def test_download_image_rejects_oversized_stream(monkeypatch, tmp_path) -> None:
    settings = PipelineSettings(
        discord_authorization="secret-token",
        discord_server_id="guild-123",
        data_dir=tmp_path,
    )

    def fake_get(url, **kwargs):
        return FakeResponse(
            200,
            headers={"content-type": "image/png"},
            chunks=[b"a" * 4, b"b" * 4],
        )

    monkeypatch.setattr(scraper.requests, "get", fake_get)
    monkeypatch.setattr(scraper, "MAX_IMAGE_BYTES", 6)

    output_path = tmp_path / "chart.png"
    assert (
        scraper.download_image("https://images.example/chart.png", output_path, settings)
        is False
    )
    assert not output_path.exists()
    assert not output_path.with_name("chart.png.part").exists()


def test_request_json_with_retries_retries_timeout_then_succeeds(monkeypatch, tmp_path) -> None:
    settings = PipelineSettings(
        discord_authorization="secret-token",
        discord_server_id="guild-123",
        data_dir=tmp_path,
    )
    responses = [
        requests.Timeout("slow"),
        FakeResponse(200, payload=[{"id": "1"}]),
    ]

    def fake_get(url, **kwargs):
        item = responses.pop(0)
        if isinstance(item, Exception):
            raise item
        return item

    monkeypatch.setattr(scraper.requests, "get", fake_get)
    monkeypatch.setattr(scraper.time, "sleep", lambda delay: None)

    assert scraper.request_json_with_retries(
        "https://discord.example/messages",
        settings,
    ) == (200, [{"id": "1"}])


def test_request_json_with_retries_uses_default_sleep_for_malformed_429(
    monkeypatch,
    tmp_path,
) -> None:
    settings = PipelineSettings(
        discord_authorization="secret-token",
        discord_server_id="guild-123",
        data_dir=tmp_path,
    )
    responses = [
        FakeResponse(429, json_exc=ValueError("not json")),
        FakeResponse(200, payload=[]),
    ]
    sleeps = []

    def fake_get(url, **kwargs):
        return responses.pop(0)

    monkeypatch.setattr(scraper.requests, "get", fake_get)
    monkeypatch.setattr(scraper.time, "sleep", lambda delay: sleeps.append(delay))

    assert scraper.request_json_with_retries(
        "https://discord.example/messages",
        settings,
    ) == (200, [])
    assert sleeps == [1.0]


def test_download_image_returns_false_after_repeated_connection_errors(
    monkeypatch,
    tmp_path,
) -> None:
    settings = PipelineSettings(
        discord_authorization="secret-token",
        discord_server_id="guild-123",
        data_dir=tmp_path,
    )

    def fake_get(url, **kwargs):
        raise requests.ConnectionError("offline")

    monkeypatch.setattr(scraper.requests, "get", fake_get)
    monkeypatch.setattr(scraper.time, "sleep", lambda delay: None)

    assert (
        scraper.download_image(
            "https://images.example/chart.png",
            tmp_path / "chart.png",
            settings,
        )
        is False
    )
