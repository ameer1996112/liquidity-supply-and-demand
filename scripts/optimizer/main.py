#!/usr/bin/env python3
"""
main.py — Entry point for the TradingView Strategy Optimizer.

Usage:
    python -m scripts.optimizer.main [--pairs EURUSD,GBPJPY] [--fast] [--smart] [--dry-run]

Or use the convenience wrapper:
    bash scripts/optimizer/run.sh [--fast] [--smart] [--pairs EURUSD,XAUUSD]
"""

# Auto-activate venv if not already active
import os
import sys

if "_OPTIMIZER_VENV_ACTIVE" not in os.environ:
    VENV_PYTHON = os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "..", "..", "venv", "bin", "python3"
    )
    if os.path.exists(VENV_PYTHON):
        os.environ["_OPTIMIZER_VENV_ACTIVE"] = "1"
        os.execv(VENV_PYTHON, [VENV_PYTHON] + sys.argv)

print("Starting TradingView Strategy Optimizer...")

import argparse
import asyncio

from .config import (
    DEFAULT_PAIRS,
    PARAM_GRID_FULL,
    PARAM_GRID_FAST,
    PARAM_GRID_GOLD,
    PARAM_GRID_INDEX,
    RESULTS_DIR,
    CHECKPOINT_FILE,
)


# ─── Minimal dry-run helper (no playwright needed) ───────────────────────────

class _DryRunOptimizer:
    """Lightweight stand-in used only for --dry-run (no browser imports)."""

    def __init__(self, fast_mode: bool, smart_mode: bool) -> None:
        self.fast_mode = fast_mode
        self.smart_mode = smart_mode

    def get_param_grid(self, symbol: str) -> dict:
        sym = symbol.upper()
        if "XAU" in sym or "GOLD" in sym:
            grid = PARAM_GRID_GOLD
        elif any(x in sym for x in ["NAS", "US100", "US500", "US30", "SPX", "NDX"]):
            grid = PARAM_GRID_INDEX
        else:
            grid = PARAM_GRID_FAST if self.fast_mode else PARAM_GRID_FULL
        return {k: v[:3] for k, v in grid.items()} if self.fast_mode else grid

    def generate_combinations(self, param_grid: dict) -> list:
        keys, values = list(param_grid.keys()), list(param_grid.values())
        combos: list = []

        def _r(idx: int, cur: dict) -> None:
            if idx == len(keys):
                combos.append(dict(cur)); return
            for val in values[idx]:
                cur[keys[idx]] = val; _r(idx + 1, cur)

        _r(0, {}); return combos


# ─── Main ─────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description="TradingView Strategy Optimizer",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--pairs",
        type=str,
        help="Comma-separated list of pairs (default: all 33 pairs)",
    )
    parser.add_argument(
        "--fast",
        action="store_true",
        help="Fast mode: fewer combinations — grid search",
    )
    parser.add_argument(
        "--smart",
        action="store_true",
        help="Smart mode: hill-climbing, one param at a time (~48 tests/pair)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be tested without launching a browser",
    )
    args = parser.parse_args()

    pairs = args.pairs.split(",") if args.pairs else DEFAULT_PAIRS
    pairs = [p.strip().upper() for p in pairs if p.strip()]

    if args.dry_run:
        helper = _DryRunOptimizer(fast_mode=args.fast, smart_mode=args.smart)
        _dry_run(helper, pairs)
        return

    # Defer the playwright-dependent import until we actually need the browser
    from .optimizer import TradingViewOptimizer  # noqa: PLC0415
    optimizer = TradingViewOptimizer(
        pairs=pairs, fast_mode=args.fast, smart_mode=args.smart
    )
    asyncio.run(optimizer.run())


def _dry_run(helper: _DryRunOptimizer, pairs: list[str]) -> None:
    """Print parameter combinations that would be tested, then exit."""
    print(f"\nDRY RUN — Parameter combinations that would be tested:\n")
    total_combos = 0

    for symbol in pairs:
        grid = helper.get_param_grid(symbol)
        combos = helper.generate_combinations(grid)
        total_combos += len(combos)
        print(f"  {symbol}: {len(combos)} combinations")
        print(f"    Params: {list(grid.keys())}")
        for k, v in grid.items():
            print(f"      {k}: {v}")
        print()

    est_minutes = total_combos * 8 // 60
    print(f"  TOTAL : {total_combos} combinations across {len(pairs)} pairs")
    print(f"  Est.  : ~{est_minutes} minutes ({est_minutes // 60}h {est_minutes % 60}m)")
    print(f"\n  Results dir : {RESULTS_DIR}")
    print(f"  Checkpoint  : {CHECKPOINT_FILE}")
    print(f"  Smart mode  : {helper.smart_mode}")
    print(f"  Fast mode   : {helper.fast_mode}")


if __name__ == "__main__":
    main()
