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


def _window_score(row: dict[str, Any]) -> float:
    pf = _num(row, "profit_factor")
    net = _num(row, "net_profit")
    dd = _num(row, "max_drawdown_pct", 999.0)
    trades = _num(row, "total_trades")
    return (pf - 1.0) * 100.0 + min(net / 100.0, 40.0) + min(trades / 10.0, 12.0) - dd * 3.0


def score_candidate(
    symbol: str,
    *,
    windows: dict[str, dict[str, Any]],
    broker_agreement: bool = False,
    walk_forward_pass_rate: float = 0.0,
    stability_score: float = 0.0,
    stress_passed: bool = False,
    forward_test_quality: float = 0.0,
    portfolio_fit: bool = True,
) -> dict[str, Any]:
    window_scores = {name: _window_score(row) for name, row in windows.items()}
    final_score = min(window_scores.values()) if window_scores else 0.0
    penalties: list[str] = []
    bonuses: list[str] = []
    if broker_agreement:
        final_score += 5.0
        bonuses.append("broker_agreement")
    final_score += walk_forward_pass_rate * 5.0
    final_score += stability_score * 5.0
    if stress_passed:
        final_score += 5.0
        bonuses.append("stress_survival")
    final_score += forward_test_quality * 5.0
    if not portfolio_fit:
        final_score -= 10.0
        penalties.append("correlation_penalty")
    recent = windows.get("30d", {})
    if _num(recent, "profit_factor") < 1.05 or _num(recent, "net_profit") <= 0:
        final_score -= 20.0
        penalties.append("weak_recent_30d")
    if _num(recent, "total_trades") < 5:
        final_score -= 8.0
        penalties.append("low_sample_penalty")
    if _num(recent, "max_drawdown_pct") > 2.5:
        final_score -= 8.0
        penalties.append("recent_drawdown_penalty")
    return {
        "symbol": symbol,
        "final_score": final_score,
        "window_scores": window_scores,
        "bonuses": bonuses,
        "penalties": penalties,
    }


def write_outputs(scores: dict[str, dict[str, Any]], results_dir: Path = RESULTS_DIR) -> None:
    ranking = dict(sorted(scores.items(), key=lambda item: item[1].get("final_score", 0.0), reverse=True))
    base = {"schema_version": 1, "created_at": _now(), "source_files": [], "prop_profile": None, "status": "completed", "warnings": []}
    (results_dir / "candidate_scores.json").write_text(json.dumps({**base, "results": scores}, indent=2))
    (results_dir / "candidate_ranking.json").write_text(json.dumps({**base, "results": ranking}, indent=2))


def cli(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Score robust optimizer candidates with weakest-window logic.")
    parser.add_argument("--input", required=True)
    args = parser.parse_args(argv)
    payload = json.loads(Path(args.input).read_text())
    rows = payload.get("results", payload)
    scores = {symbol: score_candidate(symbol, windows=row.get("windows", {})) for symbol, row in rows.items() if isinstance(row, dict)}
    write_outputs(scores)


if __name__ == "__main__":
    cli()
