from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from functools import lru_cache
import json
import logging
from pathlib import Path
import plistlib
import subprocess
from typing import Any, Callable

import requests

from config.settings import get_settings


logger = logging.getLogger(__name__)

MCP_REPO_PATH = Path(__file__).resolve().parents[2] / "mcp" / "tradingview-mcp"
MCP_STATUS_COMMAND = ["node", "src/cli/index.js", "status"]
BACKEND_APPROVALS_PATH = "/api/v1/config/tradingview-mcp"
DEFAULT_RAILWAY_API_BASE_URL = "https://grand-learning-production-bc96.up.railway.app"


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _isoformat(value: datetime) -> str:
    return value.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _read_tradingview_version(app_path: Path) -> str | None:
    info_plist = app_path / "Contents" / "Info.plist"
    if not info_plist.is_file():
        return None

    try:
        with info_plist.open("rb") as handle:
            payload = plistlib.load(handle)
    except (OSError, plistlib.InvalidFileException):
        return None

    version = str(
        payload.get("CFBundleShortVersionString")
        or payload.get("CFBundleVersion")
        or ""
    ).strip()
    return version or None


def _normalize_versions(versions: list[Any]) -> list[str]:
    normalized: list[str] = []
    seen: set[str] = set()

    for raw_version in versions:
        version = str(raw_version).strip()
        if not version or version in seen:
            continue
        seen.add(version)
        normalized.append(version)

    return normalized


def _backend_base_url() -> str:
    settings = get_settings()
    base_url = settings.public_api_base_url or DEFAULT_RAILWAY_API_BASE_URL
    return base_url.rstrip("/")


def _backend_request_headers() -> dict[str, str]:
    settings = get_settings()
    admin_api_key = (settings.admin_api_key or "").strip()
    if not admin_api_key:
        return {}
    return {"X-Admin-API-Key": admin_api_key}


def _fetch_approved_versions_from_backend() -> list[str]:
    response = requests.get(
        f"{_backend_base_url()}{BACKEND_APPROVALS_PATH}",
        headers=_backend_request_headers(),
        timeout=5,
    )
    response.raise_for_status()
    payload = response.json()
    approved_versions = payload.get("approved_versions", [])
    if not isinstance(approved_versions, list):
        return []
    return _normalize_versions(approved_versions)


def _run_status_probe(mcp_repo_path: Path) -> dict[str, Any]:
    try:
        completed = subprocess.run(
            MCP_STATUS_COMMAND,
            cwd=mcp_repo_path,
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
    except (FileNotFoundError, OSError) as exc:
        return {"success": False, "error": f"status probe failed to launch: {exc}"}

    if completed.returncode != 0:
        return {
            "success": False,
            "error": completed.stderr.strip() or completed.stdout.strip() or "status probe failed",
        }

    try:
        payload = json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        return {"success": False, "error": f"invalid JSON from status probe: {exc}"}

    if not isinstance(payload, dict):
        return {"success": False, "error": "status probe returned a non-object JSON payload"}

    return payload


@dataclass(frozen=True)
class TradingViewMcpCompatibilityStatus:
    status: str
    chart_context_enabled: bool
    tradingview_version: str
    checked_at: str
    reason: str
    probe: dict[str, Any]

    def to_payload(self) -> dict[str, Any]:
        return asdict(self)


class TradingViewMcpCompatibilityService:
    def __init__(
        self,
        *,
        ttl_seconds: int,
        tradingview_app_path: Path,
        mcp_repo_path: Path,
        approved_versions_fetcher: Callable[[], list[str]] | None = None,
        version_getter: Callable[[], str | None] | None = None,
        probe_runner: Callable[[], dict[str, Any]] | None = None,
        now_fn: Callable[[], datetime] = _utc_now,
    ) -> None:
        self._ttl = timedelta(seconds=ttl_seconds)
        self._tradingview_app_path = tradingview_app_path
        self._mcp_repo_path = mcp_repo_path
        self._approved_versions_fetcher = approved_versions_fetcher or _fetch_approved_versions_from_backend
        self._version_getter = version_getter or (lambda: _read_tradingview_version(tradingview_app_path))
        self._probe_runner = probe_runner or (lambda: _run_status_probe(mcp_repo_path))
        self._now_fn = now_fn
        self._cached_status: TradingViewMcpCompatibilityStatus | None = None
        self._cached_at: datetime | None = None

    def get_status(self, *, force_refresh: bool = False) -> TradingViewMcpCompatibilityStatus:
        now = self._now_fn()
        if (
            not force_refresh
            and self._cached_status is not None
            and self._cached_at is not None
            and now - self._cached_at < self._ttl
        ):
            return self._cached_status

        status = self._refresh(now)
        self._cached_status = status
        self._cached_at = now
        return status

    def _refresh(self, now: datetime) -> TradingViewMcpCompatibilityStatus:
        checked_at = _isoformat(now)

        version = self._version_getter()
        if not version:
            return self._build_status(
                status="tradingview_not_found",
                chart_context_enabled=False,
                tradingview_version="",
                checked_at=checked_at,
                reason=f"TradingView Desktop not found at {self._tradingview_app_path}",
                probe={"command": "status", "ok": False},
            )

        try:
            allowed_versions = set(self._approved_versions_fetcher())
        except Exception as exc:
            return self._build_status(
                status="unsupported_version",
                chart_context_enabled=False,
                tradingview_version=version,
                checked_at=checked_at,
                reason=f"Failed to load approved TradingView versions from backend config: {exc}",
                probe={"command": "status", "ok": False},
            )

        if not allowed_versions:
            return self._build_status(
                status="unsupported_version",
                chart_context_enabled=False,
                tradingview_version=version,
                checked_at=checked_at,
                reason="No approved TradingView Desktop versions are configured in app settings",
                probe={"command": "status", "ok": False},
            )

        if version not in allowed_versions:
            return self._build_status(
                status="unsupported_version",
                chart_context_enabled=False,
                tradingview_version=version,
                checked_at=checked_at,
                reason=f"TradingView Desktop {version} is not approved in app settings",
                probe={"command": "status", "ok": False},
            )

        if not self._mcp_repo_path.is_dir():
            return self._build_status(
                status="mcp_unavailable",
                chart_context_enabled=False,
                tradingview_version=version,
                checked_at=checked_at,
                reason=f"MCP repo not found at {self._mcp_repo_path}",
                probe={"command": "status", "ok": False},
            )

        cli_entry = self._mcp_repo_path / "src" / "cli" / "index.js"
        if not cli_entry.is_file():
            return self._build_status(
                status="mcp_unavailable",
                chart_context_enabled=False,
                tradingview_version=version,
                checked_at=checked_at,
                reason=f"MCP CLI entrypoint not found at {cli_entry}",
                probe={"command": "status", "ok": False},
            )

        probe_payload = self._probe_runner()
        probe_ok = bool(
            probe_payload.get("success")
            and probe_payload.get("chart_symbol")
            and probe_payload.get("chart_resolution")
        )
        if not probe_ok:
            return self._build_status(
                status="probe_failed",
                chart_context_enabled=False,
                tradingview_version=version,
                checked_at=checked_at,
                reason=str(
                    probe_payload.get(
                        "error",
                        "status probe did not return chart_symbol/chart_resolution",
                    )
                ),
                probe={"command": "status", "ok": False, "payload": probe_payload},
            )

        return self._build_status(
            status="supported",
            chart_context_enabled=True,
            tradingview_version=version,
            checked_at=checked_at,
            reason="",
            probe={"command": "status", "ok": True, "payload": probe_payload},
        )

    def _build_status(
        self,
        *,
        status: str,
        chart_context_enabled: bool,
        tradingview_version: str,
        checked_at: str,
        reason: str,
        probe: dict[str, Any],
    ) -> TradingViewMcpCompatibilityStatus:
        result = TradingViewMcpCompatibilityStatus(
            status=status,
            chart_context_enabled=chart_context_enabled,
            tradingview_version=tradingview_version,
            checked_at=checked_at,
            reason=reason,
            probe=probe,
        )
        logger.info(
            "tradingview_mcp_compatibility status=%s version=%s enabled=%s reason=%s",
            result.status,
            result.tradingview_version or "<missing>",
            result.chart_context_enabled,
            result.reason or "<none>",
        )
        return result


@lru_cache
def get_tradingview_mcp_compatibility_service() -> TradingViewMcpCompatibilityService:
    settings = get_settings()
    return TradingViewMcpCompatibilityService(
        ttl_seconds=settings.tradingview_mcp_compatibility_ttl_seconds,
        tradingview_app_path=Path(settings.tradingview_app_path),
        mcp_repo_path=MCP_REPO_PATH,
    )
