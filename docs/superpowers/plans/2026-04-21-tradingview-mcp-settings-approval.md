# TradingView MCP Settings Approval Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move TradingView MCP version approval from env vars into the app settings flow, backed by `system_config` and a settings-page approve action tied to the local provider’s detected TradingView version.

**Architecture:** Add backend config endpoints for approved TradingView versions, update the local compatibility service to fetch that approval policy from the backend instead of env-based allowlists, and add a dedicated settings panel that combines backend-approved versions with the local provider’s compatibility status. Because the browser will query `http://127.0.0.1:8765` directly, add explicit CORS support to the local provider app for this read-only status call.

**Tech Stack:** Python, FastAPI, Supabase system_config, Pydantic, requests, React, Next.js, TypeScript, Vitest, pytest

---

## File Structure

- Modify: `src/api_config.py`
  - Add TradingView MCP config models, normalization helper, and `GET/PATCH /api/v1/config/tradingview-mcp`.
- Create: `tests/api/test_api_config_tradingview_mcp.py`
  - Cover default read, normalization/deduping, and clear-to-empty behavior.
- Modify: `src/services/tradingview_mcp_compatibility.py`
  - Replace env-backed approval lookup with backend-config fetch plus short-TTL reuse.
- Modify: `config/settings.py`
  - Remove env-backed approved-version config fields no longer used for approval policy; keep local app path and TTL.
- Modify: `tests/services/test_tradingview_mcp_compatibility.py`
  - Cover backend approval fetch, unavailable backend config, and the still-required local probe behavior.
- Modify: `src/local_chart_provider_app.py`
  - Add CORS middleware so the settings page can call the local provider health endpoint from the browser.
- Modify: `tests/api/test_local_chart_provider_app.py`
  - Add focused coverage for CORS on the local compatibility endpoint.
- Modify: `frontend/src/lib/api.ts`
  - Add backend config helpers and local-provider compatibility fetch helper.
- Create: `frontend/src/components/settings/TradingViewMcpPanel.tsx`
  - Show approved versions, local status, and approve-current-version flow.
- Create: `frontend/src/components/settings/TradingViewMcpPanel.test.tsx`
  - Cover load, approve flow, and probe-failure-but-version-present behavior.
- Modify: `frontend/src/app/settings/page.tsx`
  - Mount the new TradingView MCP panel in the settings page.
- Modify: `.env.example`
  - Remove `TRADINGVIEW_ALLOWED_VERSIONS` guidance and note that approvals are now managed in the settings page.

### Task 1: Add backend config endpoints for approved TradingView versions

**Files:**
- Modify: `src/api_config.py`
- Create: `tests/api/test_api_config_tradingview_mcp.py`

- [ ] **Step 1: Write the failing API tests first**

```python
from fastapi import FastAPI
from fastapi.testclient import TestClient

import src.api_config as api_config


def test_get_tradingview_mcp_config_returns_empty_defaults(monkeypatch) -> None:
    class _Resp:
        def __init__(self, data):
            self.data = data

    class _Query:
        def select(self, *_args, **_kwargs):
            return self

        def in_(self, *_args, **_kwargs):
            return self

        def execute(self):
            return _Resp([])

    class _Supabase:
        def table(self, _name: str):
            return _Query()

    monkeypatch.setattr(api_config, "_get_supabase", lambda: _Supabase())

    app = FastAPI()
    app.include_router(api_config.router)
    client = TestClient(app)

    response = client.get("/api/v1/config/tradingview-mcp")

    assert response.status_code == 200
    assert response.json() == {"approved_versions": []}


def test_patch_tradingview_mcp_config_normalizes_and_deduplicates(monkeypatch) -> None:
    store: dict[str, str] = {}

    class _Resp:
        def __init__(self, data):
            self.data = data

    class _SelectQuery:
        def select(self, *_args, **_kwargs):
            return self

        def in_(self, _field: str, keys):
            self._keys = keys
            return self

        def execute(self):
            rows = [{"key": key, "value": value} for key, value in store.items() if key in self._keys]
            return _Resp(rows)

    class _UpsertQuery:
        def upsert(self, payload, **_kwargs):
            store[payload["key"]] = payload["value"]
            return self

        def execute(self):
            return _Resp([])

    class _Supabase:
        def table(self, _name: str):
            class _Table:
                def select(self, *_args, **_kwargs):
                    return _SelectQuery().select(*_args, **_kwargs)

                def upsert(self, payload, **_kwargs):
                    return _UpsertQuery().upsert(payload, **_kwargs)

            return _Table()

    monkeypatch.setattr(api_config, "_get_supabase", lambda: _Supabase())

    app = FastAPI()
    app.include_router(api_config.router)
    client = TestClient(app)

    response = client.patch(
        "/api/v1/config/tradingview-mcp",
        json={"approved_versions": [" 2.9.0 ", "2.9.0", "2.9.1"]},
    )

    assert response.status_code == 200
    assert response.json() == {"approved_versions": ["2.9.0", "2.9.1"]}
    assert store["local_chart_tradingview_allowed_versions"] == '["2.9.0", "2.9.1"]'


def test_patch_tradingview_mcp_config_allows_clearing_versions(monkeypatch) -> None:
    store = {"local_chart_tradingview_allowed_versions": '["2.9.0"]'}

    class _Resp:
        def __init__(self, data):
            self.data = data

    class _SelectQuery:
        def select(self, *_args, **_kwargs):
            return self

        def in_(self, _field: str, keys):
            self._keys = keys
            return self

        def execute(self):
            rows = [{"key": key, "value": value} for key, value in store.items() if key in self._keys]
            return _Resp(rows)

    class _UpsertQuery:
        def upsert(self, payload, **_kwargs):
            store[payload["key"]] = payload["value"]
            return self

        def execute(self):
            return _Resp([])

    class _Supabase:
        def table(self, _name: str):
            class _Table:
                def select(self, *_args, **_kwargs):
                    return _SelectQuery().select(*_args, **_kwargs)

                def upsert(self, payload, **_kwargs):
                    return _UpsertQuery().upsert(payload, **_kwargs)

            return _Table()

    monkeypatch.setattr(api_config, "_get_supabase", lambda: _Supabase())

    app = FastAPI()
    app.include_router(api_config.router)
    client = TestClient(app)

    response = client.patch(
        "/api/v1/config/tradingview-mcp",
        json={"approved_versions": []},
    )

    assert response.status_code == 200
    assert response.json() == {"approved_versions": []}
    assert store["local_chart_tradingview_allowed_versions"] == "[]"
```

- [ ] **Step 2: Run the new API test file to confirm it fails before implementation**

Run:

```bash
PYTHONPATH=. pytest tests/api/test_api_config_tradingview_mcp.py -v
```

Expected:

- FAIL with `404` for `/api/v1/config/tradingview-mcp`

- [ ] **Step 3: Add the new models, key constant, and normalization helper in `src/api_config.py`**

```python
import json
import logging
from typing import Dict, Literal
```

```python
class TradingViewMcpConfigResponse(BaseModel):
    approved_versions: list[str]


class PatchTradingViewMcpConfigRequest(BaseModel):
    approved_versions: list[str] = Field(default_factory=list)
```

```python
_TRADINGVIEW_MCP_ALLOWED_VERSIONS_KEY = "local_chart_tradingview_allowed_versions"
```

```python
def _normalize_tradingview_versions(values: list[str]) -> list[str]:
    normalized: list[str] = []
    seen: set[str] = set()
    for raw in values:
        value = str(raw).strip()
        if not value or value in seen:
            continue
        normalized.append(value)
        seen.add(value)
    return normalized
```

- [ ] **Step 4: Add the new TradingView MCP config endpoints in `src/api_config.py`**

```python
@router.get("/tradingview-mcp", response_model=TradingViewMcpConfigResponse)
def get_tradingview_mcp_config():
    try:
        kv = _read_system_config([_TRADINGVIEW_MCP_ALLOWED_VERSIONS_KEY])
        raw = kv.get(_TRADINGVIEW_MCP_ALLOWED_VERSIONS_KEY, "[]")
        approved_versions = json.loads(raw) if raw else []
        if not isinstance(approved_versions, list):
            approved_versions = []
        return {
            "approved_versions": _normalize_tradingview_versions(
                [str(item) for item in approved_versions]
            )
        }
    except Exception as e:
        logger.error(f"Failed to fetch TradingView MCP config: {e}")
        raise HTTPException(status_code=500, detail="Could not fetch TradingView MCP config")


@router.patch("/tradingview-mcp", response_model=TradingViewMcpConfigResponse)
def patch_tradingview_mcp_config(body: PatchTradingViewMcpConfigRequest):
    try:
        approved_versions = _normalize_tradingview_versions(body.approved_versions)
        _get_supabase().table("system_config").upsert(
            {
                "key": _TRADINGVIEW_MCP_ALLOWED_VERSIONS_KEY,
                "value": json.dumps(approved_versions),
            },
            on_conflict="key",
        ).execute()
        return {"approved_versions": approved_versions}
    except Exception as e:
        logger.error(f"Failed to update TradingView MCP config: {e}")
        raise HTTPException(status_code=500, detail="Could not update TradingView MCP config")
```

- [ ] **Step 5: Run the backend TradingView MCP config tests again**

Run:

```bash
PYTHONPATH=. pytest tests/api/test_api_config_tradingview_mcp.py -v
```

Expected:

- PASS for all 3 tests

- [ ] **Step 6: Commit the backend config API**

```bash
git add src/api_config.py tests/api/test_api_config_tradingview_mcp.py
git commit -m "DEV-188: add TradingView MCP config endpoints"
```

### Task 2: Move local compatibility approval lookup from env to backend config

**Files:**
- Modify: `src/services/tradingview_mcp_compatibility.py`
- Modify: `config/settings.py`
- Modify: `tests/services/test_tradingview_mcp_compatibility.py`

- [ ] **Step 1: Extend the compatibility tests with failing backend-approval-source coverage**

```python
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


def test_backend_approval_fetch_failure_disables_chart_context(tmp_path: Path) -> None:
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
```

- [ ] **Step 2: Run the compatibility service tests to verify they fail before the service rewrite**

Run:

```bash
PYTHONPATH=. pytest tests/services/test_tradingview_mcp_compatibility.py -v
```

Expected:

- FAIL because `approved_versions_fetcher` is not yet supported

- [ ] **Step 3: Remove the env-backed approved-version field from `config/settings.py`**

```python
    tradingview_app_path: str = Field(
        default="/Applications/TradingView.app",
        description="Local TradingView Desktop app bundle path used for version detection.",
        validation_alias="TRADINGVIEW_APP_PATH",
    )
    tradingview_mcp_compatibility_ttl_seconds: int = Field(
        default=60,
        ge=1,
        le=3600,
        description="Seconds to cache TradingView MCP compatibility results before re-probing.",
        validation_alias="TRADINGVIEW_MCP_COMPATIBILITY_TTL_SECONDS",
    )
```

Delete this property entirely:

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

- [ ] **Step 4: Rewrite `src/services/tradingview_mcp_compatibility.py` to fetch approved versions from the backend config API**

```python
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
```

```python
BACKEND_APPROVALS_PATH = "/api/v1/config/tradingview-mcp"
```

```python
def _backend_base_url() -> str:
    settings = get_settings()
    base_url = settings.public_api_base_url or "http://127.0.0.1:8000"
    return base_url.rstrip("/")


def _fetch_approved_versions_from_backend() -> list[str]:
    response = requests.get(
        f"{_backend_base_url()}{BACKEND_APPROVALS_PATH}",
        timeout=5,
    )
    response.raise_for_status()
    payload = response.json()
    approved_versions = payload.get("approved_versions", [])
    if not isinstance(approved_versions, list):
        return []
    normalized: list[str] = []
    seen: set[str] = set()
    for raw in approved_versions:
        value = str(raw).strip()
        if not value or value in seen:
            continue
        normalized.append(value)
        seen.add(value)
    return normalized
```

```python
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
```

```python
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
```

```python
@lru_cache
def get_tradingview_mcp_compatibility_service() -> TradingViewMcpCompatibilityService:
    settings = get_settings()
    return TradingViewMcpCompatibilityService(
        ttl_seconds=settings.tradingview_mcp_compatibility_ttl_seconds,
        tradingview_app_path=Path(settings.tradingview_app_path),
        mcp_repo_path=MCP_REPO_PATH,
    )
```

- [ ] **Step 5: Run the compatibility service tests again**

Run:

```bash
PYTHONPATH=. pytest tests/services/test_tradingview_mcp_compatibility.py -v
```

Expected:

- PASS for the existing probe/version tests
- PASS for the new backend-approval-source tests

- [ ] **Step 6: Commit the backend-backed compatibility service**

```bash
git add config/settings.py src/services/tradingview_mcp_compatibility.py tests/services/test_tradingview_mcp_compatibility.py
git commit -m "DEV-188: load TradingView approvals from backend config"
```

### Task 3: Add settings-page UI and browser access to local compatibility status

**Files:**
- Modify: `src/local_chart_provider_app.py`
- Modify: `tests/api/test_local_chart_provider_app.py`
- Modify: `frontend/src/lib/api.ts`
- Create: `frontend/src/components/settings/TradingViewMcpPanel.tsx`
- Create: `frontend/src/components/settings/TradingViewMcpPanel.test.tsx`
- Modify: `frontend/src/app/settings/page.tsx`

- [ ] **Step 1: Add the failing provider-app test for CORS on the compatibility endpoint**

```python
def test_compatibility_health_endpoint_allows_browser_origin(monkeypatch) -> None:
    monkeypatch.setattr(
        "src.local_chart_provider_app.get_chart_provider_compatibility_status",
        lambda: {
            "status": "supported",
            "chart_context_enabled": True,
            "tradingview_version": "2.9.0",
            "checked_at": "2026-04-21T12:00:00Z",
            "reason": "",
            "probe": {"command": "status", "ok": True},
        },
    )

    client = TestClient(app)
    response = client.options(
        "/health/compatibility",
        headers={
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": "GET",
        },
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://localhost:3000"
```

- [ ] **Step 2: Add the failing frontend component test**

```tsx
/** @vitest-environment jsdom */

import { createRoot, Root } from 'react-dom/client';
import { act } from 'react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { TradingViewMcpPanel } from './TradingViewMcpPanel';

vi.mock('@/lib/api', () => ({
  fetchTradingViewMcpConfig: vi.fn().mockResolvedValue({
    approved_versions: ['2.9.0'],
  }),
  patchTradingViewMcpConfig: vi.fn().mockResolvedValue({
    approved_versions: ['2.9.0', '2.9.1'],
  }),
  fetchLocalTradingViewMcpCompatibility: vi.fn().mockResolvedValue({
    status: 'unsupported_version',
    chart_context_enabled: false,
    tradingview_version: '2.9.1',
    checked_at: '2026-04-21T12:00:00Z',
    reason: 'TradingView Desktop 2.9.1 is not approved in app settings',
    probe: { command: 'status', ok: true },
  }),
}));

describe('TradingViewMcpPanel', () => {
  let container: HTMLDivElement;
  let root: Root;

  beforeEach(() => {
    container = document.createElement('div');
    document.body.appendChild(container);
    root = createRoot(container);
  });

  afterEach(() => {
    act(() => {
      root.unmount();
    });
    container.remove();
    vi.clearAllMocks();
  });

  it('loads status and approves the current detected version', async () => {
    const api = await import('@/lib/api');

    await act(async () => {
      root.render(<TradingViewMcpPanel />);
    });

    expect(container.textContent).toContain('TradingView MCP Compatibility');
    expect(container.textContent).toContain('2.9.1');
    expect(container.textContent).toContain('Approve Current Version');

    await act(async () => {
      const approveButton = Array.from(container.querySelectorAll('button')).find(
        (button) => button.textContent?.includes('Approve Current Version')
      );
      approveButton?.dispatchEvent(new MouseEvent('click', { bubbles: true }));
    });

    expect(api.patchTradingViewMcpConfig).toHaveBeenCalledWith({
      approved_versions: ['2.9.0', '2.9.1'],
    });
  });
});
```

- [ ] **Step 3: Run the focused provider-app and frontend test files to confirm they fail before implementation**

Run:

```bash
PYTHONPATH=. pytest tests/api/test_local_chart_provider_app.py -v
cd frontend && npx vitest run src/components/settings/TradingViewMcpPanel.test.tsx
```

Expected:

- pytest FAIL because CORS middleware is not present
- vitest FAIL because `TradingViewMcpPanel` and new API helpers do not exist yet

- [ ] **Step 4: Add CORS middleware to `src/local_chart_provider_app.py`**

```python
from fastapi import FastAPI, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
```

```python
app = FastAPI(title="Local TradingView MCP Provider", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ],
    allow_credentials=False,
    allow_methods=["GET", "OPTIONS"],
    allow_headers=["*"],
)
app.mount("/provider-artifacts", StaticFiles(directory=ARTIFACTS_DIR), name="provider-artifacts")
```

- [ ] **Step 5: Add the new frontend API helpers in `frontend/src/lib/api.ts`**

```ts
export interface TradingViewMcpConfigResponse {
  approved_versions: string[];
}

export interface LocalTradingViewMcpCompatibilityResponse {
  status: string;
  chart_context_enabled: boolean;
  tradingview_version: string;
  checked_at: string;
  reason: string;
  probe: {
    command: string;
    ok: boolean;
    payload?: Record<string, unknown>;
  };
}

export async function fetchTradingViewMcpConfig(): Promise<TradingViewMcpConfigResponse> {
  return apiFetch<TradingViewMcpConfigResponse>('/api/v1/config/tradingview-mcp');
}

export async function patchTradingViewMcpConfig(payload: {
  approved_versions: string[];
}): Promise<TradingViewMcpConfigResponse> {
  return apiFetch<TradingViewMcpConfigResponse>('/api/v1/config/tradingview-mcp', {
    method: 'PATCH',
    body: JSON.stringify(payload),
  });
}

export async function fetchLocalTradingViewMcpCompatibility(): Promise<LocalTradingViewMcpCompatibilityResponse> {
  const response = await fetch('http://127.0.0.1:8765/health/compatibility', {
    cache: 'no-store',
  });
  if (!response.ok) {
    throw new Error('Failed to fetch local TradingView MCP compatibility');
  }
  return response.json();
}
```

- [ ] **Step 6: Create `frontend/src/components/settings/TradingViewMcpPanel.tsx`**

```tsx
'use client';

import { useEffect, useState } from 'react';
import {
  fetchLocalTradingViewMcpCompatibility,
  fetchTradingViewMcpConfig,
  patchTradingViewMcpConfig,
  type LocalTradingViewMcpCompatibilityResponse,
  type TradingViewMcpConfigResponse,
} from '@/lib/api';
import { AlertTriangle, Check, Loader2, RefreshCw, Shield } from 'lucide-react';

type LoadState = 'loading' | 'loaded' | 'error';

export function TradingViewMcpPanel() {
  const [state, setState] = useState<LoadState>('loading');
  const [error, setError] = useState('');
  const [config, setConfig] = useState<TradingViewMcpConfigResponse | null>(null);
  const [localStatus, setLocalStatus] = useState<LocalTradingViewMcpCompatibilityResponse | null>(null);
  const [saving, setSaving] = useState(false);

  const load = async () => {
    setState('loading');
    setError('');
    try {
      const [nextConfig, nextLocalStatus] = await Promise.all([
        fetchTradingViewMcpConfig(),
        fetchLocalTradingViewMcpCompatibility(),
      ]);
      setConfig(nextConfig);
      setLocalStatus(nextLocalStatus);
      setState('loaded');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load TradingView MCP settings');
      setState('error');
    }
  };

  useEffect(() => {
    load();
  }, []);

  const currentVersion = localStatus?.tradingview_version?.trim() || '';
  const approvedVersions = config?.approved_versions ?? [];
  const isApproved = !!currentVersion && approvedVersions.includes(currentVersion);

  const approveCurrentVersion = async () => {
    if (!currentVersion || saving) return;
    setSaving(true);
    try {
      const nextApprovedVersions = Array.from(new Set([...approvedVersions, currentVersion]));
      const nextConfig = await patchTradingViewMcpConfig({
        approved_versions: nextApprovedVersions,
      });
      setConfig(nextConfig);
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to approve current TradingView version');
      setState('error');
    } finally {
      setSaving(false);
    }
  };

  if (state === 'loading') {
    return (
      <div className="to-panel p-6 flex items-center justify-center gap-2">
        <Loader2 className="w-4 h-4 animate-spin text-text-muted" />
        <span className="text-xs font-mono text-text-muted">Loading TradingView MCP compatibility…</span>
      </div>
    );
  }

  if (state === 'error') {
    return (
      <div className="to-panel p-6 flex flex-col items-center gap-2">
        <AlertTriangle className="w-5 h-5 text-amber-400" />
        <span className="text-xs font-mono text-text-secondary">{error}</span>
        <button onClick={load} className="text-[10px] font-mono text-text-muted hover:text-text-secondary">
          Retry
        </button>
      </div>
    );
  }

  return (
    <div className="to-panel">
      <div className="to-panel-header">
        <div className="flex items-center gap-2">
          <Shield className="h-3.5 w-3.5 text-text-dim" />
          <span className="panel-label">TradingView MCP Compatibility</span>
        </div>
        <button onClick={load} className="text-[10px] font-mono text-text-muted hover:text-text-secondary">
          <RefreshCw className="w-3 h-3" />
        </button>
      </div>
      <div className="p-4 space-y-3 text-xs">
        <div className="flex items-center justify-between">
          <span className="text-[var(--to-text-dim)]">Current local version</span>
          <span className="font-mono text-[var(--to-text-secondary)]">{currentVersion || 'Not detected'}</span>
        </div>
        <div className="flex items-center justify-between">
          <span className="text-[var(--to-text-dim)]">Local status</span>
          <span className="font-mono text-[var(--to-text-secondary)]">{localStatus?.status || 'unknown'}</span>
        </div>
        <div className="space-y-1">
          <p className="text-[var(--to-text-dim)]">Approved versions</p>
          <div className="flex flex-wrap gap-2">
            {approvedVersions.length > 0 ? approvedVersions.map((version) => (
              <span key={version} className="rounded border border-[var(--to-border)] px-2 py-1 font-mono text-[10px]">
                {version}
              </span>
            )) : (
              <span className="font-mono text-[10px] text-[var(--to-text-dim)]">None approved</span>
            )}
          </div>
        </div>
        <p className="text-[11px] text-[var(--to-text-dim)]">
          Approving a version updates backend policy only. A failing local MCP probe can still keep chart context disabled.
        </p>
        {!isApproved && currentVersion && (
          <button
            type="button"
            onClick={approveCurrentVersion}
            disabled={saving}
            className="rounded-lg border border-[var(--to-border)] bg-[var(--to-surface-raised)] px-3 py-2 text-[11px] font-mono text-white hover:border-white/20 disabled:opacity-60"
          >
            {saving ? 'Saving…' : 'Approve Current Version'}
          </button>
        )}
        {isApproved && (
          <div className="inline-flex items-center gap-2 rounded-lg bg-emerald-500/10 px-3 py-2 text-[11px] font-mono text-[var(--to-long)]">
            <Check className="w-3 h-3" />
            Current version approved
          </div>
        )}
      </div>
    </div>
  );
}
```

- [ ] **Step 7: Mount the new panel on the settings page**

```tsx
import { TradingViewMcpPanel } from '@/components/settings/TradingViewMcpPanel';
```

```tsx
      {/* TradingView MCP compatibility */}
      <TradingViewMcpPanel />

      {/* AI / ML / RAG Configuration */}
      <AiConfigPanel />
```

- [ ] **Step 8: Run the focused provider-app and frontend tests again**

Run:

```bash
PYTHONPATH=. pytest tests/api/test_local_chart_provider_app.py -v
cd frontend && npx vitest run src/components/settings/TradingViewMcpPanel.test.tsx src/components/settings/AiConfigPanel.test.tsx
```

Expected:

- PASS for the local provider app tests, including the new CORS case
- PASS for the new TradingView MCP panel test
- PASS for the existing AI config panel test

- [ ] **Step 9: Commit the settings-page UI and local browser bridge**

```bash
git add src/local_chart_provider_app.py tests/api/test_local_chart_provider_app.py frontend/src/lib/api.ts frontend/src/components/settings/TradingViewMcpPanel.tsx frontend/src/components/settings/TradingViewMcpPanel.test.tsx frontend/src/app/settings/page.tsx
git commit -m "DEV-188: add TradingView MCP settings panel"
```

### Task 4: Update docs and run the focused end-to-end verification sweep

**Files:**
- Modify: `.env.example`

- [ ] **Step 1: Remove the env-based approval variable and replace it with settings-page guidance**

```env
# Local TradingView MCP compatibility guardrail
TRADINGVIEW_APP_PATH=/Applications/TradingView.app
TRADINGVIEW_MCP_COMPATIBILITY_TTL_SECONDS=60

# Approved TradingView Desktop versions are managed from Settings -> TradingView MCP Compatibility.
# Local check:
# curl -s http://127.0.0.1:8765/health/compatibility | jq
```

Delete this line entirely:

```env
TRADINGVIEW_ALLOWED_VERSIONS=2.9.0
```

- [ ] **Step 2: Verify the env docs reflect the new approval source**

Run:

```bash
rg -n "TRADINGVIEW_ALLOWED_VERSIONS|TradingView MCP Compatibility|health/compatibility" .env.example
```

Expected:

- No remaining `TRADINGVIEW_ALLOWED_VERSIONS` match
- Matches for the new settings-page note and local health-check command

- [ ] **Step 3: Run the focused backend, provider, and frontend regression suite**

Run:

```bash
PYTHONPATH=. pytest tests/api/test_api_config_tradingview_mcp.py tests/services/test_tradingview_mcp_compatibility.py tests/api/test_local_chart_provider_app.py -v
cd frontend && npx vitest run src/components/settings/TradingViewMcpPanel.test.tsx src/components/settings/AiConfigPanel.test.tsx
```

Expected:

- PASS for all new backend config tests
- PASS for all updated compatibility service tests
- PASS for local provider app tests
- PASS for the new TradingView MCP panel test
- PASS for the existing AI config panel test

- [ ] **Step 4: Manual verification of the operator flow**

Run:

```bash
./scripts/run_local_chart_stack.sh --fresh
curl -s http://127.0.0.1:8765/health/compatibility | jq
```

Then:

1. open `/settings`
2. confirm the TradingView MCP panel shows the detected local version
3. approve the current version
4. refresh the panel
5. confirm the approved versions list includes the current version
6. confirm local compatibility becomes `supported` once both approval and the local probe are good

Expected:

- settings page shows the approved version immediately after save
- local provider status transitions to `supported` on the next refresh when the probe is healthy

- [ ] **Step 5: Commit the docs cleanup**

```bash
git add .env.example
git commit -m "DEV-188: document settings-based MCP approvals"
```

## Self-Review Checklist

- Spec coverage:
  - backend-stored approvals: Task 1
  - local provider approval fetch from backend: Task 2
  - settings-page status + approve flow: Task 3
  - local/browser access to provider status: Task 3
  - env/doc cleanup and verification: Task 4
- Placeholder scan:
  - no `TODO`, `TBD`, “handle appropriately”, or cross-task references remain
- Type consistency:
  - backend payload stays `approved_versions: string[]`
  - local compatibility payload keeps `status`, `chart_context_enabled`, `tradingview_version`, `checked_at`, `reason`, `probe`
