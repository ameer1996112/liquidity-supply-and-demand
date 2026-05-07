from __future__ import annotations

from typing import Any

from src.services.setup_evidence_capture import capture_setup_evidence_for_signal


class _FakeResponse:
    data = [{"id": 123}]


class _FakeQuery:
    def __init__(self, recorder: dict[str, Any]) -> None:
        self.recorder = recorder

    def update(self, payload: dict[str, Any]) -> "_FakeQuery":
        self.recorder["payload"] = payload
        return self

    def eq(self, key: str, value: Any) -> "_FakeQuery":
        self.recorder["eq"] = (key, value)
        return self

    def execute(self) -> _FakeResponse:
        self.recorder["executed"] = True
        return _FakeResponse()


class _FakeSupabase:
    def __init__(self) -> None:
        self.recorder: dict[str, Any] = {}

    def table(self, table_name: str) -> _FakeQuery:
        self.recorder["table"] = table_name
        return _FakeQuery(self.recorder)


def test_capture_setup_evidence_updates_signal_with_zone_screenshot() -> None:
    client = _FakeSupabase()

    def _provider(**kwargs: Any) -> dict[str, Any]:
        assert kwargs["symbol"] == "GBPJPY"
        assert kwargs["timeframe"] == "5m"
        assert kwargs["zone_id"] == 17733
        assert kwargs["timeout_seconds"] >= 20
        return {
            "status": "ok",
            "structured": {
                "setup_evidence": {
                    "status": "ok",
                    "focus_zone": {"id": 17733, "high": 215.8, "low": 215.2},
                    "focus_image": {"url": "http://provider.test/provider-artifacts/setup.png"},
                    "reason": "",
                }
            },
            "screenshot_url": "http://provider.test/provider-artifacts/setup.png",
        }

    updated = capture_setup_evidence_for_signal(
        client,
        signal_id=123,
        payload={"symbol": "GBPJPY", "timeframe": "5m", "zone_id": 17733},
        provider=_provider,
    )

    assert updated is True
    assert client.recorder["table"] == "trading_signals"
    assert client.recorder["eq"] == ("id", 123)
    assert client.recorder["payload"]["setup_evidence"]["focus_zone"]["id"] == 17733
    assert client.recorder["payload"]["image_url"] == "http://provider.test/provider-artifacts/setup.png"


def test_capture_setup_evidence_skips_payload_without_zone_id() -> None:
    client = _FakeSupabase()

    def _provider(**_kwargs: Any) -> dict[str, Any]:
        raise AssertionError("provider should not be called without a zone_id")

    updated = capture_setup_evidence_for_signal(
        client,
        signal_id=123,
        payload={"symbol": "GBPJPY", "timeframe": "5m"},
        provider=_provider,
    )

    assert updated is False
    assert client.recorder == {}


def test_capture_setup_evidence_accepts_prefixed_zone_id() -> None:
    client = _FakeSupabase()

    def _provider(**kwargs: Any) -> dict[str, Any]:
        assert kwargs["zone_id"] == 18429
        return {
            "status": "ok",
            "structured": {
                "setup_evidence": {
                    "status": "ok",
                    "focus_zone": {"id": 18429, "high": 2.282, "low": 2.281},
                    "focus_image": {"url": "http://provider.test/provider-artifacts/gbpnzd.png"},
                    "reason": "",
                }
            },
        }

    updated = capture_setup_evidence_for_signal(
        client,
        signal_id=573,
        payload={"symbol": "GBPNZD", "timeframe": "5m", "F:zone_id": 18429},
        provider=_provider,
    )

    assert updated is True
    assert client.recorder["payload"]["setup_evidence"]["focus_zone"]["id"] == 18429
    assert client.recorder["payload"]["image_url"] == "http://provider.test/provider-artifacts/gbpnzd.png"
