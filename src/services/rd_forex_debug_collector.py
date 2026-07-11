"""Durable non-execution RD Forex LAB debug event collection."""

from __future__ import annotations

import csv
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from config import get_settings


CSV_FIELDS = [
    "received_at",
    "event",
    "run_id",
    "symbol",
    "feed",
    "timeframe",
    "replay_session",
    "replay_start_time",
    "replay_end_time",
    "zone_id",
    "model",
    "zone_type",
    "origin_bar",
    "origin_time",
    "detection_bar",
    "detection_time",
    "confirmation_bar",
    "confirmation_time",
    "top",
    "bottom",
    "active",
    "liquidity_price",
    "liquidity_bar_index",
    "liquidity_swept",
    "target_swept",
    "touched",
    "invalidation_reason",
]


def _safe_run_id(run_id: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9_.=-]+", "_", run_id.strip())
    return cleaned[:120] or "unknown-run"


def _artifact_dir() -> Path:
    configured = Path(get_settings().rd_forex_debug_artifact_dir)
    return configured if configured.is_absolute() else Path.cwd() / configured


def normalize_debug_event(payload: dict[str, Any]) -> dict[str, Any]:
    """Return a stable artifact record with replay metadata fields present."""
    event = dict(payload)
    event.setdefault("feed", event.get("exchange") or event.get("broker") or "")
    event.setdefault("replay_session", "")
    event.setdefault("replay_start_time", None)
    event.setdefault("replay_end_time", None)
    event.setdefault("confirmation_time", None)
    event["received_at"] = datetime.now(timezone.utc).isoformat()
    return event


def append_debug_event(payload: dict[str, Any]) -> dict[str, str]:
    """Append one validated RD Forex debug event to JSONL and CSV artifacts."""
    event = normalize_debug_event(payload)
    run_id = _safe_run_id(str(event["run_id"]))
    artifact_dir = _artifact_dir() / run_id
    artifact_dir.mkdir(parents=True, exist_ok=True)

    jsonl_path = artifact_dir / "events.jsonl"
    csv_path = artifact_dir / "events.csv"

    with jsonl_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(event, sort_keys=True, separators=(",", ":")) + "\n")

    write_header = not csv_path.exists()
    with csv_path.open("a", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=CSV_FIELDS, extrasaction="ignore")
        if write_header:
            writer.writeheader()
        writer.writerow(event)

    return {
        "jsonl_path": str(jsonl_path),
        "csv_path": str(csv_path),
    }
