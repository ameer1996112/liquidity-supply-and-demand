from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

try:
    from .asset_classifier import classify_asset
    from .audit_result import audit_result
    from .config import RESULTS_DIR
    from .prop_profiles import load_prop_profile, params_pass_prop_profile
    from .trade_count_anomaly import detect_trade_count_anomaly
except ImportError:  # Allows `python scripts/optimizer/robust_filter.py`.
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    from scripts.optimizer.asset_classifier import classify_asset
    from scripts.optimizer.audit_result import audit_result
    from scripts.optimizer.config import RESULTS_DIR
    from scripts.optimizer.prop_profiles import load_prop_profile, params_pass_prop_profile
    from scripts.optimizer.trade_count_anomaly import detect_trade_count_anomaly

WINDOWS = ("365d", "90d", "30d")
FILES = {
    "365d": RESULTS_DIR / "parallel_results_vantage_validate_365d.json",
    "90d": RESULTS_DIR / "parallel_results_vantage_validate_90d.json",
    "30d": RESULTS_DIR / "parallel_results_vantage_validate_30d.json",
}

RULES = {
    "365d": {
        "min_net_profit": 0.0,
        "min_pf": 1.20,
        "min_trades": 50,
        "max_dd": 6.5,
    },
    "90d": {
        "min_net_profit": 0.0,
        "min_pf": 1.10,
        "min_trades": 15,
        "max_dd": 4.0,
    },
    "30d": {
        "min_net_profit": 0.0,
        "min_pf": 1.05,
        "min_trades": 5,
        "max_dd": 2.5,
    },
}

OUTPUT_PASSED_FILE = RESULTS_DIR / "robust_passed.json"
OUTPUT_REJECTED_FILE = RESULTS_DIR / "robust_rejected.json"

DECISIONS = (
    "TRADE_NORMAL_RISK",
    "TRADE_REDUCED_RISK",
    "WATCH_ONLY",
    "NO_TRADE",
)


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


def metric(row: dict[str, Any], key: str) -> float | None:
    if key not in row or row[key] in (None, ""):
        return None
    try:
        return float(row[key])
    except (TypeError, ValueError):
        return None


def _metric_or_default(row: dict[str, Any], key: str, default: float) -> float:
    value = metric(row, key)
    return default if value is None else value


def _format_number(value: float) -> str:
    if float(value).is_integer():
        return str(int(value))
    return str(value)


def pass_window(row: dict[str, Any], window: str) -> tuple[bool, list[str]]:
    rules = RULES[window]
    reasons: list[str] = []
    status = row.get("status")
    net = metric(row, "net_profit")
    pf = metric(row, "profit_factor")
    dd = metric(row, "max_drawdown_pct")
    trades = metric(row, "total_trades")
    params = row.get("params")
    result_truth = row.get("result_truth")

    if status != "completed":
        reasons.append(f"status={status or 'missing'}")
    reasons.extend(audit_result(row)["issues"])
    if net is None:
        reasons.append("missing_net_profit")
    elif net <= float(rules["min_net_profit"]):
        reasons.append(
            f"net_profit={_format_number(net)} <= {_format_number(float(rules['min_net_profit']))}"
        )
    if pf is None:
        reasons.append("missing_profit_factor")
    elif pf < float(rules["min_pf"]):
        reasons.append(f"pf={pf} < {rules['min_pf']}")
    if trades is None:
        reasons.append("missing_total_trades")
    elif int(trades) < int(rules["min_trades"]):
        reasons.append(f"trades={int(trades)} < {rules['min_trades']}")
    if dd is None:
        reasons.append("missing_max_drawdown_pct")
    elif dd > float(rules["max_dd"]):
        reasons.append(f"dd={dd} > {rules['max_dd']}")
    if not isinstance(params, dict) or not params:
        reasons.append("missing_params")
    if not isinstance(result_truth, dict):
        reasons.append("missing_result_truth")
    else:
        truth_status = str(
            result_truth.get("status")
            or result_truth.get("trust_status")
            or ""
        )
        if truth_status not in {"trusted", "trusted_with_warnings"}:
            reasons.append(f"result_truth_{truth_status or 'missing'}")
    return len(reasons) == 0, reasons


def robust_score(rows_by_window: dict[str, dict[str, Any]]) -> float:
    scores: list[float] = []
    for row in rows_by_window.values():
        net = _metric_or_default(row, "net_profit", 0.0)
        pf = _metric_or_default(row, "profit_factor", 0.0)
        dd = max(_metric_or_default(row, "max_drawdown_pct", 999.0), 0.1)
        trades = max(_metric_or_default(row, "total_trades", 1.0), 1.0)

        score = 0.0
        score += (pf - 1.0) * 100.0
        score += min(net / 100.0, 50.0)
        score += min(trades / 10.0, 10.0)
        score -= dd * 2.0
        scores.append(score)
    return min(scores) if scores else 0.0


def _params_digest(params: dict[str, Any]) -> str:
    return json.dumps(params, sort_keys=True, separators=(",", ":"))


def _status_passed(rows: dict[str, dict[str, Any]], key: str) -> bool:
    return bool(rows) and all(row.get(key) == "passed" for row in rows.values())


def _proof_failures(symbol: str, rows: dict[str, dict[str, Any]]) -> list[str]:
    reasons: list[str] = []
    if not _status_passed(rows, "strategy_fidelity_status"):
        reasons.append("strategy_fidelity_failed")
    if not _status_passed(rows, "prop_profile_status"):
        reasons.append("prop_profile_failed")

    params = next((row.get("params") for row in rows.values() if isinstance(row.get("params"), dict)), {})
    profile_name = next(
        (
            str(row.get("prop_profile"))
            for row in rows.values()
            if row.get("prop_profile")
        ),
        "generic_cfd_safe",
    )
    if isinstance(params, dict) and params:
        try:
            ok, prop_reasons = params_pass_prop_profile(params, load_prop_profile(profile_name), symbol)
        except KeyError:
            ok, prop_reasons = False, [f"unknown_prop_profile:{profile_name}"]
        if not ok:
            reasons.extend(prop_reasons)
    return reasons


def decide_trade_action(candidates: list[dict[str, Any]]) -> str:
    if not candidates:
        return "NO_TRADE"
    best = candidates[0]
    if best.get("current_regime_status") == "mismatch":
        return "WATCH_ONLY"
    if best.get("risk_mode") == "reduced":
        return "TRADE_REDUCED_RISK"
    return "TRADE_NORMAL_RISK"


def evaluate_candidates(
    all_results: dict[str, dict[str, dict[str, Any]]],
) -> tuple[list[dict[str, Any]], dict[str, dict[str, list[str]]]]:
    symbols = sorted(set().union(*(set(results) for results in all_results.values())))
    passed: list[dict[str, Any]] = []
    rejected: dict[str, dict[str, list[str]]] = {}

    for symbol in symbols:
        failures: dict[str, list[str]] = {}
        rows: dict[str, dict[str, Any]] = {}
        param_digests: set[str] = set()

        for window in WINDOWS:
            row = all_results.get(window, {}).get(symbol)
            if row is None:
                failures[window] = ["missing_window"]
                continue

            rows[window] = row
            params = row.get("params")
            if isinstance(params, dict) and params:
                param_digests.add(_params_digest(params))

            ok, reasons = pass_window(row, window)
            if not ok:
                failures[window] = reasons

        if len(param_digests) > 1:
            failures.setdefault("params", []).append("params_mismatch")
        anomaly = detect_trade_count_anomaly(rows)
        if anomaly:
            failures.setdefault("trade_count_anomaly", []).append(str(anomaly["reason"]))
        proof_failures = _proof_failures(symbol, rows)
        if proof_failures:
            failures.setdefault("proof", []).extend(proof_failures)

        if failures:
            rejected[symbol] = failures
            continue

        passed.append(
            {
                "symbol": symbol,
                "asset_class": classify_asset(symbol),
                "robust_score": robust_score(rows),
                "params": rows["365d"].get("params", {}),
                "windows": {window: rows[window] for window in WINDOWS},
                "regime_performance": {},
                "allowed_regimes": [],
                "blocked_regimes": ["NEWS_RISK", "SPREAD_RISK"],
                "regime_attribution_status": "not_available",
                "strategy_fidelity_status": "passed",
                "prop_profile_status": "passed",
                "final_decision": "TRADE_NORMAL_RISK",
            }
        )

    passed.sort(key=lambda candidate: candidate["robust_score"], reverse=True)
    return passed, rejected


def _passed_payload(passed: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {
        candidate["symbol"]: {
            "asset_class": candidate["asset_class"],
            "robust_score": candidate["robust_score"],
            "params": candidate["params"],
            "windows": candidate["windows"],
            "regime_performance": candidate["regime_performance"],
            "allowed_regimes": candidate["allowed_regimes"],
            "blocked_regimes": candidate["blocked_regimes"],
            "regime_attribution_status": candidate["regime_attribution_status"],
            "strategy_fidelity_status": candidate["strategy_fidelity_status"],
            "prop_profile_status": candidate["prop_profile_status"],
            "final_decision": candidate["final_decision"],
        }
        for candidate in passed
    }


def _print_summary(
    passed: list[dict[str, Any]],
    rejected: dict[str, dict[str, list[str]]],
) -> None:
    print("\nROBUST PASSED:")
    for candidate in passed:
        windows = candidate["windows"]
        print(
            f"{candidate['symbol']:10s} score={candidate['robust_score']:.2f} "
            f"PF365={_metric_or_default(windows['365d'], 'profit_factor', 0.0):.2f} "
            f"PF90={_metric_or_default(windows['90d'], 'profit_factor', 0.0):.2f} "
            f"PF30={_metric_or_default(windows['30d'], 'profit_factor', 0.0):.2f} "
            f"DD365={_metric_or_default(windows['365d'], 'max_drawdown_pct', 0.0):.1f} "
            f"DD90={_metric_or_default(windows['90d'], 'max_drawdown_pct', 0.0):.1f} "
            f"DD30={_metric_or_default(windows['30d'], 'max_drawdown_pct', 0.0):.1f}"
        )

    print("\nREJECTED:")
    for symbol, failures in rejected.items():
        print(f"{symbol}:")
        for window, reasons in failures.items():
            print(f"  {window}: {', '.join(reasons)}")
    print(f"\nFINAL DECISION: {decide_trade_action(passed)}")


def main(
    files: dict[str, Path] | None = None,
    output_passed_path: Path = OUTPUT_PASSED_FILE,
    output_rejected_path: Path = OUTPUT_REJECTED_FILE,
) -> tuple[dict[str, dict[str, Any]], dict[str, dict[str, list[str]]]]:
    selected_files = files or FILES
    all_results = {
        window: load_results(path)
        for window, path in selected_files.items()
    }
    passed, rejected = evaluate_candidates(all_results)
    passed_payload = _passed_payload(passed)

    _print_summary(passed, rejected)

    output_passed_path.write_text(json.dumps(passed_payload, indent=2))
    output_rejected_path.write_text(json.dumps(rejected, indent=2))
    return passed_payload, rejected


def _path_from_arg(results_dir: Path, value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else results_dir / path


def cli(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Filter frozen optimizer validation windows.")
    parser.add_argument("--results-dir", default=str(RESULTS_DIR))
    parser.add_argument("--file-365d", default=FILES["365d"].name)
    parser.add_argument("--file-90d", default=FILES["90d"].name)
    parser.add_argument("--file-30d", default=FILES["30d"].name)
    parser.add_argument("--output-passed", default=OUTPUT_PASSED_FILE.name)
    parser.add_argument("--output-rejected", default=OUTPUT_REJECTED_FILE.name)
    args = parser.parse_args(argv)

    results_dir = Path(args.results_dir)
    files = {
        "365d": _path_from_arg(results_dir, args.file_365d),
        "90d": _path_from_arg(results_dir, args.file_90d),
        "30d": _path_from_arg(results_dir, args.file_30d),
    }
    main(
        files=files,
        output_passed_path=_path_from_arg(results_dir, args.output_passed),
        output_rejected_path=_path_from_arg(results_dir, args.output_rejected),
    )


if __name__ == "__main__":
    cli()
