from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import plistlib

import src.services.tradingview_mcp_compatibility as compatibility_module
from src.services.tradingview_mcp_compatibility import (
    TradingViewMcpCompatibilityService,
)


def _write_tradingview_app(tmp_path: Path, version: str = "2.9.0") -> Path:
    app_path = tmp_path / "TradingView.app"
    info_plist = app_path / "Contents" / "Info.plist"
    info_plist.parent.mkdir(parents=True)
    info_plist.write_bytes(
        plistlib.dumps({"CFBundleShortVersionString": version})
    )
    return app_path


def _write_mcp_repo(tmp_path: Path) -> Path:
    repo_path = tmp_path / "mcp"
    cli_entry = repo_path / "src" / "cli" / "index.js"
    cli_entry.parent.mkdir(parents=True)
    cli_entry.write_text("console.log('{}')\n", encoding="utf-8")
    return repo_path


def test_known_good_version_with_passing_probe_is_supported(tmp_path: Path) -> None:
    app_path = _write_tradingview_app(tmp_path, version="2.9.0")
    mcp_repo = _write_mcp_repo(tmp_path)
    calls = {"count": 0}

    def probe_runner() -> dict[str, object]:
        calls["count"] += 1
        return {
            "success": True,
            "chart_symbol": "VANTAGE:AUDUSD",
            "chart_resolution": "5",
        }

    service = TradingViewMcpCompatibilityService(
        ttl_seconds=60,
        tradingview_app_path=app_path,
        mcp_repo_path=mcp_repo,
        approved_versions_fetcher=lambda: ["2.9.0"],
        probe_runner=probe_runner,
        now_fn=lambda: datetime(2026, 4, 21, 12, 0, tzinfo=timezone.utc),
    )

    status = service.get_status(force_refresh=True)

    assert status.status == "supported"
    assert status.chart_context_enabled is True
    assert status.tradingview_version == "2.9.0"
    assert status.probe["ok"] is True
    assert calls["count"] == 1


def test_backend_approved_versions_enable_supported_status(tmp_path: Path) -> None:
    app_path = _write_tradingview_app(tmp_path, version="2.9.0")
    mcp_repo = _write_mcp_repo(tmp_path)

    service = TradingViewMcpCompatibilityService(
        ttl_seconds=60,
        tradingview_app_path=app_path,
        mcp_repo_path=mcp_repo,
        approved_versions_fetcher=lambda: ["2.9.0"],
        probe_runner=lambda: {
            "success": True,
            "chart_symbol": "VANTAGE:AUDUSD",
            "chart_resolution": "5",
        },
    )

    status = service.get_status(force_refresh=True)

    assert status.status == "supported"
    assert status.chart_context_enabled is True


def test_backend_config_fetch_failure_disables_chart_context(tmp_path: Path) -> None:
    app_path = _write_tradingview_app(tmp_path, version="2.9.0")
    mcp_repo = _write_mcp_repo(tmp_path)

    service = TradingViewMcpCompatibilityService(
        ttl_seconds=60,
        tradingview_app_path=app_path,
        mcp_repo_path=mcp_repo,
        approved_versions_fetcher=lambda: (_ for _ in ()).throw(RuntimeError("config offline")),
        probe_runner=lambda: {"success": True},
    )

    status = service.get_status(force_refresh=True)

    assert status.status == "unsupported_version"
    assert status.chart_context_enabled is False
    assert "config offline" in status.reason


def test_default_backend_approval_fetcher_is_used(tmp_path: Path, monkeypatch) -> None:
    app_path = _write_tradingview_app(tmp_path, version="2.9.0")
    mcp_repo = _write_mcp_repo(tmp_path)

    monkeypatch.setattr(
        compatibility_module,
        "_fetch_approved_versions_from_backend",
        lambda: ["2.9.0"],
    )

    service = TradingViewMcpCompatibilityService(
        ttl_seconds=60,
        tradingview_app_path=app_path,
        mcp_repo_path=mcp_repo,
        probe_runner=lambda: {
            "success": True,
            "chart_symbol": "VANTAGE:AUDUSD",
            "chart_resolution": "5",
        },
    )

    status = service.get_status(force_refresh=True)

    assert status.status == "supported"
    assert status.chart_context_enabled is True


def test_unknown_version_returns_unsupported_without_running_probe(tmp_path: Path) -> None:
    app_path = _write_tradingview_app(tmp_path, version="2.9.1")
    mcp_repo = _write_mcp_repo(tmp_path)
    calls = {"count": 0}

    def probe_runner() -> dict[str, object]:
        calls["count"] += 1
        return {"success": True}

    service = TradingViewMcpCompatibilityService(
        ttl_seconds=60,
        tradingview_app_path=app_path,
        mcp_repo_path=mcp_repo,
        approved_versions_fetcher=lambda: ["2.9.0"],
        probe_runner=probe_runner,
    )

    status = service.get_status(force_refresh=True)

    assert status.status == "unsupported_version"
    assert status.chart_context_enabled is False
    assert "2.9.1" in status.reason
    assert calls["count"] == 0


def test_missing_tradingview_app_returns_not_found(tmp_path: Path) -> None:
    mcp_repo = _write_mcp_repo(tmp_path)

    service = TradingViewMcpCompatibilityService(
        ttl_seconds=60,
        tradingview_app_path=tmp_path / "TradingView.app",
        mcp_repo_path=mcp_repo,
        approved_versions_fetcher=lambda: ["2.9.0"],
        probe_runner=lambda: {"success": True},
    )

    status = service.get_status(force_refresh=True)

    assert status.status == "tradingview_not_found"
    assert status.chart_context_enabled is False


def test_missing_mcp_repo_returns_mcp_unavailable(tmp_path: Path) -> None:
    app_path = _write_tradingview_app(tmp_path, version="2.9.0")

    service = TradingViewMcpCompatibilityService(
        ttl_seconds=60,
        tradingview_app_path=app_path,
        mcp_repo_path=tmp_path / "missing-mcp",
        approved_versions_fetcher=lambda: ["2.9.0"],
        probe_runner=lambda: {"success": True},
    )

    status = service.get_status(force_refresh=True)

    assert status.status == "mcp_unavailable"
    assert status.chart_context_enabled is False


def test_probe_failure_returns_probe_failed(tmp_path: Path) -> None:
    app_path = _write_tradingview_app(tmp_path, version="2.9.0")
    mcp_repo = _write_mcp_repo(tmp_path)

    service = TradingViewMcpCompatibilityService(
        ttl_seconds=60,
        tradingview_app_path=app_path,
        mcp_repo_path=mcp_repo,
        approved_versions_fetcher=lambda: ["2.9.0"],
        probe_runner=lambda: {"success": False, "error": "CDP unavailable"},
    )

    status = service.get_status(force_refresh=True)

    assert status.status == "probe_failed"
    assert status.chart_context_enabled is False
    assert status.probe["ok"] is False
    assert "CDP unavailable" in status.reason


def test_cached_status_reuses_last_probe_within_ttl(tmp_path: Path) -> None:
    app_path = _write_tradingview_app(tmp_path, version="2.9.0")
    mcp_repo = _write_mcp_repo(tmp_path)
    probe_calls = {"count": 0}
    current_time = {"value": datetime(2026, 4, 21, 12, 0, tzinfo=timezone.utc)}

    def probe_runner() -> dict[str, object]:
        probe_calls["count"] += 1
        return {
            "success": True,
            "chart_symbol": "VANTAGE:AUDUSD",
            "chart_resolution": "5",
        }

    service = TradingViewMcpCompatibilityService(
        ttl_seconds=60,
        tradingview_app_path=app_path,
        mcp_repo_path=mcp_repo,
        approved_versions_fetcher=lambda: ["2.9.0"],
        probe_runner=probe_runner,
        now_fn=lambda: current_time["value"],
    )

    first = service.get_status(force_refresh=True)
    second = service.get_status()

    assert first.status == "supported"
    assert second.status == "supported"
    assert probe_calls["count"] == 1
