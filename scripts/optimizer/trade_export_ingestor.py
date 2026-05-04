from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any

REQUIRED_TRADE_FIELDS = {
    "symbol",
    "broker",
    "params_hash",
    "entry_time",
    "exit_time",
    "direction",
    "profit_usd",
    "profit_r",
    "max_drawdown_usd",
    "session",
    "spread",
    "slippage",
}


def _load_rows(path: Path) -> list[dict[str, Any]]:
    if path.suffix.lower() in {".json", ".jsonl"}:
        if path.suffix.lower() == ".jsonl":
            return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]
        payload = json.loads(path.read_text())
        rows = payload.get("trades", payload) if isinstance(payload, dict) else payload
        return [row for row in rows if isinstance(row, dict)]
    with path.open(newline="") as handle:
        return [dict(row) for row in csv.DictReader(handle)]


def ingest_trade_export(path: Path) -> dict[str, Any]:
    trades = _load_rows(path)
    accepted: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []
    for index, trade in enumerate(trades, start=1):
        missing = sorted(field for field in REQUIRED_TRADE_FIELDS if trade.get(field) in (None, ""))
        if missing:
            rejected.append({"row": index, "missing_fields": missing})
        else:
            accepted.append(trade)
    return {
        "schema_version": 1,
        "source_file": str(path),
        "status": "passed" if accepted and not rejected else ("watch_only" if accepted else "rejected"),
        "precision": "trade_level" if accepted and not rejected else "approximate",
        "trades": accepted,
        "rejected_rows": rejected,
    }


def cli(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Ingest TradingView trade-level exports for stress and prop simulation.")
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    payload = ingest_trade_export(args.input)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2))


if __name__ == "__main__":
    cli()
