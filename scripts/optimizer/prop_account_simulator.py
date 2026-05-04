from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    from .config import RESULTS_DIR
    from .prop_profiles import load_prop_profile, params_pass_prop_profile
except ImportError:
    from scripts.optimizer.config import RESULTS_DIR
    from scripts.optimizer.prop_profiles import load_prop_profile, params_pass_prop_profile


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _num(row: dict[str, Any], key: str, default: float = 0.0) -> float:
    try:
        return float(row.get(key, default))
    except (TypeError, ValueError):
        return default


def simulate_prop_account(
    symbol: str,
    params: dict[str, Any],
    metrics: dict[str, Any],
    profile: dict[str, Any],
    profile_name: str,
    trades: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    breaches: list[str] = []
    warnings: list[str] = []
    profile_params = dict(params)
    if profile.get("asset_type") == "futures":
        profile_params.setdefault("estimated_max_loss_usd", _num(metrics, "max_drawdown", _num(metrics, "max_loss_usd")))
        profile_params.setdefault("estimated_daily_loss_usd", _num(metrics, "max_daily_loss_usd"))
    params_ok, param_reasons = params_pass_prop_profile(profile_params, profile, symbol)
    if not params_ok:
        breaches.extend(param_reasons)
    if profile.get("asset_type") == "futures":
        if _num(metrics, "max_drawdown", _num(metrics, "max_loss_usd")) > float(profile.get("safe_max_loss_usd") or 0.0):
            breaches.append("max_loss_breach")
        if _num(metrics, "max_daily_loss_usd") > float(profile.get("safe_daily_loss_usd") or 0.0):
            breaches.append("daily_loss_breach")
    else:
        if _num(metrics, "max_daily_loss_pct") > float(profile.get("safe_daily_loss_pct") or 0.0):
            breaches.append("daily_loss_breach")
        if _num(metrics, "max_drawdown_pct") > float(profile.get("safe_max_dd_pct") or 0.0):
            breaches.append("max_loss_breach")
    max_dd_hit_rate_pct = min(100.0, max(0.0, (_num(metrics, "max_drawdown_pct") / max(float(profile.get("safe_max_dd_pct") or 1.0), 1.0)) * 25.0))
    daily_loss_breach_rate_pct = min(100.0, max(0.0, (_num(metrics, "max_daily_loss_pct") / max(float(profile.get("safe_daily_loss_pct") or 1.0), 1.0)) * 10.0))
    prop_survival_score_pct = max(0.0, min(100.0, 100.0 - max_dd_hit_rate_pct - daily_loss_breach_rate_pct - len(breaches) * 25.0))
    if trades is None:
        warnings.append("No trade-level data available, daily loss check approximated from metrics.")
    status = "rejected" if breaches else ("watch_only" if trades is None else "passed")
    risk = min(float(profile.get("risk_per_trade_pct", 0.25) or 0.25), _num(params, "risk_per_trade_pct", 0.25) or 0.25)
    return {
        "symbol": symbol,
        "prop_profile": profile_name,
        "profile": profile_name,
        "status": status,
        "simulation_precision": "trade_level" if trades else "approximate",
        "precision": "trade_level" if trades else "approximate",
        "prop_survival_score_pct": round(prop_survival_score_pct),
        "max_dd_hit_rate_pct": round(max_dd_hit_rate_pct),
        "daily_loss_breach_rate_pct": round(daily_loss_breach_rate_pct),
        "median_days_to_target": int(metrics.get("median_days_to_target", 0) or 0),
        "recommended_risk_per_trade_pct": risk,
        "risk_recommendation": {
            "risk_per_trade_pct": risk,
            "max_symbols_active": int(profile.get("max_symbols_active", 1) or 1),
        },
        "breaches": breaches,
        "warnings": warnings,
    }


def write_report(results: dict[str, dict[str, Any]], results_dir: Path = RESULTS_DIR, prop_profile: str | None = None) -> None:
    payload = {
        "schema_version": 1,
        "created_at": _now(),
        "source_files": [],
        "prop_profile": prop_profile,
        "status": "completed",
        "rejection_reasons": {k: v.get("breaches", []) for k, v in results.items() if v.get("status") != "passed"},
        "warnings": [warning for row in results.values() for warning in row.get("warnings", [])],
        "results": results,
    }
    (results_dir / "prop_profile_report.json").write_text(json.dumps(payload, indent=2))


def cli(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Simulate prop-account compatibility from optimizer metrics.")
    parser.add_argument("--input", required=True)
    parser.add_argument("--prop-profile", default="generic_cfd_safe")
    args = parser.parse_args(argv)
    profile = load_prop_profile(args.prop_profile)
    payload = json.loads(Path(args.input).read_text())
    results = {
        symbol: simulate_prop_account(symbol, row.get("params", {}), row, profile, args.prop_profile, row.get("trades"))
        for symbol, row in payload.items()
        if isinstance(row, dict)
    }
    write_report(results, RESULTS_DIR, args.prop_profile)


if __name__ == "__main__":
    cli()
