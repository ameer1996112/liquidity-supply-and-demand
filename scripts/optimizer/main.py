#!/usr/bin/env python3
"""
main.py — Entry point for the TradingView Strategy Optimizer.

Usage:
    # Recommended — Bayesian optimization (finds true global best, ~9h for 33 pairs)
    python -m scripts.optimizer.main --bayesian

    # Custom trial count
    python -m scripts.optimizer.main --bayesian --n-trials 150

    # Single pair test (5 trials, quick smoke test)
    python -m scripts.optimizer.main --bayesian --pairs EURUSD --n-trials 5

    # Legacy modes (kept for backward compatibility)
    python -m scripts.optimizer.main --fast
    python -m scripts.optimizer.main --smart

    # Dry run (no browser)
    python -m scripts.optimizer.main --bayesian --dry-run

Or use the convenience wrapper:
    bash scripts/optimizer/run.sh [--bayesian] [--fast] [--smart] [--pairs EURUSD,XAUUSD]
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

from scripts.optimizer.config import (
    DEFAULT_PAIRS,
    PARAM_GRID_FULL,
    PARAM_GRID_FAST,
    PARAM_GRID_GOLD,
    PARAM_GRID_INDEX,
    RESULTS_DIR,
    CHECKPOINT_FILE,
    N_BAYESIAN_TRIALS,
    PROP_FIRM_MAX_DD_PCT,
    OPTUNA_SEARCH_SPACE,
    LIQ_DISTANCE_RANGES,
    parse_fixed_overrides,
)


# ─── Minimal dry-run helper (no playwright needed) ───────────────────────────

class _DryRunOptimizer:
    """Lightweight stand-in used only for --dry-run (no browser imports)."""

    def __init__(self, fast_mode: bool, smart_mode: bool, bayesian_mode: bool) -> None:
        self.fast_mode = fast_mode
        self.smart_mode = smart_mode
        self.bayesian_mode = bayesian_mode

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
        epilog="""
Examples:
  python -m scripts.optimizer.main --bayesian
  python -m scripts.optimizer.main --bayesian --pairs EURUSD,GBPUSD --n-trials 80
  python -m scripts.optimizer.main --smart --pairs XAUUSD
  python -m scripts.optimizer.main --bayesian --dry-run
        """,
    )

    # ── Mode flags ──
    mode_group = parser.add_mutually_exclusive_group()
    mode_group.add_argument(
        "--bayesian",
        action="store_true",
        help="[RECOMMENDED] Bayesian optimization via Optuna — finds true global best",
    )
    mode_group.add_argument(
        "--smart",
        action="store_true",
        help="Hill-climbing: one param at a time (~48 tests/pair, fast but local optima)",
    )
    mode_group.add_argument(
        "--fast",
        action="store_true",
        help="Fast grid search: reduced parameter grid",
    )

    # ── Pair selection ──
    parser.add_argument(
        "--pairs",
        type=str,
        help="Comma-separated list of pairs (default: all 33 pairs)",
    )

    # ── Bayesian options ──
    parser.add_argument(
        "--n-trials",
        type=int,
        default=N_BAYESIAN_TRIALS,
        help=f"Optuna trials per pair (default: {N_BAYESIAN_TRIALS}, bayesian mode only)",
    )
    parser.add_argument(
        "--dd-limit",
        type=float,
        default=PROP_FIRM_MAX_DD_PCT,
        help=f"Prop-firm max DD%% hard limit (default: {PROP_FIRM_MAX_DD_PCT}%%)",
    )
    parser.add_argument(
        "--backtest-range",
        choices=["30d", "90d", "365d", "all", "custom"],
        default="365d",
        help="TradingView backtest window preset or custom",
    )
    parser.add_argument(
        "--custom-start-date",
        type=str,
        help="Custom backtest start date (YYYY-MM-DD), required with --backtest-range custom",
    )
    parser.add_argument(
        "--custom-end-date",
        type=str,
        help="Custom backtest end date (YYYY-MM-DD), required with --backtest-range custom",
    )

    # ── Report ──
    parser.add_argument(
        "--no-report",
        action="store_true",
        help="Skip HTML report generation",
    )

    # ── Checkpoint ──
    parser.add_argument(
        "--reset",
        action="store_true",
        help="Delete checkpoint and restart from scratch",
    )

    # ── Dry run ──
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be tested without launching a browser",
    )

    parser.add_argument(
        "--fix",
        type=str,
        default="",
        help=(
            "Comma-separated key=value pairs to pin for every trial. "
            "e.g. --fix rr_mode=fixed_4.0  or  --fix rr_mode=fixed_3.0,use_break_even=True"
        ),
    )

    args = parser.parse_args()

    pairs = args.pairs.split(",") if args.pairs else DEFAULT_PAIRS
    pairs = [p.strip().upper() for p in pairs if p.strip()]

    # Reset checkpoint if requested
    if args.reset and CHECKPOINT_FILE.exists():
        CHECKPOINT_FILE.unlink()
        print(f"[checkpoint] Deleted {CHECKPOINT_FILE}")

    if args.dry_run:
        helper = _DryRunOptimizer(
            fast_mode=args.fast,
            smart_mode=args.smart,
            bayesian_mode=args.bayesian,
        )
        _dry_run(helper, pairs, args)
        return

    # ── Check optuna is installed if using bayesian mode ──
    if args.bayesian:
        try:
            import optuna  # noqa: F401
        except ImportError:
            print("\nERROR: optuna is not installed.")
            print("Install it with: pip install optuna")
            print("Or: source .venv/bin/activate && pip install optuna")
            sys.exit(1)

    fixed_overrides = parse_fixed_overrides(args.fix)
    if fixed_overrides:
        print(f"[main] Fixed params: {fixed_overrides}")

    from scripts.optimizer.optimizer import TradingViewOptimizer
    optimizer = TradingViewOptimizer(
        pairs=pairs,
        fast_mode=args.fast,
        smart_mode=args.smart,
        bayesian_mode=args.bayesian,
        n_trials=args.n_trials,
        dd_limit=args.dd_limit,
        generate_report=not args.no_report,
        fixed_overrides=fixed_overrides,
        backtest_range=args.backtest_range,
        custom_start_date=args.custom_start_date,
        custom_end_date=args.custom_end_date,
    )
    asyncio.run(optimizer.run())


def _dry_run(helper: _DryRunOptimizer, pairs: list[str], args) -> None:
    """Print what would be tested, then exit."""
    print(f"\nDRY RUN — Mode: {'bayesian' if args.bayesian else 'smart' if args.smart else 'fast' if args.fast else 'full-grid'}\n")

    if args.bayesian:
        # Bayesian: same search space for all pairs (liq_distance range differs)
        n_total = len(pairs) * args.n_trials
        est_seconds = n_total * 12  # ~12s per trial
        print(f"  Bayesian optimization:")
        print(f"    Pairs        : {len(pairs)}")
        print(f"    Trials/pair  : {args.n_trials}")
        print(f"    Total trials : {n_total}")
        print(f"    Params       : {len(OPTUNA_SEARCH_SPACE)} (all 16 tunable)")
        print(f"    DD limit     : {args.dd_limit}%")
        print()
        for p in pairs:
            sym = p.upper()
            if "XAU" in sym or "GOLD" in sym or "XAG" in sym:
                ac = "gold"
            elif any(x in sym for x in ["NAS", "US100", "US500", "US30"]):
                ac = "index"
            else:
                ac = "forex"
            liq = LIQ_DISTANCE_RANGES[ac]
            print(f"  {p:<12} asset_class={ac:<6} liq_range=[{liq['low']}, {liq['high']}]")
        print()
        est_hours = est_seconds / 3600
        est_mins = (est_seconds % 3600) / 60
        print(f"  Estimated time: ~{int(est_hours)}h {int(est_mins)}m")
    else:
        total_combos = 0
        for symbol in pairs:
            grid = helper.get_param_grid(symbol)
            combos = helper.generate_combinations(grid)
            total_combos += len(combos)
            print(f"  {symbol}: {len(combos)} combinations")
            for k, v in grid.items():
                print(f"      {k}: {v}")
            print()
        est_minutes = total_combos * 8 // 60
        print(f"  TOTAL : {total_combos} combinations across {len(pairs)} pairs")
        print(f"  Est.  : ~{est_minutes} minutes ({est_minutes // 60}h {est_minutes % 60}m)")

    print(f"\n  Results dir : {RESULTS_DIR}")
    print(f"  Checkpoint  : {CHECKPOINT_FILE}")


if __name__ == "__main__":
    main()
