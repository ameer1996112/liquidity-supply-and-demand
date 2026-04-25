import base64
from pathlib import Path

from src.local_chart_provider_service import (
    _crop_focus_image,
    build_chart_context_payload,
    fetch_live_chart_context,
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


def test_build_chart_context_payload_prefers_requested_zone_id(tmp_path: Path, monkeypatch) -> None:
    screenshot_path = tmp_path / "setup-zone.png"
    _write_png(screenshot_path)
    monkeypatch.setattr(
        "src.local_chart_provider_service._crop_focus_image",
        lambda source_path, focus_zone: str(screenshot_path.with_name(f"{focus_zone['id']}.png")),
    )

    payload = build_chart_context_payload(
        requested_symbol="GBPJPY",
        requested_timeframe="5m",
        requested_zone_id=17733,
        status_payload={"success": True, "chart_symbol": "VANTAGE:GBPJPY", "chart_resolution": "5"},
        values_payload={"success": True, "studies": []},
        lines_payload={"success": True, "studies": []},
        labels_payload={"success": True, "studies": []},
        boxes_payload={
            "success": True,
            "studies": [
                {
                    "name": "Liquidity Zones",
                    "boxes": [{"high": 215.8, "low": 215.2}, {"high": 214.8, "low": 214.1}],
                    "all_boxes": [
                        {"id": 100, "high": 215.8, "low": 215.2, "x1": 100, "x2": 200},
                        {"id": 17733, "high": 214.8, "low": 214.1, "x1": 300, "x2": 460},
                    ],
                }
            ],
        },
        screenshot_payload={"success": True, "file_path": str(screenshot_path), "region": "chart"},
        now_iso="2026-04-17T00:20:00Z",
    )

    assert payload["metadata"]["requested_zone_id"] == 17733
    assert payload["setup_evidence"]["focus_zone"]["id"] == 17733
    assert payload["setup_evidence"]["focus_image"]["path"].endswith("17733.png")


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


def test_fetch_live_chart_context_short_circuits_when_compatibility_is_disabled(monkeypatch) -> None:
    monkeypatch.setattr(
        "src.local_chart_provider_service.get_chart_provider_compatibility_status",
        lambda: {
            "status": "unsupported_version",
            "chart_context_enabled": False,
            "tradingview_version": "1.2.3",
            "checked_at": "2026-04-21T08:00:00Z",
            "reason": "TradingView Desktop 1.2.3 is not in the approved allowlist",
            "probe": {"command": "status", "ok": False},
        },
    )

    def _unexpected_run(command: list[str]) -> dict[str, object]:
        raise AssertionError(f"MCP command should not run when compatibility is disabled: {command}")

    monkeypatch.setattr("src.local_chart_provider_service.run_mcp_command", _unexpected_run)

    payload = fetch_live_chart_context("XAUUSD", "5m")

    assert payload["symbol"] == "XAUUSD"
    assert payload["timeframe"] == "5m"
    assert payload["reason"] == "TradingView Desktop 1.2.3 is not in the approved allowlist"
    assert payload["setup_evidence"]["status"] == "degraded"
    assert payload["metadata"]["compatibility"]["status"] == "unsupported_version"


def test_fetch_live_chart_context_runs_mcp_sequence_when_compatibility_is_supported(monkeypatch) -> None:
    monkeypatch.setattr(
        "src.local_chart_provider_service.get_chart_provider_compatibility_status",
        lambda: {
            "status": "supported",
            "chart_context_enabled": True,
            "tradingview_version": "1.2.3",
            "checked_at": "2026-04-21T08:00:00Z",
            "reason": "",
            "probe": {"command": "status", "ok": True},
        },
    )
    monkeypatch.setattr("src.local_chart_provider_service._now_iso", lambda: "2026-04-21T08:00:00Z")

    seen_commands: list[list[str]] = []

    def _fake_run(command: list[str]) -> dict[str, object]:
        seen_commands.append(command)
        command_key = tuple(command)
        payload_map = {
            ("node", "src/cli/index.js", "status"): {
                "success": True,
                "chart_symbol": "VANTAGE:XAUUSD",
                "chart_resolution": "5",
            },
            ("node", "src/cli/index.js", "values"): {
                "success": True,
                "studies": [{"name": "EMA", "values": {"EMA": "3250.1"}}],
            },
            ("node", "src/cli/index.js", "data", "lines"): {"success": True, "studies": []},
            ("node", "src/cli/index.js", "data", "labels"): {"success": True, "studies": []},
            ("node", "src/cli/index.js", "data", "boxes", "--verbose"): {"success": True, "studies": []},
            (
                "node",
                "src/cli/index.js",
                "screenshot",
                "--region",
                "chart",
                "--output",
                "setup_XAUUSD_5m_2026-04-21T08-00-00Z",
            ): {
                "success": True,
                "file_path": "/tmp/chart.png",
                "region": "chart",
            },
        }
        return payload_map[command_key]

    monkeypatch.setattr("src.local_chart_provider_service.run_mcp_command", _fake_run)

    payload = fetch_live_chart_context("XAUUSD", "5m")

    assert seen_commands == [
        ["node", "src/cli/index.js", "status"],
        ["node", "src/cli/index.js", "values"],
        ["node", "src/cli/index.js", "data", "lines"],
        ["node", "src/cli/index.js", "data", "labels"],
        ["node", "src/cli/index.js", "data", "boxes", "--verbose"],
        [
            "node",
            "src/cli/index.js",
            "screenshot",
            "--region",
            "chart",
            "--output",
            "setup_XAUUSD_5m_2026-04-21T08-00-00Z",
        ],
    ]
    assert payload["symbol"] == "VANTAGE:XAUUSD"
    assert payload["timeframe"] == "5m"
    assert payload["indicator_values"]["EMA"]["EMA"] == "3250.1"
