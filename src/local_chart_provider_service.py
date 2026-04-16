from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess
from typing import Any, Dict, List, Optional, Sequence


MCP_REPO_PATH = Path(__file__).resolve().parents[1] / "mcp" / "tradingview-mcp"


def _normalize_timeframe(raw_resolution: str) -> str:
    return f"{raw_resolution}m" if raw_resolution.isdigit() else raw_resolution


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
        return {
            "success": False,
            "error": completed.stderr.strip() or completed.stdout.strip() or "command failed",
        }

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
