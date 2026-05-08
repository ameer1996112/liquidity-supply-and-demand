from scripts.rd_concepts_pipeline.list_channels import normalize_channel


def test_normalize_channel_keeps_text_channel_fields() -> None:
    raw = {"id": "123", "name": "main-pairs", "type": 0, "parent_id": "999"}
    assert normalize_channel(raw) == {
        "id": "123",
        "name": "main-pairs",
        "type": 0,
        "parent_id": "999",
    }
