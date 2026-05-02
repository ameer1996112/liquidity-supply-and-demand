from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from statistics import median
from typing import Any

try:
    from .config import RESULTS_DIR
except ImportError:
    from scripts.optimizer.config import RESULTS_DIR


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def generate_neighbor_params(params: dict[str, Any], limit: int = 30) -> list[dict[str, Any]]:
    variants: list[dict[str, Any]] = []
    adjustments: dict[str, list[float | int]] = {
        "risk_reward_ratio": [-0.5, -0.2, 0.2, 0.5],
        "liq_entry_max_dist": [-0.10, 0.10],
        "max_bars_held": [-0.10, 0.10],
        "min_body_perc": [-5, 5],
        "stop_loss_buffer_pips": [-0.10, 0.10],
        "trading_start_hour": [-1, 1],
        "trading_end_hour": [-1, 1],
        "ai_quality_threshold": [-5, 5],
    }
    for key, deltas in adjustments.items():
        if key not in params:
            continue
        for delta in deltas:
            variant = dict(params)
            value = params[key]
            if isinstance(value, bool):
                continue
            if key in {"liq_entry_max_dist", "max_bars_held", "stop_loss_buffer_pips"}:
                variant[key] = type(value)(max(0, float(value) * (1 + float(delta))))
            else:
                variant[key] = type(value)(float(value) + float(delta))
            variants.append(variant)
            if len(variants) >= limit:
                return variants
    return variants


def _num(row: dict[str, Any], key: str, default: float = 0.0) -> float:
    try:
        return float(row.get(key, default))
    except (TypeError, ValueError):
        return default


def evaluate_stability(symbol: str, original: dict[str, Any], neighbor_results: list[dict[str, Any]]) -> dict[str, Any]:
    reasons: list[str] = []
    if not neighbor_results:
        reasons.append("missing_neighbor_results")
        return {"symbol": symbol, "status": "rejected", "stability_score": 0.0, "rejection_reasons": reasons, "warnings": []}
    profitable_rate = sum(1 for row in neighbor_results if _num(row, "net_profit") > 0) / len(neighbor_results)
    pf_pass_rate = sum(1 for row in neighbor_results if _num(row, "profit_factor") >= 1.05) / len(neighbor_results)
    pfs = [_num(row, "profit_factor") for row in neighbor_results]
    dds = [_num(row, "max_drawdown_pct") for row in neighbor_results]
    median_pf = median(pfs)
    median_dd = median(dds)
    original_dd = _num(original, "max_drawdown_pct")
    original_pf = _num(original, "profit_factor")
    if profitable_rate < 0.40:
        reasons.append("profitable_neighbor_rate_below_0.40")
    if pf_pass_rate < 0.30:
        reasons.append("pf_neighbor_rate_below_0.30")
    if median_pf < 1.05:
        reasons.append("median_neighbor_pf_below_1.05")
    if median_dd > original_dd + 1.5:
        reasons.append("median_neighbor_dd_above_original_plus_1.5")
    if original_pf > median_pf + 0.75 and pf_pass_rate < 0.50:
        reasons.append("best_result_is_extreme_outlier")
    return {
        "symbol": symbol,
        "status": "rejected" if reasons else "passed",
        "stability_score": min(profitable_rate, pf_pass_rate),
        "profitable_neighbor_rate": profitable_rate,
        "pf_neighbor_rate": pf_pass_rate,
        "median_neighbor_pf": median_pf,
        "median_neighbor_dd": median_dd,
        "rejection_reasons": reasons,
        "warnings": [],
    }


def write_outputs(results: dict[str, dict[str, Any]], results_dir: Path = RESULTS_DIR, prop_profile: str | None = None) -> None:
    base = {"schema_version": 1, "created_at": _now(), "source_files": [], "prop_profile": prop_profile, "warnings": []}
    passed = {k: v for k, v in results.items() if v.get("status") == "passed"}
    rejected = {k: v for k, v in results.items() if v.get("status") != "passed"}
    (results_dir / "parameter_stability_results.json").write_text(json.dumps({**base, "status": "completed", "results": results}, indent=2))
    (results_dir / "parameter_stability_passed.json").write_text(json.dumps({**base, "status": "completed", "results": passed}, indent=2))
    (results_dir / "parameter_stability_rejected.json").write_text(json.dumps({**base, "status": "completed", "rejection_reasons": rejected}, indent=2))


def cli(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Evaluate optimizer parameter-neighborhood stability.")
    parser.add_argument("--input", required=True)
    parser.add_argument("--prop-profile")
    args = parser.parse_args(argv)
    payload = json.loads(Path(args.input).read_text())
    results = {
        symbol: evaluate_stability(symbol, row.get("original", row), row.get("neighbor_results", []))
        for symbol, row in payload.items()
        if isinstance(row, dict)
    }
    write_outputs(results, RESULTS_DIR, args.prop_profile)


if __name__ == "__main__":
    cli()
