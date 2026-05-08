from scripts.rd_concepts_pipeline.scraper import (
    extract_image_urls,
    next_before_id,
    normalize_message,
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
