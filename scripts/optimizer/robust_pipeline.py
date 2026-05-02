from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    from .config import RESULTS_DIR
    from .daily_candidate_selector import select_daily_candidates, write_outputs as write_daily_outputs
    from .portfolio_filter import filter_portfolio, write_outputs as write_portfolio_outputs
    from .prop_profiles import load_prop_profile
except ImportError:
    from scripts.optimizer.config import RESULTS_DIR
    from scripts.optimizer.daily_candidate_selector import select_daily_candidates, write_outputs as write_daily_outputs
    from scripts.optimizer.portfolio_filter import filter_portfolio, write_outputs as write_portfolio_outputs
    from scripts.optimizer.prop_profiles import load_prop_profile


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _metadata(status: str, prop_profile: str | None, warnings: list[str] | None = None) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "created_at": _now(),
        "source_files": [],
        "prop_profile": prop_profile,
        "status": status,
        "rejection_reasons": {},
        "warnings": warnings or [],
    }


def _load_results(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    payload = json.loads(path.read_text())
    if isinstance(payload, dict):
        return payload.get("results", payload)
    return {}


def _write_reports(results_dir: Path, decision: dict[str, Any], portfolio_report: dict[str, Any], prop_profile_name: str) -> None:
    reports_dir = results_dir.parent.parent / "reports" if results_dir.name == "optimization_results" else results_dir / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    allowed = decision.get("allowed_symbols", {})
    blocked = decision.get("blocked_symbols", {})
    (reports_dir / "daily_decision.md").write_text(
        "\n".join(
            [
                f"# Daily Decision",
                "",
                f"Decision: {decision.get('decision')}",
                f"Prop profile: {prop_profile_name}",
                "",
                "## Allowed Symbols",
                *(f"- {symbol}: risk {row.get('risk_per_trade_pct')}%, max trades {row.get('max_trades_today')}" for symbol, row in allowed.items()),
                "",
                "## Blocked Symbols",
                *(f"- {symbol}: {', '.join(reasons)}" for symbol, reasons in blocked.items()),
                "",
            ]
        )
    )
    (reports_dir / "robust_candidates.md").write_text("# Robust Candidates\n\n" + ("\n".join(f"- {symbol}" for symbol in allowed) or "No candidates currently allowed.\n"))
    (reports_dir / "prop_profile_report.md").write_text(f"# Prop Profile Report\n\nProfile: {prop_profile_name}\n")
    (reports_dir / "portfolio_risk_report.md").write_text("# Portfolio Risk Report\n\n" + json.dumps(portfolio_report, indent=2))
    (reports_dir / "rejection_reasons.md").write_text("# Rejection Reasons\n\n" + json.dumps(blocked, indent=2))


def run_pipeline(
    *,
    pairs: list[str] | None = None,
    broker: str = "vantage",
    brokers: list[str] | None = None,
    prop_profile_name: str = "generic_cfd_safe",
    results_dir: Path = RESULTS_DIR,
    run_training: bool = False,
    run_validation: bool = False,
    run_broker_check: bool = False,
    run_walk_forward: bool = False,
    run_stability: bool = False,
    run_stress: bool = False,
    run_prop_sim: bool = False,
    run_selector: bool = False,
) -> dict[str, Any]:
    results_dir.mkdir(parents=True, exist_ok=True)
    profile = load_prop_profile(prop_profile_name)
    profile["name"] = prop_profile_name
    warnings: list[str] = []
    errors: dict[str, str] = {}
    stages: dict[str, str] = {}
    selected_pairs = [item.upper() for item in (pairs or [])]
    for enabled, stage in [
        (run_training, "training"),
        (run_validation, "validation"),
        (run_broker_check, "broker_check"),
        (run_walk_forward, "walk_forward"),
        (run_stability, "stability"),
        (run_stress, "stress"),
        (run_prop_sim, "prop_sim"),
    ]:
        if enabled:
            stages[stage] = "external_stage_not_run_by_orchestrator"
            warnings.append(f"{stage} requires existing TradingView/result inputs or a dedicated runner invocation")
    portfolio_allowed, portfolio_blocked, portfolio_report = filter_portfolio(selected_pairs, profile)
    write_portfolio_outputs(portfolio_allowed, portfolio_blocked, portfolio_report, results_dir)
    decision: dict[str, Any] = {
        **_metadata("completed", prop_profile_name),
        "decision": "NO_TRADE",
        "allowed_symbols": {},
        "blocked_symbols": {symbol: ["selector_not_run"] for symbol in selected_pairs},
    }
    if run_selector:
        robust_passed = _load_results(results_dir / "robust_passed.json")
        broker_passed = _load_results(results_dir / "robust_broker_passed.json")
        walk_forward_passed = _load_results(results_dir / "walk_forward_passed.json")
        stability_passed = _load_results(results_dir / "parameter_stability_passed.json")
        stress_passed = _load_results(results_dir / "stress_test_passed.json")
        prop_report = _load_results(results_dir / "prop_profile_report.json")
        regime_payload = _load_results(results_dir / "regime_snapshots.json")
        regime_snapshots = regime_payload.get("snapshots", regime_payload) if isinstance(regime_payload, dict) else {}
        decision = select_daily_candidates(
            robust_passed=robust_passed,
            broker_passed=broker_passed,
            walk_forward_passed=walk_forward_passed,
            stability_passed=stability_passed,
            stress_passed=stress_passed,
            prop_profile_report=prop_report,
            regime_snapshots=regime_snapshots,
            portfolio_allowed=portfolio_allowed,
            prop_profile=profile,
        )
        decision["prop_profile"] = prop_profile_name
        write_daily_outputs(decision, results_dir)
        stages["selector"] = "completed"
    else:
        (results_dir / "no_trade_report.json").write_text(json.dumps(decision, indent=2))
    robust_forward = {
        **_metadata("completed", prop_profile_name, warnings),
        "results": decision.get("allowed_symbols", {}),
    }
    (results_dir / "robust_forward_candidates.json").write_text(json.dumps(robust_forward, indent=2))
    pipeline_status = {
        **_metadata("completed", prop_profile_name, warnings),
        "broker": broker,
        "brokers": brokers or [],
        "stages": stages,
        "decision": decision.get("decision"),
    }
    status = "completed_with_no_trade" if decision.get("decision") == "NO_TRADE" else "completed"
    pipeline_status["status"] = status
    summary = {**pipeline_status, "allowed_symbols": list(decision.get("allowed_symbols", {})), "blocked_symbols": decision.get("blocked_symbols", {})}
    (results_dir / "pipeline_status.json").write_text(json.dumps(pipeline_status, indent=2))
    (results_dir / "pipeline_summary.json").write_text(json.dumps(summary, indent=2))
    (results_dir / "pipeline_errors.json").write_text(json.dumps({**_metadata("completed", prop_profile_name), "errors": errors}, indent=2))
    _write_reports(results_dir, decision, portfolio_report, prop_profile_name)
    return pipeline_status


def cli(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Orchestrate robust optimizer validation and daily selection.")
    parser.add_argument("--pairs", default="")
    parser.add_argument("--broker", default="vantage")
    parser.add_argument("--brokers", default="vantage,oanda,fxcm")
    parser.add_argument("--prop-profile", default="generic_cfd_safe")
    parser.add_argument("--workers", type=int, default=1)
    parser.add_argument("--train-start")
    parser.add_argument("--train-end")
    parser.add_argument("--run-training", action="store_true")
    parser.add_argument("--run-validation", action="store_true")
    parser.add_argument("--run-broker-check", action="store_true")
    parser.add_argument("--run-walk-forward", action="store_true")
    parser.add_argument("--run-stability", action="store_true")
    parser.add_argument("--run-stress", action="store_true")
    parser.add_argument("--run-prop-sim", action="store_true")
    parser.add_argument("--run-selector", action="store_true")
    parser.add_argument("--results-dir", default=str(RESULTS_DIR))
    args = parser.parse_args(argv)
    run_pipeline(
        pairs=[item for item in args.pairs.split(",") if item],
        broker=args.broker,
        brokers=[item for item in args.brokers.split(",") if item],
        prop_profile_name=args.prop_profile,
        results_dir=Path(args.results_dir),
        run_training=args.run_training,
        run_validation=args.run_validation,
        run_broker_check=args.run_broker_check,
        run_walk_forward=args.run_walk_forward,
        run_stability=args.run_stability,
        run_stress=args.run_stress,
        run_prop_sim=args.run_prop_sim,
        run_selector=args.run_selector,
    )


if __name__ == "__main__":
    cli()
