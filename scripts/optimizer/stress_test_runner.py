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


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _num(row: dict[str, Any], key: str, default: float = 0.0) -> float:
    try:
        return float(row.get(key, default))
    except (TypeError, ValueError):
        return default


def evaluate_stress_tests(
    symbol: str,
    base_metrics: dict[str, Any],
    stress_metrics: dict[str, dict[str, Any]],
    profile: dict[str, Any],
    trade_list: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    reasons: list[str] = []
    warnings: list[str] = []
    for name, row in stress_metrics.items():
        if _num(row, "net_profit") <= 0:
            reasons.append(f"{name}_not_profitable")
        if _num(row, "profit_factor") < 1.0:
            reasons.append(f"{name}_pf_below_1.0")
        if _num(row, "max_drawdown_pct") > float(profile.get("safe_max_dd_pct") or 999.0):
            reasons.append(f"{name}_dd_breaches_profile")
    if not trade_list:
        warnings.append("trade_list_unavailable")
        warnings.append("no_trade_level_export")
        warnings.append("best_trade_best_day_monte_carlo_unavailable")
    status = "rejected" if reasons else ("watch_only" if not trade_list else "passed")
    return {
        "symbol": symbol,
        "status": status,
        "precision": "trade_level" if trade_list else "approximate",
        "reason": "no_trade_level_export" if not trade_list and not reasons else "",
        "base_metrics": base_metrics,
        "stress_metrics": stress_metrics,
        "rejection_reasons": reasons,
        "warnings": warnings,
    }


def write_outputs(results: dict[str, dict[str, Any]], results_dir: Path = RESULTS_DIR, prop_profile: str | None = None) -> None:
    base = {"schema_version": 1, "created_at": _now(), "source_files": [], "prop_profile": prop_profile, "warnings": []}
    passed = {k: v for k, v in results.items() if v.get("status") == "passed"}
    rejected = {k: v for k, v in results.items() if v.get("status") != "passed"}
    (results_dir / "stress_test_results.json").write_text(json.dumps({**base, "status": "completed", "results": results}, indent=2))
    (results_dir / "stress_test_passed.json").write_text(json.dumps({**base, "status": "completed", "results": passed}, indent=2))
    (results_dir / "stress_test_rejected.json").write_text(json.dumps({**base, "status": "completed", "rejection_reasons": rejected}, indent=2))


def cli(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Evaluate stress-test metrics for optimizer candidates.")
    parser.add_argument("--input", required=True)
    parser.add_argument("--prop-profile")
    args = parser.parse_args(argv)
    payload = json.loads(Path(args.input).read_text())
    results = {
        symbol: evaluate_stress_tests(symbol, row.get("base_metrics", row), row.get("stress_metrics", {}), row.get("profile", {}), row.get("trades"))
        for symbol, row in payload.items()
        if isinstance(row, dict)
    }
    write_outputs(results, RESULTS_DIR, args.prop_profile)


if __name__ == "__main__":
    cli()
