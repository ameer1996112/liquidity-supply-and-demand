from __future__ import annotations

import argparse
import csv
import json
import statistics
from collections import defaultdict
from pathlib import Path
from typing import Any, Iterable

try:
    from .config import RESULTS_DIR
except ImportError:
    from scripts.optimizer.config import RESULTS_DIR


DISCORD_SUMMARY_OUTPUT = RESULTS_DIR / "discord_backtest_summary.json"

FIELD_ALIASES = {
    "instrument": ("instrument", "symbol", "ticker", "market"),
    "date": ("date", "trade_date"),
    "entry_time": ("entry_time", "time", "timestamp"),
    "hour": ("hour", "session_hour"),
    "entry_model": ("entry_type", "entry_model", "model", "setup"),
    "side": ("side", "direction"),
    "grade": ("grade", "zone_grade", "setup_grade", "Zone Grade"),
    "rr": ("rr", "r", "profit_r", "result_r", "R:R"),
    "comments": ("comments", "notes"),
}


def _cell(row: dict[str, Any], field: str) -> Any:
    for name in FIELD_ALIASES[field]:
        if name in row and row[name] not in (None, ""):
            return row[name]
    return ""


def _parse_float(value: Any, default: float = 0.0) -> float:
    if value in (None, ""):
        return default
    text = str(value).strip().replace(",", "")
    if text.lower() in {"inf", "+inf", "infinity"}:
        return float("inf")
    try:
        return float(text)
    except ValueError:
        return default


def _parse_hour(row: dict[str, Any]) -> int | None:
    raw_hour = _cell(row, "hour")
    if raw_hour not in (None, ""):
        try:
            return int(float(str(raw_hour).strip()))
        except ValueError:
            pass
    raw_time = str(_cell(row, "entry_time") or "").strip()
    if ":" in raw_time:
        try:
            return int(raw_time.split(":", 1)[0])
        except ValueError:
            return None
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


def _json_number(value: float) -> float | str:
    if value == float("inf"):
        return "inf"
    if value == float("-inf"):
        return "-inf"
    return round(value, 6)


def _metrics(rows: list[dict[str, Any]]) -> dict[str, Any]:
    r_values = [float(row["rr"]) for row in rows]
    wins = [value for value in r_values if value > 0]
    losses = [value for value in r_values if value < 0]
    gross_win = sum(wins)
    gross_loss = abs(sum(losses))
    profit_factor = float("inf") if gross_win > 0 and gross_loss == 0 else (gross_win / gross_loss if gross_loss else 0.0)
    sorted_r = sorted(r_values)
    return {
        "trades": len(rows),
        "wins": len(wins),
        "losses": len(losses),
        "net_r": round(sum(r_values), 6),
        "avg_r": round(sum(r_values) / len(rows), 6) if rows else 0.0,
        "win_rate_pct": round((len(wins) / len(rows)) * 100.0, 6) if rows else 0.0,
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


def normalize_discord_backtest_row(row: dict[str, Any]) -> dict[str, Any] | None:
    instrument = str(_cell(row, "instrument") or "").strip().upper()
    if not instrument:
        return None
    rr = _parse_float(_cell(row, "rr"))
    hour = _parse_hour(row)
    return {
        "instrument": instrument,
        "date": str(_cell(row, "date") or "").strip(),
        "entry_time": str(_cell(row, "entry_time") or "").strip(),
        "hour": hour,
        "entry_model": _normalize_entry_model(_cell(row, "entry_model")),
        "side": _normalize_side(_cell(row, "side")),
        "grade": str(_cell(row, "grade") or "").strip().upper(),
        "rr": rr,
        "comments": str(_cell(row, "comments") or "").strip(),
    }


def summarize_discord_backtest_rows(rows: Iterable[dict[str, Any]], *, source_file: str | None = None) -> dict[str, Any]:
    trades = [normalized for row in rows if (normalized := normalize_discord_backtest_row(row))]
    summary = {
        "schema_version": 1,
        "source_file": source_file,
        "trade_count": len(trades),
        "metrics": _metrics(trades) if trades else _metrics([]),
        "by_instrument": _group_metrics(trades, "instrument"),
        "by_hour": _group_metrics(trades, "hour"),
        "by_entry_model": _group_metrics(trades, "entry_model"),
        "by_side": _group_metrics(trades, "side"),
        "by_grade": _group_metrics(trades, "grade"),
        "trades": trades,
    }
    return summary


def load_discord_backtest_rows(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    if path.suffix.lower() == ".csv":
        with path.open(newline="") as handle:
            return [dict(row) for row in csv.DictReader(handle)]
    if path.suffix.lower() in {".xlsx", ".xlsm"}:
        try:
            import openpyxl
        except ImportError as exc:
            raise RuntimeError("openpyxl is required to ingest Excel backtest files") from exc
        workbook = openpyxl.load_workbook(path, read_only=True, data_only=True)
        rows: list[dict[str, Any]] = []
        for sheet in workbook.worksheets:
            values = list(sheet.iter_rows(values_only=True))
            if not values:
                continue
            headers = [str(value or "").strip() for value in values[0]]
            for raw in values[1:]:
                row = {headers[index]: value for index, value in enumerate(raw) if index < len(headers)}
                row.setdefault("source_sheet", sheet.title)
                rows.append(row)
        return rows
    return []


def ingest_discord_backtest(input_path: Path, output_path: Path = DISCORD_SUMMARY_OUTPUT) -> dict[str, Any]:
    rows = load_discord_backtest_rows(input_path)
    payload = summarize_discord_backtest_rows(rows, source_file=str(input_path))
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, indent=2))
    return payload


def cli(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Ingest Discord/manual backtest rows into optimizer evidence.")
    parser.add_argument("--input", type=Path, default=Path("data/backtests/discord_backtesting_normalized.csv"))
    parser.add_argument("--output", type=Path, default=DISCORD_SUMMARY_OUTPUT)
    args = parser.parse_args(argv)
    ingest_discord_backtest(args.input, args.output)


if __name__ == "__main__":
    cli()
