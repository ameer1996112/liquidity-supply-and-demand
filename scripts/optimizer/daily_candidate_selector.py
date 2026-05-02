from __future__ import annotations

import argparse
import json
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

try:
    from .asset_classifier import classify_asset
    from .config import RESULTS_DIR
except ImportError:
    from scripts.optimizer.asset_classifier import classify_asset
    from scripts.optimizer.config import RESULTS_DIR

DECISIONS = {"TRADE_NORMAL_RISK", "TRADE_REDUCED_RISK", "WATCH_ONLY", "NO_TRADE"}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _symbols(*sources: dict[str, Any]) -> set[str]:
    result: set[str] = set()
    for source in sources:
        result.update(str(symbol).upper() for symbol in source)
    return result


def _regime_matches(candidate: dict[str, Any], snapshot: dict[str, Any]) -> tuple[bool, list[str]]:
    regimes = set(snapshot.get("regimes") or [])
    allowed = set(candidate.get("allowed_regimes") or regimes or ["UNKNOWN"])
    blocked = set(candidate.get("blocked_regimes") or [])
    reasons: list[str] = []
    if regimes & blocked:
        reasons.append(f"current regime {sorted(regimes & blocked)[0]} is blocked")
    if allowed and not regimes.intersection(allowed):
        reasons.append("current_regime_not_validated")
    return not reasons, reasons


def select_daily_candidates(
    *,
    robust_passed: dict[str, Any],
    broker_passed: dict[str, Any],
    walk_forward_passed: dict[str, Any],
    stability_passed: dict[str, Any],
    stress_passed: dict[str, Any],
    prop_profile_report: dict[str, Any],
    regime_snapshots: dict[str, Any],
    portfolio_allowed: list[str],
    prop_profile: dict[str, Any],
    manual_blocklist: list[str] | None = None,
    account_buffer_low: bool = False,
) -> dict[str, Any]:
    allowed_symbols: dict[str, Any] = {}
    blocked_symbols: dict[str, list[str]] = {}
    manual_blocked = {item.upper() for item in (manual_blocklist or [])}
    candidates = _symbols(robust_passed, broker_passed, walk_forward_passed, stability_passed, stress_passed)
    for symbol in sorted(candidates):
        reasons: list[str] = []
        conservative_reasons: list[str] = []
        for label, source in [
            ("robust filter", robust_passed),
            ("broker filter", broker_passed),
            ("walk-forward filter", walk_forward_passed),
            ("parameter stability filter", stability_passed),
            ("stress filter", stress_passed),
        ]:
            if symbol not in source:
                reasons.append(f"failed {label}")
        prop_row = prop_profile_report.get(symbol, {})
        if prop_row and prop_row.get("status") in {"watch_only", "WATCH_ONLY"}:
            conservative_reasons.append("prop simulation approximate")
        elif prop_row and prop_row.get("status") not in {None, "passed"}:
            reasons.append("failed prop profile simulation")
        if symbol not in {item.upper() for item in portfolio_allowed}:
            reasons.append("portfolio exposure unacceptable")
        if symbol in manual_blocked:
            reasons.append("manual_blocklist")
        snapshot = regime_snapshots.get(symbol, {})
        if snapshot:
            ok, regime_reasons = _regime_matches(robust_passed.get(symbol, {}), snapshot)
            if not ok:
                reasons.extend(regime_reasons)
        else:
            snapshot = {"regimes": ["UNKNOWN"], "confidence": 0.0}
            conservative_reasons.append("current regime is not validated")
        if account_buffer_low:
            reasons.append("prop account buffer too low")
        if reasons:
            blocked_symbols[symbol] = reasons
            continue
        risk = float(prop_profile.get("risk_per_trade_pct", 0.25) or 0.25)
        confidence = float(snapshot.get("confidence", 1.0) if snapshot else 1.0)
        allowed_symbols[symbol] = {
            "asset_class": classify_asset(symbol),
            "risk_per_trade_pct": risk if confidence >= 0.6 else max(risk / 2, 0.01),
            "max_trades_today": int(prop_profile.get("max_trades_per_day", 1) or 1),
            "reason": [
                "passed robust filter",
                "passed broker filter",
                "passed walk-forward filter",
                "passed parameter stability filter",
                "passed stress filter",
                "portfolio exposure acceptable",
            ] + conservative_reasons,
            "current_regime": snapshot.get("regimes", []),
            "regime_confidence": confidence,
            "conservative_reasons": conservative_reasons,
        }
    if not allowed_symbols:
        decision = "NO_TRADE"
    elif any(
        row.get("regime_confidence", 1.0) < 0.6
        or row.get("conservative_reasons")
        for row in allowed_symbols.values()
    ):
        decision = "WATCH_ONLY"
    else:
        decision = "TRADE_REDUCED_RISK" if len(allowed_symbols) < 2 else "TRADE_NORMAL_RISK"
    return {
        "schema_version": 1,
        "created_at": _now(),
        "source_files": [],
        "date": date.today().isoformat(),
        "prop_profile": prop_profile.get("name"),
        "status": "completed",
        "decision": decision,
        "allowed_symbols": allowed_symbols,
        "blocked_symbols": blocked_symbols,
        "rejection_reasons": blocked_symbols,
        "warnings": [],
    }


def write_outputs(decision: dict[str, Any], results_dir: Path = RESULTS_DIR) -> None:
    (results_dir / "daily_allowed_symbols.json").write_text(json.dumps({"schema_version": 1, "created_at": _now(), "symbols": decision["allowed_symbols"]}, indent=2))
    (results_dir / "daily_blocked_symbols.json").write_text(json.dumps({"schema_version": 1, "created_at": _now(), "rejection_reasons": decision["blocked_symbols"]}, indent=2))
    (results_dir / "daily_decision.json").write_text(json.dumps(decision, indent=2))
    if decision["decision"] == "NO_TRADE":
        (results_dir / "no_trade_report.json").write_text(json.dumps(decision, indent=2))


def _load(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    payload = json.loads(path.read_text())
    return payload.get("results", payload) if isinstance(payload, dict) else {}


def cli(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Select daily robust forward-test candidates.")
    parser.add_argument("--results-dir", default=str(RESULTS_DIR))
    parser.add_argument("--prop-profile-json", default="{}")
    args = parser.parse_args(argv)
    results_dir = Path(args.results_dir)
    decision = select_daily_candidates(
        robust_passed=_load(results_dir / "robust_passed.json"),
        broker_passed=_load(results_dir / "robust_broker_passed.json"),
        walk_forward_passed=_load(results_dir / "walk_forward_passed.json"),
        stability_passed=_load(results_dir / "parameter_stability_passed.json"),
        stress_passed=_load(results_dir / "stress_test_passed.json"),
        prop_profile_report=_load(results_dir / "prop_profile_report.json"),
        regime_snapshots=_load(results_dir / "regime_snapshots.json"),
        portfolio_allowed=list(_load(results_dir / "portfolio_allowed_symbols.json").get("symbols", [])),
        prop_profile=json.loads(args.prop_profile_json),
    )
    write_outputs(decision, results_dir)


if __name__ == "__main__":
    cli()
