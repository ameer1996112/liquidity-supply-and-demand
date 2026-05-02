from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

try:
    from .config import RESULTS_DIR
except ImportError:  # Allows `python scripts/optimizer/robust_broker_filter.py`.
    from scripts.optimizer.config import RESULTS_DIR

DEFAULT_REQUIRED_BROKERS = ("vantage", "oanda", "fxcm")
OUTPUT_PASSED_FILE = RESULTS_DIR / "robust_broker_passed.json"
OUTPUT_REJECTED_FILE = RESULTS_DIR / "robust_broker_rejected.json"

BROKER_RULES = {
    "min_net_profit": 0.0,
    "min_pf": 1.05,
    "min_trades": 10,
    "max_dd": 5.0,
}
BROKER_RULES_365D = {
    "min_net_profit": 0.0,
    "min_pf": 1.10,
    "min_trades": 30,
    "max_dd": 6.5,
}


def load_results(path: Path) -> dict[str, dict[str, Any]]:
    if not path.exists():
        raise FileNotFoundError(path)
    payload = json.loads(path.read_text())
    raw_results = payload.get("results") if isinstance(payload, dict) else None
    if raw_results is None and isinstance(payload, dict):
        raw_results = payload
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


def broker_rules_for_range(backtest_range: str = "90d") -> dict[str, float]:
    return BROKER_RULES_365D if backtest_range == "365d" else BROKER_RULES


def pass_broker(
    row: dict[str, Any],
    *,
    rules: dict[str, float] | None = None,
) -> tuple[bool, list[str]]:
    selected_rules = rules or BROKER_RULES
    reasons: list[str] = []
    status = row.get("status")
    net = metric(row, "net_profit")
    pf = metric(row, "profit_factor")
    trades = metric(row, "total_trades")
    dd = metric(row, "max_drawdown_pct")

    if status != "completed":
        reasons.append(f"status={status or 'missing'}")
    if net is None:
        reasons.append("missing_net_profit")
    elif net <= float(selected_rules["min_net_profit"]):
        reasons.append(f"net_profit={net:g} <= {selected_rules['min_net_profit']:g}")
    if pf is None:
        reasons.append("missing_profit_factor")
    elif pf < float(selected_rules["min_pf"]):
        reasons.append(f"pf={pf} < {selected_rules['min_pf']}")
    if trades is None:
        reasons.append("missing_total_trades")
    elif int(trades) < int(selected_rules["min_trades"]):
        reasons.append(f"trades={int(trades)} < {int(selected_rules['min_trades'])}")
    if dd is None:
        reasons.append("missing_max_drawdown_pct")
    elif dd > float(selected_rules["max_dd"]):
        reasons.append(f"dd={dd} > {selected_rules['max_dd']}")
    return len(reasons) == 0, reasons


def evaluate_broker_candidates(
    results: dict[str, dict[str, Any]],
    *,
    required_brokers: list[str] | tuple[str, ...] = DEFAULT_REQUIRED_BROKERS,
    backtest_range: str = "90d",
) -> tuple[dict[str, dict[str, Any]], dict[str, dict[str, list[str]]]]:
    required = [broker.strip().lower() for broker in required_brokers if broker.strip()]
    rules = broker_rules_for_range(backtest_range)
    passed: dict[str, dict[str, Any]] = {}
    rejected: dict[str, dict[str, list[str]]] = {}

    for symbol, row in sorted(results.items()):
        brokers = row.get("brokers")
        failures: dict[str, list[str]] = {}
        if not isinstance(brokers, dict):
            rejected[symbol] = {"brokers": ["missing_brokers"]}
            continue

        for broker in required:
            broker_row = brokers.get(broker)
            if not isinstance(broker_row, dict):
                failures[broker] = ["missing_broker"]
                continue
            ok, reasons = pass_broker(broker_row, rules=rules)
            if not ok:
                failures[broker] = reasons

        if failures:
            rejected[symbol] = failures
            continue

        passed[symbol] = {
            "params": row.get("params", {}),
            "brokers": {broker: brokers[broker] for broker in required},
        }

    return passed, rejected


def _print_summary(
    passed: dict[str, dict[str, Any]],
    rejected: dict[str, dict[str, list[str]]],
) -> None:
    print("\nBROKER PASSED:")
    for symbol, row in passed.items():
        details = []
        for broker, metrics in row["brokers"].items():
            details.append(
                f"{broker}:PF={float(metrics.get('profit_factor', 0) or 0):.2f} "
                f"DD={float(metrics.get('max_drawdown_pct', 0) or 0):.1f}"
            )
        print(f"{symbol}: " + " ".join(details))

    print("\nBROKER REJECTED:")
    for symbol, failures in rejected.items():
        print(f"{symbol}:")
        for broker, reasons in failures.items():
            print(f"  {broker}: {', '.join(reasons)}")


def main(
    *,
    input_path: Path,
    output_passed_path: Path = OUTPUT_PASSED_FILE,
    output_rejected_path: Path = OUTPUT_REJECTED_FILE,
    required_brokers: list[str] | tuple[str, ...] = DEFAULT_REQUIRED_BROKERS,
    backtest_range: str = "90d",
) -> tuple[dict[str, dict[str, Any]], dict[str, dict[str, list[str]]]]:
    passed, rejected = evaluate_broker_candidates(
        load_results(input_path),
        required_brokers=required_brokers,
        backtest_range=backtest_range,
    )
    _print_summary(passed, rejected)
    output_passed_path.write_text(json.dumps(passed, indent=2))
    output_rejected_path.write_text(json.dumps(rejected, indent=2))
    return passed, rejected


def cli(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Filter multi-broker optimizer validation results.")
    parser.add_argument("--input", required=True)
    parser.add_argument("--brokers", default=",".join(DEFAULT_REQUIRED_BROKERS))
    parser.add_argument("--backtest-range", default="90d", choices=["30d", "90d", "365d", "custom"])
    parser.add_argument("--output-passed", default=str(OUTPUT_PASSED_FILE))
    parser.add_argument("--output-rejected", default=str(OUTPUT_REJECTED_FILE))
    args = parser.parse_args(argv)

    main(
        input_path=Path(args.input),
        output_passed_path=Path(args.output_passed),
        output_rejected_path=Path(args.output_rejected),
        required_brokers=[broker.strip() for broker in args.brokers.split(",")],
        backtest_range=args.backtest_range,
    )


if __name__ == "__main__":
    cli()
