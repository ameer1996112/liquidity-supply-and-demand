from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

try:
    from .config import RESULTS_DIR
except ImportError:
    from scripts.optimizer.config import RESULTS_DIR


def build_frozen_validation_commands(
    *,
    pairs: str,
    broker: str,
    source_params_file: str,
    workers: int = 3,
) -> dict[str, list[str]]:
    base = [
        "python",
        "-m",
        "scripts.optimizer.parallel_runner",
        "--workers",
        str(workers),
        "--mode",
        "validate",
        "--broker",
        broker,
        "--pairs",
        pairs,
        "--source-params-file",
        source_params_file,
    ]
    return {
        "365d": base + [
            "--backtest-range",
            "custom",
            "--custom-start-date",
            "2025-05-01",
            "--custom-end-date",
            "2026-04-30",
            "--results-label",
            "validate_oos_365d",
            "--reset",
        ],
        "90d": base + ["--backtest-range", "90d", "--results-label", "validate_90d", "--reset"],
        "30d": base + ["--backtest-range", "30d", "--results-label", "validate_30d", "--reset"],
    }


def write_command_manifest(commands: dict[str, list[str]], output_path: Path = RESULTS_DIR / "frozen_validation_commands.json") -> dict[str, Any]:
    payload = {"schema_version": 1, "commands": commands}
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, indent=2))
    return payload


def cli(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Build frozen 365d/90d/30d validation commands for parallel_runner.")
    parser.add_argument("--pairs", required=True)
    parser.add_argument("--broker", default="vantage")
    parser.add_argument("--source-params-file", required=True)
    parser.add_argument("--workers", type=int, default=3)
    parser.add_argument("--output", type=Path, default=RESULTS_DIR / "frozen_validation_commands.json")
    args = parser.parse_args(argv)
    write_command_manifest(
        build_frozen_validation_commands(
            pairs=args.pairs,
            broker=args.broker,
            source_params_file=args.source_params_file,
            workers=args.workers,
        ),
        args.output,
    )


if __name__ == "__main__":
    cli()
