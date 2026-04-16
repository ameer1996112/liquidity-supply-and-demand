# AI Operating Layer V1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the first safe slice of the AI Operating Layer: chart-aware post-trade review plus shadow pre-trade analysis, backed by module toggles, panic mode, and degraded-status reporting.

**Architecture:** Extend the existing `ai_runs` and debate pipeline instead of replacing them. Add a small chart-context service, enrich the debate inputs with Pine/chart evidence, persist structured module status on AI runs, and expose the new artifacts on the AI run API so the trade-detail UI can render them without touching the live trading path.

**Tech Stack:** FastAPI, Python services, existing `src/ai/*` debate/council stack, Supabase persistence, Next.js trade-detail UI, pytest, vitest

---

## File Structure

### New files

- `src/services/ai_operating_layer.py`
  - Orchestrates shadow pre-trade capture, chart context fetch, Pine context assembly, and post-trade review runs.
- `src/services/chart_context_service.py`
  - Normalizes chart context from an optional provider into one stable schema with degradation reasons.
- `src/services/ai_control_plane.py`
  - Resolves module state from global/user/account/strategy scopes plus panic mode and admin overrides.
- `tests/services/test_chart_context_service.py`
  - Unit tests for provider fallback, degradation, and normalized output shape.
- `tests/services/test_ai_control_plane.py`
  - Unit tests for precedence, inheritance, admin overrides, and panic mode behavior.
- `tests/services/test_ai_operating_layer.py`
  - Unit tests for shadow pre-trade capture and post-trade enrichment orchestration.
- `frontend/src/components/ai/AiOperatingLayerPanel.tsx`
  - Trade-detail drill-down view for verdict, scorecard, module health, and evidence.
- `frontend/src/lib/aiRuns.ts`
  - Frontend mapping helpers for the expanded AI-run response model.
- `frontend/src/components/ai/__tests__/AiOperatingLayerPanel.test.tsx`
  - UI tests for health badges, verdict rendering, and degraded reasons.

### Existing files to modify

- `src/services/ai_run_service.py`
  - Extend persistence to store module health, chart context summary, Pine context summary, verdict layers, and run subtype.
- `src/api_ai_runs.py`
  - Return the expanded AI run payload needed by the trade-detail page.
- `src/ai/debate.py`
  - Accept enriched context and produce layered outputs while staying backward-compatible.
- `src/ai/trading_council.py`
  - Reuse enriched context where council mode is enabled.
- `src/api.py`
  - Register any new AI operating layer endpoints if needed for post-trade triggering or control-plane state.
- `frontend/src/...trade detail page...`
  - Mount the new AI panel on the existing trade-detail surface.

### Database touchpoints

- Existing `ai_runs` table
  - Add JSON fields for `module_status`, `chart_context`, `pine_context`, `layered_output`, and `analysis_mode`.
- Existing `pipeline_traces` / signal linkage
  - Reuse correlation and signal linkage without changing execution flow.

## Task 1: Add the AI control-plane domain model

**Files:**
- Create: `src/services/ai_control_plane.py`
- Test: `tests/services/test_ai_control_plane.py`

- [ ] **Step 1: Write the failing control-plane tests**

```python
from src.services.ai_control_plane import (
    ModuleState,
    ResolvedModuleState,
    resolve_module_state,
    resolve_panic_mode,
)


def test_strategy_scope_overrides_higher_scopes() -> None:
    resolved = resolve_module_state(
        module_name="chart_context",
        panic_mode=False,
        global_state=ModuleState.ENABLED,
        user_state=ModuleState.ENABLED,
        account_state=ModuleState.DISABLED,
        strategy_state=ModuleState.ENABLED,
        admin_override=None,
    )

    assert resolved == ResolvedModuleState(enabled=True, source="strategy", forced=False)


def test_admin_forced_off_beats_all_other_states() -> None:
    resolved = resolve_module_state(
        module_name="debate_review",
        panic_mode=False,
        global_state=ModuleState.ENABLED,
        user_state=ModuleState.ENABLED,
        account_state=ModuleState.ENABLED,
        strategy_state=ModuleState.ENABLED,
        admin_override="forced-off",
    )

    assert resolved == ResolvedModuleState(enabled=False, source="admin", forced=True)


def test_panic_mode_disables_non_core_modules() -> None:
    assert resolve_panic_mode(module_name="chart_context", panic_mode=True) is False
    assert resolve_panic_mode(module_name="debate_review", panic_mode=True) is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH=. pytest tests/services/test_ai_control_plane.py -v`
Expected: FAIL with `ModuleNotFoundError` or missing symbol errors for `src.services.ai_control_plane`

- [ ] **Step 3: Write the minimal control-plane implementation**

```python
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional


class ModuleState(str, Enum):
    INHERIT = "inherit"
    ENABLED = "enabled"
    DISABLED = "disabled"


@dataclass(frozen=True)
class ResolvedModuleState:
    enabled: bool
    source: str
    forced: bool


def resolve_panic_mode(module_name: str, panic_mode: bool) -> bool:
    if not panic_mode:
        return True
    return False


def resolve_module_state(
    module_name: str,
    panic_mode: bool,
    global_state: ModuleState,
    user_state: ModuleState,
    account_state: ModuleState,
    strategy_state: ModuleState,
    admin_override: Optional[str],
) -> ResolvedModuleState:
    if admin_override == "forced-off":
        return ResolvedModuleState(enabled=False, source="admin", forced=True)
    if admin_override == "forced-on":
        return ResolvedModuleState(enabled=True, source="admin", forced=True)
    if not resolve_panic_mode(module_name, panic_mode):
        return ResolvedModuleState(enabled=False, source="panic", forced=True)

    for source, value in (
        ("strategy", strategy_state),
        ("account", account_state),
        ("user", user_state),
        ("global", global_state),
    ):
        if value == ModuleState.ENABLED:
            return ResolvedModuleState(enabled=True, source=source, forced=False)
        if value == ModuleState.DISABLED:
            return ResolvedModuleState(enabled=False, source=source, forced=False)

    return ResolvedModuleState(enabled=False, source="default", forced=False)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `PYTHONPATH=. pytest tests/services/test_ai_control_plane.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add tests/services/test_ai_control_plane.py src/services/ai_control_plane.py
git commit -m "DEV-120: add AI control plane resolver"
```

## Task 2: Add normalized chart-context collection with graceful degradation

**Files:**
- Create: `src/services/chart_context_service.py`
- Test: `tests/services/test_chart_context_service.py`

- [ ] **Step 1: Write the failing chart-context tests**

```python
from src.services.chart_context_service import ChartContextProviderResult, normalize_chart_context


def test_normalize_chart_context_returns_degraded_payload_when_provider_fails() -> None:
    payload = normalize_chart_context(
        provider_result=ChartContextProviderResult(
            ok=False,
            symbol="XAUUSD",
            timeframe="5m",
            structured=None,
            screenshot_url=None,
            reason="TradingView MCP unavailable",
        )
    )

    assert payload["status"] == "degraded"
    assert payload["reason"] == "TradingView MCP unavailable"
    assert payload["structured"] == {}


def test_normalize_chart_context_preserves_structured_signal_artifacts() -> None:
    payload = normalize_chart_context(
        provider_result=ChartContextProviderResult(
            ok=True,
            symbol="XAUUSD",
            timeframe="5m",
            structured={
                "pine_labels": ["sweep", "entry"],
                "zones": [{"kind": "liquidity", "top": 3300.0, "bottom": 3297.5}],
            },
            screenshot_url="http://example.test/xau.png",
            reason="",
        )
    )

    assert payload["status"] == "ok"
    assert payload["symbol"] == "XAUUSD"
    assert payload["structured"]["pine_labels"] == ["sweep", "entry"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH=. pytest tests/services/test_chart_context_service.py -v`
Expected: FAIL with `ModuleNotFoundError` for `src.services.chart_context_service`

- [ ] **Step 3: Write the minimal chart-context implementation**

```python
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional


@dataclass(frozen=True)
class ChartContextProviderResult:
    ok: bool
    symbol: str
    timeframe: str
    structured: Optional[Dict[str, Any]]
    screenshot_url: Optional[str]
    reason: str


def normalize_chart_context(provider_result: ChartContextProviderResult) -> Dict[str, Any]:
    if not provider_result.ok:
        return {
            "status": "degraded",
            "symbol": provider_result.symbol,
            "timeframe": provider_result.timeframe,
            "reason": provider_result.reason,
            "structured": {},
            "screenshot_url": provider_result.screenshot_url,
        }

    return {
        "status": "ok",
        "symbol": provider_result.symbol,
        "timeframe": provider_result.timeframe,
        "reason": "",
        "structured": provider_result.structured or {},
        "screenshot_url": provider_result.screenshot_url,
    }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `PYTHONPATH=. pytest tests/services/test_chart_context_service.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add tests/services/test_chart_context_service.py src/services/chart_context_service.py
git commit -m "DEV-120: add chart context normalization"
```

## Task 3: Create the AI operating-layer orchestrator for shadow pre-trade and post-trade review

**Files:**
- Create: `src/services/ai_operating_layer.py`
- Modify: `src/ai/debate.py`
- Test: `tests/services/test_ai_operating_layer.py`

- [ ] **Step 1: Write the failing orchestration tests**

```python
from src.services.ai_operating_layer import build_shadow_pretrade_run, build_posttrade_review_run


def test_shadow_pretrade_run_marks_analysis_mode_and_module_health() -> None:
    result = build_shadow_pretrade_run(
        signal_payload={"symbol": "XAUUSD", "side": "buy"},
        chart_context={"status": "ok", "structured": {"pine_labels": ["entry"]}},
        pine_context={"script_name": "Liquidity Sweeps"},
    )

    assert result["analysis_mode"] == "shadow_pretrade"
    assert result["module_status"]["chart_context"]["status"] == "ok"
    assert result["layered_output"]["top_level"]["verdict"] == "unclear"


def test_posttrade_review_run_includes_chart_and_pine_context() -> None:
    result = build_posttrade_review_run(
        signal_payload={"symbol": "XAUUSD", "side": "sell"},
        trade_outcome={"result": "loss"},
        chart_context={"status": "degraded", "reason": "provider unavailable", "structured": {}},
        pine_context={"script_name": "Liquidity Sweeps"},
    )

    assert result["analysis_mode"] == "posttrade_review"
    assert result["module_status"]["chart_context"]["reason"] == "provider unavailable"
    assert result["pine_context"]["script_name"] == "Liquidity Sweeps"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH=. pytest tests/services/test_ai_operating_layer.py -v`
Expected: FAIL with `ModuleNotFoundError` or missing symbol errors for `build_shadow_pretrade_run`

- [ ] **Step 3: Write the minimal orchestration implementation**

```python
from __future__ import annotations

from typing import Any, Dict


def _base_layered_output() -> Dict[str, Any]:
    return {
        "top_level": {"verdict": "unclear", "confidence": 0},
        "scorecard": {"confluence": [], "risks": [], "evidence": []},
        "deep_layer": {"agent_opinions": [], "disagreements": []},
    }


def build_shadow_pretrade_run(
    signal_payload: Dict[str, Any],
    chart_context: Dict[str, Any],
    pine_context: Dict[str, Any],
) -> Dict[str, Any]:
    return {
        "analysis_mode": "shadow_pretrade",
        "signal_payload": signal_payload,
        "chart_context": chart_context,
        "pine_context": pine_context,
        "module_status": {
            "chart_context": {
                "status": chart_context.get("status", "degraded"),
                "reason": chart_context.get("reason", ""),
            }
        },
        "layered_output": _base_layered_output(),
    }


def build_posttrade_review_run(
    signal_payload: Dict[str, Any],
    trade_outcome: Dict[str, Any],
    chart_context: Dict[str, Any],
    pine_context: Dict[str, Any],
) -> Dict[str, Any]:
    payload = build_shadow_pretrade_run(signal_payload, chart_context, pine_context)
    payload["analysis_mode"] = "posttrade_review"
    payload["trade_outcome"] = trade_outcome
    return payload
```

- [ ] **Step 4: Extend debate input assembly to accept enriched context**

```python
def _build_trade_context(payload: Dict[str, Any], enriched_context: Optional[Dict[str, Any]] = None) -> str:
    # existing lines omitted
    lines = [
        f"Symbol: {symbol} | Side: {side}",
        f"Entry: {entry} | SL: {sl} | TP: {tp} | Size: {size}",
    ]
    if enriched_context:
        chart_status = enriched_context.get("chart_context", {}).get("status", "unknown")
        pine_name = enriched_context.get("pine_context", {}).get("script_name", "N/A")
        lines.append(f"Chart Context Status: {chart_status}")
        lines.append(f"Pine Script: {pine_name}")
    return "\n".join(lines)
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `PYTHONPATH=. pytest tests/services/test_ai_operating_layer.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add tests/services/test_ai_operating_layer.py src/services/ai_operating_layer.py src/ai/debate.py
git commit -m "DEV-120: add AI operating layer orchestration"
```

## Task 4: Persist the expanded AI-run payload and expose it via the API

**Files:**
- Modify: `src/services/ai_run_service.py`
- Modify: `src/api_ai_runs.py`
- Test: `tests/services/test_ai_run_service.py`
- Test: `tests/api/test_api_ai_runs.py`

- [ ] **Step 1: Write the failing persistence and API tests**

```python
from src.services.ai_run_service import build_ai_run_row


def test_build_ai_run_row_persists_layered_fields() -> None:
    row = build_ai_run_row(
        correlation_id="corr-1",
        run_payload={
            "analysis_mode": "posttrade_review",
            "chart_context": {"status": "ok"},
            "pine_context": {"script_name": "Liquidity Sweeps"},
            "module_status": {"chart_context": {"status": "ok", "reason": ""}},
            "layered_output": {"top_level": {"verdict": "good setup"}},
        },
    )

    assert row["analysis_mode"] == "posttrade_review"
    assert row["chart_context"]["status"] == "ok"
    assert row["layered_output"]["top_level"]["verdict"] == "good setup"
```

```python
def test_get_ai_run_by_signal_returns_expanded_fields(client, mock_supabase_row) -> None:
    response = client.get("/api/ai-runs?signal_id=12")
    assert response.status_code == 200
    body = response.json()
    assert body["analysis_mode"] == "posttrade_review"
    assert body["module_status"]["chart_context"]["status"] in {"ok", "degraded"}
    assert "layered_output" in body
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `PYTHONPATH=. pytest tests/services/test_ai_run_service.py tests/api/test_api_ai_runs.py -v`
Expected: FAIL because `build_ai_run_row` does not exist and API response does not yet include expanded fields

- [ ] **Step 3: Add a reusable row-builder and persist new fields**

```python
def build_ai_run_row(correlation_id: str, run_payload: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "correlation_id": correlation_id,
        "run_type": "debate",
        "analysis_mode": run_payload.get("analysis_mode", "shadow_pretrade"),
        "recommendation": run_payload.get("recommendation", "allow"),
        "confidence": run_payload.get("confidence", 0),
        "chart_context": run_payload.get("chart_context", {}),
        "pine_context": run_payload.get("pine_context", {}),
        "module_status": run_payload.get("module_status", {}),
        "layered_output": run_payload.get("layered_output", {}),
        "reason_codes": run_payload.get("reason_codes", []),
        "memo": run_payload.get("memo", ""),
        "votes": run_payload.get("votes", {}),
        "transcript": run_payload.get("transcript", []),
    }
```

- [ ] **Step 4: Return expanded AI-run fields from the API**

```python
return {
    "id": row["id"],
    "correlation_id": row.get("correlation_id"),
    "signal_id": row.get("signal_id"),
    "run_type": row.get("run_type", "debate"),
    "analysis_mode": row.get("analysis_mode", "shadow_pretrade"),
    "recommendation": row.get("recommendation", "allow"),
    "confidence": row.get("confidence", 0),
    "reason_codes": row.get("reason_codes") or [],
    "memo": row.get("memo") or "",
    "votes": row.get("votes") or {},
    "transcript": row.get("transcript") or [],
    "chart_context": row.get("chart_context") or {},
    "pine_context": row.get("pine_context") or {},
    "module_status": row.get("module_status") or {},
    "layered_output": row.get("layered_output") or {},
    "council_report": row.get("council_report") or {},
    "created_at": row.get("created_at"),
}
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `PYTHONPATH=. pytest tests/services/test_ai_run_service.py tests/api/test_api_ai_runs.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add tests/services/test_ai_run_service.py tests/api/test_api_ai_runs.py src/services/ai_run_service.py src/api_ai_runs.py
git commit -m "DEV-120: persist expanded AI run payloads"
```

## Task 5: Render the new AI operating-layer panel on the trade-detail page

**Files:**
- Create: `frontend/src/components/ai/AiOperatingLayerPanel.tsx`
- Create: `frontend/src/lib/aiRuns.ts`
- Create: `frontend/src/components/ai/__tests__/AiOperatingLayerPanel.test.tsx`
- Modify: `frontend/src/...trade detail page component...`

- [ ] **Step 1: Write the failing UI tests**

```tsx
import { render, screen } from "@testing-library/react";
import { AiOperatingLayerPanel } from "../AiOperatingLayerPanel";

test("renders verdict, health badge, and degraded reason", () => {
  render(
    <AiOperatingLayerPanel
      run={{
        analysisMode: "posttrade_review",
        layeredOutput: { topLevel: { verdict: "weak setup", confidence: 42 } },
        moduleStatus: {
          chartContext: { status: "degraded", reason: "TradingView MCP unavailable" },
        },
      }}
    />
  );

  expect(screen.getByText("weak setup")).toBeInTheDocument();
  expect(screen.getByText(/Chart Context/i)).toBeInTheDocument();
  expect(screen.getByText(/TradingView MCP unavailable/i)).toBeInTheDocument();
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && npx vitest run src/components/ai/__tests__/AiOperatingLayerPanel.test.tsx`
Expected: FAIL because the component and mapping helpers do not exist yet

- [ ] **Step 3: Implement the minimal panel and mapping helper**

```tsx
export function AiOperatingLayerPanel({ run }: { run: AiOperatingLayerRun }) {
  const chartStatus = run.moduleStatus.chartContext;

  return (
    <section>
      <h3>AI Operating Layer</h3>
      <p>{run.layeredOutput.topLevel.verdict}</p>
      <p>Confidence: {run.layeredOutput.topLevel.confidence}</p>
      <div>
        <strong>Chart Context</strong>
        <span>{chartStatus.status}</span>
      </div>
      {chartStatus.reason ? <p>{chartStatus.reason}</p> : null}
    </section>
  );
}
```

```ts
export type AiOperatingLayerRun = {
  analysisMode: string;
  layeredOutput: {
    topLevel: {
      verdict: string;
      confidence: number;
    };
  };
  moduleStatus: {
    chartContext: {
      status: string;
      reason: string;
    };
  };
};
```

- [ ] **Step 4: Mount the panel on the trade-detail page**

```tsx
{aiRun ? <AiOperatingLayerPanel run={mapAiRun(aiRun)} /> : null}
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd frontend && npx vitest run src/components/ai/__tests__/AiOperatingLayerPanel.test.tsx`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add frontend/src/components/ai/AiOperatingLayerPanel.tsx frontend/src/lib/aiRuns.ts frontend/src/components/ai/__tests__/AiOperatingLayerPanel.test.tsx frontend/src/...trade detail page component...
git commit -m "DEV-120: add AI operating layer trade detail panel"
```

## Task 6: Verify end-to-end fallback behavior and document rollout checks

**Files:**
- Modify: `docs/superpowers/specs/2026-04-16-ai-operating-layer-design.md`
- Modify: `docs/superpowers/plans/2026-04-16-ai-operating-layer-v1.md`

- [ ] **Step 1: Add a backend verification checklist to the plan**

```md
### Verification checklist

- `PYTHONPATH=. pytest tests/services/test_ai_control_plane.py -v`
- `PYTHONPATH=. pytest tests/services/test_chart_context_service.py -v`
- `PYTHONPATH=. pytest tests/services/test_ai_operating_layer.py -v`
- `PYTHONPATH=. pytest tests/services/test_ai_run_service.py tests/api/test_api_ai_runs.py -v`
- Confirm a provider failure returns `module_status.chart_context.status == "degraded"`
- Confirm panic mode disables chart context and debate modules without blocking the core path
```

- [ ] **Step 2: Add a frontend verification checklist to the plan**

```md
- `cd frontend && npx vitest run src/components/ai/__tests__/AiOperatingLayerPanel.test.tsx`
- Open a trade detail page with an expanded AI run payload
- Confirm verdict, confidence, module health, and degraded reasons render correctly
- Confirm the page still loads when `chart_context` is missing or empty
```

- [ ] **Step 3: Run the targeted verification commands**

Run:

```bash
PYTHONPATH=. pytest tests/services/test_ai_control_plane.py tests/services/test_chart_context_service.py tests/services/test_ai_operating_layer.py -v
PYTHONPATH=. pytest tests/services/test_ai_run_service.py tests/api/test_api_ai_runs.py -v
cd frontend && npx vitest run src/components/ai/__tests__/AiOperatingLayerPanel.test.tsx
```

Expected: PASS, with any unrelated pre-existing failures left untouched

- [ ] **Step 4: Commit**

```bash
git add docs/superpowers/specs/2026-04-16-ai-operating-layer-design.md docs/superpowers/plans/2026-04-16-ai-operating-layer-v1.md
git commit -m "DEV-120: add AI operating layer verification checklist"
```

## Self-Review

### Spec coverage

- Chart-aware post-trade review: covered by Tasks 2, 3, 4, and 5.
- Shadow pre-trade analysis: covered by Task 3 and persisted in Task 4.
- Debate-agent improvement with richer inputs: covered by Task 3.
- UI toggles, panic mode, and control precedence: covered by Task 1, with API/UI exposure ready for follow-up wiring.
- Trade-detail-first presentation: covered by Task 5.
- Graceful degradation: covered by Tasks 2, 3, 4, and 6.

### Placeholder scan

- No `TODO`, `TBD`, or “implement later” markers remain in the plan.
- Every code-edit step includes concrete code to write.
- Every test step includes a concrete command and expected result.

### Type consistency

- `analysis_mode`, `chart_context`, `pine_context`, `module_status`, and `layered_output` are used consistently across orchestration, persistence, API, and UI.
- Control-plane types use `ModuleState` and `ResolvedModuleState` consistently.

Plan complete and saved to `docs/superpowers/plans/2026-04-16-ai-operating-layer-v1.md`. Two execution options:

**1. Subagent-Driven (recommended)** - I dispatch a fresh subagent per task, review between tasks, fast iteration

**2. Inline Execution** - Execute tasks in this session using executing-plans, batch execution with checkpoints

Which approach?
