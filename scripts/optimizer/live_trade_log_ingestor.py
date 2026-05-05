from __future__ import annotations

import argparse
import csv
import json
import statistics
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable

try:
    from .config import RESULTS_DIR
except ImportError:
    from scripts.optimizer.config import RESULTS_DIR


LIVE_SUMMARY_OUTPUT = RESULTS_DIR / "live_trade_summary.json"

EXECUTION_FAILURE_STATUSES = {
    "EXECUTION_FAILED",
    "BROKER_REJECTED",
    "ORDER_REJECTED",
    "SEND_FAILED",
}
REJECTION_STATUS_MARKERS = ("REJECTED", "STALE", "UNEXECUTED", "EXPIRED", "SKIPPED")
EXECUTED_STATUSES = {"CLOSED", "OPEN", "EXECUTED", "FILLED", "PARTIAL"}

FIELD_ALIASES = {
    "timestamp": ("Date", "date", "timestamp", "created_at", "entry_time"),
    "symbol": ("Symbol", "symbol", "instrument"),
    "side": ("Side", "side", "direction"),
    "status": ("Status", "status"),
    "entry_model": ("Entry Model", "entry_model", "entry_type", "model"),
    "session": ("Session", "session"),
    "grade": ("Zone Grade", "grade", "setup_grade"),
    "exit_type": ("Exit Type", "exit_type"),
    "rr": ("profit_r", "pnl_r", "realized_r", "R", "R:R", "rr"),
    "notes": ("Notes", "notes", "comments"),
}


def _cell(row: dict[str, Any], field: str) -> Any:
    for name in FIELD_ALIASES[field]:
        if name in row and row[name] not in (None, ""):
            return row[name]
    return ""


def _parse_float(value: Any, default: float = 0.0) -> float:
    if value in (None, ""):
        return default
    try:
        return float(str(value).strip().replace(",", ""))
    except ValueError:
        return default


def _parse_timestamp(value: Any) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M"):
        try:
            return datetime.strptime(text.replace("Z", ""), fmt)
        except ValueError:
            continue
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None


def _normalize_side(value: Any) -> str:
    text = str(value or "").strip().upper()
    if text in {"BUY", "BUYS", "LONG"}:
        return "BUY"
    if text in {"SELL", "SELLS", "SHORT"}:
        return "SELL"
    return text


def _normalize_entry_model(value: Any) -> str:
    text = str(value or "UNKNOWN").strip().upper().replace("-", "_").replace(" ", "_")
    aliases = {
        "FLIP_ENTRY": "FLIP",
        "2ND_FLIP": "FLIP",
        "LATE_FLIP": "FLIP",
        "BOC": "BOC",
        "BREAK_OF_CANDLE": "BREAK_CANDLE",
        "DIRECTIONAL/BOC": "BOC",
    }
    return aliases.get(text, text)


def _realized_r(row: dict[str, Any], status: str) -> float | None:
    if status != "CLOSED":
        return None
    raw_rr = _parse_float(_cell(row, "rr"))
    exit_type = str(_cell(row, "exit_type") or "").strip().lower()
    if exit_type in {"sl_hit", "stop_loss", "loss"}:
        return -1.0
    if exit_type in {"tp_hit", "take_profit", "win"}:
        return raw_rr if raw_rr else 1.0
    if "profit_r" in row or "pnl_r" in row or "realized_r" in row or "R" in row:
        return raw_rr
    return None


def _json_number(value: float) -> float | str:
    if value == float("inf"):
        return "inf"
    return round(value, 6)


def _metrics(rows: list[dict[str, Any]]) -> dict[str, Any]:
    closed = [row for row in rows if row.get("realized_r") is not None]
    r_values = [float(row["realized_r"]) for row in closed]
    wins = [value for value in r_values if value > 0]
    losses = [value for value in r_values if value < 0]
    gross_win = sum(wins)
    gross_loss = abs(sum(losses))
    profit_factor = float("inf") if gross_win > 0 and gross_loss == 0 else (gross_win / gross_loss if gross_loss else 0.0)
    sorted_r = sorted(r_values)
    return {
        "signals": len(rows),
        "trades": len(closed),
        "wins": len(wins),
        "losses": len(losses),
        "net_r": round(sum(r_values), 6),
        "avg_r": round(sum(r_values) / len(r_values), 6) if r_values else 0.0,
        "win_rate_pct": round((len(wins) / len(r_values)) * 100.0, 6) if r_values else 0.0,
        "profit_factor_r": _json_number(profit_factor),
        "rr_distribution": {
            "min": round(min(sorted_r), 6) if sorted_r else 0.0,
            "max": round(max(sorted_r), 6) if sorted_r else 0.0,
            "median": round(statistics.median(sorted_r), 6) if sorted_r else 0.0,
            "positive_count": len(wins),
            "negative_count": len(losses),
        },
    }


def _group_metrics(rows: list[dict[str, Any]], field: str) -> dict[str, Any]:
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        value = row.get(field)
        if value not in (None, ""):
            groups[str(value)].append(row)
    return {key: _metrics(group_rows) for key, group_rows in sorted(groups.items())}


def normalize_live_trade_row(row: dict[str, Any]) -> dict[str, Any] | None:
    symbol = str(_cell(row, "symbol") or "").strip().upper()
    if not symbol:
        return None
    timestamp = _parse_timestamp(_cell(row, "timestamp"))
    status = str(_cell(row, "status") or "UNKNOWN").strip().upper()
    rejection = any(marker in status for marker in REJECTION_STATUS_MARKERS)
    execution_failure = status in EXECUTION_FAILURE_STATUSES
    return {
        "timestamp": timestamp.isoformat() if timestamp else "",
        "hour": timestamp.hour if timestamp else None,
        "symbol": symbol,
        "side": _normalize_side(_cell(row, "side")),
        "status": status,
        "entry_model": _normalize_entry_model(_cell(row, "entry_model")),
        "session": str(_cell(row, "session") or "").strip().upper(),
        "grade": str(_cell(row, "grade") or "").strip().upper(),
        "realized_r": _realized_r(row, status),
        "execution_failure": execution_failure,
        "rejected_or_stale": rejection,
        "unexecuted": status not in EXECUTED_STATUSES and status != "CLOSED",
        "notes": str(_cell(row, "notes") or "").strip(),
    }


def summarize_live_trade_rows(rows: Iterable[dict[str, Any]], *, source_files: list[str] | None = None) -> dict[str, Any]:
    trades = [normalized for row in rows if (normalized := normalize_live_trade_row(row))]
    signal_count = len(trades)
    execution_failures = sum(1 for row in trades if row["execution_failure"])
    stale_rejected_unexecuted = sum(1 for row in trades if row["rejected_or_stale"] or row["unexecuted"])
    return {
        "schema_version": 1,
        "source_files": source_files or [],
        "signal_count": signal_count,
        "execution_failures": execution_failures,
        "execution_failure_rate_pct": round((execution_failures / signal_count) * 100.0, 6) if signal_count else 0.0,
        "stale_rejected_unexecuted": stale_rejected_unexecuted,
        "staleness_rejection_rate_pct": round((stale_rejected_unexecuted / signal_count) * 100.0, 6) if signal_count else 0.0,
        "metrics": _metrics(trades),
        "by_symbol": _group_metrics(trades, "symbol"),
        "by_hour": _group_metrics(trades, "hour"),
        "by_session": _group_metrics(trades, "session"),
        "by_entry_model": _group_metrics(trades, "entry_model"),
        "by_side": _group_metrics(trades, "side"),
        "by_grade": _group_metrics(trades, "grade"),
        "trades": trades,
    }


def load_live_trade_rows(paths: Iterable[Path]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for path in paths:
        if not path.exists() or path.suffix.lower() != ".csv":
            continue
        with path.open(newline="") as handle:
            rows.extend(dict(row) for row in csv.DictReader(handle))
    return rows


def discover_live_trade_paths(input_path: Path) -> list[Path]:
    if input_path.is_dir():
        return sorted(input_path.glob("trades_*.csv"))
    return [input_path]


def ingest_live_trade_logs(input_path: Path, output_path: Path = LIVE_SUMMARY_OUTPUT) -> dict[str, Any]:
    paths = discover_live_trade_paths(input_path)
    rows = load_live_trade_rows(paths)
    payload = summarize_live_trade_rows(rows, source_files=[str(path) for path in paths if path.exists()])
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, indent=2))
    return payload


def cli(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Ingest bot live trade CSV logs into optimizer evidence.")
    parser.add_argument("--input", type=Path, default=Path("data/live_trades"))
    parser.add_argument("--output", type=Path, default=LIVE_SUMMARY_OUTPUT)
    args = parser.parse_args(argv)
    ingest_live_trade_logs(args.input, args.output)


if __name__ == "__main__":
    cli()
