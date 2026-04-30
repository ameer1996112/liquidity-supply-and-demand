"""
optimizer.py — TradingViewOptimizer: connects to Chrome, drives sequential
per-pair optimization with checkpoint/resume.

Modes:
  default       Full grid search over PARAM_GRID_FULL / PARAM_GRID_GOLD / PARAM_GRID_INDEX
  --fast        Reduced grid (PARAM_GRID_FAST)
  --smart       Hill-climbing over HILL_CLIMB_PARAMS (optimize_pair_smart)
  --bayesian    Bayesian optimization via Optuna (optimize_pair_bayesian) [recommended]
"""

import asyncio
import csv
import hashlib
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
    N_BAYESIAN_TRIALS,
    N_STARTUP_TRIALS,
    OPTIMIZER_CONTEXT_PARAM_DEFAULTS,
    PROP_FIRM_MAX_DD_PCT,
)
from .models import BacktestResult
from .tab_worker import TabWorker, backtest_range_to_label, normalize_backtest_range
from src.services.optimizer_survival_scoring import classify_pair_result

try:
    from playwright.async_api import async_playwright, Page, Browser
except ImportError:
    print("ERROR: playwright not installed. Run: pip3 install playwright")
    sys.exit(1)

_PAIR_TIMEOUT_SECS = 600  # 10-minute hard limit per pair (increased for bayesian)
_DEFAULT_DAILY_DD_LIMIT_PCT = 4.0
_FINAL_REPLAY_TIMEOUT_SECS = 360


class TradingViewOptimizer:
    """Automates TradingView strategy backtesting via Playwright."""

    def __init__(
        self,
        pairs: list[str],
        broker: str = "vantage",
        param_grid: Optional[dict] = None,
        fast_mode: bool = False,
        smart_mode: bool = False,
        bayesian_mode: bool = False,
        n_trials: int = N_BAYESIAN_TRIALS,
        dd_limit: float = PROP_FIRM_MAX_DD_PCT,
        generate_report: bool = True,
        fixed_overrides: dict = None,
        backtest_range: str = "365d",
    ):
        self.pairs = pairs
        self.broker = broker
        self.fast_mode = fast_mode
        self.smart_mode = smart_mode
        self.bayesian_mode = bayesian_mode
        self.n_trials = n_trials
        self.dd_limit = dd_limit
        self.daily_dd_limit = _DEFAULT_DAILY_DD_LIMIT_PCT
        self.generate_report = generate_report
        self.fixed_overrides = fixed_overrides or {}
        self.backtest_range = normalize_backtest_range(backtest_range)
        self.backtest_range_label = backtest_range_to_label(self.backtest_range)
        self.results: list[BacktestResult] = []
        self.best_per_pair: dict[str, BacktestResult] = {}
        self.page: Optional[Page] = None
        self.browser: Optional[Browser] = None
        self.tv_pages: list[Page] = []
        self.runtime_state = None
        self.run_id: Optional[str] = None
        self.worker_id: Optional[int] = None

        # Select parameter grid based on mode (legacy grid/smart modes)
        if param_grid:
            self.default_param_grid = param_grid
        elif fast_mode:
            self.default_param_grid = PARAM_GRID_FAST
        else:
            self.default_param_grid = PARAM_GRID_FULL

    def _worker_log_tag(self) -> str:
        """Return a stable worker label for human-readable logs."""
        if self.worker_id is None:
            return "worker-?"
        return f"worker-{self.worker_id}"

    def _format_trial_log_line(
        self,
        *,
        symbol: str,
        trial_num: int,
        n_trials: int,
        eta: str,
        reason: str | None = None,
        result: Optional[BacktestResult] = None,
    ) -> str:
        """Build one atomic log line per trial so parallel workers do not interleave."""
        prefix = (
            f"  [{self._worker_log_tag()}][{symbol}] "
            f"Trial {trial_num:>3}/{n_trials}  ETA={eta}"
        )
        if result is None:
            detail = f"-> SKIP ({reason or 'unknown'})"
            return f"{prefix}  {detail}"

        pf = f"PF={result.profit_factor:.2f}" if result.profit_factor else "PF=N/A"
        dd = f"DD={result.max_drawdown_pct:.1f}%"
        compliant = "✅" if result.is_prop_firm_compliant(self.dd_limit) else "❌"
        return (
            f"{prefix}  {pf}  {dd}  T={result.total_trades}  "
            f"S={result.score:.2f}  {compliant}"
        )

    async def _require_worker_backtest_range(self, worker: TabWorker) -> None:
        """Use the generic range API when available and fall back for legacy shims."""
        if self.backtest_range == "custom":
            start_date = getattr(self, "custom_start_date", None)
            end_date = getattr(self, "custom_end_date", None)
            if not start_date or not end_date:
                raise RuntimeError("custom_start_date and custom_end_date are required")
            if hasattr(worker, "_require_custom_date_range"):
                await worker._require_custom_date_range(start_date, end_date)
                return
            raise RuntimeError("custom date range is not supported by this worker")
        if hasattr(worker, "_require_backtest_range"):
            await worker._require_backtest_range(self.backtest_range_label)
            return
        await worker._require_last_365_days()

    # ─────────────────────────────────── param helpers ───────────────────────

    def get_param_grid(self, symbol: str) -> dict:
        """Return the appropriate parameter grid for a symbol (legacy modes)."""
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
                combos.append({**OPTIMIZER_CONTEXT_PARAM_DEFAULTS, **current})
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
            "metrics": result.to_dict(),
        }
        try:
            with open(CHECKPOINT_FILE, "w") as f:
                json.dump(checkpoint, f, indent=2)
        except Exception as e:
            print(f"[checkpoint] WARNING: could not write checkpoint: {e}")

    def _apply_staged_survival_result(self, result: BacktestResult) -> BacktestResult:
        """Attach staged survival payloads to the final per-pair result."""
        forward_metrics = {
            "net_profit": result.net_profit,
            "profit_factor": result.profit_factor,
            "total_trades": result.total_trades,
            "max_drawdown_pct": result.max_drawdown_pct,
            "max_daily_loss_pct": float(
                result.params.get("max_daily_loss_pct", self.daily_dd_limit)
            ),
        }
        stress_results = list(result.stress_results)
        decision = classify_pair_result(
            forward_metrics=forward_metrics,
            stress_metrics=stress_results,
            pair_dd_limit=self.dd_limit,
            pair_daily_limit=self.daily_dd_limit,
        )
        risk_weight = (
            1.0
            if decision["status"] == "PASS"
            else 0.5 if decision["status"] == "REDUCE_RISK" else 0.0
        )

        result.forward_metrics = forward_metrics
        result.validation_metrics = {
            "prop_firm_compliant": result.is_prop_firm_compliant(self.dd_limit),
            "drawdown_source": result.drawdown_source,
            "verified_symbol": result.verified_symbol,
        }
        result.stress_results = stress_results
        result.decision = {
            "status": decision["status"],
            "reason": decision["reason"],
            "risk_weight": risk_weight,
        }
        return result

    # ─────────────────────────────────── browser ─────────────────────────────

    async def connect_to_brave(self) -> None:
        """Connect to an already-running Chrome browser via CDP."""
        print("\n" + "=" * 70)
        print("TRADINGVIEW STRATEGY OPTIMIZER")
        print("=" * 70)
        mode_label = (
            "BAYESIAN (Optuna)" if self.bayesian_mode
            else "SMART (hill-climb)" if self.smart_mode
            else "FAST grid" if self.fast_mode
            else "FULL grid"
        )
        print(f"Mode: {mode_label}")
        if self.bayesian_mode:
            print(f"Trials per pair: {self.n_trials}")
            print(f"Prop-firm DD limit: {self.dd_limit}%")
        print(f"Backtest range: {self.backtest_range_label}")
        print("\nConnecting to Chrome browser on port 9222...")

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

    # ─────────────────────────────────── bayesian optimization ───────────────

    async def optimize_pair_bayesian(
        self, worker: TabWorker, symbol: str, n_trials: int
    ) -> Optional[BacktestResult]:
        """
        Bayesian optimization using Optuna TPE (Tree-structured Parzen Estimator).

        Uses ask()/tell() API for async compatibility — each trial is run
        sequentially in the browser, results fed back to Optuna after each one.

        Phase 1 (trials 1–25): random exploration (Optuna's startup sampler)
        Phase 2 (trials 26–N): Bayesian exploitation of promising regions
        """
        try:
            import optuna
        except ImportError:
            print("ERROR: optuna not installed. Run: pip install optuna")
            sys.exit(1)

        optuna.logging.set_verbosity(optuna.logging.WARNING)

        study = optuna.create_study(
            direction="maximize",
            sampler=optuna.samplers.TPESampler(n_startup_trials=N_STARTUP_TRIALS, seed=42),
        )

        await worker._switch_symbol(symbol)

        print(f"\n[{symbol}] Bayesian optimization: {n_trials} trials")
        print(f"[{symbol}] Phase 1: random exploration (trials 1–25)")
        print(f"[{symbol}] Phase 2: Bayesian focus (trials 26–{n_trials})")
        if self.fixed_overrides:
            locked = ", ".join(f"{k}={v}" for k, v in self.fixed_overrides.items())
            print(f"[{symbol}] 🔒 Locked params: {locked}")
        print(f"[{symbol}] DD penalty: higher DD = lower score (✅ = profitable + DD≤{self.dd_limit}%)\n")


        best: Optional[BacktestResult] = None           # highest raw score (any DD)
        best_compliant: Optional[BacktestResult] = None  # highest score that passes DD limit
        start = time.time()

        # ── Always set backtest range (even if symbol didn't change) ───────────
        await self._require_worker_backtest_range(worker)
        if hasattr(worker, "_prepare_clean_chart"):
            await worker._prepare_clean_chart()

        # ── Reset risk to 0.5% before every pair ───────────────────────────────
        # Ensures TradingView isn't left at a different risk from a previous run.
        # 0.5% is the baseline for optimization (1% interacts badly with the
        # 4% daily loss limit, killing good trades and destroying backtest PF).
        if hasattr(worker, "_apply_baseline_risk_reset"):
            baseline_outcome = await worker._apply_baseline_risk_reset(0.5)
        else:
            baseline_outcome = await worker._apply_params({"risk_per_trade_pct": 0.5})
        if not baseline_outcome.fresh:
            print(
                f"[{symbol}] WARNING: baseline risk reset was not fresh "
                f"({baseline_outcome.reason}); continuing with trial validation."
            )

        consecutive_failures = 0
        _MAX_CONSECUTIVE_FAILURES = 3

        for trial_num in range(1, n_trials + 1):
            if trial_num == 26:
                print(f"\n[{symbol}] ── Phase 2: Bayesian focus ──\n")

            # Recovery: if TradingView stopped responding, reload the tab and
            # re-bind the expected symbol/range before continuing.
            if consecutive_failures >= _MAX_CONSECUTIVE_FAILURES:
                print(
                    f"[{symbol}] ⚠️  {consecutive_failures} consecutive failed trials — reloading tab"
                )
                try:
                    await worker.page.reload(wait_until="domcontentloaded", timeout=30000)
                    await asyncio.sleep(5)
                    await worker._switch_symbol(symbol)
                    await self._require_worker_backtest_range(worker)
                except Exception as e:
                    print(f"[{symbol}] Tab reload failed: {e}")
                consecutive_failures = 0

            trial = study.ask()
            params = worker.sample_params(trial, symbol, self.fixed_overrides)

            elapsed = time.time() - start
            avg_secs = elapsed / trial_num if trial_num > 1 else 0
            remaining = (n_trials - trial_num) * avg_secs
            eta = f"{int(remaining // 60)}m{int(remaining % 60)}s" if remaining else "?"

            # Hard per-trial timeout — prevents a frozen Playwright call from
            # deadlocking the entire run (as seen with CADJPY trial 22).
            _TRIAL_HARD_TIMEOUT = 360  # 6 minutes max per trial (150s update × 2 retries + buffer)

            try:
                apply_outcome = await asyncio.wait_for(
                    worker._apply_params(params), timeout=_TRIAL_HARD_TIMEOUT
                )
            except asyncio.TimeoutError:
                self._record_trial_event(
                    symbol=symbol,
                    trial_num=trial_num,
                    params=params,
                    outcome="timed_out",
                    hash_before="",
                    hash_after="",
                )
                print(
                    self._format_trial_log_line(
                        symbol=symbol,
                        trial_num=trial_num,
                        n_trials=n_trials,
                        eta=eta,
                        reason=f"trial hard-timeout {_TRIAL_HARD_TIMEOUT}s",
                    )
                )
                consecutive_failures += 1
                study.tell(trial, state=optuna.trial.TrialState.FAIL)
                continue
            except Exception as e:
                self._record_trial_event(
                    symbol=symbol,
                    trial_num=trial_num,
                    params=params,
                    outcome="apply_exception",
                    hash_before="",
                    hash_after="",
                )
                print(
                    self._format_trial_log_line(
                        symbol=symbol,
                        trial_num=trial_num,
                        n_trials=n_trials,
                        eta=eta,
                        reason=f"apply exception: {e}",
                    )
                )
                consecutive_failures += 1
                study.tell(trial, state=optuna.trial.TrialState.FAIL)
                continue

            if not apply_outcome.fresh:
                self._record_trial_event(
                    symbol=symbol,
                    trial_num=trial_num,
                    params=params,
                    outcome=(
                        "stale" if apply_outcome.reason == "stale_result_hash"
                        else apply_outcome.reason or "apply_failed"
                    ),
                    hash_before=apply_outcome.results_hash_before,
                    hash_after=apply_outcome.results_hash_after,
                )
                if (
                    self.runtime_state is not None
                    and self.run_id is not None
                    and self.worker_id is not None
                    and apply_outcome.reason == "stale_result_hash"
                ):
                    self.runtime_state.mark_worker_unhealthy(
                        run_id=self.run_id,
                        worker_id=self.worker_id,
                        stale_reads=apply_outcome.attempt,
                        reason=apply_outcome.reason,
                    )
                print(
                    self._format_trial_log_line(
                        symbol=symbol,
                        trial_num=trial_num,
                        n_trials=n_trials,
                        eta=eta,
                        reason=apply_outcome.reason or "stale apply outcome",
                    )
                )
                consecutive_failures += 1
                study.tell(trial, state=optuna.trial.TrialState.FAIL)
                continue

            try:
                result = await asyncio.wait_for(
                    worker._read_results(symbol, params), timeout=_TRIAL_HARD_TIMEOUT
                )
            except RuntimeError as e:
                self._record_trial_event(
                    symbol=symbol,
                    trial_num=trial_num,
                    params=params,
                    outcome="symbol_mismatch",
                    hash_before=apply_outcome.results_hash_before,
                    hash_after=apply_outcome.results_hash_after,
                )
                print(
                    self._format_trial_log_line(
                        symbol=symbol,
                        trial_num=trial_num,
                        n_trials=n_trials,
                        eta=eta,
                        reason=f"symbol mismatch: {e}",
                    )
                )
                consecutive_failures += 1
                study.tell(trial, state=optuna.trial.TrialState.FAIL)
                continue
            except asyncio.TimeoutError:
                self._record_trial_event(
                    symbol=symbol,
                    trial_num=trial_num,
                    params=params,
                    outcome="timed_out",
                    hash_before=apply_outcome.results_hash_before,
                    hash_after=apply_outcome.results_hash_after,
                )
                print(
                    self._format_trial_log_line(
                        symbol=symbol,
                        trial_num=trial_num,
                        n_trials=n_trials,
                        eta=eta,
                        reason=f"read_results hard-timeout {_TRIAL_HARD_TIMEOUT}s",
                    )
                )
                consecutive_failures += 1
                study.tell(trial, state=optuna.trial.TrialState.FAIL)
                continue
            consecutive_failures = 0
            worker.results.append(result)
            study.tell(trial, result.score)
            self._record_trial_event(
                symbol=symbol,
                trial_num=trial_num,
                params=params,
                outcome="fresh",
                hash_before=apply_outcome.results_hash_before,
                hash_after=apply_outcome.results_hash_after,
                result=result,
            )

            print(
                self._format_trial_log_line(
                    symbol=symbol,
                    trial_num=trial_num,
                    n_trials=n_trials,
                    eta=eta,
                    result=result,
                )
            )

            # Track best overall (highest raw score)
            if best is None or result.score > best.score:
                best = result
                # Only update worker.best_result (used for timeout recovery) with the
                # compliant version if available, otherwise fall back to raw best
                if not best_compliant:
                    worker.best_result = result
                print(
                f"  [{symbol}] ★ NEW BEST  Score={result.score:.2f}  "
                f"PF={result.profit_factor:.2f}  DD={result.max_drawdown_pct:.1f}%  "
                f"T={result.total_trades}  via {self._worker_log_tag()}"
                )

            # Track best compliant (highest score that passes DD limit)
            if result.is_prop_firm_compliant(self.dd_limit) and (
                best_compliant is None or result.score > best_compliant.score
            ):
                best_compliant = result
                worker.best_result = result  # prefer compliant for timeout recovery
                print(
                    f"  [{symbol}] ✅ NEW BEST COMPLIANT  Score={result.score:.2f}  "
                    f"PF={result.profit_factor:.2f}  DD={result.max_drawdown_pct:.1f}%  "
                    f"T={result.total_trades}  via {self._worker_log_tag()}"
                )

        elapsed = time.time() - start
        print(
            f"\n[{symbol}] Done — {n_trials} trials in "
            f"{int(elapsed // 60)}m{int(elapsed % 60)}s"
        )

        # Prefer the best compliant result for deployment; fall back to overall best
        # only if no compliant result was found at all.
        final = best_compliant if best_compliant is not None else best

        if final:
            from .tab_worker import _print_pair_summary_table
            if best_compliant is None and best is not None:
                print(
                    f"  [{symbol}] ⚠ No prop-firm compliant result found. "
                    f"Saving best overall (DD={best.max_drawdown_pct:.1f}%)."
                )
            elif best_compliant is not None and best is not None and best is not best_compliant:
                print(
                    f"  [{symbol}] ℹ Best overall had DD={best.max_drawdown_pct:.1f}% (non-compliant). "
                    f"Saving best compliant instead (DD={best_compliant.max_drawdown_pct:.1f}%)."
                )
            final = await asyncio.wait_for(
                self._verify_final_result_replay(worker, symbol, final),
                timeout=_FINAL_REPLAY_TIMEOUT_SECS,
            )
            _print_pair_summary_table(final)
            return final

        raise RuntimeError(
            f"No valid optimization result produced for {symbol}; all trials failed or were skipped"
        )

    @staticmethod
    def _result_metric_snapshot(result: BacktestResult) -> dict:
        return {
            "net_profit": round(float(result.net_profit), 2),
            "win_rate": round(float(result.win_rate), 2),
            "profit_factor": round(float(result.profit_factor), 3),
            "max_drawdown_pct": round(float(result.max_drawdown_pct), 2),
            "total_trades": int(result.total_trades),
            "score": float(result.score),
        }

    @classmethod
    def _result_metrics_match(cls, expected: BacktestResult, actual: BacktestResult) -> bool:
        return (
            abs(float(expected.net_profit) - float(actual.net_profit)) <= 1.0
            and abs(float(expected.profit_factor) - float(actual.profit_factor)) <= 0.005
            and abs(float(expected.max_drawdown_pct) - float(actual.max_drawdown_pct)) <= 0.05
            and abs(float(expected.win_rate) - float(actual.win_rate)) <= 0.05
            and int(expected.total_trades) == int(actual.total_trades)
        )

    async def _verify_final_result_replay(
        self,
        worker: TabWorker,
        symbol: str,
        candidate: BacktestResult,
    ) -> BacktestResult:
        """
        Reapply the selected params once and save the replayed Strategy Report.

        This prevents stale/intermediate trial reads from becoming the published
        best result. The replay metrics are the final source of truth.
        """
        print(f"  [{symbol}] Final replay validation: reapplying selected params...")
        apply_outcome = await worker._apply_params(
            candidate.params,
            allow_unchanged_hash=True,
        )
        if not apply_outcome.fresh:
            raise RuntimeError(
                f"Final replay validation failed for {symbol}: "
                f"{apply_outcome.reason or 'apply_failed'}"
            )

        replay = await worker._read_results(symbol, candidate.params)
        matched = self._result_metrics_match(candidate, replay)
        replay.validation_metrics.update(candidate.validation_metrics)
        replay.validation_metrics["final_replay"] = {
            "matched_original": matched,
            "original": self._result_metric_snapshot(candidate),
            "replay": self._result_metric_snapshot(replay),
            "apply_reason": apply_outcome.reason,
            "results_hash_before": apply_outcome.results_hash_before,
            "results_hash_after": apply_outcome.results_hash_after,
        }
        if not matched:
            print(
                f"  [{symbol}] ⚠ Final replay differed from trial read; "
                "saving replayed metrics as source of truth."
            )
        else:
            print(f"  [{symbol}] Final replay validation matched.")
        return replay

    def _record_trial_event(
        self,
        *,
        symbol: str,
        trial_num: int,
        params: dict,
        outcome: str,
        hash_before: str,
        hash_after: str,
        result: Optional[BacktestResult] = None,
    ) -> None:
        if self.runtime_state is None or self.run_id is None or self.worker_id is None:
            return

        params_hash = hashlib.md5(
            json.dumps(params, sort_keys=True).encode("utf-8")
        ).hexdigest()[:8]
        metrics = None
        if result is not None:
            metrics = {
                "verified_symbol": result.verified_symbol,
                "profit_factor": result.profit_factor,
                "max_drawdown_pct": result.max_drawdown_pct,
                "drawdown_source": result.drawdown_source,
                "total_trades": result.total_trades,
                "score": result.score,
            }
        self.runtime_state.record_trial_event(
            run_id=self.run_id,
            worker_id=self.worker_id,
            symbol=symbol,
            trial=trial_num,
            outcome=outcome,
            params_hash=params_hash,
            results_hash_before=hash_before,
            results_hash_after=hash_after,
            metrics=metrics,
        )

    # ─────────────────────────────────── main run loop ───────────────────────

    async def run(self) -> None:
        """Run the full optimization pipeline (sequential, with checkpoint & timeout)."""
        await self.connect_to_brave()

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
            print(f"\n--- Starting {symbol} ---")
            try:
                worker = TabWorker(page, self)

                if self.bayesian_mode:
                    timeout = self.n_trials * 120  # 120s per trial — TV can hang for 90s on a single trial
                    coro = self.optimize_pair_bayesian(worker, symbol, self.n_trials)
                elif self.smart_mode:
                    timeout = _PAIR_TIMEOUT_SECS
                    coro = worker.optimize_pair_smart(symbol)
                else:
                    timeout = _PAIR_TIMEOUT_SECS
                    coro = worker.optimize_pair(symbol)

                result = await asyncio.wait_for(coro, timeout=timeout)

                if result:
                    result = self._apply_staged_survival_result(result)
                    self.best_per_pair[symbol] = result
                    self.results.extend(worker.results)
                    self._save_checkpoint(checkpoint, symbol, result)

            except asyncio.TimeoutError:
                # Save whatever partial results the worker accumulated before timeout
                partial_best = getattr(worker, 'best_result', None)
                n_done = len(getattr(worker, 'results', []))
                if partial_best and partial_best.score > 0:
                    print(
                        f"\n  WARNING: {symbol} timed out after {n_done} trials — "
                        f"saving partial best (score={partial_best.score:.2f})"
                    )
                    partial_best = self._apply_staged_survival_result(partial_best)
                    self.best_per_pair[symbol] = partial_best
                    self.results.extend(worker.results)
                    self._save_checkpoint(checkpoint, symbol, partial_best)
                else:
                    print(f"\n  WARNING: {symbol} timed out — no valid result found yet")
                continue
            except Exception as e:
                print(f"\n  ERROR optimizing {symbol}: {e}")
                traceback.print_exc()
                continue

        elapsed = time.time() - start_time
        minutes = int(elapsed // 60)
        seconds = int(elapsed % 60)

        # Persist CSV + JSON
        self.save_results()

        # Generate HTML report (bayesian mode default, opt-in for others)
        if self.generate_report and self.best_per_pair:
            from .report import generate_html_report
            report_path = generate_html_report(
                best_per_pair=self.best_per_pair,
                all_results=self.results,
                dd_limit=self.dd_limit,
            )
            print(f"\nHTML Report: {report_path}")
            import webbrowser
            webbrowser.open(f"file://{report_path}")

        print(f"\n{'=' * 60}")
        print("OPTIMIZATION COMPLETE")
        print(f"{'=' * 60}")
        print(f"Time elapsed: {minutes}m {seconds}s")
        print(f"Pairs optimized: {len(self.best_per_pair)}/{len(self.pairs)}")
        print(f"Total combinations tested: {len(self.results)}")

        # Final leaderboard
        if self.best_per_pair:
            ranked = sorted(
                self.best_per_pair.items(), key=lambda kv: kv[1].score, reverse=True
            )
            print(f"\n{'─' * 70}")
            print("FINAL LEADERBOARD (by score, best first)")
            print(f"{'─' * 70}")
            header = (
                f"  {'#':>3}  {'Symbol':<10} | {'PF':>5} | {'WR':>7} | "
                f"{'Trades':>6} | {'DD%':>5} | {'Score':>8} | Prop"
            )
            sep = "  " + "─" * (len(header) - 2)
            print(sep)
            print(header)
            print(sep)
            for rank, (sym, res) in enumerate(ranked, 1):
                compliant = "✅" if res.is_prop_firm_compliant(self.dd_limit) else "❌"
                print(
                    f"  {rank:>3}  {sym:<10} | "
                    f"{res.profit_factor:>5.2f} | "
                    f"{res.win_rate:>6.1f}% | "
                    f"{res.total_trades:>6} | "
                    f"{res.max_drawdown_pct:>4.1f}% | "
                    f"{res.score:>8.2f} | {compliant}"
                )
            print(sep)

    # ─────────────────────────────────── persistence ─────────────────────────

    def save_results(self) -> None:
        """Save all results to CSV and best-per-pair to JSON."""
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
                    **res.to_dict(),
                    "prop_firm_compliant": res.is_prop_firm_compliant(self.dd_limit),
                },
            }
        with open(best_file, "w") as f:
            json.dump(best_data, f, indent=2)
        print(f"Best settings: {best_file}")
