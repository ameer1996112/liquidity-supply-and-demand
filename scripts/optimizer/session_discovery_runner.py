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

SESSION_BLOCKS = {
    "asia": {"start_utc": 0, "end_utc": 7},
    "london": {"start_utc": 7, "end_utc": 12},
    "london_ny_overlap": {"start_utc": 12, "end_utc": 16},
    "ny": {"start_utc": 14, "end_utc": 21},
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _num(row: dict[str, Any], key: str, default: float = 0.0) -> float:
    try:
        return float(row.get(key, default))
    except (TypeError, ValueError):
        return default


def score_session(row: dict[str, Any]) -> float:
    score = 0.0
    score += max(0.0, _num(row, "net_profit")) / 100.0
    score += (_num(row, "profit_factor") - 1.0) * 100.0
    score += min(_num(row, "total_trades"), 60.0) / 3.0
    score -= _num(row, "max_drawdown_pct") * 4.0
    score -= max(0.0, -_num(row, "worst_day")) / 50.0
    if row.get("result_truth", {}).get("trust_status") in {"trusted", "trusted_with_warnings"} or row.get("result_truth", {}).get("status") in {"trusted", "trusted_with_warnings"}:
        score += 15.0
    if row.get("trade_density_anomaly"):
        score -= 50.0
    return round(score, 2)


def evaluate_session_discovery(symbol: str, session_rows: dict[str, dict[str, Any]], min_trades: int = 10) -> dict[str, Any]:
    sessions: dict[str, Any] = {}
    for name, block in SESSION_BLOCKS.items():
        row = session_rows.get(name, {})
        truth_status = row.get("result_truth", {}).get("status") or row.get("result_truth", {}).get("trust_status")
        reasons: list[str] = []
        if _num(row, "profit_factor") < 1.10:
            reasons.append("pf_below_1.10")
        if int(_num(row, "total_trades")) < min_trades:
            reasons.append("trades_below_minimum")
        if _num(row, "max_drawdown_pct") > _num(row, "safe_max_dd_pct", 999.0):
            reasons.append("dd_above_prop_safe_limit")
        if truth_status not in {"trusted", "trusted_with_warnings"}:
            reasons.append("result_truth_not_trusted")
        if row.get("trade_density_anomaly"):
            reasons.append("trade_density_anomaly")
        sessions[name] = {
            "session": block,
            "status": "passed" if not reasons else "rejected",
            "score": score_session(row),
            "rejection_reasons": reasons,
            "metrics": row,
        }
    best = sorted(sessions.items(), key=lambda item: item[1]["score"], reverse=True)
    return {
        "symbol": symbol,
        "status": "passed" if best and best[0][1]["status"] == "passed" else "rejected",
        "best_session": best[0][0] if best else "",
        "sessions": sessions,
    }


def write_outputs(results: dict[str, dict[str, Any]], results_dir: Path = RESULTS_DIR) -> None:
    results_dir.mkdir(parents=True, exist_ok=True)
    payload = {"schema_version": 1, "created_at": _now(), "sessions": SESSION_BLOCKS, "results": results}
    (results_dir / "session_discovery_results.json").write_text(json.dumps(payload, indent=2))
    lines = ["# Session Discovery Report", ""]
    for symbol, row in results.items():
        lines.append(f"- {symbol}: {row['status']} best={row['best_session']}")
    Path("reports").mkdir(exist_ok=True)
    Path("reports/session_discovery_report.md").write_text("\n".join(lines) + "\n")


def cli(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Evaluate fixed UTC session blocks for candidate pairs.")
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--results-dir", type=Path, default=RESULTS_DIR)
    args = parser.parse_args(argv)
    payload = json.loads(args.input.read_text())
    results = {symbol: evaluate_session_discovery(symbol, rows) for symbol, rows in payload.items() if isinstance(rows, dict)}
    write_outputs(results, args.results_dir)


if __name__ == "__main__":
    cli()
