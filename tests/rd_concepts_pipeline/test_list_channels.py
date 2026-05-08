from __future__ import annotations

import json
from typing import Any

import pytest

from scripts.rd_concepts_pipeline import list_channels
from scripts.rd_concepts_pipeline.list_channels import normalize_channel


def test_normalize_channel_keeps_text_channel_fields() -> None:
    raw = {"id": "123", "name": "main-pairs", "type": 0, "parent_id": "999"}
    assert normalize_channel(raw) == {
        "id": "123",
        "name": "main-pairs",
        "type": 0,
        "parent_id": "999",
    }


def test_normalize_channel_converts_numeric_parent_id_to_string() -> None:
    raw = {"id": 123, "name": "main-pairs", "type": 0, "parent_id": 999}
    assert normalize_channel(raw) == {
        "id": "123",
        "name": "main-pairs",
        "type": 0,
        "parent_id": "999",
    }


def test_normalize_channel_preserves_missing_or_null_parent_id() -> None:
    assert normalize_channel({"id": "123", "name": "main-pairs", "type": 0}) == {
        "id": "123",
        "name": "main-pairs",
        "type": 0,
        "parent_id": None,
    }
    assert normalize_channel(
        {"id": "123", "name": "main-pairs", "type": 0, "parent_id": None}
    ) == {
        "id": "123",
        "name": "main-pairs",
        "type": 0,
        "parent_id": None,
    }


def test_fetch_channels_filters_visible_channel_types(monkeypatch: pytest.MonkeyPatch) -> None:
    class Settings:
        discord_server_id = "guild-123"
        request_timeout_seconds = 10

        def require_discord_authorization(self) -> str:
            return "Bearer token"

    class Response:
        status_code = 200
        text = ""

        def json(self) -> list[dict[str, Any]]:
            return [
                {"id": "1", "name": "text", "type": 0, "parent_id": None},
                {"id": "2", "name": "voice", "type": 2, "parent_id": None},
                {"id": "3", "name": "forum", "type": 15, "parent_id": "9"},
            ]

    def fake_get(url: str, *, headers: dict[str, str], timeout: int) -> Response:
        assert url == f"{list_channels.DISCORD_API}/guilds/guild-123/channels"
        assert headers == {"Authorization": "Bearer token"}
        assert timeout == 10
        return Response()

    monkeypatch.setattr(list_channels, "get_settings", lambda: Settings())
    monkeypatch.setattr(list_channels.requests, "get", fake_get)

    assert list_channels.fetch_channels() == [
        {"id": "1", "name": "text", "type": 0, "parent_id": None},
        {"id": "3", "name": "forum", "type": 15, "parent_id": "9"},
    ]


def test_main_prints_json_output(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(
        list_channels,
        "fetch_channels",
        lambda: [
            {"id": "2", "name": "z-channel", "type": 0, "parent_id": None},
            {"id": "1", "name": "a-channel", "type": 15, "parent_id": "9"},
        ],
    )
    monkeypatch.setattr("sys.argv", ["list_channels.py", "--json"])

    assert list_channels.main() == 0

    captured = capsys.readouterr()
    assert json.loads(captured.out) == [
        {"id": "1", "name": "a-channel", "type": 15, "parent_id": "9"},
        {"id": "2", "name": "z-channel", "type": 0, "parent_id": None},
    ]
    assert captured.err == ""


def test_main_prints_text_output(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(
        list_channels,
        "fetch_channels",
        lambda: [{"id": "1", "name": "main-pairs", "type": 0, "parent_id": None}],
    )
    monkeypatch.setattr("sys.argv", ["list_channels.py"])

    assert list_channels.main() == 0

    captured = capsys.readouterr()
    assert captured.out == "main-pairs: 1 (type=0)\n"
    assert captured.err == ""


def test_main_redacts_cli_errors(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    token = "abcdefghijklmnopqrstuv.abcdef.abcdefghijklmnopqrstuv"

    def fail_fetch() -> list[dict[str, Any]]:
        raise RuntimeError(f"Discord failed with {token}")

    monkeypatch.setattr(list_channels, "fetch_channels", fail_fetch)
    monkeypatch.setattr("sys.argv", ["list_channels.py"])

    assert list_channels.main() == 1

    captured = capsys.readouterr()
    assert captured.out == ""
    assert "error: Discord failed with [REDACTED]\n" == captured.err
    assert token not in captured.err


def test_main_collapses_cli_error_whitespace(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    token = "abcdefghijklmnopqrstuv.abcdef.abcdefghijklmnopqrstuv"

    def fail_fetch() -> list[dict[str, Any]]:
        raise RuntimeError(f"Discord failed\nwith\t {token}\nsecond line")

    monkeypatch.setattr(list_channels, "fetch_channels", fail_fetch)
    monkeypatch.setattr("sys.argv", ["list_channels.py"])

    assert list_channels.main() == 1

    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == "error: Discord failed with [REDACTED] second line\n"
    assert token not in captured.err
