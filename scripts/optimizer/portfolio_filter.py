from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    from .config import RESULTS_DIR
except ImportError:
    from scripts.optimizer.config import RESULTS_DIR

CORRELATION_GROUPS: dict[str, set[str]] = {
    "usd_majors": {"EURUSD", "GBPUSD", "AUDUSD", "NZDUSD", "USDCAD", "USDJPY", "USDCHF"},
    "jpy_crosses": {"USDJPY", "EURJPY", "GBPJPY", "AUDJPY"},
    "metals": {"XAUUSD", "XAGUSD", "GC", "MGC", "SI", "SIL"},
    "index": {"NAS100", "US100", "US500", "US30", "NQ", "MNQ", "ES", "MES", "YM", "MYM"},
    "energy": {"CL", "MCL"},
}

MUTUALLY_EXCLUSIVE = [
    ({"XAUUSD", "XAGUSD"}, "metals"),
    ({"NAS100", "NQ"}, "index"),
    ({"US100", "NAS100"}, "index"),
]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _root(symbol: str) -> str:
    clean = symbol.upper().split(":")[-1]
    return "".join(ch for ch in clean if ch.isalpha())


def groups_for(symbol: str) -> list[str]:
    root = _root(symbol)
    return [name for name, members in CORRELATION_GROUPS.items() if root in members]


def filter_portfolio(
    candidates: list[str],
    profile: dict[str, Any],
) -> tuple[list[str], dict[str, str], dict[str, Any]]:
    allowed: list[str] = []
    blocked: dict[str, str] = {}
    group_counts: dict[str, int] = {}
    max_symbols = int(profile.get("max_symbols_active", len(candidates)) or len(candidates))
    max_correlated = int(profile.get("max_correlated_symbols", 1) or 1)
    for symbol in candidates:
        clean = symbol.upper()
        if len(allowed) >= max_symbols:
            blocked[clean] = "blocked because max_symbols_active reached"
            continue
        exclusive_reason = None
        for exclusive_set, group in MUTUALLY_EXCLUSIVE:
            if clean in exclusive_set and any(_root(item) in exclusive_set for item in allowed):
                exclusive_reason = f"blocked because {group} correlated exposure already selected"
                break
        if exclusive_reason:
            blocked[clean] = exclusive_reason
            continue
        symbol_groups = groups_for(clean)
        over_group = next((group for group in symbol_groups if group_counts.get(group, 0) >= max_correlated), None)
        if over_group:
            blocked[clean] = f"blocked because correlated {over_group} exposure already selected"
            continue
        allowed.append(clean)
        for group in symbol_groups:
            group_counts[group] = group_counts.get(group, 0) + 1
    report = {
        "schema_version": 1,
        "created_at": _now(),
        "source_files": [],
        "prop_profile": profile.get("name"),
        "status": "filtered",
        "allowed_symbols": allowed,
        "blocked_symbols": blocked,
        "rejection_reasons": blocked,
        "warnings": [],
        "group_counts": group_counts,
    }
    return allowed, blocked, report


def write_outputs(allowed: list[str], blocked: dict[str, str], report: dict[str, Any], results_dir: Path = RESULTS_DIR) -> None:
    (results_dir / "portfolio_allowed_symbols.json").write_text(json.dumps({"schema_version": 1, "created_at": _now(), "symbols": allowed}, indent=2))
    (results_dir / "portfolio_blocked_symbols.json").write_text(json.dumps({"schema_version": 1, "created_at": _now(), "rejection_reasons": blocked}, indent=2))
    (results_dir / "portfolio_risk_report.json").write_text(json.dumps(report, indent=2))


def cli(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Filter correlated optimizer candidates.")
    parser.add_argument("--candidates", default="")
    parser.add_argument("--profile", default='{"max_symbols_active":3,"max_correlated_symbols":1}')
    args = parser.parse_args(argv)
    allowed, blocked, report = filter_portfolio([item for item in args.candidates.split(",") if item], json.loads(args.profile))
    write_outputs(allowed, blocked, report)


if __name__ == "__main__":
    cli()
