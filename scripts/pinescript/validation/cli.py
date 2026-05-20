from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from scripts.pinescript.validation.comparator import compare_zones
from scripts.pinescript.validation.fixtures import load_fixture
from scripts.pinescript.validation.models import Zone
from scripts.pinescript.validation.report import write_report


INPUT_ERROR_EXIT_CODE = 2


def _load_actual(path: Path) -> list[Zone]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if "zones" not in payload:
        raise ValueError("actual payload must include a 'zones' list")
    zones = payload["zones"]
    if not isinstance(zones, list):
        raise ValueError("actual payload field 'zones' must be a list")
    return [Zone.from_dict(item) for item in zones]


def compare_fixtures(args: argparse.Namespace) -> int:
    expected = load_fixture(Path(args.expected))
    try:
        actual_zones = _load_actual(Path(args.actual))
    except ValueError as exc:
        print(f"Input error: {exc}", file=sys.stderr)
        return INPUT_ERROR_EXIT_CODE
    result = compare_zones(
        expected.scenario,
        expected_zones=expected.zones,
        actual_zones=actual_zones,
    )
    report_path = write_report(Path(args.output_dir), result)
    summary = {
        "passed": result.passed,
        "report": str(report_path),
        "mismatches": [mismatch.to_dict() for mismatch in result.mismatches],
    }
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0 if result.passed else 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="TradingView S&D validation harness")
    subcommands = parser.add_subparsers(dest="command", required=True)
    compare = subcommands.add_parser("compare-fixtures")
    compare.add_argument("--expected", required=True)
    compare.add_argument("--actual", required=True)
    compare.add_argument("--output-dir", required=True)
    compare.set_defaults(func=compare_fixtures)
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
