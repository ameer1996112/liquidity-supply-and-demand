from __future__ import annotations

from typing import Any

from src.services.setup_evidence_capture import (
    capture_setup_evidence_for_signal,
    needs_setup_evidence_backfill,
    setup_evidence_matches_signal,
)


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
        assert kwargs["setup_time"] == "2026-04-17 00:20:00"
        assert kwargs["zone_top"] == 215.8
        assert kwargs["zone_bottom"] == 215.2
        assert kwargs["zone_type"] == "supply"
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
        payload={
            "symbol": "GBPJPY",
            "timeframe": "5m",
            "zone_id": 17733,
            "signal_time": "2026-04-17 00:20:00",
            "zone_top": 215.8,
            "zone_bottom": 215.2,
            "zone_type": "supply",
        },
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


def test_capture_setup_evidence_clears_stale_image_url_when_image_is_invalid() -> None:
    client = _FakeSupabase()

    def _provider(**_kwargs: Any) -> dict[str, Any]:
        return {
            "status": "degraded",
            "structured": {
                "setup_evidence": {
                    "status": "degraded",
                    "focus_zone": {
                        "type": "supply",
                        "source": "signal",
                        "id": 18981,
                        "high": 4750.34,
                        "low": 4743.55,
                    },
                    "focus_image": None,
                    "reason": "visual chart screenshot was blank or still loading",
                }
            },
        }

    updated = capture_setup_evidence_for_signal(
        client,
        signal_id=575,
        payload={"symbol": "XAUUSD", "timeframe": "5m", "zone_id": 18981},
        provider=_provider,
    )

    assert updated is True
    assert client.recorder["payload"]["setup_evidence"]["status"] == "degraded"
    assert client.recorder["payload"]["image_url"] is None


def test_setup_evidence_matches_exact_signal_zone() -> None:
    payload = {
        "zone_id": 18429,
        "zone_type": "supply",
        "zone_top": 2.28358,
        "zone_bottom": 2.28294,
    }
    evidence = {
        "status": "ok",
        "focus_zone": {
            "id": 18429,
            "type": "supply",
            "high": 2.28358,
            "low": 2.28294,
        },
        "focus_image": {"url": "http://provider/setup.png"},
    }

    assert setup_evidence_matches_signal(payload, evidence) is True
    assert needs_setup_evidence_backfill({**payload, "setup_evidence": evidence}) is False


def test_setup_evidence_rejects_requested_id_without_exact_focus_zone() -> None:
    payload = {
        "zone_id": 18429,
        "zone_type": "supply",
        "zone_top": 2.28358,
        "zone_bottom": 2.28294,
    }
    wrong_evidence = {
        "status": "ok",
        "focus_zone": {
            "type": "horizontal_level",
            "price": 2.89,
            "requested_zone_id": 18429,
        },
        "focus_image": {"url": "http://provider/wrong.png"},
    }

    assert setup_evidence_matches_signal(payload, wrong_evidence) is False
    assert needs_setup_evidence_backfill({**payload, "setup_evidence": wrong_evidence}) is True


def test_setup_evidence_rejects_mismatched_zone_range() -> None:
    payload = {
        "zone_id": 18429,
        "zone_type": "supply",
        "zone_top": 2.28358,
        "zone_bottom": 2.28294,
    }
    wrong_range = {
        "status": "ok",
        "focus_zone": {
            "id": 18429,
            "type": "supply",
            "high": 2.29,
            "low": 2.28,
        },
        "focus_image": {"url": "http://provider/wrong.png"},
    }

    assert setup_evidence_matches_signal(payload, wrong_range) is False
