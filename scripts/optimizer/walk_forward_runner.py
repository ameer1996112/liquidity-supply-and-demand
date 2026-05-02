from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from statistics import median
from typing import Any

try:
    from .config import RESULTS_DIR
    from .prop_profiles import load_prop_profile
except ImportError:
    from scripts.optimizer.config import RESULTS_DIR
    from scripts.optimizer.prop_profiles import load_prop_profile


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _num(row: dict[str, Any], key: str, default: float = 0.0) -> float:
    try:
        return float(row.get(key, default))
    except (TypeError, ValueError):
        return default


def is_catastrophic_fold(fold: dict[str, Any], profile: dict[str, Any]) -> bool:
    safe_dd = float(profile.get("safe_max_dd_pct") or 999.0)
    safe_daily = float(profile.get("safe_daily_loss_pct") or 999.0)
    return (
        _num(fold, "max_drawdown_pct") > safe_dd
        or _num(fold, "daily_loss_pct") > safe_daily
        or _num(fold, "profit_factor") < 0.90
        or _num(fold, "net_profit") < -abs(float(profile.get("max_loss_pct", 10.0)))
    )


def evaluate_walk_forward(symbol: str, folds: list[dict[str, Any]], profile: dict[str, Any]) -> dict[str, Any]:
    reasons: list[str] = []
    warnings: list[str] = []
    if not folds:
        return {
            "symbol": symbol,
            "status": "rejected",
            "fold_pass_rate": 0.0,
            "rejection_reasons": ["missing_folds"],
            "warnings": [],
        }
    passed_count = sum(1 for fold in folds if fold.get("status") == "passed")
    pass_rate = passed_count / len(folds)
    pfs = [_num(fold, "profit_factor") for fold in folds]
    nets = [_num(fold, "net_profit") for fold in folds]
    dds = [_num(fold, "max_drawdown_pct") for fold in folds]
    catastrophic = [index for index, fold in enumerate(folds, start=1) if is_catastrophic_fold(fold, profile)]
    if pass_rate < 0.60:
        reasons.append("fold_pass_rate_below_0.60")
    if catastrophic:
        reasons.append("catastrophic_fold")
    if folds[-1].get("status") != "passed":
        reasons.append("latest_fold_failed")
    if max(dds or [999.0]) > float(profile.get("safe_max_dd_pct") or 999.0):
        reasons.append("worst_validation_dd_above_profile_limit")
    if median(pfs or [0.0]) < 1.10:
        reasons.append("median_pf_below_1.10")
    if median(nets or [0.0]) <= 0:
        reasons.append("median_net_profit_not_positive")
    return {
        "symbol": symbol,
        "status": "rejected" if reasons else "passed",
        "fold_pass_rate": pass_rate,
        "median_pf": median(pfs or [0.0]),
        "median_net_profit": median(nets or [0.0]),
        "worst_validation_dd": max(dds or [0.0]),
        "catastrophic_folds": catastrophic,
        "folds": folds,
        "rejection_reasons": reasons,
        "warnings": warnings,
    }


def write_outputs(results: dict[str, dict[str, Any]], results_dir: Path = RESULTS_DIR, prop_profile: str | None = None) -> None:
    passed = {symbol: row for symbol, row in results.items() if row.get("status") == "passed"}
    rejected = {symbol: row for symbol, row in results.items() if row.get("status") != "passed"}
    base = {
        "schema_version": 1,
        "created_at": _now(),
        "source_files": [],
        "prop_profile": prop_profile,
        "warnings": [],
    }
    (results_dir / "walk_forward_results.json").write_text(json.dumps({**base, "status": "completed", "results": results}, indent=2))
    (results_dir / "walk_forward_passed.json").write_text(json.dumps({**base, "status": "completed", "results": passed}, indent=2))
    (results_dir / "walk_forward_rejected.json").write_text(json.dumps({**base, "status": "completed", "rejection_reasons": rejected}, indent=2))


def cli(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Evaluate rolling walk-forward optimizer folds.")
    parser.add_argument("--pairs", default="")
    parser.add_argument("--broker", default="vantage")
    parser.add_argument("--train-days", type=int, default=365)
    parser.add_argument("--validate-days", type=int, default=90)
    parser.add_argument("--step-days", type=int, default=30)
    parser.add_argument("--folds", type=int, default=8)
    parser.add_argument("--workers", type=int, default=1)
    parser.add_argument("--prop-profile", default="generic_cfd_safe")
    parser.add_argument("--fold-results")
    args = parser.parse_args(argv)
    profile = load_prop_profile(args.prop_profile)
    fold_payload = json.loads(Path(args.fold_results).read_text()) if args.fold_results else {}
    results = {
        symbol.strip().upper(): evaluate_walk_forward(symbol.strip().upper(), fold_payload.get(symbol.strip().upper(), []), profile)
        for symbol in args.pairs.split(",")
        if symbol.strip()
    }
    write_outputs(results, RESULTS_DIR, args.prop_profile)


if __name__ == "__main__":
    cli()
