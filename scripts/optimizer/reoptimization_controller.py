from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def should_reoptimize(candidate_state: dict[str, Any]) -> dict[str, Any]:
    reasons: list[str] = []
    verified = list(candidate_state.get("verified_decay_reasons") or [])
    if int(candidate_state.get("bad_day_count", 0) or 0) == 1:
        reasons.append("single_bad_day_ignored")
    if not verified:
        reasons.append("no_verified_decay")
        return {"symbol": candidate_state.get("symbol", ""), "decision": "do_not_reoptimize", "reasons": reasons}
    if len(verified) < 2 and candidate_state.get("state") not in {"PROBATION", "BLOCKED"}:
        reasons.append("insufficient_decay_confirmation")
        return {"symbol": candidate_state.get("symbol", ""), "decision": "do_not_reoptimize", "reasons": reasons + verified}
    return {"symbol": candidate_state.get("symbol", ""), "decision": "reoptimize", "reasons": verified}


def cli(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Decide whether verified decay warrants reoptimization.")
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    payload = json.loads(args.input.read_text())
    rows = payload.get("results", payload)
    results = {
        symbol: should_reoptimize({**row, "symbol": symbol})
        for symbol, row in rows.items()
        if isinstance(row, dict)
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps({"schema_version": 1, "results": results}, indent=2))


if __name__ == "__main__":
    cli()
