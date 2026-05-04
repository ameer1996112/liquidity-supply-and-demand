from __future__ import annotations

import argparse
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

try:
    from .config import RESULTS_DIR
except ImportError:
    from scripts.optimizer.config import RESULTS_DIR

RESEARCH_GATES = {
    "strategy_fidelity_status": {"passed"},
    "result_truth_status": {"trusted", "trusted_with_warnings"},
    "walk_forward_status": {"passed"},
    "frozen_validation_status": {"passed"},
    "parameter_stability_status": {"passed"},
    "stress_test_status": {"passed"},
    "prop_survival_status": {"passed"},
    "broker_filter_status": {"passed"},
    "human_review_status": {"reviewed", "approved"},
    "anomaly_status": {"passed", "none"},
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _expiry(generated_at: str) -> str:
    parsed = datetime.fromisoformat(generated_at.replace("Z", "+00:00"))
    return (parsed + timedelta(days=31)).date().isoformat()


def _rejections(row: dict[str, Any]) -> list[str]:
    reasons: list[str] = []
    for key, allowed in RESEARCH_GATES.items():
        value = str(row.get(key) or "missing")
        if value not in allowed:
            reasons.append(f"{key}={value}")
    if not row.get("params_hash"):
        reasons.append("missing_params_hash")
    if not isinstance(row.get("params"), dict) or not row.get("params"):
        reasons.append("missing_params")
    return reasons


def build_approved_candidates(
    candidate_rows: list[dict[str, Any]],
    *,
    generated_at: str | None = None,
) -> tuple[dict[str, Any], dict[str, list[str]]]:
    generated_at = generated_at or _now()
    approved_until = _expiry(generated_at)
    payload = {
        "schema_version": 1,
        "generated_at": generated_at,
        "human_review_required": True,
        "candidates": {},
    }
    rejected: dict[str, list[str]] = {}
    for row in candidate_rows:
        symbol = str(row.get("symbol") or "").upper()
        if not symbol:
            continue
        reasons = _rejections(row)
        if reasons:
            rejected[symbol] = reasons
            continue
        params = dict(row["params"])
        normal_risk = float(params.get("risk_per_trade_pct", params.get("risk_pct", 0.25)))
        max_trades = int(params.get("max_trades_per_day", 1))
        payload["candidates"][symbol] = {
            "candidate_status": "RESEARCH_APPROVED",
            "approved_until": approved_until,
            "asset_class": row.get("asset_class", "unknown"),
            "broker": row.get("broker", "vantage"),
            "timeframe": row.get("timeframe", "5m"),
            "params_hash": row["params_hash"],
            "allowed_sessions_utc": row.get("allowed_sessions_utc") or [{"name": "all", "start": 0, "end": 24}],
            "allowed_regimes": row.get("allowed_regimes") or ["CLEAN_TREND", "NORMAL_VOLATILITY"],
            "blocked_conditions": row.get("blocked_conditions") or ["NEWS_RISK", "HIGH_SPREAD", "RECENT_30D_DECAY"],
            "scores": row.get("scores", {}),
            "risk": {
                "normal_risk_per_trade_pct": normal_risk,
                "reduced_risk_per_trade_pct": round(normal_risk / 2.0, 6),
                "max_trades_per_day": max_trades,
            },
            "params": params,
        }
    return payload, rejected


def write_approved_candidates(
    candidate_rows: list[dict[str, Any]],
    *,
    output_path: Path = RESULTS_DIR / "approved_candidates.json",
    report_path: Path = Path("reports/approved_candidates_report.md"),
    generated_at: str | None = None,
) -> tuple[dict[str, Any], dict[str, list[str]]]:
    payload, rejected = build_approved_candidates(candidate_rows, generated_at=generated_at)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, indent=2))
    lines = ["# Approved Candidates Report", "", f"- Approved: {len(payload['candidates'])}", f"- Rejected: {len(rejected)}"]
    for symbol, reasons in rejected.items():
        lines.append(f"- {symbol}: {', '.join(reasons)}")
    report_path.write_text("\n".join(lines) + "\n")
    return payload, rejected


def cli(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Write research-approved candidates after all DEV-266 gates pass.")
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=RESULTS_DIR / "approved_candidates.json")
    args = parser.parse_args(argv)
    payload = json.loads(args.input.read_text())
    rows = payload.get("candidates", payload.get("results", payload))
    if isinstance(rows, dict):
        rows = list(rows.values())
    write_approved_candidates([row for row in rows if isinstance(row, dict)], output_path=args.output)


if __name__ == "__main__":
    cli()
