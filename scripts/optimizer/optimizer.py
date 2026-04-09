"""
optimizer.py — TradingViewOptimizer: connects to Chrome, drives sequential
per-pair optimization with checkpoint/resume and 5-minute per-pair timeout.
"""

import asyncio
import csv
import json
import sys
import time
import traceback
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Optional

from .config import (
    RESULTS_DIR,
    CHECKPOINT_FILE,
    PARAM_GRID_FULL,
    PARAM_GRID_FAST,
    PARAM_GRID_GOLD,
    PARAM_GRID_INDEX,
    INPUT_INDEX,
)
from .models import BacktestResult
from .tab_worker import TabWorker

try:
    from playwright.async_api import async_playwright, Page, Browser
except ImportError:
    print("ERROR: playwright not installed. Run: pip3 install playwright")
    sys.exit(1)

_PAIR_TIMEOUT_SECS = 300  # 5-minute hard limit per pair


class TradingViewOptimizer:
    """Automates TradingView strategy backtesting via Playwright."""

    def __init__(
        self,
        pairs: list[str],
        param_grid: Optional[dict] = None,
        fast_mode: bool = False,
        smart_mode: bool = False,
    ):
        self.pairs = pairs
        self.fast_mode = fast_mode
        self.smart_mode = smart_mode
        self.results: list[BacktestResult] = []
        self.best_per_pair: dict[str, BacktestResult] = {}
        self.page: Optional[Page] = None
        self.browser: Optional[Browser] = None
        self.tv_pages: list[Page] = []

        # Select parameter grid based on mode
        if param_grid:
            self.default_param_grid = param_grid
        elif fast_mode:
            self.default_param_grid = PARAM_GRID_FAST
        else:
            self.default_param_grid = PARAM_GRID_FULL

    # ─────────────────────────────────── param helpers ───────────────────────

    def get_param_grid(self, symbol: str) -> dict:
        """Return the appropriate parameter grid for a symbol."""
        sym = symbol.upper()
        if "XAU" in sym or "GOLD" in sym:
            return (
                PARAM_GRID_GOLD
                if not self.fast_mode
                else {k: v[:3] for k, v in PARAM_GRID_GOLD.items()}
            )
        if any(idx in sym for idx in ["NAS", "US100", "US500", "US30", "SPX", "NDX"]):
            return (
                PARAM_GRID_INDEX
                if not self.fast_mode
                else {k: v[:3] for k, v in PARAM_GRID_INDEX.items()}
            )
        return self.default_param_grid

    def generate_combinations(self, param_grid: dict) -> list[dict]:
        """Generate all parameter combinations from the grid."""
        keys = list(param_grid.keys())
        values = list(param_grid.values())
        combos: list[dict] = []

        def _recurse(idx: int, current: dict) -> None:
            if idx == len(keys):
                combos.append(dict(current))
                return
            for val in values[idx]:
                current[keys[idx]] = val
                _recurse(idx + 1, current)

        _recurse(0, {})
        return combos

    # ─────────────────────────────────── checkpoint ──────────────────────────

    def _load_checkpoint(self) -> dict:
        """Load checkpoint.json if it exists; return empty structure otherwise."""
        if CHECKPOINT_FILE.exists():
            try:
                with open(CHECKPOINT_FILE) as f:
                    data = json.load(f)
                completed = data.get("completed", [])
                print(
                    f"[checkpoint] Resuming — {len(completed)} pairs already done: "
                    + ", ".join(completed)
                )
                return data
            except Exception as e:
                print(f"[checkpoint] Could not read checkpoint.json: {e}")
        return {"completed": [], "results": {}}

    def _save_checkpoint(self, checkpoint: dict, symbol: str, result: BacktestResult) -> None:
        """Append one completed pair to checkpoint.json immediately."""
        if symbol not in checkpoint["completed"]:
            checkpoint["completed"].append(symbol)
        checkpoint["results"][symbol] = {
            "params": result.params,
            "metrics": {
                "net_profit": result.net_profit,
                "total_trades": result.total_trades,
                "win_rate": result.win_rate,
                "profit_factor": result.profit_factor,
                "max_drawdown_pct": result.max_drawdown_pct,
                "score": result.score,
            },
        }
        try:
            with open(CHECKPOINT_FILE, "w") as f:
                json.dump(checkpoint, f, indent=2)
        except Exception as e:
            print(f"[checkpoint] WARNING: could not write checkpoint: {e}")

    # ─────────────────────────────────── browser ─────────────────────────────

    async def connect_to_brave(self) -> None:
        """Connect to an already-running Chrome browser via CDP."""
        print("\n" + "=" * 70)
        print("TRADINGVIEW STRATEGY OPTIMIZER")
        print("=" * 70)
        print("\nConnecting to Chrome browser on port 9222...")
        print("Make sure you started Chrome with:")
        print('  open -a "Google Chrome" --args --remote-debugging-port=9222\n')

        self._pw = await async_playwright().start()

        try:
            self.browser = await self._pw.chromium.connect_over_cdp(
                "http://127.0.0.1:9222"
            )
            print("Connected to Chrome browser!")
        except Exception as e:
            print(f"\nERROR: Could not connect to Chrome browser: {e}")
            print("\nTo fix this:")
            print("1. Close all Chrome windows")
            print("2. Start Chrome with remote debugging:")
            print(
                '   open -a "Google Chrome" --args --remote-debugging-port=9222'
            )
            print("3. Open TradingView and load your chart with S&D Algo [Pro]")
            print("4. Run this script again")
            sys.exit(1)

        # Find ALL TradingView chart tabs
        self.tv_pages = []
        for context in self.browser.contexts:
            for page in context.pages:
                if "tradingview.com/chart" in page.url:
                    self.tv_pages.append(page)
                    print(f"  Found TradingView tab: {page.url}")

        if not self.tv_pages:
            print("\nERROR: No TradingView chart tabs found.")
            print("Please open TradingView chart tabs in Chrome with S&D Algo [Pro]")
            sys.exit(1)

        self.page = self.tv_pages[0]
        print(f"\nFound {len(self.tv_pages)} TradingView tab(s)")
        print("Ready to optimize!\n")

    # ─────────────────────────────────── main run loop ───────────────────────

    async def run(self) -> None:
        """Run the full optimization pipeline (sequential, with checkpoint & timeout)."""
        await self.connect_to_brave()

        # Load checkpoint — skip already-completed pairs
        checkpoint = self._load_checkpoint()
        completed_set = set(checkpoint.get("completed", []))

        pending = [p for p in self.pairs if p not in completed_set]
        skipped = len(self.pairs) - len(pending)
        if skipped:
            print(f"  Skipping {skipped} already-completed pair(s).\n")

        start_time = time.time()
        page = self.tv_pages[0]
        print(f"\nRunning {len(pending)} pairs sequentially on one tab...\n")

        for symbol in pending:
            print(f"\n--- Starting {symbol} (5 min timeout) ---")
            try:
                worker = TabWorker(page, self)
                coro = (
                    worker.optimize_pair_smart(symbol)
                    if self.smart_mode
                    else worker.optimize_pair(symbol)
                )
                result = await asyncio.wait_for(coro, timeout=_PAIR_TIMEOUT_SECS)

                if result:
                    self.best_per_pair[symbol] = result
                    self.results.extend(worker.results)
                    self._save_checkpoint(checkpoint, symbol, result)

            except asyncio.TimeoutError:
                print(
                    f"\n  WARNING: {symbol} hit the {_PAIR_TIMEOUT_SECS // 60}-minute "
                    "timeout — skipping."
                )
                continue
            except Exception as e:
                print(f"\n  ERROR optimizing {symbol}: {e}")
                traceback.print_exc()
                continue

        elapsed = time.time() - start_time
        minutes = int(elapsed // 60)
        seconds = int(elapsed % 60)

        # Persist CSV + Pine presets
        self.save_results()
        self.generate_pine_presets()

        print(f"\n{'=' * 60}")
        print("OPTIMIZATION COMPLETE")
        print(f"{'=' * 60}")
        print(f"Time elapsed: {minutes}m {seconds}s")
        print(f"Pairs optimized: {len(self.best_per_pair)}/{len(self.pairs)}")
        print(f"Total combinations tested: {len(self.results)}")
        print(f"\nResults saved to: {RESULTS_DIR}/")

        # ── Final leaderboard ranked by score descending ───────────────────
        if self.best_per_pair:
            ranked = sorted(
                self.best_per_pair.items(), key=lambda kv: kv[1].score, reverse=True
            )
            print(f"\n{'─' * 60}")
            print("FINAL LEADERBOARD (by score, best first)")
            print(f"{'─' * 60}")
            header = (
                f"  {'#':>3}  {'Symbol':<10} | {'PF':>5} | {'WR':>7} | "
                f"{'Trades':>6} | {'DD%':>5} | {'Score':>7}"
            )
            sep = "  " + "-" * (len(header) - 2)
            print(sep)
            print(header)
            print(sep)
            for rank, (sym, res) in enumerate(ranked, 1):
                print(
                    f"  {rank:>3}  {sym:<10} | "
                    f"{res.profit_factor:>5.2f} | "
                    f"{res.win_rate:>6.1f}% | "
                    f"{res.total_trades:>6} | "
                    f"{res.max_drawdown_pct:>4.1f}% | "
                    f"{res.score:>7.1f}"
                )
            print(sep)

    # ─────────────────────────────────── persistence ─────────────────────────

    def save_results(self) -> None:
        """Save all results to CSV."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        if self.results:
            all_results_file = RESULTS_DIR / f"all_results_{timestamp}.csv"
            fieldnames = [
                "symbol", "net_profit", "total_trades", "win_rate",
                "profit_factor", "max_drawdown", "max_drawdown_pct",
                "profitable_trades", "score", "timestamp",
            ]
            param_keys: set[str] = set()
            for r in self.results:
                param_keys.update(r.params.keys())
            fieldnames.extend(sorted(param_keys))

            with open(all_results_file, "w", newline="") as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
                for r in self.results:
                    row = {
                        "symbol": r.symbol,
                        "net_profit": r.net_profit,
                        "total_trades": r.total_trades,
                        "win_rate": r.win_rate,
                        "profit_factor": r.profit_factor,
                        "max_drawdown": r.max_drawdown,
                        "max_drawdown_pct": r.max_drawdown_pct,
                        "profitable_trades": r.profitable_trades,
                        "score": r.score,
                        "timestamp": r.timestamp,
                    }
                    row.update(r.params)
                    writer.writerow(row)
            print(f"\nAll results: {all_results_file}")

        best_file = RESULTS_DIR / f"best_settings_{timestamp}.json"
        best_data: dict = {}
        for sym, res in self.best_per_pair.items():
            best_data[sym] = {
                "params": res.params,
                "metrics": {
                    "net_profit": res.net_profit,
                    "total_trades": res.total_trades,
                    "win_rate": res.win_rate,
                    "profit_factor": res.profit_factor,
                    "max_drawdown_pct": res.max_drawdown_pct,
                    "score": res.score,
                },
            }
        with open(best_file, "w") as f:
            json.dump(best_data, f, indent=2)
        print(f"Best settings: {best_file}")

    def generate_pine_presets(self) -> None:
        """Generate Pine Script code for the best presets per asset class."""
        if not self.best_per_pair:
            return

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        preset_file = RESULTS_DIR / f"pine_presets_{timestamp}.pine"

        groups: dict[str, list] = {
            "Major USD": [], "Cross/Minor": [], "JPY Pairs": [],
            "Gold": [], "Indices": [], "Other": [],
        }
        for sym, res in self.best_per_pair.items():
            su = sym.upper()
            if "XAU" in su or "GOLD" in su:
                groups["Gold"].append((sym, res))
            elif any(idx in su for idx in ["NAS", "US100", "US500", "US30", "SPX"]):
                groups["Indices"].append((sym, res))
            elif "JPY" in su:
                groups["JPY Pairs"].append((sym, res))
            elif su in ["EURUSD", "GBPUSD", "AUDUSD", "NZDUSD", "USDCAD", "USDCHF"]:
                groups["Major USD"].append((sym, res))
            elif any(x in su for x in ["EUR", "GBP", "AUD", "NZD", "CAD", "CHF"]):
                groups["Cross/Minor"].append((sym, res))
            else:
                groups["Other"].append((sym, res))

        lines = [
            f"// === AUTO-GENERATED PRESETS ({datetime.now().strftime('%Y-%m-%d %H:%M')}) ===",
            "// Generated by scripts/optimizer/main.py",
            "// Timeframe: 5-minute | Scoring: PF * sqrt(trades) * (1 - DD%/100)",
            "//",
            '// Paste inside the \'if use_profile_defaults\' section,',
            '// after adding "Per-Asset-Class (Optimized)" to config_profile options.',
            "",
            '    if config_profile == "Per-Asset-Class (Optimized)"',
        ]

        for group_name, pairs in groups.items():
            if not pairs:
                continue

            avg_params: dict = {}
            for _, res in pairs:
                for k, v in res.params.items():
                    avg_params.setdefault(k, []).append(v)

            for k in list(avg_params.keys()):
                vals = avg_params[k]
                if isinstance(vals[0], str):
                    avg_params[k] = Counter(vals).most_common(1)[0][0]
                elif isinstance(vals[0], bool):
                    avg_params[k] = sum(vals) > len(vals) / 2
                elif isinstance(vals[0], int):
                    avg_params[k] = int(round(sum(vals) / len(vals)))
                else:
                    avg_params[k] = round(sum(vals) / len(vals), 1)

            avg_pf = sum(r.profit_factor for _, r in pairs) / len(pairs)
            avg_wr = sum(r.win_rate for _, r in pairs) / len(pairs)
            avg_trades = sum(r.total_trades for _, r in pairs) / len(pairs)
            pair_names = ", ".join(s for s, _ in pairs)

            lines += [
                "",
                f"        // {group_name}: {pair_names}",
                f"        // Avg PF={avg_pf:.2f} WR={avg_wr:.1f}% Trades={avg_trades:.0f}",
            ]

            if group_name == "Gold":
                lines.append("        if is_gold or is_xpt")
            elif group_name == "Indices":
                lines.append("        else if is_index")
            elif group_name == "JPY Pairs":
                lines.append("        else if is_jpy_pair")
            elif group_name == "Major USD":
                lines.append("        else if is_usd_quote or is_usd_base")
            else:
                lines.append(f"        else  // {group_name}")

            for param, val in avg_params.items():
                lines.append(f"            {param} := {val}")

        lines += [
            "",
            "        // Common settings for all Per-Asset-Class presets",
            "        require_major_liquidity := true",
            '        structure_mode := "Relaxed (Wicks)"',
            "        stop_loss_buffer_pips := 1.0",
        ]

        preset_code = "\n".join(lines)
        with open(preset_file, "w") as f:
            f.write(preset_code)
        print(f"Pine presets: {preset_file}")

        print(f"\n{'=' * 60}")
        print("GENERATED PINE PRESET CODE")
        print(f"{'=' * 60}")
        print(preset_code)
