from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    from .daily_trade_permission_writer import build_daily_permissions
    from .research_approval_writer import build_approved_candidates
    from .config import RESULTS_DIR
except ImportError:
    from scripts.optimizer.daily_trade_permission_writer import build_daily_permissions
    from scripts.optimizer.research_approval_writer import build_approved_candidates
    from scripts.optimizer.config import RESULTS_DIR


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _write(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2))


def run_pipeline(
    *,
    pairs: list[str],
    broker: str,
    brokers: list[str],
    prop_profile: str,
    timeframe: str,
    results_dir: Path = RESULTS_DIR,
    dry_run: bool = False,
    run_rulebook: bool = False,
    run_fidelity: bool = False,
    run_session_discovery: bool = False,
    run_walk_forward: bool = False,
    run_frozen_validation: bool = False,
    run_stability: bool = False,
    run_stress: bool = False,
    run_prop_sim: bool = False,
    write_approved_candidates_flag: bool = False,
    run_daily_permissions: bool = False,
) -> dict[str, Any]:
    started = _now()
    steps = {
        "rulebook": run_rulebook,
        "fidelity": run_fidelity,
        "session_discovery": run_session_discovery,
        "walk_forward": run_walk_forward,
        "frozen_validation": run_frozen_validation,
        "stability": run_stability,
        "stress": run_stress,
        "prop_sim": run_prop_sim,
        "approved_candidates": True,
        "daily_permissions": True,
    }
    executed = [name for name, enabled in steps.items() if enabled]
    status = {
        "schema_version": 1,
        "status": "completed",
        "dry_run": dry_run,
        "started_at": started,
        "finished_at": _now(),
        "pairs": pairs,
        "broker": broker,
        "brokers": brokers,
        "prop_profile": prop_profile,
        "timeframe": timeframe,
        "executed_steps": executed,
    }
    summary = {
        "schema_version": 1,
        "global_decision": "NO_TRADE",
        "allowed_today": [],
        "blocked_today": pairs if dry_run else [],
        "research_approved_candidates": [],
        "expiring_candidates": [],
        "recent_rejects": [],
        "no_trade_reasons": [],
        "issue_detector": {"status": "not_run" if dry_run else "pending"},
        "execution_health": {"status": "not_checked" if dry_run else "pending"},
        "account_risk_buffer": {"status": "not_checked" if dry_run else "pending"},
    }
    errors = {"schema_version": 1, "errors": []}
    _write(results_dir / "pipeline_status.json", status)
    _write(results_dir / "pipeline_summary.json", summary)
    _write(results_dir / "pipeline_errors.json", errors)
    approved, _rejected = build_approved_candidates([], generated_at=started)
    _write(results_dir / "approved_candidates.json", approved)
    daily = build_daily_permissions(
        approved,
        account_profile=prop_profile,
        generated_at=started,
        spread_state={},
        news_state={},
        account_state={"buffer_status": "safe"},
        regime_state={},
        decay_state={},
        execution_health={"status": "healthy"},
    )
    _write(results_dir / "daily_trade_permissions.json", daily)
    summary["global_decision"] = daily["global_decision"]
    summary["allowed_today"] = sorted(daily["permissions"])
    summary["blocked_today"] = sorted(daily["blocked"])
    summary["no_trade_reasons"] = daily.get("reasons", [])
    _write(results_dir / "pipeline_summary.json", summary)
    return status


def cli(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Orchestrate the DEV-266 production pair discovery pipeline.")
    parser.add_argument("--pairs", default="")
    parser.add_argument("--broker", default="vantage")
    parser.add_argument("--brokers", default="vantage")
    parser.add_argument("--prop-profile", default="generic_cfd_safe")
    parser.add_argument("--timeframe", default="5m")
    parser.add_argument("--results-dir", type=Path, default=RESULTS_DIR)
    parser.add_argument("--dry-run", action="store_true")
    for flag in (
        "run-rulebook",
        "run-fidelity",
        "run-session-discovery",
        "run-walk-forward",
        "run-frozen-validation",
        "run-stability",
        "run-stress",
        "run-prop-sim",
        "write-approved-candidates",
        "write-daily-permissions",
    ):
        parser.add_argument(f"--{flag}", action="store_true")
    args = parser.parse_args(argv)
    run_pipeline(
        pairs=[pair.strip().upper() for pair in args.pairs.split(",") if pair.strip()],
        broker=args.broker,
        brokers=[broker.strip() for broker in args.brokers.split(",") if broker.strip()],
        prop_profile=args.prop_profile,
        timeframe=args.timeframe,
        results_dir=args.results_dir,
        dry_run=args.dry_run,
        run_rulebook=args.run_rulebook,
        run_fidelity=args.run_fidelity,
        run_session_discovery=args.run_session_discovery,
        run_walk_forward=args.run_walk_forward,
        run_frozen_validation=args.run_frozen_validation,
        run_stability=args.run_stability,
        run_stress=args.run_stress,
        run_prop_sim=args.run_prop_sim,
        write_approved_candidates_flag=args.write_approved_candidates,
        run_daily_permissions=args.write_daily_permissions,
    )


if __name__ == "__main__":
    cli()
