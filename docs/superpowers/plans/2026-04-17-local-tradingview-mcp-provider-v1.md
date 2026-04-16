# Local TradingView MCP Provider Wrapper Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a local-only HTTP provider on the operator machine that reads the active TradingView chart through `tradingview-mcp`, normalizes the result into the existing `/chart-context` contract, and can later be exposed to Railway through a tunnel.

**Architecture:** Add a small Python FastAPI app that runs independently from the main backend, plus a focused service module that shells out to the verified `tradingview-mcp` CLI commands and normalizes their JSON output. Keep the existing backend adapter untouched so the current AI Operating Layer can consume the provider without any contract changes.

**Tech Stack:** Python, FastAPI, subprocess-based CLI bridge, pytest, TradingView Desktop, `tradingview-mcp`

---

## File Structure

- Create: `src/local_chart_provider_service.py`
  - Owns subprocess execution of `tradingview-mcp` CLI commands and normalization into the provider contract.
- Create: `src/local_chart_provider_app.py`
  - Owns the small FastAPI app and `GET /chart-context` endpoint.
- Create: `tests/services/test_local_chart_provider_service.py`
  - Covers normalization, timeframe mapping, partial failure handling, and degraded payloads.
- Create: `tests/api/test_local_chart_provider_app.py`
  - Covers endpoint responses and HTTP-level behavior.
- Modify: `docs/superpowers/specs/2026-04-17-local-tradingview-mcp-provider-design.md`
  - Only if implementation reveals a needed wording clarification during execution.

### Task 1: Build the local MCP bridge service

**Files:**
- Create: `src/local_chart_provider_service.py`
- Test: `tests/services/test_local_chart_provider_service.py`

- [ ] **Step 1: Write the failing service tests**

```python
from src.local_chart_provider_service import build_chart_context_payload


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
                    "labels": [{"text": "🟢 LONG", "price": 0.71}],
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
    assert payload["pine_labels"][0]["label"] == "🟢 LONG"


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
```

- [ ] **Step 2: Run the service tests to verify they fail**

Run:

```bash
PYTHONPATH=. pytest tests/services/test_local_chart_provider_service.py -v
```

Expected:

- `ModuleNotFoundError` for `src.local_chart_provider_service`, or failing imports/assertions because the file does not exist yet.

- [ ] **Step 3: Write the minimal service implementation**

```python
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


def _normalize_timeframe(raw_resolution: str) -> str:
    if raw_resolution.isdigit():
        return f"{raw_resolution}m"
    return raw_resolution


def _normalize_indicator_values(values_payload: Optional[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    studies = (values_payload or {}).get("studies") or []
    return {
        study["name"]: study.get("values", {})
        for study in studies
        if study.get("name")
    }


def _normalize_zones(lines_payload: Optional[Dict[str, Any]]) -> List[Dict[str, Any]]:
    zones: List[Dict[str, Any]] = []
    for study in ((lines_payload or {}).get("studies") or []):
        for level in study.get("horizontal_levels", []) or []:
            zones.append(
                {
                    "type": "horizontal_level",
                    "source": "pine",
                    "label": study.get("name", ""),
                    "price": level,
                    "study": study.get("name", ""),
                }
            )
    return zones


def _normalize_labels(labels_payload: Optional[Dict[str, Any]]) -> List[Dict[str, Any]]:
    labels: List[Dict[str, Any]] = []
    for study in ((labels_payload or {}).get("studies") or []):
        for item in study.get("labels", []) or []:
            labels.append(
                {
                    "type": "label",
                    "source": "pine",
                    "label": item.get("text", ""),
                    "price": item.get("price"),
                    "study": study.get("name", ""),
                }
            )
    return labels


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def build_chart_context_payload(
    requested_symbol: str,
    requested_timeframe: str,
    status_payload: Dict[str, Any],
    values_payload: Optional[Dict[str, Any]],
    lines_payload: Optional[Dict[str, Any]],
    labels_payload: Optional[Dict[str, Any]],
    now_iso: Optional[str] = None,
) -> Dict[str, Any]:
    timestamp = now_iso or _now_iso()
    if not status_payload.get("success"):
        return {
            "symbol": requested_symbol,
            "timeframe": requested_timeframe,
            "provider_timestamp": timestamp,
            "pine_labels": [],
            "zones": [],
            "indicator_values": {},
            "reason": status_payload.get("error", "status failed"),
            "metadata": {"partial_failures": []},
        }

    partial_failures: List[str] = []
    if values_payload and not values_payload.get("success"):
        partial_failures.append(values_payload.get("error", "values failed"))
    if lines_payload and not lines_payload.get("success"):
        partial_failures.append(lines_payload.get("error", "lines failed"))
    if labels_payload and not labels_payload.get("success"):
        partial_failures.append(labels_payload.get("error", "labels failed"))

    return {
        "symbol": status_payload.get("chart_symbol", requested_symbol),
        "timeframe": _normalize_timeframe(status_payload.get("chart_resolution", requested_timeframe)),
        "provider_timestamp": timestamp,
        "pine_labels": _normalize_labels(labels_payload if labels_payload and labels_payload.get("success") else None),
        "zones": _normalize_zones(lines_payload if lines_payload and lines_payload.get("success") else None),
        "indicator_values": _normalize_indicator_values(values_payload if values_payload and values_payload.get("success") else None),
        "reason": "",
        "metadata": {
            "requested_symbol": requested_symbol,
            "requested_timeframe": requested_timeframe,
            "partial_failures": partial_failures,
        },
    }
```

- [ ] **Step 4: Run the service tests to verify they pass**

Run:

```bash
PYTHONPATH=. pytest tests/services/test_local_chart_provider_service.py -v
```

Expected:

- All tests in `tests/services/test_local_chart_provider_service.py` pass.

- [ ] **Step 5: Commit the service normalization work**

```bash
git add tests/services/test_local_chart_provider_service.py src/local_chart_provider_service.py
git commit -m "DEV-122: add local chart provider service"
```

### Task 2: Add subprocess MCP execution helpers

**Files:**
- Modify: `src/local_chart_provider_service.py`
- Test: `tests/services/test_local_chart_provider_service.py`

- [ ] **Step 1: Add failing tests for subprocess command execution**

```python
from src.local_chart_provider_service import run_mcp_command


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
```

- [ ] **Step 2: Run the targeted tests to verify they fail**

Run:

```bash
PYTHONPATH=. pytest tests/services/test_local_chart_provider_service.py -v
```

Expected:

- Failing import or assertion because `run_mcp_command` does not exist yet.

- [ ] **Step 3: Implement the subprocess bridge**

```python
import json
import subprocess
from pathlib import Path
from typing import Sequence


MCP_REPO_PATH = Path(__file__).resolve().parents[1] / "mcp" / "tradingview-mcp"


def run_mcp_command(command: Sequence[str]) -> Dict[str, Any]:
    completed = subprocess.run(
        command,
        cwd=MCP_REPO_PATH,
        capture_output=True,
        text=True,
        timeout=10,
        check=False,
    )
    if completed.returncode != 0:
        return {"success": False, "error": completed.stderr.strip() or completed.stdout.strip() or "command failed"}

    try:
        return json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        return {"success": False, "error": f"invalid JSON from MCP CLI: {exc}"}


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
        )

    values_payload = run_mcp_command(["node", "src/cli/index.js", "values"])
    lines_payload = run_mcp_command(["node", "src/cli/index.js", "data", "lines"])
    labels_payload = run_mcp_command(["node", "src/cli/index.js", "data", "labels"])

    return build_chart_context_payload(
        requested_symbol=requested_symbol,
        requested_timeframe=requested_timeframe,
        status_payload=status_payload,
        values_payload=values_payload,
        lines_payload=lines_payload,
        labels_payload=labels_payload,
    )
```

- [ ] **Step 4: Run the service tests to verify the bridge works**

Run:

```bash
PYTHONPATH=. pytest tests/services/test_local_chart_provider_service.py -v
```

Expected:

- All tests pass, including the subprocess command tests.

- [ ] **Step 5: Commit the CLI bridge work**

```bash
git add tests/services/test_local_chart_provider_service.py src/local_chart_provider_service.py
git commit -m "DEV-122: add MCP CLI bridge"
```

### Task 3: Add the local FastAPI provider app

**Files:**
- Create: `src/local_chart_provider_app.py`
- Test: `tests/api/test_local_chart_provider_app.py`

- [ ] **Step 1: Write the failing endpoint tests**

```python
from fastapi.testclient import TestClient

from src.local_chart_provider_app import app


def test_chart_context_endpoint_returns_provider_payload(monkeypatch) -> None:
    monkeypatch.setattr(
        "src.local_chart_provider_app.fetch_live_chart_context",
        lambda symbol, timeframe: {
            "symbol": symbol,
            "timeframe": timeframe,
            "provider_timestamp": "2026-04-17T00:20:00Z",
            "pine_labels": [],
            "zones": [],
            "indicator_values": {},
            "reason": "",
            "metadata": {"partial_failures": []},
        },
    )

    client = TestClient(app)
    response = client.get("/chart-context", params={"symbol": "XAUUSD", "timeframe": "5m"})

    assert response.status_code == 200
    assert response.json()["symbol"] == "XAUUSD"
    assert response.json()["provider_timestamp"] == "2026-04-17T00:20:00Z"


def test_chart_context_endpoint_requires_query_params() -> None:
    client = TestClient(app)
    response = client.get("/chart-context")
    assert response.status_code == 422
```

- [ ] **Step 2: Run the endpoint tests to verify they fail**

Run:

```bash
PYTHONPATH=. pytest tests/api/test_local_chart_provider_app.py -v
```

Expected:

- `ModuleNotFoundError` for `src.local_chart_provider_app`, or missing app import failures.

- [ ] **Step 3: Implement the local FastAPI app**

```python
from __future__ import annotations

import logging

from fastapi import FastAPI, Query

from src.local_chart_provider_service import fetch_live_chart_context


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("local_chart_provider")

app = FastAPI(title="Local TradingView MCP Provider", version="0.1.0")


@app.get("/chart-context")
async def get_chart_context(
    symbol: str = Query(...),
    timeframe: str = Query(...),
) -> dict:
    logger.info("chart-context request symbol=%s timeframe=%s", symbol, timeframe)
    payload = fetch_live_chart_context(symbol, timeframe)
    logger.info(
        "chart-context response actual_symbol=%s actual_timeframe=%s reason=%s",
        payload.get("symbol"),
        payload.get("timeframe"),
        payload.get("reason", ""),
    )
    return payload
```

- [ ] **Step 4: Run the endpoint tests to verify they pass**

Run:

```bash
PYTHONPATH=. pytest tests/api/test_local_chart_provider_app.py -v
```

Expected:

- All tests in `tests/api/test_local_chart_provider_app.py` pass.

- [ ] **Step 5: Commit the local app**

```bash
git add tests/api/test_local_chart_provider_app.py src/local_chart_provider_app.py
git commit -m "DEV-122: add local chart provider app"
```

### Task 4: Verify the local provider end to end

**Files:**
- Modify: `src/local_chart_provider_app.py` (only if a tiny entrypoint tweak is needed)
- Test: `tests/services/test_local_chart_provider_service.py`
- Test: `tests/api/test_local_chart_provider_app.py`

- [ ] **Step 1: Run the full focused automated test suite**

Run:

```bash
PYTHONPATH=. pytest tests/services/test_local_chart_provider_service.py tests/api/test_local_chart_provider_app.py -v
```

Expected:

- All provider wrapper tests pass.

- [ ] **Step 2: Start the local provider app**

Run:

```bash
source ./venv/bin/activate && PYTHONPATH=. python3 -m uvicorn src.local_chart_provider_app:app --host 0.0.0.0 --port 8765
```

Expected:

- Uvicorn starts and listens on `http://localhost:8765`.

- [ ] **Step 3: Smoke-test the endpoint against the live TradingView/MCP setup**

Run:

```bash
curl "http://localhost:8765/chart-context?symbol=VANTAGE:AUDUSD&timeframe=5m"
```

Expected:

- JSON payload with:
  - `symbol`
  - `timeframe`
  - `provider_timestamp`
  - `pine_labels`
  - `zones`
  - `indicator_values`

- [ ] **Step 4: Confirm compatibility with the existing backend adapter contract**

Run:

```bash
PYTHONPATH=. pytest tests/adapters/test_tradingview_chart_provider.py tests/services/test_chart_context_service.py tests/services/test_chart_context_fetch.py -v
```

Expected:

- Existing provider adapter and chart context service tests still pass unchanged.

- [ ] **Step 5: Commit the verification-ready wrapper**

```bash
git add src/local_chart_provider_service.py src/local_chart_provider_app.py tests/services/test_local_chart_provider_service.py tests/api/test_local_chart_provider_app.py
git commit -m "DEV-122: add local provider wrapper"
```

## Self-Review

- Spec coverage check:
  - local-only wrapper: covered by Tasks 2-4
  - Python implementation: covered by Tasks 1-3
  - existing `/chart-context` contract: covered by Tasks 1 and 3
  - graceful degradation: covered by Tasks 1 and 2
  - local debug flow: covered by Task 4
- Placeholder scan:
  - no `TODO`, `TBD`, or “handle appropriately” placeholders remain
- Type consistency:
  - plan consistently uses `build_chart_context_payload`, `run_mcp_command`, and `fetch_live_chart_context`

