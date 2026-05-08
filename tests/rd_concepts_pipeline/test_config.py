from pathlib import Path

import pytest

from scripts.rd_concepts_pipeline import config
from scripts.rd_concepts_pipeline.config import (
    PipelineSettings,
    configured_channels,
    get_settings,
)


def test_configured_channels_skips_incomplete_ids() -> None:
    settings = PipelineSettings(
        discord_authorization="secret",
        discord_server_id="1160558784314343484",
        data_dir=Path("data/rd_concepts"),
        channels={
            "5m-charts-mechanical": " 1240929130980053052 ",
            "main-pairs": "PASTE_ID",
            "blank": "",
        },
    )

    assert configured_channels(settings) == {
        "5m-charts-mechanical": "1240929130980053052"
    }


def test_settings_requires_authorization_for_live_calls() -> None:
    settings = PipelineSettings(
        discord_authorization="",
        discord_server_id="1160558784314343484",
        data_dir=Path("data/rd_concepts"),
        channels={"5m-charts-mechanical": "1240929130980053052"},
    )

    with pytest.raises(ValueError, match="RD_DISCORD_AUTHORIZATION"):
        settings.require_discord_authorization()


def test_get_settings_loads_package_env_and_parses_values(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    env_path = tmp_path / ".env"
    env_path.write_text(
        "\n".join(
            [
                "RD_DISCORD_AUTHORIZATION=from-local-env",
                "RD_DISCORD_SERVER_ID=987654321",
                "RD_DATA_DIR=tmp/rd_data",
                "RD_REQUEST_TIMEOUT_SECONDS=45",
                "RD_MAX_RETRIES=5",
                "RD_PAGE_LIMIT=50",
            ]
        ),
        encoding="utf-8",
    )
    for key in (
        "RD_DISCORD_AUTHORIZATION",
        "RD_DISCORD_SERVER_ID",
        "RD_DATA_DIR",
        "RD_REQUEST_TIMEOUT_SECONDS",
        "RD_MAX_RETRIES",
        "RD_PAGE_LIMIT",
    ):
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setattr(config, "PACKAGE_ENV_PATH", env_path)

    settings = get_settings()

    assert settings.discord_authorization == "from-local-env"
    assert settings.discord_server_id == "987654321"
    assert settings.data_dir == Path("tmp/rd_data")
    assert settings.request_timeout_seconds == 45
    assert settings.max_retries == 5
    assert settings.page_limit == 50


def test_get_settings_preserves_explicit_env_over_package_env(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    env_path = tmp_path / ".env"
    env_path.write_text(
        "\n".join(
            [
                "RD_DISCORD_AUTHORIZATION=from-local-env",
                "RD_DISCORD_SERVER_ID=987654321",
                "RD_DATA_DIR=tmp/rd_data",
                "RD_REQUEST_TIMEOUT_SECONDS=45",
                "RD_MAX_RETRIES=5",
                "RD_PAGE_LIMIT=50",
            ]
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(config, "PACKAGE_ENV_PATH", env_path)
    monkeypatch.setenv("RD_DISCORD_AUTHORIZATION", "from-process-env")
    monkeypatch.setenv("RD_DISCORD_SERVER_ID", "123456789")
    monkeypatch.setenv("RD_DATA_DIR", "tmp/process_rd_data")
    monkeypatch.setenv("RD_REQUEST_TIMEOUT_SECONDS", "60")
    monkeypatch.setenv("RD_MAX_RETRIES", "7")
    monkeypatch.setenv("RD_PAGE_LIMIT", "25")

    settings = get_settings()

    assert settings.discord_authorization == "from-process-env"
    assert settings.discord_server_id == "123456789"
    assert settings.data_dir == Path("tmp/process_rd_data")
    assert settings.request_timeout_seconds == 60
    assert settings.max_retries == 7
    assert settings.page_limit == 25
