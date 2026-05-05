from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    from .config import RESULTS_DIR
    from .discord_backtest_ingestor import DISCORD_SUMMARY_OUTPUT
    from .live_trade_log_ingestor import LIVE_SUMMARY_OUTPUT
except ImportError:
    from scripts.optimizer.config import RESULTS_DIR
    from scripts.optimizer.discord_backtest_ingestor import DISCORD_SUMMARY_OUTPUT
    from scripts.optimizer.live_trade_log_ingestor import LIVE_SUMMARY_OUTPUT


GAP_REPORT_OUTPUT = RESULTS_DIR / "backtest_live_gap_report.json"
GAP_MARKDOWN_OUTPUT = Path("reports/backtest_live_gap_report.md")

DEFAULT_THRESHOLDS = {
    "min_discord_backtest_trades": 30,
    "min_discord_backtest_pf": 1.20,
    "min_discord_avg_r": 0.25,
    "min_live_trades_for_confirmation": 30,
    "max_execution_failure_rate": 5.0,
    "max_staleness_rejection_rate": 10.0,
}

IMPLEMENTATION_GAP_CAUSES = [
    "pine_manual_mismatch",
    "execution_latency_slippage",
    "wrong_session_timezone",
    "wrong_entry_model_mapping",
    "bot_taking_lower_grade_setups",
    "missing_filters",
    "wrong_symbol_broker_feed",
    "trade_lifecycle_bug",
]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _as_float(value: Any) -> float:
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value or "0").strip().lower()
    if text in {"inf", "+inf", "infinity"}:
        return float("inf")
    try:
        return float(text)
    except ValueError:
        return 0.0


def _is_backtest_strong(metrics: dict[str, Any], thresholds: dict[str, float]) -> bool:
    return (
        int(metrics.get("trades", 0)) >= int(thresholds["min_discord_backtest_trades"])
        and _as_float(metrics.get("profit_factor_r")) >= float(thresholds["min_discord_backtest_pf"])
        and _as_float(metrics.get("avg_r")) >= float(thresholds["min_discord_avg_r"])
    )


def _is_live_strong(metrics: dict[str, Any], thresholds: dict[str, float]) -> bool:
    return (
        int(metrics.get("trades", 0)) >= int(thresholds["min_live_trades_for_confirmation"])
        and _as_float(metrics.get("profit_factor_r")) >= float(thresholds["min_discord_backtest_pf"])
        and _as_float(metrics.get("avg_r")) >= float(thresholds["min_discord_avg_r"])
    )


def _is_live_weak(metrics: dict[str, Any], thresholds: dict[str, float]) -> bool:
    return int(metrics.get("trades", 0)) >= int(thresholds["min_live_trades_for_confirmation"]) and not _is_live_strong(
        metrics,
        thresholds,
    )


def _expected_sessions_for_hours(hours: set[int]) -> set[str]:
    expected: set[str] = set()
    for hour in hours:
        if 7 <= hour <= 11:
            expected.add("LDN")
        elif 12 <= hour <= 16:
            expected.add("NY")
        elif 0 <= hour <= 6:
            expected.add("ASIA")
        else:
            expected.add("OFF")
    return expected


def _top_keys(group: dict[str, Any], *, min_trades: int = 1) -> set[str]:
    if not group:
        return set()
    max_trades = max(int(metrics.get("trades", metrics.get("signals", 0))) for metrics in group.values())
    floor = max(min_trades, int(max_trades * 0.5))
    return {str(key) for key, metrics in group.items() if int(metrics.get("trades", metrics.get("signals", 0))) >= floor}


def _strong_segment_keys(group: dict[str, Any], thresholds: dict[str, float]) -> list[str]:
    keys = [
        str(key)
        for key, metrics in group.items()
        if int(metrics.get("trades", 0)) >= int(thresholds["min_discord_backtest_trades"])
        and _as_float(metrics.get("profit_factor_r")) >= float(thresholds["min_discord_backtest_pf"])
        and _as_float(metrics.get("avg_r")) >= float(thresholds["min_discord_avg_r"])
    ]
    return sorted(keys)


def _detect_gaps(symbol: str, discord_summary: dict[str, Any], live_summary: dict[str, Any]) -> list[str]:
    gaps: list[str] = []
    discord_trades = [row for row in discord_summary.get("trades", []) if row.get("instrument") == symbol]
    live_trades = [row for row in live_summary.get("trades", []) if row.get("symbol") == symbol]

    backtest_hours = {int(row["hour"]) for row in discord_trades if row.get("hour") is not None}
    live_hours = {int(row["hour"]) for row in live_trades if row.get("hour") is not None}
    live_sessions = {str(row.get("session") or "").upper() for row in live_trades if row.get("session")}
    expected_sessions = _expected_sessions_for_hours(backtest_hours)
    if live_sessions and expected_sessions and live_sessions.isdisjoint(expected_sessions):
        gaps.append("session_timezone_mismatch")
    elif live_hours and backtest_hours and live_hours.isdisjoint(backtest_hours):
        gaps.append("session_hour_mismatch")

    backtest_models = {str(row.get("entry_model") or "").upper() for row in discord_trades if row.get("entry_model")}
    live_models = {str(row.get("entry_model") or "").upper() for row in live_trades if row.get("entry_model")}
    if backtest_models and live_models and live_models.isdisjoint(backtest_models):
        gaps.append("entry_model_mismatch")

    backtest_grades = {str(row.get("grade") or "").upper() for row in discord_trades if row.get("grade")}
    live_grades = {str(row.get("grade") or "").upper() for row in live_trades if row.get("grade")}
    if backtest_grades and live_grades and not live_grades.issubset(backtest_grades):
        gaps.append("grade_mix_mismatch")

    return gaps


def _health_failed(live_summary: dict[str, Any], thresholds: dict[str, float]) -> bool:
    return (
        _as_float(live_summary.get("execution_failure_rate_pct")) >= float(thresholds["max_execution_failure_rate"])
        or _as_float(live_summary.get("staleness_rejection_rate_pct")) >= float(thresholds["max_staleness_rejection_rate"])
    )


def _status_for_candidate(
    backtest_metrics: dict[str, Any],
    live_metrics: dict[str, Any] | None,
    live_summary: dict[str, Any],
    thresholds: dict[str, float],
) -> str:
    if int(backtest_metrics.get("trades", 0)) < int(thresholds["min_discord_backtest_trades"]):
        return "WATCH_ONLY"
    if not _is_backtest_strong(backtest_metrics, thresholds):
        return "REJECT_RESEARCH"
    if _health_failed(live_summary, thresholds):
        return "NO_TRADE_EXECUTION_HEALTH_FAILED"
    if not live_metrics or int(live_metrics.get("trades", 0)) == 0:
        return "WATCH_ONLY"
    if int(live_metrics.get("trades", 0)) < int(thresholds["min_live_trades_for_confirmation"]):
        return "WATCH_ONLY"
    if _is_live_strong(live_metrics, thresholds):
        return "CANDIDATE_FOR_SHADOW_FORWARD_TEST"
    if _is_live_weak(live_metrics, thresholds):
        return "IMPLEMENTATION_GAP"
    return "WATCH_ONLY"


def _global_status(candidate_statuses: list[str]) -> str:
    priority = [
        "NO_TRADE_EXECUTION_HEALTH_FAILED",
        "IMPLEMENTATION_GAP",
        "CANDIDATE_FOR_SHADOW_FORWARD_TEST",
        "WATCH_ONLY",
        "REJECT_RESEARCH",
    ]
    for status in priority:
        if status in candidate_statuses:
            return status
    return "WATCH_ONLY"


def analyze_backtest_live_gap(
    discord_summary: dict[str, Any],
    live_summary: dict[str, Any],
    *,
    thresholds: dict[str, float] | None = None,
    generated_at: str | None = None,
) -> dict[str, Any]:
    thresholds = {**DEFAULT_THRESHOLDS, **(thresholds or {})}
    generated_at = generated_at or _now()
    candidates: dict[str, Any] = {}

    live_by_symbol = live_summary.get("by_symbol", {})
    for symbol, backtest_metrics in sorted((discord_summary.get("by_instrument") or {}).items()):
        live_metrics = live_by_symbol.get(symbol)
        status = _status_for_candidate(backtest_metrics, live_metrics, live_summary, thresholds)
        detected_gaps = _detect_gaps(symbol, discord_summary, live_summary)
        possible_causes = IMPLEMENTATION_GAP_CAUSES if status in {"IMPLEMENTATION_GAP", "NO_TRADE_EXECUTION_HEALTH_FAILED"} else []
        if "session_timezone_mismatch" in detected_gaps and "wrong_session_timezone" not in possible_causes:
            possible_causes.append("wrong_session_timezone")
        if "entry_model_mismatch" in detected_gaps and "wrong_entry_model_mapping" not in possible_causes:
            possible_causes.append("wrong_entry_model_mapping")
        candidates[symbol] = {
            "status": status,
            "recommendation": "NO_LIVE_TRADING"
            if status in {"IMPLEMENTATION_GAP", "NO_TRADE_EXECUTION_HEALTH_FAILED", "REJECT_RESEARCH"}
            else "WATCH_ONLY",
            "discord_backtest": backtest_metrics,
            "bot_live": live_metrics or {},
            "detected_gaps": detected_gaps,
            "possible_causes": possible_causes,
        }

    report = {
        "schema_version": 1,
        "generated_at": generated_at,
        "thresholds": thresholds,
        "global_status": _global_status([row["status"] for row in candidates.values()]),
        "execution_health": {
            "execution_failures": live_summary.get("execution_failures", 0),
            "execution_failure_rate_pct": live_summary.get("execution_failure_rate_pct", 0.0),
            "stale_rejected_unexecuted": live_summary.get("stale_rejected_unexecuted", 0),
            "staleness_rejection_rate_pct": live_summary.get("staleness_rejection_rate_pct", 0.0),
            "status": "failed" if _health_failed(live_summary, thresholds) else "passed",
        },
        "comparison_dimensions": [
            "symbol/instrument",
            "session/hour",
            "entry model",
            "side",
            "grade",
            "RR distribution",
            "win rate",
            "profit factor",
            "average R",
            "sample size",
            "execution issues",
            "stale/rejected/unexecuted signals",
        ],
        "candidates": candidates,
        "top_backtest_segments": {
            "instruments": sorted(_top_keys(discord_summary.get("by_instrument", {}), min_trades=thresholds["min_discord_backtest_trades"])),
            "hours": sorted(_top_keys(discord_summary.get("by_hour", {}))),
            "entry_models": sorted(_top_keys(discord_summary.get("by_entry_model", {}))),
        },
        "strong_backtest_segments": {
            "instruments": _strong_segment_keys(discord_summary.get("by_instrument", {}), thresholds),
            "hours": _strong_segment_keys(discord_summary.get("by_hour", {}), thresholds),
            "entry_models": _strong_segment_keys(discord_summary.get("by_entry_model", {}), thresholds),
        },
    }
    return report


def render_markdown_report(report: dict[str, Any]) -> str:
    lines = [
        "# Backtest vs Live Gap Report",
        "",
        f"- Global status: {report['global_status']}",
        f"- Execution health: {report['execution_health']['status']}",
        f"- Execution failure rate: {report['execution_health']['execution_failure_rate_pct']}%",
        f"- Stale/rejected/unexecuted rate: {report['execution_health']['staleness_rejection_rate_pct']}%",
        "",
        "## Candidates",
    ]
    for symbol, row in report.get("candidates", {}).items():
        backtest = row.get("discord_backtest", {})
        live = row.get("bot_live", {})
        lines.extend(
            [
                "",
                f"### {symbol}",
                f"- Status: {row['status']}",
                f"- Recommendation: {row['recommendation']}",
                f"- Discord: {backtest.get('trades', 0)} trades, PF {backtest.get('profit_factor_r', 0)}, avg R {backtest.get('avg_r', 0)}",
                f"- Live bot: {live.get('trades', 0)} trades, PF {live.get('profit_factor_r', 0)}, avg R {live.get('avg_r', 0)}",
                f"- Detected gaps: {', '.join(row.get('detected_gaps') or ['none'])}",
                f"- Possible causes: {', '.join(row.get('possible_causes') or ['none'])}",
            ]
        )
    lines.extend(
        [
            "",
            "## Permission Stance",
            "",
            "No live trading is approved from this report. Strong Discord candidates remain watch-only until the bot confirms live execution health and performance.",
        ]
    )
    return "\n".join(lines) + "\n"


def write_backtest_live_gap_report(
    discord_summary_path: Path = DISCORD_SUMMARY_OUTPUT,
    live_summary_path: Path = LIVE_SUMMARY_OUTPUT,
    output_path: Path = GAP_REPORT_OUTPUT,
    markdown_path: Path = GAP_MARKDOWN_OUTPUT,
) -> dict[str, Any]:
    discord_summary = json.loads(discord_summary_path.read_text()) if discord_summary_path.exists() else {"by_instrument": {}}
    live_summary = json.loads(live_summary_path.read_text()) if live_summary_path.exists() else {"by_symbol": {}, "trades": []}
    report = analyze_backtest_live_gap(discord_summary, live_summary)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    markdown_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, indent=2))
    markdown_path.write_text(render_markdown_report(report))
    return report


def cli(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Compare Discord backtests with bot live trade behavior.")
    parser.add_argument("--discord-summary", type=Path, default=DISCORD_SUMMARY_OUTPUT)
    parser.add_argument("--live-summary", type=Path, default=LIVE_SUMMARY_OUTPUT)
    parser.add_argument("--output", type=Path, default=GAP_REPORT_OUTPUT)
    parser.add_argument("--markdown", type=Path, default=GAP_MARKDOWN_OUTPUT)
    args = parser.parse_args(argv)
    write_backtest_live_gap_report(args.discord_summary, args.live_summary, args.output, args.markdown)


if __name__ == "__main__":
    cli()
