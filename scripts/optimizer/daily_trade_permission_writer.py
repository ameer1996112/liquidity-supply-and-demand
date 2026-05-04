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

TRADE_NORMAL_RISK = "TRADE_NORMAL_RISK"
TRADE_REDUCED_RISK = "TRADE_REDUCED_RISK"
WATCH_ONLY = "WATCH_ONLY"
NO_TRADE = "NO_TRADE"
TRADEABLE = {TRADE_NORMAL_RISK, TRADE_REDUCED_RISK}


def _parse_time(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)


def _session_expiry(generated_at: str, session: dict[str, Any]) -> str:
    generated = _parse_time(generated_at)
    end_hour = int(float(session.get("end", 24)))
    end = generated.replace(hour=end_hour % 24, minute=0, second=0, microsecond=0)
    if end <= generated:
        end = end + timedelta(days=1)
    return end.isoformat().replace("+00:00", "Z")


def _first_session(candidate: dict[str, Any]) -> dict[str, Any]:
    sessions = candidate.get("allowed_sessions_utc")
    if isinstance(sessions, list) and sessions and isinstance(sessions[0], dict):
        return sessions[0]
    return {"name": "all", "start": 0, "end": 24}


def _decision_for_symbol(
    symbol: str,
    candidate: dict[str, Any],
    *,
    spread_state: dict[str, str],
    news_state: dict[str, str],
    account_state: dict[str, Any],
    regime_state: dict[str, str],
    decay_state: dict[str, str],
    execution_health: dict[str, Any],
) -> tuple[str, list[str]]:
    reasons = ["research approved"]
    if candidate.get("candidate_status") != "RESEARCH_APPROVED":
        return WATCH_ONLY, ["candidate_not_research_approved"]
    if str(news_state.get(symbol, "clear")) in {"blocked", "blackout", "active"}:
        return NO_TRADE, ["news_blackout_active"]
    if str(spread_state.get(symbol, "normal")) not in {"normal", "ok"}:
        return NO_TRADE, ["spread_not_acceptable"]
    if str(account_state.get("buffer_status", "safe")) not in {"safe", "ok"}:
        return NO_TRADE, ["account_buffer_not_safe"]
    if str(execution_health.get("status", "healthy")) not in {"healthy", "ok"}:
        return NO_TRADE, ["execution_health_bad"]
    if str(regime_state.get(symbol, "acceptable")) not in {"acceptable", "clean", "normal"}:
        return WATCH_ONLY, ["market_regime_not_allowed"]
    decay = str(decay_state.get(symbol, "fresh"))
    if decay in {"stale", "expired"}:
        return WATCH_ONLY, ["evidence_stale"]
    if decay in {"weak_recent_performance", "reduced_risk"}:
        return TRADE_REDUCED_RISK, reasons + ["recent performance weak"]
    return TRADE_NORMAL_RISK, reasons + ["session allowed", "spread normal", "account buffer safe", "regime acceptable"]


def build_daily_permissions(
    approved_candidates: dict[str, Any],
    *,
    account_profile: str,
    generated_at: str,
    spread_state: dict[str, str] | None = None,
    news_state: dict[str, str] | None = None,
    account_state: dict[str, Any] | None = None,
    regime_state: dict[str, str] | None = None,
    decay_state: dict[str, str] | None = None,
    execution_health: dict[str, Any] | None = None,
) -> dict[str, Any]:
    spread_state = spread_state or {}
    news_state = news_state or {}
    account_state = account_state or {"buffer_status": "safe"}
    regime_state = regime_state or {}
    decay_state = decay_state or {}
    execution_health = execution_health or {"status": "healthy"}
    permissions: dict[str, Any] = {}
    blocked: dict[str, list[str]] = {}
    watch_only: dict[str, list[str]] = {}

    for symbol, candidate in sorted((approved_candidates.get("candidates") or {}).items()):
        status, reasons = _decision_for_symbol(
            symbol,
            candidate,
            spread_state=spread_state,
            news_state=news_state,
            account_state=account_state,
            regime_state=regime_state,
            decay_state=decay_state,
            execution_health=execution_health,
        )
        if status == NO_TRADE:
            blocked[symbol] = reasons
            continue
        if status == WATCH_ONLY:
            watch_only[symbol] = reasons
            continue
        risk = candidate.get("risk", {})
        session = _first_session(candidate)
        permissions[symbol] = {
            "status": status,
            "risk_per_trade_pct": float(
                risk.get(
                    "normal_risk_per_trade_pct" if status == TRADE_NORMAL_RISK else "reduced_risk_per_trade_pct",
                    0.0,
                )
            ),
            "max_trades_today": int(risk.get("max_trades_per_day", 1)),
            "session_utc": {"start": session.get("start", 0), "end": session.get("end", 24)},
            "expires_at": _session_expiry(generated_at, session),
            "reasons": reasons,
        }

    global_decision = NO_TRADE
    statuses = {row["status"] for row in permissions.values()}
    if TRADE_NORMAL_RISK in statuses:
        global_decision = TRADE_NORMAL_RISK
    elif TRADE_REDUCED_RISK in statuses:
        global_decision = TRADE_REDUCED_RISK
    elif watch_only:
        global_decision = WATCH_ONLY
    return {
        "schema_version": 1,
        "generated_at": generated_at,
        "account_profile": account_profile,
        "global_decision": global_decision,
        "permissions": permissions,
        "blocked": blocked,
        "watch_only": watch_only,
    }


def write_daily_permissions(
    approved_candidates_path: Path = RESULTS_DIR / "approved_candidates.json",
    output_path: Path = RESULTS_DIR / "daily_trade_permissions.json",
    report_path: Path = Path("reports/daily_decision_report.md"),
    *,
    account_profile: str = "generic_cfd_safe",
    generated_at: str | None = None,
) -> dict[str, Any]:
    generated_at = generated_at or datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    approved = json.loads(approved_candidates_path.read_text()) if approved_candidates_path.exists() else {"candidates": {}}
    payload = build_daily_permissions(approved, account_profile=account_profile, generated_at=generated_at)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, indent=2))
    lines = ["# Daily Decision Report", "", f"- Global decision: {payload['global_decision']}"]
    for symbol, row in payload["permissions"].items():
        lines.append(f"- {symbol}: {row['status']} at {row['risk_per_trade_pct']}%")
    for symbol, reasons in payload["blocked"].items():
        lines.append(f"- {symbol}: blocked ({', '.join(reasons)})")
    report_path.write_text("\n".join(lines) + "\n")
    return payload


def cli(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Write today's trading permissions from research-approved candidates.")
    parser.add_argument("--approved-candidates", type=Path, default=RESULTS_DIR / "approved_candidates.json")
    parser.add_argument("--output", type=Path, default=RESULTS_DIR / "daily_trade_permissions.json")
    parser.add_argument("--account-profile", default="generic_cfd_safe")
    args = parser.parse_args(argv)
    write_daily_permissions(args.approved_candidates, args.output, account_profile=args.account_profile)


if __name__ == "__main__":
    cli()
