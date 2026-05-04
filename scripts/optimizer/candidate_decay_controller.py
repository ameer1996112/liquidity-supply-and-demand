from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def evaluate_candidate_decay(candidate: dict[str, Any]) -> dict[str, Any]:
    state = str(candidate.get("state") or "ACTIVE")
    reasons: list[str] = []
    decay_reasons: list[str] = []
    if int(candidate.get("bad_day_count", 0) or 0) == 1:
        reasons.append("one_bad_day_is_not_decay")
    if candidate.get("latest_30d_status") == "failed":
        decay_reasons.append("latest_30d_validation_failed")
    if candidate.get("latest_90d_status") in {"failed", "weak"}:
        decay_reasons.append("latest_90d_validation_weakened")
    if float(candidate.get("forward_pf", 99.0) or 99.0) < 1.0 and int(candidate.get("forward_trade_count", 0) or 0) >= 30:
        decay_reasons.append("forward_pf_below_1_after_30_trades")
    if candidate.get("regime_status") == "not_allowed":
        decay_reasons.append("current_market_regime_not_allowed")
    if candidate.get("execution_status") == "degraded":
        decay_reasons.append("execution_quality_degraded")
    if candidate.get("result_truth_status") == "stale":
        decay_reasons.append("result_truth_stale")
    reasons.extend(decay_reasons)
    new_state = state
    if len(decay_reasons) >= 2:
        new_state = "PROBATION"
    elif decay_reasons:
        new_state = "WATCH_ONLY"
    if "strategy_fidelity_failed" in decay_reasons:
        new_state = "BLOCKED"
    return {
        "symbol": candidate.get("symbol", ""),
        "old_state": state,
        "new_state": new_state,
        "verified_decay_reasons": decay_reasons,
        "reasons": reasons,
    }


def cli(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Evaluate research candidate decay without emotional reoptimization.")
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    payload = json.loads(args.input.read_text())
    rows = payload.get("candidates", payload)
    results = {
        symbol: evaluate_candidate_decay({**row, "symbol": symbol})
        for symbol, row in rows.items()
        if isinstance(row, dict)
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps({"schema_version": 1, "results": results}, indent=2))


if __name__ == "__main__":
    cli()
