from __future__ import annotations

import json
from pathlib import Path
from typing import Any

try:
    from .config import RESULTS_DIR
except ImportError:  # Allows `python scripts/optimizer/robust_filter.py`.
    from scripts.optimizer.config import RESULTS_DIR

FILES = {
    "365d": RESULTS_DIR / "parallel_results_vantage_oos_365.json",
    "90d": RESULTS_DIR / "parallel_results_vantage_latest_90d.json",
    "30d": RESULTS_DIR / "parallel_results_vantage_latest_30d.json",
}

RULES = {
    "365d": {"min_pf": 1.20, "min_trades": 50, "max_dd": 6.5},
    "90d": {"min_pf": 1.10, "min_trades": 15, "max_dd": 4.0},
    "30d": {"min_pf": 1.05, "min_trades": 5, "max_dd": 2.5},
}

OUTPUT_FILE = RESULTS_DIR / "robust_passed.json"


def load_results(path: Path) -> dict[str, dict[str, Any]]:
    if not path.exists():
        raise FileNotFoundError(path)
    payload = json.loads(path.read_text())
    raw_results = payload.get("results") if isinstance(payload, dict) else None
    if raw_results is None and isinstance(payload, dict):
        raw_results = {
            symbol: data
            for symbol, data in payload.items()
            if isinstance(data, dict) and (
                "params" in data or "status" in data or "profit_factor" in data
            )
        }
    if not isinstance(raw_results, dict):
        return {}
    return {
        str(symbol).upper(): data
        for symbol, data in raw_results.items()
        if isinstance(data, dict)
    }


def metric(row: dict[str, Any], key: str, default: float = 0.0) -> float:
    try:
        return float(row.get(key, default) or default)
    except (TypeError, ValueError):
        return default


def pass_window(row: dict[str, Any], window: str) -> tuple[bool, list[str]]:
    rules = RULES[window]
    reasons: list[str] = []
    net = metric(row, "net_profit")
    pf = metric(row, "profit_factor")
    dd = metric(row, "max_drawdown_pct", 999.0)
    trades = int(metric(row, "total_trades"))

    if row.get("status") != "completed":
        reasons.append("not_completed")
    if net <= 0:
        reasons.append(f"net_profit={net}")
    if pf < rules["min_pf"]:
        reasons.append(f"pf={pf} < {rules['min_pf']}")
    if trades < rules["min_trades"]:
        reasons.append(f"trades={trades} < {rules['min_trades']}")
    if dd > rules["max_dd"]:
        reasons.append(f"dd={dd} > {rules['max_dd']}")
    return len(reasons) == 0, reasons


def robust_score(rows_by_window: dict[str, dict[str, Any]]) -> float:
    scores: list[float] = []
    for row in rows_by_window.values():
        net = metric(row, "net_profit")
        pf = metric(row, "profit_factor")
        dd = max(metric(row, "max_drawdown_pct", 999.0), 0.1)
        trades = max(metric(row, "total_trades"), 1.0)
        score = (pf - 1.0) * 100.0
        score += min(net / 100.0, 50.0)
        score += min(trades / 10.0, 10.0)
        score -= dd * 2.0
        scores.append(score)
    return min(scores) if scores else 0.0


def evaluate_candidates(
    all_results: dict[str, dict[str, dict[str, Any]]],
) -> tuple[list[dict[str, Any]], dict[str, dict[str, list[str]]]]:
    symbols = sorted(set().union(*(set(results) for results in all_results.values())))
    passed: list[dict[str, Any]] = []
    rejected: dict[str, dict[str, list[str]]] = {}

    for symbol in symbols:
        failures: dict[str, list[str]] = {}
        rows: dict[str, dict[str, Any]] = {}
        for window in FILES:
            row = all_results.get(window, {}).get(symbol)
            if row is None:
                failures[window] = ["missing_window"]
                continue
            rows[window] = row
            ok, reasons = pass_window(row, window)
            if not ok:
                failures[window] = reasons

        if failures:
            rejected[symbol] = failures
            continue

        passed.append(
            {
                "symbol": symbol,
                "robust_score": robust_score(rows),
                "params": rows["365d"].get("params", {}),
            }
        )

    passed.sort(key=lambda candidate: candidate["robust_score"], reverse=True)
    return passed, rejected


def main(
    files: dict[str, Path] | None = None,
    output_path: Path = OUTPUT_FILE,
) -> None:
    selected_files = files or FILES
    all_results = {
        window: load_results(path)
        for window, path in selected_files.items()
    }
    passed, rejected = evaluate_candidates(all_results)

    print("\nROBUST PASSED:")
    for candidate in passed:
        print(f"{candidate['symbol']:10s} score={candidate['robust_score']:.2f}")

    print("\nREJECTED:")
    for symbol, failures in rejected.items():
        print(symbol, failures)

    output_path.write_text(
        json.dumps(
            {
                candidate["symbol"]: {
                    "robust_score": candidate["robust_score"],
                    "params": candidate["params"],
                }
                for candidate in passed
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
