import base64
from pathlib import Path

from src.local_chart_provider_service import (
    _crop_focus_image,
    build_chart_context_payload,
    run_mcp_command,
)


_ONE_BY_ONE_PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+aRX0AAAAASUVORK5CYII="
)


def _write_png(path: Path) -> None:
    path.write_bytes(_ONE_BY_ONE_PNG)


def test_build_chart_context_payload_normalizes_successful_cli_results() -> None:
    payload = build_chart_context_payload(
        requested_symbol="XAUUSD",
        requested_timeframe="5m",
        status_payload={
            "success": True,
            "chart_symbol": "VANTAGE:AUDUSD",
            "chart_resolution": "5",
        },
        values_payload={
            "success": True,
            "studies": [
                {"name": "Moving Average Exponential", "values": {"EMA": "0.71664"}},
                {"name": "Institutional Liquidity Protocol [Pro]", "values": {"Shapes": "0.00000"}},
            ],
        },
        lines_payload={
            "success": True,
            "studies": [
                {
                    "name": "Institutional Liquidity Protocol [Pro]",
                    "horizontal_levels": [0.72],
                }
            ],
        },
        labels_payload={
            "success": True,
            "studies": [
                {
                    "name": "Institutional Liquidity Protocol [Pro]",
                    "labels": [{"text": "LONG", "price": 0.71}],
                }
            ],
        },
        now_iso="2026-04-17T00:20:00Z",
    )

    assert payload["symbol"] == "VANTAGE:AUDUSD"
    assert payload["timeframe"] == "5m"
    assert payload["provider_timestamp"] == "2026-04-17T00:20:00Z"
    assert payload["indicator_values"]["Moving Average Exponential"]["EMA"] == "0.71664"
    assert payload["zones"][0]["type"] == "horizontal_level"
    assert payload["pine_labels"][0]["label"] == "LONG"


def test_build_chart_context_payload_returns_degraded_shape_when_status_fails() -> None:
    payload = build_chart_context_payload(
        requested_symbol="XAUUSD",
        requested_timeframe="5m",
        status_payload={"success": False, "error": "CDP unavailable"},
        values_payload=None,
        lines_payload=None,
        labels_payload=None,
        now_iso="2026-04-17T00:20:00Z",
    )

    assert payload["symbol"] == "XAUUSD"
    assert payload["timeframe"] == "5m"
    assert payload["reason"] == "CDP unavailable"
    assert payload["pine_labels"] == []
    assert payload["zones"] == []
    assert payload["indicator_values"] == {}


def test_build_chart_context_payload_tolerates_secondary_failures() -> None:
    payload = build_chart_context_payload(
        requested_symbol="XAUUSD",
        requested_timeframe="5m",
        status_payload={"success": True, "chart_symbol": "XAUUSD", "chart_resolution": "15"},
        values_payload={"success": False, "error": "values failed"},
        lines_payload={"success": True, "studies": []},
        labels_payload={"success": False, "error": "labels failed"},
        now_iso="2026-04-17T00:20:00Z",
    )

    assert payload["timeframe"] == "15m"
    assert payload["indicator_values"] == {}
    assert payload["pine_labels"] == []
    assert "values failed" in payload["metadata"]["partial_failures"]
    assert "labels failed" in payload["metadata"]["partial_failures"]


def test_build_chart_context_payload_includes_setup_evidence_bundle(tmp_path: Path, monkeypatch) -> None:
    screenshot_path = tmp_path / "setup-focus.png"
    _write_png(screenshot_path)
    focus_path = tmp_path / "setup-focus_focus.png"
    _write_png(focus_path)
    monkeypatch.setattr(
        "src.local_chart_provider_service._crop_focus_image",
        lambda source_path, focus_zone: str(focus_path),
    )

    payload = build_chart_context_payload(
        requested_symbol="XAUUSD",
        requested_timeframe="5m",
        status_payload={
            "success": True,
            "chart_symbol": "VANTAGE:AUDUSD",
            "chart_resolution": "5",
        },
        values_payload={"success": True, "studies": []},
        lines_payload={"success": True, "studies": []},
        labels_payload={"success": True, "studies": []},
        boxes_payload={
            "success": True,
            "studies": [
                {
                    "name": "Institutional Liquidity Protocol [Pro]",
                    "boxes": [{"high": 0.7210, "low": 0.7195}],
                    "all_boxes": [{"high": 0.7210, "low": 0.7195, "x1": 240, "x2": 520}],
                }
            ],
        },
        screenshot_payload={
            "success": True,
            "file_path": str(screenshot_path),
            "region": "chart",
        },
        now_iso="2026-04-17T00:20:00Z",
    )

    assert payload["setup_evidence"]["status"] == "ok"
    assert payload["setup_evidence"]["focus_zone"]["high"] == 0.7210
    assert payload["setup_evidence"]["focus_image"]["path"] == str(focus_path)


def test_build_chart_context_payload_keeps_structured_context_when_screenshot_fails() -> None:
    payload = build_chart_context_payload(
        requested_symbol="XAUUSD",
        requested_timeframe="5m",
        status_payload={
            "success": True,
            "chart_symbol": "VANTAGE:AUDUSD",
            "chart_resolution": "5",
        },
        values_payload={"success": True, "studies": []},
        lines_payload={"success": True, "studies": []},
        labels_payload={"success": True, "studies": []},
        boxes_payload={"success": True, "studies": []},
        screenshot_payload={"success": False, "error": "capture failed"},
        now_iso="2026-04-17T00:20:00Z",
    )

    assert payload["reason"] == ""
    assert payload["setup_evidence"]["status"] == "degraded"
    assert payload["setup_evidence"]["reason"] == "capture failed"


def test_crop_focus_image_returns_original_path_without_zone_coordinates(tmp_path: Path) -> None:
    screenshot_path = tmp_path / "setup-focus.png"
    _write_png(screenshot_path)

    assert _crop_focus_image(str(screenshot_path), {"high": 0.7210, "low": 0.7195}) == str(screenshot_path)


def test_run_mcp_command_parses_successful_json(monkeypatch) -> None:
    class _Completed:
        returncode = 0
        stdout = '{"success": true, "chart_symbol": "VANTAGE:AUDUSD"}'
        stderr = ""

    monkeypatch.setattr(
        "src.local_chart_provider_service.subprocess.run",
        lambda *args, **kwargs: _Completed(),
    )

    payload = run_mcp_command(["node", "src/cli/index.js", "status"])
    assert payload["success"] is True
    assert payload["chart_symbol"] == "VANTAGE:AUDUSD"


def test_run_mcp_command_returns_failure_payload_on_bad_exit(monkeypatch) -> None:
    class _Completed:
        returncode = 1
        stdout = ""
        stderr = "CDP connection failed"

    monkeypatch.setattr(
        "src.local_chart_provider_service.subprocess.run",
        lambda *args, **kwargs: _Completed(),
    )

    payload = run_mcp_command(["node", "src/cli/index.js", "status"])
    assert payload["success"] is False
    assert "CDP connection failed" in payload["error"]
