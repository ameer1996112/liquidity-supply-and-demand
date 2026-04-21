# TradingView MCP Compatibility Guardrail Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a compatibility gate around the local TradingView Desktop MCP bridge so chart-context enrichment only runs on approved TradingView versions with a passing MCP smoke test.

**Architecture:** Introduce a small compatibility service that owns TradingView version detection, exact-version allowlisting, MCP `status` probing, and short-TTL caching. Wire that service into the local chart provider so unsupported or broken environments return degraded chart context immediately, and expose the same compatibility verdict over a lightweight health endpoint for operators.

**Tech Stack:** Python, FastAPI, Pydantic settings, pytest, stdlib `plistlib`, existing local TradingView MCP CLI

---

## File Structure

- Create: `src/services/tradingview_mcp_compatibility.py`
  - Own TradingView version detection, MCP probe execution, compatibility status dataclass, and TTL cache.
- Modify: `config/settings.py`
  - Add env-configured allowlist, app path, and cache TTL fields.
- Modify: `src/local_chart_provider_service.py`
  - Gate the full MCP command sequence on compatibility and expose a reusable compatibility payload helper.
- Modify: `src/local_chart_provider_app.py`
  - Add an operator-facing compatibility health endpoint.
- Create: `tests/services/test_tradingview_mcp_compatibility.py`
  - Cover allowlist decisions, missing app detection, probe failure, missing MCP repo, and TTL cache reuse.
- Modify: `tests/services/test_local_chart_provider_service.py`
  - Cover degraded short-circuit behavior when compatibility is disabled.
- Modify: `tests/api/test_local_chart_provider_app.py`
  - Cover the new compatibility health endpoint.
- Modify: `.env.example`
  - Document the new guardrail env vars and the curl command operators should use to verify compatibility.

### Task 1: Add configuration and the compatibility service

**Files:**
- Create: `src/services/tradingview_mcp_compatibility.py`
- Create: `tests/services/test_tradingview_mcp_compatibility.py`
- Modify: `config/settings.py`

- [ ] **Step 1: Write the failing service tests first**

```python
from datetime import datetime, timezone
from pathlib import Path

from src.services.tradingview_mcp_compatibility import (
    TradingViewMcpCompatibilityService,
)


def test_known_good_version_with_passing_probe_is_supported(tmp_path: Path) -> None:
    mcp_repo = tmp_path / "mcp"
    mcp_repo.mkdir()
    calls = {"count": 0}

    def probe_runner() -> dict[str, object]:
        calls["count"] += 1
        return {
            "success": True,
            "chart_symbol": "VANTAGE:AUDUSD",
            "chart_resolution": "5",
        }

    service = TradingViewMcpCompatibilityService(
        allowed_versions={"2.9.0"},
        ttl_seconds=60,
        tradingview_app_path=tmp_path / "TradingView.app",
        mcp_repo_path=mcp_repo,
        version_getter=lambda: "2.9.0",
        probe_runner=probe_runner,
        now_fn=lambda: datetime(2026, 4, 21, 12, 0, tzinfo=timezone.utc),
    )

    status = service.get_status(force_refresh=True)

    assert status.status == "supported"
    assert status.chart_context_enabled is True
    assert status.tradingview_version == "2.9.0"
    assert status.probe["ok"] is True
    assert calls["count"] == 1


def test_unknown_version_returns_unsupported_without_running_probe(tmp_path: Path) -> None:
    mcp_repo = tmp_path / "mcp"
    mcp_repo.mkdir()
    calls = {"count": 0}

    service = TradingViewMcpCompatibilityService(
        allowed_versions={"2.9.0"},
        ttl_seconds=60,
        tradingview_app_path=tmp_path / "TradingView.app",
        mcp_repo_path=mcp_repo,
        version_getter=lambda: "2.9.1",
        probe_runner=lambda: calls.__setitem__("count", calls["count"] + 1) or {"success": True},
    )

    status = service.get_status(force_refresh=True)

    assert status.status == "unsupported_version"
    assert status.chart_context_enabled is False
    assert "2.9.1" in status.reason
    assert calls["count"] == 0


def test_missing_tradingview_app_returns_not_found(tmp_path: Path) -> None:
    mcp_repo = tmp_path / "mcp"
    mcp_repo.mkdir()

    service = TradingViewMcpCompatibilityService(
        allowed_versions={"2.9.0"},
        ttl_seconds=60,
        tradingview_app_path=tmp_path / "TradingView.app",
        mcp_repo_path=mcp_repo,
        version_getter=lambda: None,
        probe_runner=lambda: {"success": True},
    )

    status = service.get_status(force_refresh=True)

    assert status.status == "tradingview_not_found"
    assert status.chart_context_enabled is False


def test_missing_mcp_repo_returns_mcp_unavailable(tmp_path: Path) -> None:
    service = TradingViewMcpCompatibilityService(
        allowed_versions={"2.9.0"},
        ttl_seconds=60,
        tradingview_app_path=tmp_path / "TradingView.app",
        mcp_repo_path=tmp_path / "missing-mcp",
        version_getter=lambda: "2.9.0",
        probe_runner=lambda: {"success": True},
    )

    status = service.get_status(force_refresh=True)

    assert status.status == "mcp_unavailable"
    assert status.chart_context_enabled is False


def test_cached_status_reuses_last_probe_within_ttl(tmp_path: Path) -> None:
    mcp_repo = tmp_path / "mcp"
    mcp_repo.mkdir()
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
        allowed_versions={"2.9.0"},
        ttl_seconds=60,
        tradingview_app_path=tmp_path / "TradingView.app",
        mcp_repo_path=mcp_repo,
        version_getter=lambda: "2.9.0",
        probe_runner=probe_runner,
        now_fn=lambda: current_time["value"],
    )

    first = service.get_status(force_refresh=True)
    second = service.get_status()

    assert first.status == "supported"
    assert second.status == "supported"
    assert probe_calls["count"] == 1
```

- [ ] **Step 2: Run the new service test file to confirm it fails before implementation**

Run:

```bash
PYTHONPATH=. pytest tests/services/test_tradingview_mcp_compatibility.py -v
```

Expected:

- FAIL with `ModuleNotFoundError` for `src.services.tradingview_mcp_compatibility`

- [ ] **Step 3: Add the new settings fields in `config/settings.py`**

```python
    tradingview_app_path: str = Field(
        default="/Applications/TradingView.app",
        description="Local TradingView Desktop app bundle path used for version detection.",
        validation_alias="TRADINGVIEW_APP_PATH",
    )
    tradingview_allowed_versions: str = Field(
        default="",
        description="Comma-separated exact TradingView Desktop versions approved for chart-context MCP usage.",
        validation_alias="TRADINGVIEW_ALLOWED_VERSIONS",
    )
    tradingview_mcp_compatibility_ttl_seconds: int = Field(
        default=60,
        ge=1,
        le=3600,
        description="Seconds to cache TradingView MCP compatibility results before re-probing.",
        validation_alias="TRADINGVIEW_MCP_COMPATIBILITY_TTL_SECONDS",
    )
```

- [ ] **Step 4: Add a parsed allowlist property near the existing `Settings` properties**

```python
    @property
    def tradingview_allowed_version_set(self) -> set[str]:
        """Parsed exact-version allowlist for the local TradingView Desktop app."""
        return {
            item.strip()
            for item in self.tradingview_allowed_versions.split(",")
            if item.strip()
        }
```

- [ ] **Step 5: Create `src/services/tradingview_mcp_compatibility.py` with the compatibility model and service**

```python
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

from config.settings import get_settings


logger = logging.getLogger("tradingview_mcp_compatibility")
MCP_REPO_PATH = Path(__file__).resolve().parents[2] / "mcp" / "tradingview-mcp"


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _isoformat(value: datetime) -> str:
    return value.replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _read_tradingview_version(app_path: Path) -> str | None:
    info_plist = app_path / "Contents" / "Info.plist"
    if not info_plist.exists():
        return None

    with info_plist.open("rb") as handle:
        payload = plistlib.load(handle)

    version = str(
        payload.get("CFBundleShortVersionString")
        or payload.get("CFBundleVersion")
        or ""
    ).strip()
    return version or None


def _run_status_probe(mcp_repo_path: Path) -> dict[str, Any]:
    completed = subprocess.run(
        ["node", "src/cli/index.js", "status"],
        cwd=mcp_repo_path,
        capture_output=True,
        text=True,
        timeout=10,
        check=False,
    )
    if completed.returncode != 0:
        return {
            "success": False,
            "error": completed.stderr.strip() or completed.stdout.strip() or "status probe failed",
        }

    try:
        return json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        return {"success": False, "error": f"invalid JSON from status probe: {exc}"}


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
        allowed_versions: set[str],
        ttl_seconds: int,
        tradingview_app_path: Path,
        mcp_repo_path: Path,
        version_getter: Callable[[], str | None] | None = None,
        probe_runner: Callable[[], dict[str, Any]] | None = None,
        now_fn: Callable[[], datetime] = _utc_now,
    ) -> None:
        self._allowed_versions = allowed_versions
        self._ttl = timedelta(seconds=ttl_seconds)
        self._tradingview_app_path = tradingview_app_path
        self._mcp_repo_path = mcp_repo_path
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
            return TradingViewMcpCompatibilityStatus(
                status="tradingview_not_found",
                chart_context_enabled=False,
                tradingview_version="",
                checked_at=checked_at,
                reason=f"TradingView Desktop not found at {self._tradingview_app_path}",
                probe={"command": "status", "ok": False},
            )

        if self._allowed_versions and version not in self._allowed_versions:
            return TradingViewMcpCompatibilityStatus(
                status="unsupported_version",
                chart_context_enabled=False,
                tradingview_version=version,
                checked_at=checked_at,
                reason=f"TradingView Desktop {version} is not in the approved allowlist",
                probe={"command": "status", "ok": False},
            )

        if not self._mcp_repo_path.exists():
            return TradingViewMcpCompatibilityStatus(
                status="mcp_unavailable",
                chart_context_enabled=False,
                tradingview_version=version,
                checked_at=checked_at,
                reason=f"MCP repo not found at {self._mcp_repo_path}",
                probe={"command": "status", "ok": False},
            )

        probe_payload = self._probe_runner()
        probe_ok = bool(
            probe_payload.get("success")
            and probe_payload.get("chart_symbol")
            and probe_payload.get("chart_resolution")
        )
        if not probe_ok:
            return TradingViewMcpCompatibilityStatus(
                status="probe_failed",
                chart_context_enabled=False,
                tradingview_version=version,
                checked_at=checked_at,
                reason=str(probe_payload.get("error", "status probe did not return chart_symbol/chart_resolution")),
                probe={"command": "status", "ok": False, "payload": probe_payload},
            )

        status = TradingViewMcpCompatibilityStatus(
            status="supported",
            chart_context_enabled=True,
            tradingview_version=version,
            checked_at=checked_at,
            reason="",
            probe={"command": "status", "ok": True, "payload": probe_payload},
        )
        logger.info(
            "tradingview_mcp_compatibility status=%s version=%s enabled=%s",
            status.status,
            status.tradingview_version,
            status.chart_context_enabled,
        )
        return status


@lru_cache
def get_tradingview_mcp_compatibility_service() -> TradingViewMcpCompatibilityService:
    settings = get_settings()
    return TradingViewMcpCompatibilityService(
        allowed_versions=settings.tradingview_allowed_version_set,
        ttl_seconds=settings.tradingview_mcp_compatibility_ttl_seconds,
        tradingview_app_path=Path(settings.tradingview_app_path),
        mcp_repo_path=MCP_REPO_PATH,
    )
```

- [ ] **Step 6: Run the service tests again**

Run:

```bash
PYTHONPATH=. pytest tests/services/test_tradingview_mcp_compatibility.py -v
```

Expected:

- PASS for all service tests

- [ ] **Step 7: Commit the new settings and compatibility service**

```bash
git add config/settings.py src/services/tradingview_mcp_compatibility.py tests/services/test_tradingview_mcp_compatibility.py
git commit -m "DEV-185: add TradingView MCP compatibility service"
```

### Task 2: Gate chart-context enrichment on compatibility status

**Files:**
- Modify: `src/local_chart_provider_service.py`
- Modify: `tests/services/test_local_chart_provider_service.py`

- [ ] **Step 1: Add the failing provider-service tests**

```python
from src.local_chart_provider_service import fetch_live_chart_context


def test_fetch_live_chart_context_short_circuits_when_compatibility_is_disabled(monkeypatch) -> None:
    monkeypatch.setattr(
        "src.local_chart_provider_service.get_tradingview_mcp_compatibility_status",
        lambda force_refresh=False: {
            "status": "unsupported_version",
            "chart_context_enabled": False,
            "tradingview_version": "2.9.2",
            "checked_at": "2026-04-21T12:00:00Z",
            "reason": "TradingView Desktop 2.9.2 is not in the approved allowlist",
            "probe": {"command": "status", "ok": False},
        },
    )

    commands: list[list[str]] = []

    monkeypatch.setattr(
        "src.local_chart_provider_service.run_mcp_command",
        lambda command: commands.append(list(command)) or {"success": True},
    )

    payload = fetch_live_chart_context("XAUUSD", "5m")

    assert payload["reason"] == "TradingView Desktop 2.9.2 is not in the approved allowlist"
    assert payload["setup_evidence"]["status"] == "degraded"
    assert commands == []


def test_fetch_live_chart_context_runs_mcp_commands_when_compatibility_is_supported(monkeypatch) -> None:
    monkeypatch.setattr(
        "src.local_chart_provider_service.get_tradingview_mcp_compatibility_status",
        lambda force_refresh=False: {
            "status": "supported",
            "chart_context_enabled": True,
            "tradingview_version": "2.9.0",
            "checked_at": "2026-04-21T12:00:00Z",
            "reason": "",
            "probe": {"command": "status", "ok": True},
        },
    )

    responses = iter(
        [
            {"success": True, "chart_symbol": "VANTAGE:AUDUSD", "chart_resolution": "5"},
            {"success": True, "studies": []},
            {"success": True, "studies": []},
            {"success": True, "studies": []},
            {"success": True, "studies": []},
            {"success": False, "error": "capture failed"},
        ]
    )

    monkeypatch.setattr(
        "src.local_chart_provider_service.run_mcp_command",
        lambda command: next(responses),
    )

    payload = fetch_live_chart_context("XAUUSD", "5m")

    assert payload["symbol"] == "VANTAGE:AUDUSD"
    assert payload["timeframe"] == "5m"
    assert payload["setup_evidence"]["status"] == "degraded"
```

- [ ] **Step 2: Run the provider-service tests to verify they fail before the wiring**

Run:

```bash
PYTHONPATH=. pytest tests/services/test_local_chart_provider_service.py -v
```

Expected:

- FAIL because `get_tradingview_mcp_compatibility_status` does not exist yet

- [ ] **Step 3: Import the compatibility service into `src/local_chart_provider_service.py` and expose a helper**

```python
from src.services.tradingview_mcp_compatibility import (
    get_tradingview_mcp_compatibility_service,
)


def get_tradingview_mcp_compatibility_status(force_refresh: bool = False) -> Dict[str, Any]:
    status = get_tradingview_mcp_compatibility_service().get_status(force_refresh=force_refresh)
    return status.to_payload()
```

- [ ] **Step 4: Gate `fetch_live_chart_context()` before the full MCP command sequence**

```python
def fetch_live_chart_context(requested_symbol: str, requested_timeframe: str) -> Dict[str, Any]:
    compatibility = get_tradingview_mcp_compatibility_status()
    if not compatibility.get("chart_context_enabled", False):
        return build_chart_context_payload(
            requested_symbol=requested_symbol,
            requested_timeframe=requested_timeframe,
            status_payload={
                "success": False,
                "error": str(compatibility.get("reason", "TradingView MCP compatibility check failed")),
            },
            values_payload=None,
            lines_payload=None,
            labels_payload=None,
            boxes_payload=None,
            screenshot_payload=None,
        )

    status_payload = run_mcp_command(["node", "src/cli/index.js", "status"])
    if not status_payload.get("success"):
        return build_chart_context_payload(
            requested_symbol=requested_symbol,
            requested_timeframe=requested_timeframe,
            status_payload=status_payload,
            values_payload=None,
            lines_payload=None,
            labels_payload=None,
            boxes_payload=None,
            screenshot_payload=None,
        )

    screenshot_name = f"setup_{requested_symbol}_{requested_timeframe}_{_now_iso()}".replace(":", "-")
    values_payload = run_mcp_command(["node", "src/cli/index.js", "values"])
    lines_payload = run_mcp_command(["node", "src/cli/index.js", "data", "lines"])
    labels_payload = run_mcp_command(["node", "src/cli/index.js", "data", "labels"])
    boxes_payload = run_mcp_command(["node", "src/cli/index.js", "data", "boxes", "--verbose"])
    screenshot_payload = run_mcp_command(
        ["node", "src/cli/index.js", "screenshot", "--region", "chart", "--output", screenshot_name]
    )

    return build_chart_context_payload(
        requested_symbol=requested_symbol,
        requested_timeframe=requested_timeframe,
        status_payload=status_payload,
        values_payload=values_payload,
        lines_payload=lines_payload,
        labels_payload=labels_payload,
        boxes_payload=boxes_payload,
        screenshot_payload=screenshot_payload,
    )
```

- [ ] **Step 5: Run the provider-service tests again**

Run:

```bash
PYTHONPATH=. pytest tests/services/test_local_chart_provider_service.py -v
```

Expected:

- PASS for the existing payload tests
- PASS for the new compatibility short-circuit tests

- [ ] **Step 6: Commit the provider gating change**

```bash
git add src/local_chart_provider_service.py tests/services/test_local_chart_provider_service.py
git commit -m "DEV-185: gate chart context on MCP compatibility"
```

### Task 3: Expose the compatibility verdict over HTTP for operators

**Files:**
- Modify: `src/local_chart_provider_app.py`
- Modify: `tests/api/test_local_chart_provider_app.py`

- [ ] **Step 1: Add the failing API test**

```python
def test_compatibility_health_endpoint_returns_cached_status(monkeypatch) -> None:
    monkeypatch.setattr(
        "src.local_chart_provider_app.get_tradingview_mcp_compatibility_status",
        lambda force_refresh=False: {
            "status": "supported",
            "chart_context_enabled": True,
            "tradingview_version": "2.9.0",
            "checked_at": "2026-04-21T12:00:00Z",
            "reason": "",
            "probe": {"command": "status", "ok": True},
        },
    )

    client = TestClient(app)
    response = client.get("/health/compatibility")

    assert response.status_code == 200
    assert response.json()["status"] == "supported"
    assert response.json()["chart_context_enabled"] is True
    assert response.json()["tradingview_version"] == "2.9.0"
```

- [ ] **Step 2: Run the API tests to verify the new endpoint does not exist yet**

Run:

```bash
PYTHONPATH=. pytest tests/api/test_local_chart_provider_app.py -v
```

Expected:

- FAIL with `AttributeError` or `404` for `/health/compatibility`

- [ ] **Step 3: Import the compatibility helper and add the new endpoint**

```python
from src.local_chart_provider_service import (
    fetch_live_chart_context,
    get_tradingview_mcp_compatibility_status,
)


@app.get("/health/compatibility")
async def get_compatibility_health() -> dict:
    return get_tradingview_mcp_compatibility_status()
```

- [ ] **Step 4: Run the API tests again**

Run:

```bash
PYTHONPATH=. pytest tests/api/test_local_chart_provider_app.py -v
```

Expected:

- PASS for the three existing `/chart-context` tests
- PASS for the new `/health/compatibility` test

- [ ] **Step 5: Manually verify the operator endpoint locally**

Run:

```bash
curl -s http://127.0.0.1:8765/health/compatibility | jq
```

Expected:

- JSON response with `status`, `chart_context_enabled`, `tradingview_version`, `checked_at`, `reason`, and `probe`

- [ ] **Step 6: Commit the API health endpoint**

```bash
git add src/local_chart_provider_app.py tests/api/test_local_chart_provider_app.py
git commit -m "DEV-185: expose TradingView MCP compatibility health"
```

### Task 4: Document the env knobs and operator smoke-test command

**Files:**
- Modify: `.env.example`

- [ ] **Step 1: Add the new env block to `.env.example`**

```env
# Local TradingView MCP compatibility guardrail
TRADINGVIEW_APP_PATH=/Applications/TradingView.app
TRADINGVIEW_ALLOWED_VERSIONS=2.9.0
TRADINGVIEW_MCP_COMPATIBILITY_TTL_SECONDS=60

# Operator check:
# curl -s http://127.0.0.1:8765/health/compatibility | jq
```

- [ ] **Step 2: Verify the new env keys are present and spelled correctly**

Run:

```bash
rg -n "TRADINGVIEW_APP_PATH|TRADINGVIEW_ALLOWED_VERSIONS|TRADINGVIEW_MCP_COMPATIBILITY_TTL_SECONDS|health/compatibility" .env.example
```

Expected:

- Four matches in `.env.example`

- [ ] **Step 3: Run the focused regression suite before finalizing**

Run:

```bash
PYTHONPATH=. pytest tests/services/test_tradingview_mcp_compatibility.py tests/services/test_local_chart_provider_service.py tests/api/test_local_chart_provider_app.py -v
```

Expected:

- PASS for all compatibility, provider-service, and provider-app tests

- [ ] **Step 4: Commit the operator documentation**

```bash
git add .env.example
git commit -m "DEV-185: document TradingView MCP compatibility settings"
```

## Self-Review Checklist

- Spec coverage:
  - allowlist + smoke test: Task 1
  - short-TTL cache: Task 1
  - degraded chart-context short-circuit: Task 2
  - operator-facing compatibility check: Task 3
  - env/documentation workflow: Task 4
- Placeholder scan:
  - no `TODO`, `TBD`, or “handle appropriately” instructions remain
- Type consistency:
  - status payload fields stay aligned across service, provider, and API: `status`, `chart_context_enabled`, `tradingview_version`, `checked_at`, `reason`, `probe`
