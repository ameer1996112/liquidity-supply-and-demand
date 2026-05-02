from __future__ import annotations

import argparse
import csv
import json
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

try:
    from .config import RESULTS_DIR
except ImportError:
    from scripts.optimizer.config import RESULTS_DIR


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _num(row: dict[str, Any], key: str, default: float = 0.0) -> float:
    try:
        return float(row.get(key, default))
    except (TypeError, ValueError):
        return default


def summarize_forward_tests(records: list[dict[str, Any]], symbol: str) -> dict[str, Any]:
    rows = [row for row in records if str(row.get("symbol", "")).upper() == symbol.upper()]
    reasons: list[str] = []
    if not rows:
        reasons.append("missing_forward_test_records")
        return {"symbol": symbol, "status": "WATCH_ONLY", "rejection_reasons": reasons, "warnings": []}
    dates = sorted({str(row.get("date", ""))[:10] for row in rows if row.get("date")})
    days = 0
    if dates:
        start = date.fromisoformat(dates[0])
        end = date.fromisoformat(dates[-1])
        days = (end - start).days + 1
    wins = sum(_num(row, "profit_loss") for row in rows if _num(row, "profit_loss") > 0)
    losses = abs(sum(_num(row, "profit_loss") for row in rows if _num(row, "profit_loss") < 0))
    net = sum(_num(row, "profit_loss") for row in rows)
    pf = wins / losses if losses else (99.0 if wins > 0 else 0.0)
    if days < 30:
        reasons.append("minimum_30_calendar_days_not_met")
    if len(rows) < 20:
        reasons.append("minimum_20_trades_not_met")
    if net < 0:
        reasons.append("net_profit_negative")
    if pf < 1.05:
        reasons.append("pf_below_1.05")
    if any(bool(row.get("rule_breach")) for row in rows):
        reasons.append("prop_profile_breach")
    status = "passed" if not reasons else "WATCH_ONLY"
    return {
        "symbol": symbol,
        "status": status,
        "calendar_days": days,
        "total_trades": len(rows),
        "net_profit": net,
        "profit_factor": pf,
        "rejection_reasons": reasons,
        "warnings": [],
    }


def load_records(path: Path) -> list[dict[str, Any]]:
    if path.suffix.lower() == ".csv":
        with path.open() as handle:
            return list(csv.DictReader(handle))
    payload = json.loads(path.read_text())
    return payload if isinstance(payload, list) else payload.get("records", [])


def write_outputs(results: dict[str, dict[str, Any]], records: list[dict[str, Any]], results_dir: Path = RESULTS_DIR) -> None:
    base = {"schema_version": 1, "created_at": _now(), "source_files": [], "prop_profile": None, "warnings": []}
    passed = {k: v for k, v in results.items() if v.get("status") == "passed"}
    rejected = {k: v for k, v in results.items() if v.get("status") != "passed"}
    (results_dir / "forward_test_results.json").write_text(json.dumps({**base, "status": "completed", "records": records}, indent=2))
    (results_dir / "forward_test_summary.json").write_text(json.dumps({**base, "status": "completed", "results": results}, indent=2))
    (results_dir / "forward_test_passed.json").write_text(json.dumps({**base, "status": "completed", "results": passed}, indent=2))
    (results_dir / "forward_test_rejected.json").write_text(json.dumps({**base, "status": "completed", "rejection_reasons": rejected}, indent=2))


def cli(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Summarize demo/paper forward-test records.")
    parser.add_argument("--input", required=True)
    parser.add_argument("--symbols", default="")
    args = parser.parse_args(argv)
    records = load_records(Path(args.input))
    symbols = [item.strip().upper() for item in args.symbols.split(",") if item.strip()] or sorted({str(row.get("symbol", "")).upper() for row in records})
    results = {symbol: summarize_forward_tests(records, symbol) for symbol in symbols}
    write_outputs(results, records)


if __name__ == "__main__":
    cli()
