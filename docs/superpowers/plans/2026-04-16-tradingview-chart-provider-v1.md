# TradingView Chart Provider V1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the first read-only TradingView chart provider integration so the AI Operating Layer can automatically attach real structured chart context to shadow pre-trade and post-trade review runs.

**Architecture:** Add one external adapter that calls a single global provider endpoint, validates the provider response through the existing chart-context service, and threads normalized chart state into AI Operating Layer runs. Keep the provider read-only, execution-independent, and failure-tolerant with a short retry budget and degraded fallback behavior.

**Tech Stack:** Python services and adapters, FastAPI config API, existing AI Operating Layer services, pytest

---

## File Structure

### New files

- `src/adapters/tradingview_chart_provider.py`
  - Read-only adapter for the external TradingView chart provider endpoint.
- `tests/adapters/test_tradingview_chart_provider.py`
  - Adapter tests for success, retry, timeout, and degraded failure cases.
- `tests/services/test_chart_context_fetch.py`
  - Service tests for validating required structured fields and degraded normalization.
- `tests/services/test_ai_operating_layer_provider_integration.py`
  - Orchestration tests for automatic pre-trade and post-trade fetch behavior.

### Existing files to modify

- `src/services/chart_context_service.py`
  - Expand normalization to validate required provider contract fields and expose fetch helpers.
- `src/services/ai_operating_layer.py`
  - Automatically fetch chart context for shadow pre-trade and post-trade review runs.
- `src/api_config.py`
  - Extend AI Operating Layer config to include provider enabled/base URL/timeout/retry settings.
- `frontend/src/lib/api.ts`
  - Extend config typing if new provider config fields are exposed to the existing settings UI.
- `frontend/src/components/settings/AiConfigPanel.tsx`
  - Add global provider endpoint and retry/timeout controls if this plan includes operator configuration in the first slice.

## Task 1: Build the TradingView chart provider adapter

**Files:**
- Create: `src/adapters/tradingview_chart_provider.py`
- Test: `tests/adapters/test_tradingview_chart_provider.py`

- [ ] **Step 1: Write the failing adapter tests**

```python
from src.adapters.tradingview_chart_provider import fetch_chart_context


def test_fetch_chart_context_returns_provider_payload(monkeypatch) -> None:
    class _Response:
        status_code = 200

        def json(self):
            return {
                "symbol": "XAUUSD",
                "timeframe": "5m",
                "provider_timestamp": "2026-04-16T12:00:00Z",
                "pine_labels": ["entry"],
                "zones": [],
                "indicator_values": {"rsi": 54.2},
            }

        def raise_for_status(self):
            return None

    monkeypatch.setattr(
        "src.adapters.tradingview_chart_provider.requests.get",
        lambda *args, **kwargs: _Response(),
    )

    payload = fetch_chart_context(
        base_url="http://provider.test",
        symbol="XAUUSD",
        timeframe="5m",
        timeout_seconds=1.0,
        retry_count=0,
    )

    assert payload["symbol"] == "XAUUSD"
    assert payload["indicator_values"]["rsi"] == 54.2


def test_fetch_chart_context_returns_failure_reason_after_retries(monkeypatch) -> None:
    calls = {"count": 0}

    def _boom(*_args, **_kwargs):
        calls["count"] += 1
        raise TimeoutError("provider timeout")

    monkeypatch.setattr(
        "src.adapters.tradingview_chart_provider.requests.get",
        _boom,
    )

    payload = fetch_chart_context(
        base_url="http://provider.test",
        symbol="XAUUSD",
        timeframe="5m",
        timeout_seconds=0.2,
        retry_count=2,
    )

    assert payload["ok"] is False
    assert "provider timeout" in payload["reason"]
    assert calls["count"] == 3
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH=. pytest tests/adapters/test_tradingview_chart_provider.py -v`
Expected: FAIL with `ModuleNotFoundError` for `src.adapters.tradingview_chart_provider`

- [ ] **Step 3: Write the minimal adapter implementation**

```python
from __future__ import annotations

from typing import Any, Dict

import requests


def fetch_chart_context(
    base_url: str,
    symbol: str,
    timeframe: str,
    timeout_seconds: float,
    retry_count: int,
) -> Dict[str, Any]:
    last_error = "unknown provider error"
    for _attempt in range(retry_count + 1):
        try:
            response = requests.get(
                f"{base_url.rstrip('/')}/chart-context",
                params={"symbol": symbol, "timeframe": timeframe},
                timeout=timeout_seconds,
            )
            response.raise_for_status()
            payload = response.json()
            return {"ok": True, **payload}
        except Exception as exc:  # noqa: BLE001
            last_error = str(exc)

    return {
        "ok": False,
        "symbol": symbol,
        "timeframe": timeframe,
        "reason": last_error,
    }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `PYTHONPATH=. pytest tests/adapters/test_tradingview_chart_provider.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add tests/adapters/test_tradingview_chart_provider.py src/adapters/tradingview_chart_provider.py
git commit -m "DEV-121: add tradingview chart provider adapter"
```

## Task 2: Expand chart-context service validation and normalization

**Files:**
- Modify: `src/services/chart_context_service.py`
- Test: `tests/services/test_chart_context_fetch.py`

- [ ] **Step 1: Write the failing chart-context validation tests**

```python
from src.services.chart_context_service import (
    ChartContextProviderResult,
    normalize_chart_context,
)


def test_normalize_chart_context_requires_structured_contract_fields() -> None:
    payload = normalize_chart_context(
        ChartContextProviderResult(
            ok=True,
            symbol="XAUUSD",
            timeframe="5m",
            structured={"zones": []},
            screenshot_url=None,
            reason="",
        )
    )

    assert payload["status"] == "degraded"
    assert payload["reason"] == "provider returned incomplete structured state"


def test_normalize_chart_context_accepts_full_structured_contract() -> None:
    payload = normalize_chart_context(
        ChartContextProviderResult(
            ok=True,
            symbol="XAUUSD",
            timeframe="5m",
            structured={
                "provider_timestamp": "2026-04-16T12:00:00Z",
                "pine_labels": [],
                "zones": [],
                "indicator_values": {"rsi": 54.2},
            },
            screenshot_url=None,
            reason="",
        )
    )

    assert payload["status"] == "ok"
    assert payload["structured"]["provider_timestamp"] == "2026-04-16T12:00:00Z"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH=. pytest tests/services/test_chart_context_fetch.py -v`
Expected: FAIL because `normalize_chart_context` currently accepts incomplete structured state

- [ ] **Step 3: Implement structured contract validation**

```python
_REQUIRED_STRUCTURED_KEYS = {
    "provider_timestamp",
    "pine_labels",
    "zones",
    "indicator_values",
}


def _has_required_structured_fields(structured: Dict[str, Any]) -> bool:
    return _REQUIRED_STRUCTURED_KEYS.issubset(structured.keys())


def normalize_chart_context(provider_result: ChartContextProviderResult) -> Dict[str, Any]:
    structured = provider_result.structured or {}
    if not provider_result.ok:
        return {
            "status": "degraded",
            "symbol": provider_result.symbol,
            "timeframe": provider_result.timeframe,
            "reason": provider_result.reason,
            "structured": {},
            "screenshot_url": provider_result.screenshot_url,
        }
    if not _has_required_structured_fields(structured):
        return {
            "status": "degraded",
            "symbol": provider_result.symbol,
            "timeframe": provider_result.timeframe,
            "reason": "provider returned incomplete structured state",
            "structured": {},
            "screenshot_url": provider_result.screenshot_url,
        }
    return {
        "status": "ok",
        "symbol": provider_result.symbol,
        "timeframe": provider_result.timeframe,
        "reason": "",
        "structured": structured,
        "screenshot_url": provider_result.screenshot_url,
    }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `PYTHONPATH=. pytest tests/services/test_chart_context_fetch.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add tests/services/test_chart_context_fetch.py src/services/chart_context_service.py
git commit -m "DEV-121: validate chart provider contract"
```

## Task 3: Automatically fetch provider context inside the AI Operating Layer

**Files:**
- Modify: `src/services/ai_operating_layer.py`
- Test: `tests/services/test_ai_operating_layer_provider_integration.py`

- [ ] **Step 1: Write the failing orchestration tests**

```python
from src.services.ai_operating_layer import build_shadow_pretrade_run, build_posttrade_review_run


def test_shadow_pretrade_run_fetches_chart_context(monkeypatch) -> None:
    monkeypatch.setattr(
        "src.services.ai_operating_layer.fetch_and_normalize_chart_context",
        lambda **_kwargs: {"status": "ok", "structured": {"provider_timestamp": "2026-04-16T12:00:00Z"}},
    )

    payload = build_shadow_pretrade_run(
        signal_payload={"symbol": "XAUUSD", "timeframe": "5m"},
        chart_context=None,
        pine_context={"script_name": "Liquidity Sweeps"},
    )

    assert payload["chart_context"]["status"] == "ok"
    assert payload["module_status"]["chart_context"]["status"] == "ok"


def test_posttrade_review_run_records_degraded_provider_failure(monkeypatch) -> None:
    monkeypatch.setattr(
        "src.services.ai_operating_layer.fetch_and_normalize_chart_context",
        lambda **_kwargs: {"status": "degraded", "reason": "provider timeout", "structured": {}},
    )

    payload = build_posttrade_review_run(
        signal_payload={"symbol": "XAUUSD", "timeframe": "5m"},
        trade_outcome={"result": "loss"},
        chart_context=None,
        pine_context={"script_name": "Liquidity Sweeps"},
    )

    assert payload["chart_context"]["status"] == "degraded"
    assert payload["module_status"]["chart_context"]["reason"] == "provider timeout"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH=. pytest tests/services/test_ai_operating_layer_provider_integration.py -v`
Expected: FAIL because `build_shadow_pretrade_run` and `build_posttrade_review_run` do not fetch provider context automatically

- [ ] **Step 3: Implement the minimal automatic fetch path**

```python
from src.adapters.tradingview_chart_provider import fetch_chart_context
from src.services.chart_context_service import (
    ChartContextProviderResult,
    normalize_chart_context,
)


def fetch_and_normalize_chart_context(
    base_url: str,
    symbol: str,
    timeframe: str,
    timeout_seconds: float,
    retry_count: int,
) -> Dict[str, Any]:
    raw = fetch_chart_context(base_url, symbol, timeframe, timeout_seconds, retry_count)
    return normalize_chart_context(
        ChartContextProviderResult(
            ok=raw.get("ok", False),
            symbol=raw.get("symbol", symbol),
            timeframe=raw.get("timeframe", timeframe),
            structured={
                "provider_timestamp": raw.get("provider_timestamp"),
                "pine_labels": raw.get("pine_labels", []),
                "zones": raw.get("zones", []),
                "indicator_values": raw.get("indicator_values", {}),
            }
            if raw.get("ok")
            else {},
            screenshot_url=raw.get("screenshot_url"),
            reason=raw.get("reason", ""),
        )
    )
```

```python
def build_shadow_pretrade_run(
    signal_payload: Dict[str, Any],
    chart_context: Dict[str, Any] | None,
    pine_context: Dict[str, Any],
) -> Dict[str, Any]:
    resolved_chart_context = chart_context or fetch_and_normalize_chart_context(
        base_url="http://localhost:8765",
        symbol=str(signal_payload.get("symbol", "UNKNOWN")),
        timeframe=str(signal_payload.get("timeframe", "5m")),
        timeout_seconds=1.0,
        retry_count=2,
    )
    return {
        "analysis_mode": "shadow_pretrade",
        "signal_payload": signal_payload,
        "chart_context": resolved_chart_context,
        "pine_context": pine_context,
        "module_status": {
            "chart_context": {
                "status": resolved_chart_context.get("status", "degraded"),
                "reason": resolved_chart_context.get("reason", ""),
            }
        },
        "layered_output": _base_layered_output(),
    }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `PYTHONPATH=. pytest tests/services/test_ai_operating_layer_provider_integration.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add tests/services/test_ai_operating_layer_provider_integration.py src/services/ai_operating_layer.py
git commit -m "DEV-121: auto-fetch chart context for AI runs"
```

## Task 4: Add global provider config to the config API

**Files:**
- Modify: `src/api_config.py`
- Test: `tests/api/test_api_config_ai_operating_layer.py`

- [ ] **Step 1: Extend the failing API test with provider config assertions**

```python
def test_patch_ai_operating_layer_config_updates_provider_fields(monkeypatch) -> None:
    # setup omitted
    response = client.patch(
        "/api/v1/config/ai-operating-layer",
        json={
            "provider": {
                "enabled": True,
                "base_url": "http://provider.test",
                "timeout_seconds": 1.0,
                "retry_count": 2,
            }
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["provider"]["enabled"] is True
    assert body["provider"]["base_url"] == "http://provider.test"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH=. pytest tests/api/test_api_config_ai_operating_layer.py -v`
Expected: FAIL because provider config fields are not part of the response model yet

- [ ] **Step 3: Add provider config to the API models and persistence**

```python
class AiOperatingLayerProviderConfig(BaseModel):
    enabled: bool
    base_url: str
    timeout_seconds: float
    retry_count: int


class AiOperatingLayerConfigResponse(BaseModel):
    panic_mode: bool
    modules: Dict[str, str]
    provider: AiOperatingLayerProviderConfig
```

```python
provider = {
    "enabled": str(kv.get(_AI_LAYER_PROVIDER_ENABLED_KEY, "false")).lower() == "true",
    "base_url": kv.get(_AI_LAYER_PROVIDER_BASE_URL_KEY, ""),
    "timeout_seconds": float(kv.get(_AI_LAYER_PROVIDER_TIMEOUT_KEY, "1.0")),
    "retry_count": int(kv.get(_AI_LAYER_PROVIDER_RETRY_KEY, "2")),
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `PYTHONPATH=. pytest tests/api/test_api_config_ai_operating_layer.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add tests/api/test_api_config_ai_operating_layer.py src/api_config.py
git commit -m "DEV-121: add chart provider config API"
```

## Task 5: Surface provider config in the existing settings UI

**Files:**
- Modify: `frontend/src/lib/api.ts`
- Modify: `frontend/src/components/settings/AiConfigPanel.tsx`
- Modify: `frontend/src/components/settings/AiConfigPanel.test.tsx`

- [ ] **Step 1: Extend the failing frontend test with provider config expectations**

```tsx
expect(container.textContent).toContain('Provider Endpoint');
expect(container.textContent).toContain('Retry Count');
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && npx vitest run src/components/settings/AiConfigPanel.test.tsx`
Expected: FAIL because the settings panel does not render provider controls yet

- [ ] **Step 3: Add provider config fields to the UI**

```tsx
<div className="space-y-2">
  <label className="text-[11px] text-[var(--to-text-dim)] uppercase tracking-wider font-mono">
    Provider Endpoint
  </label>
  <input
    value={providerDraft.base_url}
    onChange={(e) =>
      setProviderDraft((current) => ({ ...current, base_url: e.target.value }))
    }
    className="w-full rounded border border-[#2a2e39] bg-[#1e222d] px-2 py-1 text-[11px] font-mono text-[var(--to-text-primary)]"
  />
</div>
```

```tsx
<ConfigRow label="Retry Count" value={providerDraft.retry_count} />
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd frontend && npx vitest run src/components/settings/AiConfigPanel.test.tsx`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add frontend/src/lib/api.ts frontend/src/components/settings/AiConfigPanel.tsx frontend/src/components/settings/AiConfigPanel.test.tsx
git commit -m "DEV-121: add chart provider settings UI"
```

## Task 6: Run targeted verification for the provider slice

**Files:**
- Modify: `docs/superpowers/plans/2026-04-16-tradingview-chart-provider-v1.md`

- [ ] **Step 1: Add the provider verification checklist to the plan**

```md
### Verification checklist

- `PYTHONPATH=. pytest tests/adapters/test_tradingview_chart_provider.py -v`
- `PYTHONPATH=. pytest tests/services/test_chart_context_fetch.py tests/services/test_ai_operating_layer_provider_integration.py -v`
- `PYTHONPATH=. pytest tests/api/test_api_config_ai_operating_layer.py -v`
- `cd frontend && npx vitest run src/components/settings/AiConfigPanel.test.tsx`
- Confirm provider failures result in degraded chart context instead of hard failure
- Confirm pre-trade and post-trade runs attach normalized chart context when provider succeeds
```

- [ ] **Step 2: Run the verification commands**

Run:

```bash
PYTHONPATH=. pytest tests/adapters/test_tradingview_chart_provider.py tests/services/test_chart_context_fetch.py tests/services/test_ai_operating_layer_provider_integration.py -v
PYTHONPATH=. pytest tests/api/test_api_config_ai_operating_layer.py -v
cd frontend && npx vitest run src/components/settings/AiConfigPanel.test.tsx
```

Expected: PASS, with unrelated pre-existing warnings left untouched

- [ ] **Step 3: Commit**

```bash
git add docs/superpowers/plans/2026-04-16-tradingview-chart-provider-v1.md
git commit -m "DEV-121: add chart provider verification checklist"
```

## Self-Review

### Spec coverage

- External read-only adapter: covered by Task 1.
- Structured provider contract validation: covered by Task 2.
- Automatic pre-trade and post-trade fetch integration: covered by Task 3.
- Global provider config: covered by Task 4.
- Settings UI for provider config: covered by Task 5.
- Verification and degraded behavior: covered by Task 6.

### Placeholder scan

- No `TODO`, `TBD`, or “implement later” markers remain.
- Every code-edit step includes concrete code to write.
- Every test step includes a concrete command and expected result.

### Type consistency

- Provider fields use `enabled`, `base_url`, `timeout_seconds`, and `retry_count` consistently across adapter config, API models, and UI.
- Chart payload contract uses `provider_timestamp`, `pine_labels`, `zones`, and `indicator_values` consistently across adapter, service, and orchestration steps.

Plan complete and saved to `docs/superpowers/plans/2026-04-16-tradingview-chart-provider-v1.md`. Two execution options:

**1. Subagent-Driven (recommended)** - I dispatch a fresh subagent per task, review between tasks, fast iteration

**2. Inline Execution** - Execute tasks in this session using executing-plans, batch execution with checkpoints

Which approach?
