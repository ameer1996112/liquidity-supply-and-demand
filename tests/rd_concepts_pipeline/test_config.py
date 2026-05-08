from pathlib import Path

import pytest

from scripts.rd_concepts_pipeline.config import PipelineSettings, configured_channels


def test_configured_channels_skips_incomplete_ids() -> None:
    settings = PipelineSettings(
        discord_authorization="secret",
        discord_server_id="1160558784314343484",
        data_dir=Path("data/rd_concepts"),
        channels={
            "5m-charts-mechanical": "1240929130980053052",
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
