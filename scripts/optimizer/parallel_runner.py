"""
parallel_runner.py — Parallel TradingView optimizer coordinator.

Spawns N independent browser contexts, each handling a queue of pairs.
Each worker runs in its own asyncio task against a dedicated Chrome page.

Usage:
    python -m scripts.optimizer.parallel_runner --workers 3 --mode bayesian
    python -m scripts.optimizer.parallel_runner --workers 2 --mode bayesian --dry-run
    python -m scripts.optimizer.parallel_runner --workers 3 --pairs EURUSD,GBPUSD,XAUUSD

Architecture:
    coordinator
    ├── worker-0  →  page 0  →  pairs [0, 3, 6, ...]
    ├── worker-1  →  page 1  →  pairs [1, 4, 7, ...]
    └── worker-2  →  page 2  →  pairs [2, 5, 8, ...]

Each worker:
  - Gets pairs from a shared asyncio.Queue
  - Writes results to a shared results dict (protected by asyncio.Lock)
  - Retries failed pairs up to MAX_PAIR_RETRIES with a fresh page context
  - Logs structured JSON results per pair
"""

import asyncio
import json
import logging
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Optional

from .config import (
    RESULTS_DIR,
    DEFAULT_PAIRS,
    N_BAYESIAN_TRIALS,
    PROP_FIRM_MAX_DD_PCT,
    OPTUNA_SEARCH_SPACE,
    LIQ_DISTANCE_RANGES,
)
from .models import BacktestResult

try:
    from playwright.async_api import async_playwright, Page, Browser, BrowserContext
except ImportError:
    print("ERROR: playwright not installed. Run: pip3 install playwright")
    sys.exit(1)

log = logging.getLogger(__name__)

PARALLEL_RESULTS_FILE = RESULTS_DIR / "parallel_results.json"
PARALLEL_LOG_FILE = RESULTS_DIR / "parallel_run.log"
MAX_PAIR_RETRIES = 2
WORKER_STARTUP_DELAY = 3.0  # stagger worker starts to avoid race on Chrome


# ──────────────────────────────────────────────────────────────────────────────
# Logging setup
# ──────────────────────────────────────────────────────────────────────────────

def setup_logging() -> None:
    RESULTS_DIR.mkdir(exist_ok=True)
    handlers = [
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(PARALLEL_LOG_FILE, mode='w'),
    ]
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        handlers=handlers,
    )


# ──────────────────────────────────────────────────────────────────────────────
# Self-healing selector helper
# ──────────────────────────────────────────────────────────────────────────────

async def find_element_resilient(page: Page, strategies: list[dict]) -> Optional[object]:
    """
    Try multiple selector strategies in order.
    Each strategy: {"type": "css"|"aria"|"text", "value": "..."}
    Returns the first matching locator, or None.
    """
    for strategy in strategies:
        try:
            s_type = strategy["type"]
            value = strategy["value"]
            if s_type == "css":
                loc = page.locator(value)
            elif s_type == "aria":
                loc = page.get_by_role("button", name=value)
            elif s_type == "text":
                loc = page.get_by_text(value, exact=False)
            else:
                continue

            if await loc.count() > 0:
                return loc
        except Exception:
            continue
    return None


# ──────────────────────────────────────────────────────────────────────────────
# Worker
# ──────────────────────────────────────────────────────────────────────────────

async def optimize_pair_on_page(
    page: Page,
    symbol: str,
    mode: str,
    n_trials: int,
    dd_limit: float,
    dry_run: bool,
) -> Optional[BacktestResult]:
    """
    Run optimization for one pair on a given page.
    In dry_run mode, returns a fake result after a short sleep.
    """
    if dry_run:
        await asyncio.sleep(2)
        return BacktestResult(
            symbol=symbol,
            params={"dry_run": True},
            net_profit=999.0,
            total_trades=50,
            win_rate=55.0,
            profit_factor=1.5,
            max_drawdown_pct=5.0,
            score=1.5,
        )

    # Import TabWorker here to avoid circular import
    from .tab_worker import TabWorker
    from .optimizer import TradingViewOptimizer

    # Create a minimal optimizer shell just to pass to TabWorker
    opt_shell = TradingViewOptimizer(
        pairs=[symbol],
        bayesian_mode=(mode == "bayesian"),
        smart_mode=(mode == "smart"),
        fast_mode=(mode == "fast"),
        n_trials=n_trials,
        dd_limit=dd_limit,
    )
    opt_shell.page = page

    # TabWorker signature is (page, optimizer) — not (optimizer, page, symbol)
    worker = TabWorker(page, opt_shell)

    if mode == "bayesian":
        # optimize_pair_bayesian lives on TradingViewOptimizer, takes (worker, symbol, n_trials)
        return await opt_shell.optimize_pair_bayesian(worker, symbol, n_trials)
    elif mode == "smart":
        return await worker.optimize_pair_smart(symbol)
    else:
        return await worker.optimize_pair(symbol)


async def worker_task(
    worker_id: int,
    page: Page,
    pair_queue: asyncio.Queue,
    results: dict,
    results_lock: asyncio.Lock,
    error_log: list,
    mode: str,
    n_trials: int,
    dd_limit: float,
    dry_run: bool,
) -> None:
    """Worker coroutine: pulls pairs from queue, optimizes, saves results."""
    log.info(f"[worker-{worker_id}] Started")

    while True:
        try:
            symbol = pair_queue.get_nowait()
        except asyncio.QueueEmpty:
            break

        retries = 0
        result = None

        while retries <= MAX_PAIR_RETRIES:
            try:
                log.info(f"[worker-{worker_id}] Starting {symbol} (attempt {retries + 1})")
                start = time.time()
                result = await optimize_pair_on_page(
                    page, symbol, mode, n_trials, dd_limit, dry_run
                )
                elapsed = time.time() - start
                log.info(
                    f"[worker-{worker_id}] ✅ {symbol} done in {elapsed:.1f}s "
                    f"| score={result.score:.3f} pf={result.profit_factor:.2f} "
                    f"dd={result.max_drawdown_pct:.1f}%"
                )
                break
            except Exception as e:
                retries += 1
                log.warning(f"[worker-{worker_id}] ⚠️  {symbol} attempt {retries} failed: {e}")
                if isinstance(e, OSError) and e.errno == 28:
                    log.error(
                        "[worker-%d] Disk is full while optimizing %s. "
                        "Free space and rerun; this failure can look like the optimizer is stuck.",
                        worker_id,
                        symbol,
                    )
                if retries <= MAX_PAIR_RETRIES:
                    await asyncio.sleep(5)
                else:
                    log.error(f"[worker-{worker_id}] ❌ {symbol} failed after {MAX_PAIR_RETRIES} retries")
                    error_log.append({"symbol": symbol, "worker": worker_id, "error": str(e)})

        if result is not None:
            async with results_lock:
                results[symbol] = {
                    "params": result.params,
                    "score": result.score,
                    "net_profit": result.net_profit,
                    "win_rate": result.win_rate,
                    "profit_factor": result.profit_factor,
                    "max_drawdown_pct": result.max_drawdown_pct,
                    "total_trades": result.total_trades,
                    "worker_id": worker_id,
                    "timestamp": datetime.now().isoformat(),
                }
                # Write results incrementally — never lose completed work
                with open(PARALLEL_RESULTS_FILE, "w") as f:
                    json.dump(results, f, indent=2)

        pair_queue.task_done()

    log.info(f"[worker-{worker_id}] Queue exhausted — done")


# ──────────────────────────────────────────────────────────────────────────────
# Coordinator
# ──────────────────────────────────────────────────────────────────────────────

async def run_parallel(
    pairs: list[str],
    n_workers: int,
    mode: str,
    n_trials: int,
    dd_limit: float,
    dry_run: bool,
) -> dict:
    """
    Main coordinator: opens browser, distributes pairs to workers, collects results.
    """
    setup_logging()

    log.info(f"Parallel optimizer starting")
    log.info(f"  Pairs: {len(pairs)} | Workers: {n_workers} | Mode: {mode}")
    if dry_run:
        log.info("  DRY RUN MODE — no real TradingView interaction")

    # Load existing results to skip already-completed pairs
    existing_results = {}
    if PARALLEL_RESULTS_FILE.exists():
        try:
            with open(PARALLEL_RESULTS_FILE) as f:
                existing_results = json.load(f)
            log.info(f"Resuming — {len(existing_results)} pairs already completed")
        except Exception:
            pass

    remaining_pairs = [p for p in pairs if p not in existing_results]
    log.info(f"Pairs to process: {len(remaining_pairs)}")

    if not remaining_pairs:
        log.info("All pairs already completed!")
        return existing_results

    results = dict(existing_results)
    results_lock = asyncio.Lock()
    error_log = []

    # Build queue
    pair_queue: asyncio.Queue = asyncio.Queue()
    for pair in remaining_pairs:
        await pair_queue.put(pair)

    start_time = time.time()

    async with async_playwright() as pw:
        if dry_run:
            # In dry run, use a real browser context but don't touch TradingView
            browser = await pw.chromium.launch(headless=True)
            contexts = [await browser.new_context() for _ in range(n_workers)]
            pages = [await ctx.new_page() for ctx in contexts]
        else:
            # Connect to existing Chrome with remote debugging
            try:
                browser = await pw.chromium.connect_over_cdp("http://127.0.0.1:9222")
                log.info("Connected to Chrome on port 9222")
            except Exception as e:
                log.error(f"Could not connect to Chrome: {e}")
                log.error("Start Chrome with: open -a 'Google Chrome' --args --remote-debugging-port=9222")
                sys.exit(1)

            # Get existing TradingView pages
            tv_pages = []
            for context in browser.contexts:
                for page in context.pages:
                    if "tradingview.com/chart" in page.url:
                        tv_pages.append(page)

            if len(tv_pages) < n_workers:
                log.warning(
                    f"Only {len(tv_pages)} TradingView tabs open, "
                    f"but {n_workers} workers requested. "
                    f"Open {n_workers - len(tv_pages)} more TradingView chart tabs."
                )
                n_workers = len(tv_pages)

            pages = tv_pages[:n_workers]

        # Stagger worker starts to avoid race conditions
        tasks = []
        for i, page in enumerate(pages[:n_workers]):
            if i > 0:
                await asyncio.sleep(WORKER_STARTUP_DELAY)
            task = asyncio.create_task(
                worker_task(
                    worker_id=i,
                    page=page,
                    pair_queue=pair_queue,
                    results=results,
                    results_lock=results_lock,
                    error_log=error_log,
                    mode=mode,
                    n_trials=n_trials,
                    dd_limit=dd_limit,
                    dry_run=dry_run,
                ),
                name=f"worker-{i}",
            )
            tasks.append(task)

        await asyncio.gather(*tasks, return_exceptions=True)

        if dry_run:
            await browser.close()

    elapsed = time.time() - start_time
    log.info(f"\n{'='*60}")
    log.info(f"Parallel run complete in {elapsed:.1f}s")
    log.info(f"  Completed: {len(results)} pairs")
    log.info(f"  Failed: {len(error_log)} pairs")
    if error_log:
        log.warning(f"  Failed pairs: {[e['symbol'] for e in error_log]}")
    log.info(f"  Results: {PARALLEL_RESULTS_FILE}")
    log.info(f"{'='*60}")

    return results


# ──────────────────────────────────────────────────────────────────────────────
# CLI entry point
# ──────────────────────────────────────────────────────────────────────────────

def main() -> None:
    import argparse
    parser = argparse.ArgumentParser(description="Parallel TradingView Strategy Optimizer")
    parser.add_argument("--workers", type=int, default=3, help="Number of parallel workers (default: 3)")
    parser.add_argument("--mode", choices=["bayesian", "smart", "fast", "full"], default="bayesian")
    parser.add_argument("--trials", type=int, default=N_BAYESIAN_TRIALS, help="Optuna trials per pair")
    parser.add_argument("--dd-limit", type=float, default=PROP_FIRM_MAX_DD_PCT, help="Max drawdown %")
    parser.add_argument("--pairs", type=str, help="Comma-separated list of pairs (default: all)")
    parser.add_argument("--dry-run", action="store_true", help="Test with fake results (2 pairs, 2 trials)")
    parser.add_argument("--reset", action="store_true", help="Clear existing results and start fresh")
    args = parser.parse_args()

    if args.reset and PARALLEL_RESULTS_FILE.exists():
        PARALLEL_RESULTS_FILE.unlink()
        print("Cleared existing parallel results")

    if args.pairs:
        pairs = [p.strip().upper() for p in args.pairs.split(",")]
    elif args.dry_run:
        pairs = DEFAULT_PAIRS[:4]  # only 4 pairs in dry run
    else:
        pairs = list(DEFAULT_PAIRS)

    if args.dry_run:
        args.trials = 2
        print(f"\n🧪 DRY RUN: {len(pairs)} pairs, {args.workers} workers, {args.trials} trials each")

    asyncio.run(run_parallel(
        pairs=pairs,
        n_workers=args.workers,
        mode=args.mode,
        n_trials=args.trials,
        dd_limit=args.dd_limit,
        dry_run=args.dry_run,
    ))


if __name__ == "__main__":
    main()
