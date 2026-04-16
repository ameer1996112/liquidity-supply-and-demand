# Setup Evidence Bundle Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Automatically capture a focused setup-evidence bundle from the TradingView MCP provider, persist it with AI runs, and render it in the AI Memo UI.

**Architecture:** Extend the local MCP-backed provider so `/chart-context` returns structured chart context plus a focused setup image reference derived from the same provider session. Thread that bundle through the existing chart-context normalization and `ai_runs.chart_context` JSON payload, then render the stored evidence in the existing AI Operating Layer panel without adding a new persistence subsystem.

**Tech Stack:** FastAPI, Python service layer, existing TradingView MCP CLI, Pillow, requests, Supabase-backed `ai_runs`, Next.js, TypeScript, Vitest

---

## File Structure

- Modify: `src/local_chart_provider_service.py`
  - Add MCP box-reading, primary-zone selection, chart screenshot capture, and focused crop helpers.
- Modify: `src/local_chart_provider_app.py`
  - Expose provider artifact files and promote relative screenshot paths to request-aware public URLs.
- Modify: `tests/services/test_local_chart_provider_service.py`
  - Cover bundle construction, zone selection, and screenshot degradation behavior.
- Modify: `tests/api/test_local_chart_provider_app.py`
  - Cover absolute screenshot URL shaping and static artifact exposure.
- Modify: `src/services/chart_context_service.py`
  - Normalize the new setup-evidence payload without breaking degraded behavior.
- Modify: `src/services/ai_operating_layer.py`
  - Preserve evidence bundle data in normalized chart context for pre-trade and post-trade runs.
- Modify: `tests/services/test_chart_context_fetch.py`
  - Extend normalized contract assertions for evidence payloads.
- Modify: `tests/services/test_ai_operating_layer_provider_integration.py`
  - Verify AI runs keep the evidence bundle in both success and degraded-image cases.
- Modify: `frontend/src/lib/api.ts`
  - Type the evidence bundle on `AiRunResponse`.
- Modify: `frontend/src/lib/aiRuns.ts`
  - Map typed setup evidence into the UI model.
- Create: `frontend/src/components/ai/SetupEvidencePanel.tsx`
  - Render the focused setup image, primary zone metadata, and compact chart evidence.
- Modify: `frontend/src/components/ai/AiOperatingLayerPanel.tsx`
  - Embed the setup evidence panel below chart-context status.
- Create: `frontend/src/components/ai/SetupEvidencePanel.test.tsx`
  - Verify screenshot, fallback, and zone rendering in isolation.

## Task 1: Extend the local provider contract with setup evidence

**Files:**
- Modify: `src/local_chart_provider_service.py`
- Modify: `tests/services/test_local_chart_provider_service.py`

- [ ] **Step 1: Write the failing provider tests for a successful evidence bundle**

```python
from src.local_chart_provider_service import build_chart_context_payload


def test_build_chart_context_payload_includes_setup_evidence_bundle() -> None:
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
            "file_path": "/tmp/setup-focus.png",
            "region": "chart",
        },
        now_iso="2026-04-17T00:20:00Z",
    )

    assert payload["setup_evidence"]["status"] == "ok"
    assert payload["setup_evidence"]["focus_zone"]["high"] == 0.7210
    assert payload["setup_evidence"]["focus_image"]["path"] == "/tmp/setup-focus.png"
```

- [ ] **Step 2: Write the failing provider test for screenshot degradation**

```python
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
```

- [ ] **Step 3: Run the focused provider tests to verify they fail**

Run:

```bash
PYTHONPATH=. pytest tests/services/test_local_chart_provider_service.py -k "setup_evidence or screenshot_fails" -v
```

Expected:

- FAIL because `build_chart_context_payload()` does not yet accept `boxes_payload` or `screenshot_payload`.

- [ ] **Step 4: Add provider helpers for boxes, zone selection, and evidence shaping**

```python
def _normalize_box_zones(boxes_payload: Optional[Dict[str, Any]]) -> List[Dict[str, Any]]:
    zones: List[Dict[str, Any]] = []
    for study in ((boxes_payload or {}).get("studies") or []):
        for item in study.get("boxes", []) or []:
            high = item.get("high")
            low = item.get("low")
            if high is None or low is None:
                continue
            coords = next(
                (
                    candidate
                    for candidate in (study.get("all_boxes") or [])
                    if candidate.get("high") == high and candidate.get("low") == low
                ),
                {},
            )
            zones.append(
                {
                    "type": "price_zone",
                    "source": "pine",
                    "label": study.get("name", ""),
                    "high": high,
                    "low": low,
                    "study": study.get("name", ""),
                    "x1": coords.get("x1"),
                    "x2": coords.get("x2"),
                }
            )
    return zones


def _pick_primary_zone(zones: Sequence[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    for zone in zones:
        if zone.get("type") == "price_zone":
            return zone
    return None


def _build_setup_evidence(
    focus_zone: Optional[Dict[str, Any]],
    screenshot_payload: Optional[Dict[str, Any]],
) -> Dict[str, Any]:
    if screenshot_payload and screenshot_payload.get("success") and focus_zone:
        return {
            "status": "ok",
            "focus_zone": focus_zone,
            "focus_image": {
                "path": screenshot_payload.get("file_path", ""),
                "region": screenshot_payload.get("region", "chart"),
            },
            "reason": "",
        }

    return {
        "status": "degraded",
        "focus_zone": focus_zone,
        "focus_image": None,
        "reason": (screenshot_payload or {}).get("error", "setup image unavailable"),
    }


def _crop_focus_image(source_path: str, focus_zone: Optional[Dict[str, Any]]) -> Optional[str]:
    if not focus_zone:
        return source_path
    x1 = focus_zone.get("x1")
    x2 = focus_zone.get("x2")
    if x1 is None or x2 is None:
        return source_path

    from pathlib import Path

    from PIL import Image

    image = Image.open(source_path)
    width, height = image.size
    left = max(0, int(float(x1) - width * 0.08))
    right = min(width, int(float(x2) + width * 0.08))
    top = max(0, int(height * 0.18))
    bottom = min(height, int(height * 0.82))
    cropped = image.crop((left, top, right, bottom))
    target = str(Path(source_path).with_name(Path(source_path).stem + "_focus.png"))
    cropped.save(target)
    return target
```

- [ ] **Step 5: Update the payload builder and live fetch path**

```python
def build_chart_context_payload(
    requested_symbol: str,
    requested_timeframe: str,
    status_payload: Dict[str, Any],
    values_payload: Optional[Dict[str, Any]],
    lines_payload: Optional[Dict[str, Any]],
    labels_payload: Optional[Dict[str, Any]],
    boxes_payload: Optional[Dict[str, Any]],
    screenshot_payload: Optional[Dict[str, Any]],
    now_iso: Optional[str] = None,
) -> Dict[str, Any]:
    timestamp = now_iso or _now_iso()
    partial_failures: List[str] = []
    if values_payload and not values_payload.get("success"):
        partial_failures.append(values_payload.get("error", "values failed"))
    if lines_payload and not lines_payload.get("success"):
        partial_failures.append(lines_payload.get("error", "lines failed"))
    if labels_payload and not labels_payload.get("success"):
        partial_failures.append(labels_payload.get("error", "labels failed"))
    if boxes_payload and not boxes_payload.get("success"):
        partial_failures.append(boxes_payload.get("error", "boxes failed"))
    normalized_box_zones = _normalize_box_zones(
        boxes_payload if boxes_payload and boxes_payload.get("success") else None
    )
    normalized_line_zones = _normalize_zones(
        lines_payload if lines_payload and lines_payload.get("success") else None
    )
    focus_zone = _pick_primary_zone(normalized_box_zones) or (
        normalized_line_zones[0] if normalized_line_zones else None
    )
    if screenshot_payload and screenshot_payload.get("success"):
        screenshot_payload = {
            **screenshot_payload,
            "file_path": _crop_focus_image(
                str(screenshot_payload.get("file_path", "")),
                focus_zone,
            ),
        }
    setup_evidence = _build_setup_evidence(focus_zone, screenshot_payload)

    return {
        "symbol": status_payload.get("chart_symbol", requested_symbol),
        "timeframe": _normalize_timeframe(status_payload.get("chart_resolution", requested_timeframe)),
        "provider_timestamp": timestamp,
        "pine_labels": _normalize_labels(labels_payload if labels_payload and labels_payload.get("success") else None),
        "zones": [*normalized_box_zones, *normalized_line_zones],
        "indicator_values": _normalize_indicator_values(values_payload if values_payload and values_payload.get("success") else None),
        "setup_evidence": setup_evidence,
        "reason": "",
        "metadata": {
            "requested_symbol": requested_symbol,
            "requested_timeframe": requested_timeframe,
            "partial_failures": partial_failures,
        },
    }
```

- [ ] **Step 6: Fetch MCP boxes and a chart screenshot in the live path**

```python
def fetch_live_chart_context(requested_symbol: str, requested_timeframe: str) -> Dict[str, Any]:
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

- [ ] **Step 7: Run the provider tests to verify the new contract passes**

Run:

```bash
PYTHONPATH=. pytest tests/services/test_local_chart_provider_service.py -v
```

Expected:

- PASS with new `setup_evidence` assertions.

- [ ] **Step 8: Commit the provider contract work**

```bash
git add src/local_chart_provider_service.py tests/services/test_local_chart_provider_service.py
git commit -m "DEV-124: capture setup evidence in provider"
```

## Task 2: Publish screenshot artifacts from the provider app

**Files:**
- Modify: `src/local_chart_provider_app.py`
- Modify: `tests/api/test_local_chart_provider_app.py`

- [ ] **Step 1: Write the failing API test for request-aware screenshot URLs**

```python
def test_chart_context_endpoint_promotes_focus_image_to_absolute_url(monkeypatch) -> None:
    monkeypatch.setattr(
        "src.local_chart_provider_app.fetch_live_chart_context",
        lambda symbol, timeframe: {
            "symbol": symbol,
            "timeframe": timeframe,
            "provider_timestamp": "2026-04-17T00:20:00Z",
            "pine_labels": [],
            "zones": [],
            "indicator_values": {},
            "setup_evidence": {
                "status": "ok",
                "focus_zone": {"label": "ILP", "high": 0.7210, "low": 0.7195},
                "focus_image": {"path": "mcp/tradingview-mcp/screenshots/setup-audusd.png"},
                "reason": "",
            },
            "reason": "",
            "metadata": {"partial_failures": []},
        },
    )

    client = TestClient(app)
    response = client.get("/chart-context", params={"symbol": "XAUUSD", "timeframe": "5m"})

    assert response.status_code == 200
    assert response.json()["setup_evidence"]["focus_image"]["url"].startswith("http://testserver/provider-artifacts/")
```

- [ ] **Step 2: Run the API test to verify it fails**

Run:

```bash
PYTHONPATH=. pytest tests/api/test_local_chart_provider_app.py -k "focus_image" -v
```

Expected:

- FAIL because the app currently returns only the raw provider payload.

- [ ] **Step 3: Mount a static artifact route and promote relative paths**

```python
from pathlib import Path

from fastapi import FastAPI, Query, Request
from fastapi.staticfiles import StaticFiles

ARTIFACTS_DIR = Path(__file__).resolve().parents[1] / "mcp" / "tradingview-mcp" / "screenshots"

app = FastAPI(title="Local TradingView MCP Provider", version="0.1.0")
app.mount("/provider-artifacts", StaticFiles(directory=ARTIFACTS_DIR), name="provider-artifacts")


def _attach_focus_image_url(payload: dict, request: Request) -> dict:
    setup_evidence = payload.get("setup_evidence")
    focus_image = (setup_evidence or {}).get("focus_image")
    if not focus_image or not focus_image.get("path"):
        return payload

    filename = Path(str(focus_image["path"])).name
    focus_image["url"] = str(request.base_url).rstrip("/") + f"/provider-artifacts/{filename}"
    return payload
```

- [ ] **Step 4: Update the endpoint signature to use the helper**

```python
@app.get("/chart-context")
async def get_chart_context(
    request: Request,
    symbol: str = Query(...),
    timeframe: str = Query(...),
) -> dict:
    payload = fetch_live_chart_context(symbol, timeframe)
    return _attach_focus_image_url(payload, request)
```

- [ ] **Step 5: Run the provider app tests**

Run:

```bash
PYTHONPATH=. pytest tests/api/test_local_chart_provider_app.py -v
```

Expected:

- PASS with the absolute `focus_image.url` assertion.

- [ ] **Step 6: Commit the provider app work**

```bash
git add src/local_chart_provider_app.py tests/api/test_local_chart_provider_app.py
git commit -m "DEV-124: publish setup evidence artifacts"
```

## Task 3: Thread setup evidence through normalized chart context and AI runs

**Files:**
- Modify: `src/services/chart_context_service.py`
- Modify: `src/services/ai_operating_layer.py`
- Modify: `tests/services/test_chart_context_fetch.py`
- Modify: `tests/services/test_ai_operating_layer_provider_integration.py`

- [ ] **Step 1: Write the failing normalization test for setup evidence**

```python
def test_normalize_chart_context_preserves_setup_evidence_bundle() -> None:
    payload = normalize_chart_context(
        ChartContextProviderResult(
            ok=True,
            symbol="XAUUSD",
            timeframe="5m",
            structured={
                "provider_timestamp": "2026-04-16T12:00:00Z",
                "pine_labels": [],
                "zones": [],
                "indicator_values": {},
                "setup_evidence": {
                    "status": "ok",
                    "focus_zone": {"label": "ILP", "high": 0.7210, "low": 0.7195},
                    "focus_image": {"url": "https://provider/setup.png"},
                    "reason": "",
                },
            },
            screenshot_url="https://provider/setup.png",
            reason="",
        )
    )

    assert payload["status"] == "ok"
    assert payload["structured"]["setup_evidence"]["focus_image"]["url"] == "https://provider/setup.png"
```

- [ ] **Step 2: Write the failing AI run integration test**

```python
def test_shadow_pretrade_run_keeps_setup_evidence_in_chart_context(monkeypatch) -> None:
    monkeypatch.setattr(
        "src.services.ai_operating_layer.fetch_and_normalize_chart_context",
        lambda **_kwargs: {
            "status": "ok",
            "reason": "",
            "structured": {
                "provider_timestamp": "2026-04-17T00:20:00Z",
                "pine_labels": [],
                "zones": [],
                "indicator_values": {},
                "setup_evidence": {
                    "status": "ok",
                    "focus_zone": {"label": "ILP", "high": 0.7210, "low": 0.7195},
                    "focus_image": {"url": "https://provider/setup.png"},
                    "reason": "",
                },
            },
        },
    )

    payload = build_shadow_pretrade_run(
        signal_payload={"symbol": "XAUUSD", "timeframe": "5m"},
        chart_context=None,
        pine_context={"script_name": "Liquidity Sweeps"},
    )

    assert payload["chart_context"]["structured"]["setup_evidence"]["status"] == "ok"
```

- [ ] **Step 3: Run the backend-focused tests to verify they fail**

Run:

```bash
PYTHONPATH=. pytest tests/services/test_chart_context_fetch.py tests/services/test_ai_operating_layer_provider_integration.py -v
```

Expected:

- FAIL because the normalized payload currently ignores `setup_evidence`.

- [ ] **Step 4: Preserve setup evidence in chart-context normalization**

```python
def normalize_chart_context(provider_result: ChartContextProviderResult) -> Dict[str, Any]:
    structured = provider_result.structured or {}
    setup_evidence = structured.get(
        "setup_evidence",
        {"status": "degraded", "focus_zone": None, "focus_image": None, "reason": "setup evidence unavailable"},
    )

    if not provider_result.ok:
        return {
            "status": "degraded",
            "symbol": provider_result.symbol,
            "timeframe": provider_result.timeframe,
            "reason": provider_result.reason,
            "structured": {"setup_evidence": setup_evidence},
            "screenshot_url": provider_result.screenshot_url,
        }

    return {
        "status": "ok",
        "symbol": provider_result.symbol,
        "timeframe": provider_result.timeframe,
        "reason": "",
        "structured": {**structured, "setup_evidence": setup_evidence},
        "screenshot_url": provider_result.screenshot_url,
    }
```

- [ ] **Step 5: Thread setup evidence through the provider adapter boundary**

```python
def fetch_and_normalize_chart_context(
    base_url: str,
    symbol: str,
    timeframe: str,
    timeout_seconds: float,
    retry_count: int,
) -> Dict[str, Any]:
    raw = fetch_chart_context(base_url, symbol, timeframe, timeout_seconds, retry_count)
    setup_evidence = raw.get(
        "setup_evidence",
        {"status": "degraded", "focus_zone": None, "focus_image": None, "reason": "setup evidence unavailable"},
    )
    screenshot_url = (
        ((setup_evidence.get("focus_image") or {}).get("url"))
        or raw.get("screenshot_url")
    )
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
                "setup_evidence": setup_evidence,
            } if raw.get("ok") else {"setup_evidence": setup_evidence},
            screenshot_url=screenshot_url,
            reason=raw.get("reason", ""),
        )
    )
```

- [ ] **Step 6: Run the backend tests to verify setup evidence survives**

Run:

```bash
PYTHONPATH=. pytest tests/services/test_chart_context_fetch.py tests/services/test_ai_operating_layer_provider_integration.py -v
```

Expected:

- PASS with `setup_evidence` present in normalized chart context and AI run payloads.

- [ ] **Step 7: Commit the backend normalization work**

```bash
git add src/services/chart_context_service.py src/services/ai_operating_layer.py tests/services/test_chart_context_fetch.py tests/services/test_ai_operating_layer_provider_integration.py
git commit -m "DEV-124: persist setup evidence in ai runs"
```

## Task 4: Type and render setup evidence in the frontend

**Files:**
- Modify: `frontend/src/lib/api.ts`
- Modify: `frontend/src/lib/aiRuns.ts`
- Create: `frontend/src/components/ai/SetupEvidencePanel.tsx`
- Modify: `frontend/src/components/ai/AiOperatingLayerPanel.tsx`
- Create: `frontend/src/components/ai/SetupEvidencePanel.test.tsx`

- [ ] **Step 1: Write the failing component test for focused setup evidence**

```tsx
import { render, screen } from '@testing-library/react';

import { SetupEvidencePanel } from '@/components/ai/SetupEvidencePanel';

it('renders focused setup image and primary zone context', () => {
  render(
    <SetupEvidencePanel
      evidence={{
        status: 'ok',
        focusZone: { label: 'Institutional Liquidity Protocol [Pro]', high: 0.721, low: 0.7195 },
        focusImage: { url: 'https://provider/setup.png' },
        reason: '',
      }}
      zones={[{ label: 'Institutional Liquidity Protocol [Pro]', high: 0.721, low: 0.7195 }]}
      pineLabels={[{ label: 'LONG', price: 0.72 }]}
    />
  );

  expect(screen.getByRole('img', { name: /focused setup/i })).toHaveAttribute(
    'src',
    'https://provider/setup.png'
  );
  expect(screen.getByText(/0.721/i)).toBeInTheDocument();
  expect(screen.getByText(/LONG/i)).toBeInTheDocument();
});
```

- [ ] **Step 2: Run the frontend test to verify it fails**

Run:

```bash
cd frontend && npx vitest run src/components/ai/SetupEvidencePanel.test.tsx
```

Expected:

- FAIL because `SetupEvidencePanel` does not exist yet.

- [ ] **Step 3: Extend the frontend AI types**

```ts
export interface AiRunResponse {
  id: number;
  chart_context?: {
    status?: string;
    symbol?: string;
    timeframe?: string;
    reason?: string;
    structured?: {
      provider_timestamp?: string;
      pine_labels?: Array<Record<string, unknown>>;
      zones?: Array<Record<string, unknown>>;
      indicator_values?: Record<string, unknown>;
      setup_evidence?: {
        status?: string;
        focus_zone?: Record<string, unknown> | null;
        focus_image?: { url?: string | null } | null;
        reason?: string;
      };
    };
  };
}
```

- [ ] **Step 4: Map setup evidence into the UI model**

```ts
export type AiOperatingLayerRun = {
  analysisMode: string;
  layeredOutput: { topLevel: { verdict: string; confidence: number } };
  moduleStatus: { chartContext: { status: string; reason: string } };
  chartContext: {
    structured: {
      setupEvidence: {
        status: string;
        focusZone: Record<string, unknown> | null;
        focusImage: { url: string } | null;
        reason: string;
      };
      zones: Array<Record<string, unknown>>;
      pineLabels: Array<Record<string, unknown>>;
    };
  };
  pineContext: Record<string, unknown>;
};
```

- [ ] **Step 5: Build the evidence panel and embed it in the AI Operating Layer panel**

```tsx
export function SetupEvidencePanel({
  evidence,
  zones,
  pineLabels,
}: {
  evidence: {
    status: string;
    focusZone: Record<string, unknown> | null;
    focusImage: { url: string } | null;
    reason: string;
  };
  zones: Array<Record<string, unknown>>;
  pineLabels: Array<Record<string, unknown>>;
}) {
  return (
    <div className='space-y-3 rounded-lg border border-border/80 bg-background/40 p-3'>
      <div className='flex items-center justify-between gap-3'>
        <span className='text-[11px] text-muted-foreground uppercase tracking-wider'>
          Setup Evidence
        </span>
        <Badge className='text-[10px] px-2 py-0.5 border-0 bg-muted text-muted-foreground'>
          {evidence.status}
        </Badge>
      </div>
      {evidence.focusImage?.url ? (
        <img
          src={evidence.focusImage.url}
          alt='Focused setup'
          className='w-full rounded-md border border-border object-cover'
        />
      ) : (
        <p className='text-xs text-muted-foreground'>{evidence.reason}</p>
      )}
    </div>
  );
}
```

```tsx
const structured = (run.chartContext.structured as Record<string, unknown> | undefined) ?? {};
const setupEvidence = (structured.setupEvidence as {
  status: string;
  focusZone: Record<string, unknown> | null;
  focusImage: { url: string } | null;
  reason: string;
}) ?? {
  status: 'degraded',
  focusZone: null,
  focusImage: null,
  reason: 'setup evidence unavailable',
};

<SetupEvidencePanel
  evidence={setupEvidence}
  zones={(structured.zones as Array<Record<string, unknown>> | undefined) ?? []}
  pineLabels={(structured.pineLabels as Array<Record<string, unknown>> | undefined) ?? []}
/>
```

- [ ] **Step 6: Run the focused frontend tests**

Run:

```bash
cd frontend && npx vitest run src/components/ai/SetupEvidencePanel.test.tsx
```

Expected:

- PASS with focused setup image and fallback rendering covered.

- [ ] **Step 7: Commit the frontend evidence UI**

```bash
git add frontend/src/lib/api.ts frontend/src/lib/aiRuns.ts frontend/src/components/ai/SetupEvidencePanel.tsx frontend/src/components/ai/AiOperatingLayerPanel.tsx frontend/src/components/ai/SetupEvidencePanel.test.tsx
git commit -m "DEV-124: render setup evidence in ai memo"
```

## Task 5: Verify the full slice end to end

**Files:**
- Modify: no new source files
- Verify: provider and frontend surfaces added above

- [ ] **Step 1: Run the backend evidence test suite**

Run:

```bash
PYTHONPATH=. pytest tests/services/test_local_chart_provider_service.py tests/api/test_local_chart_provider_app.py tests/services/test_chart_context_fetch.py tests/services/test_ai_operating_layer_provider_integration.py -v
```

Expected:

- PASS for provider, normalization, and AI-run evidence tests.

- [ ] **Step 2: Run the focused frontend tests**

Run:

```bash
cd frontend && npx vitest run src/components/ai/SetupEvidencePanel.test.tsx
```

Expected:

- PASS.

- [ ] **Step 3: Run the frontend production build**

Run:

```bash
cd frontend && npm run build
```

Expected:

- PASS with no new TypeScript errors.

- [ ] **Step 4: Smoke-test the provider locally**

Run:

```bash
PYTHONPATH=. python3 -m uvicorn src.local_chart_provider_app:app --host 127.0.0.1 --port 8765
curl "http://127.0.0.1:8765/chart-context?symbol=VANTAGE:AUDUSD&timeframe=5m"
```

Expected:

- JSON response includes:
  - `setup_evidence.status`
  - `setup_evidence.focus_zone`
  - `setup_evidence.focus_image.url` when screenshot capture succeeds

- [ ] **Step 5: Commit the final verification checkpoint**

```bash
git add .
git commit -m "DEV-124: verify setup evidence bundle"
```

## Self-Review

- Spec coverage:
  - automatic capture at provider level: covered in Task 1 and Task 2
  - journal-first storage via existing `ai_runs.chart_context`: covered in Task 3
  - trade detail UI rendering first: covered in Task 4
  - failure-tolerant degraded image handling: covered in Task 1 and Task 3
  - future Discord/Telegram/manual reuse: intentionally deferred, preserved by storing the bundle in `chart_context`
- Placeholder scan:
  - no `TBD`, `TODO`, or “write tests later” placeholders remain
  - each task contains exact files, code, and commands
- Type consistency:
  - provider returns `setup_evidence`
  - backend normalization preserves `structured.setup_evidence`
  - frontend maps that to `setupEvidence`
  - the naming transition is explicit in the mapper task instead of implicit
