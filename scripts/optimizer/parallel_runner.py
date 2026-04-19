"""
parallel_runner.py — Parallel TradingView optimizer coordinator.

Spawns N independent browser contexts, each handling a queue of pairs.
Each worker runs in its own asyncio task against a dedicated TradingView page.

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
import os
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Optional, Any
from urllib.parse import quote, urlparse

from .config import (
    RESULTS_DIR,
    DEFAULT_PAIRS,
    N_BAYESIAN_TRIALS,
    PROP_FIRM_MAX_DD_PCT,
    OPTUNA_SEARCH_SPACE,
    LIQ_DISTANCE_RANGES,
)
from .models import BacktestResult
from .optimizer_mcp import OptimizerMcpController, OptimizerWorkspaceSlot
from .runtime_state import OptimizerRuntimeState

try:
    from playwright.async_api import async_playwright, Page
except ImportError:
    async_playwright = None  # type: ignore[assignment]
    Page = Any  # type: ignore[misc,assignment]

log = logging.getLogger(__name__)

LEGACY_PARALLEL_RESULTS_FILE = RESULTS_DIR / "parallel_results.json"
PARALLEL_LOG_FILE = RESULTS_DIR / "parallel_run.log"
MAX_PAIR_RETRIES = 2
WORKER_STARTUP_DELAY = 15.0  # stagger worker starts to reduce startup contention
TRADINGVIEW_DESKTOP_CDP_URL = os.environ.get("OPTIMIZER_DESKTOP_CDP_URL", "http://127.0.0.1:9222")
SUPPORTED_BROKERS = {"vantage", "oanda", "fxcm"}


def results_file_for_broker(broker: str) -> Path:
    normalized = broker.strip().lower()
    if normalized not in SUPPORTED_BROKERS:
        raise ValueError(f"Unsupported broker: {broker}")
    return RESULTS_DIR / f"parallel_results_{normalized}.json"


def write_results_snapshot(results: dict[str, Any], results_file: Path) -> None:
    with open(results_file, "w") as handle:
        json.dump(results, handle, indent=2)
    with open(LEGACY_PARALLEL_RESULTS_FILE, "w") as handle:
        json.dump(results, handle, indent=2)


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


def detect_desktop_cdp_pid() -> int | None:
    """Return the first PID listening on the TradingView Desktop CDP port, if any."""
    try:
        output = (
            subprocess.check_output(["lsof", "-ti", ":9222"], text=True)
            .strip()
            .splitlines()
        )
    except Exception:
        return None

    if not output:
        return None
    try:
        return int(output[0])
    except ValueError:
        return None


def detect_cdp_pid() -> int | None:
    """Backward-compatible alias for the desktop CDP PID detector."""
    return detect_desktop_cdp_pid()


def emit_event(event_type: str, **payload: object) -> None:
    event = {"event_type": event_type, **payload}
    print(json.dumps(event), flush=True)


def _extract_chart_id(url: str) -> str | None:
    """Return the TradingView chart id from a chart URL, if present."""
    try:
        parsed = urlparse(url)
    except Exception:
        return None

    if "tradingview.com" not in parsed.netloc or not parsed.path.startswith("/chart/"):
        return None

    parts = [part for part in parsed.path.split("/") if part]
    if len(parts) < 2 or parts[0] != "chart":
        return None

    chart_id = parts[1].strip()
    return chart_id or None


def _collect_tradingview_pages(browser: Any) -> list[Any]:
    """Collect chart pages from every attached browser context."""
    tv_pages: list[Any] = []
    for context in getattr(browser, "contexts", []):
        for page in getattr(context, "pages", []):
            try:
                if "tradingview.com/chart" in page.url:
                    tv_pages.append(page)
            except Exception:
                continue
    return tv_pages


def _match_pages_to_slots(tv_pages: list[Any], slots: list[OptimizerWorkspaceSlot]) -> list[Any]:
    """Match chart pages to MCP workspace slots using chart ids when available."""
    ordered_slots = sorted(slots, key=lambda slot: slot.index)
    if len(tv_pages) < len(ordered_slots):
        raise RuntimeError(
            f"TradingView Desktop returned {len(tv_pages)} chart page(s) for {len(ordered_slots)} prepared MCP slot(s)"
        )

    remaining_pages = list(tv_pages)
    used_page_ids: set[int] = set()
    matched_pages: list[Any] = []

    for slot in ordered_slots:
        slot_page = None
        if slot.chart_id:
            for page in remaining_pages:
                if id(page) in used_page_ids:
                    continue
                if _extract_chart_id(getattr(page, "url", "")) == slot.chart_id:
                    slot_page = page
                    break

        if slot_page is None:
            for page in remaining_pages:
                if id(page) not in used_page_ids:
                    slot_page = page
                    break

        if slot_page is None:
            raise RuntimeError(
                f"Could not resolve a TradingView page for MCP slot {slot.index} ({slot.tab_id})"
            )

        used_page_ids.add(id(slot_page))
        matched_pages.append(slot_page)

    return matched_pages


def _prepare_mcp_backed_pages(browser: Any, slots: list[OptimizerWorkspaceSlot]) -> list[Any]:
    """Resolve real Playwright page objects from prepared MCP slots."""
    tv_pages = _collect_tradingview_pages(browser)
    return _match_pages_to_slots(tv_pages, slots)


async def _wait_for_chart_id(page: Any, timeout: float = 60.0) -> str | None:
    """Wait until TradingView assigns a real chart id to the page URL."""
    start = time.time()
    while time.time() - start < timeout:
        try:
            chart_id = _extract_chart_id(page.url)
            if chart_id:
                return chart_id
        except Exception:
            pass
        await asyncio.sleep(1)
    return None


async def ensure_tradingview_tabs(browser, required_tabs: int, bootstrap_symbol: str) -> list[Any]:
    """Legacy Chrome bootstrap helper kept for compatibility with older flows."""
    tv_pages: list[Any] = []
    for context in browser.contexts:
        for page in context.pages:
            try:
                if "tradingview.com/chart" in page.url:
                    tv_pages.append(page)
            except Exception:
                continue

    if len(tv_pages) >= required_tabs:
        return tv_pages[:required_tabs]

    if not browser.contexts:
        raise RuntimeError("Chrome has no browser contexts to open TradingView tabs")

    context = browser.contexts[0]
    missing = required_tabs - len(tv_pages)
    log.info(
        "Opening %d TradingView chart tab(s) using %s as bootstrap symbol",
        missing,
        bootstrap_symbol,
    )

    for idx in range(missing):
        page = await context.new_page()
        try:
            await page.goto(
                "https://www.tradingview.com/chart/",
                wait_until="domcontentloaded",
                timeout=30000,
            )
        except Exception as e:
            log.warning("Bootstrap tab %d navigation warning: %s", idx + 1, e)

        chart_id = await _wait_for_chart_id(page, timeout=60.0)
        if not chart_id:
            raise RuntimeError(
                "Could not open a real TradingView chart tab. Open TradingView manually and retry."
            )

        try:
            await page.goto(
                f"https://www.tradingview.com/chart/{chart_id}/?symbol=VANTAGE%3A{quote(bootstrap_symbol.upper())}",
                wait_until="domcontentloaded",
                timeout=30000,
            )
        except Exception as e:
            log.warning("Bootstrap tab %d symbol navigation warning: %s", idx + 1, e)

        confirmed_id = await _wait_for_chart_id(page, timeout=30.0)
        if not confirmed_id:
            raise RuntimeError(
                "TradingView chart tab did not finish initializing after bootstrap."
            )
        log.info("Bootstrap tab %d ready with chart id %s", idx + 1, confirmed_id)
        tv_pages.append(page)

    tv_pages = []
    for context in browser.contexts:
        for page in context.pages:
            try:
                if "tradingview.com/chart" in page.url:
                    tv_pages.append(page)
            except Exception:
                continue

    if len(tv_pages) < required_tabs:
        raise RuntimeError(
            f"Only {len(tv_pages)} TradingView chart tab(s) available after bootstrap; need {required_tabs}."
        )

    return tv_pages[:required_tabs]


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
    page: Page | None,
    symbol: str,
    mode: str,
    n_trials: int,
    dd_limit: float,
    dry_run: bool,
    runtime_state: OptimizerRuntimeState | None = None,
    run_id: str | None = None,
    worker_id: int | None = None,
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
    opt_shell.runtime_state = runtime_state
    opt_shell.run_id = run_id
    opt_shell.worker_id = worker_id

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
    page: Page | None,
    pair_queue: asyncio.Queue,
    results: dict,
    results_file: Path,
    results_lock: asyncio.Lock,
    error_log: list,
    mode: str,
    n_trials: int,
    dd_limit: float,
    dry_run: bool,
    runtime_state: OptimizerRuntimeState | None,
    run_id: str | None,
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
                if runtime_state is not None and run_id is not None:
                    runtime_state.mark_pair_started(
                        run_id=run_id,
                        worker_id=worker_id,
                        symbol=symbol,
                    )
                    runtime_state.record_run_event(
                        run_id=run_id,
                        event_type="pair_started",
                        payload={"worker_id": worker_id, "symbol": symbol, "attempt": retries + 1},
                    )
                    emit_event(
                        "pair_started",
                        run_id=run_id,
                        worker_id=worker_id,
                        symbol=symbol,
                        attempt=retries + 1,
                    )
                start = time.time()
                result = await optimize_pair_on_page(
                    page,
                    symbol,
                    mode,
                    n_trials,
                    dd_limit,
                    dry_run,
                    runtime_state=runtime_state,
                    run_id=run_id,
                    worker_id=worker_id,
                )
                elapsed = time.time() - start
                log.info(
                    f"[worker-{worker_id}] ✅ {symbol} done in {elapsed:.1f}s "
                    f"| score={result.score:.3f} pf={result.profit_factor:.2f} "
                    f"dd={result.max_drawdown_pct:.1f}%"
                )
                if runtime_state is not None and run_id is not None:
                    runtime_state.mark_pair_completed(
                        run_id=run_id,
                        worker_id=worker_id,
                        symbol=symbol,
                    )
                    payload = {
                        "worker_id": worker_id,
                        "symbol": symbol,
                        "elapsed_seconds": elapsed,
                        "params": result.params,
                        "metrics": {
                            "score": result.score,
                            "net_profit": result.net_profit,
                            "win_rate": result.win_rate,
                            "profit_factor": result.profit_factor,
                            "max_drawdown_pct": result.max_drawdown_pct,
                            "total_trades": result.total_trades,
                        },
                    }
                    runtime_state.record_run_event(
                        run_id=run_id,
                        event_type="pair_completed",
                        payload=payload,
                    )
                    emit_event("pair_completed", run_id=run_id, **payload)
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
                    if runtime_state is not None and run_id is not None:
                        payload = {
                            "worker_id": worker_id,
                            "symbol": symbol,
                            "error_message": str(e),
                        }
                        runtime_state.record_run_event(
                            run_id=run_id,
                            event_type="pair_failed",
                            payload=payload,
                        )
                        emit_event("pair_failed", run_id=run_id, **payload)

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
                write_results_snapshot(results, results_file)

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
    broker: str,
    raw_args: list[str] | None = None,
) -> dict:
    """
    Main coordinator: prepares TradingView Desktop tabs, distributes pairs to workers, collects results.
    """
    setup_logging()
    results_file = results_file_for_broker(broker)

    log.info(f"Parallel optimizer starting")
    log.info(f"  Pairs: {len(pairs)} | Workers: {n_workers} | Mode: {mode} | Broker: {broker}")
    if dry_run:
        log.info("  DRY RUN MODE — no real TradingView interaction")

    # Load existing results to skip already-completed pairs
    existing_results = {}
    if results_file.exists():
        try:
            with open(results_file) as f:
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
    runtime_state = OptimizerRuntimeState(results_dir=RESULTS_DIR)
    run_status = runtime_state.start_run(
        args=["--parallel", *(raw_args or [])],
        mode=mode,
        workers=n_workers,
        log_file=os.environ.get("OPTIMIZER_LAUNCH_LOG_FILE", str(PARALLEL_LOG_FILE)),
        optimizer_pid=os.getpid(),
        desktop_cdp_pid=detect_desktop_cdp_pid(),
    )
    run_id = run_status["run_id"]
    runtime_state.record_run_event(
        run_id=run_id,
        event_type="run_started",
        payload={"mode": mode, "workers": n_workers, "pairs": remaining_pairs, "dry_run": dry_run, "broker": broker},
    )
    emit_event(
        "run_started",
        run_id=run_id,
        mode=mode,
        workers=n_workers,
        pairs=remaining_pairs,
        dry_run=dry_run,
        broker=broker,
    )

    # Build queue
    pair_queue: asyncio.Queue = asyncio.Queue()
    for pair in remaining_pairs:
        await pair_queue.put(pair)

    start_time = time.time()

    try:
        if not dry_run and async_playwright is None:
            raise RuntimeError("playwright not installed. Install in venv: python3 -m pip install playwright && python3 -m playwright install chromium")

        if dry_run:
            # Dry-run mode never touches a real page; keep it browserless so it works
            # even when Playwright browsers are not installed locally.
            browser = None
            pages = [None] * n_workers
        else:
            controller = OptimizerMcpController()
            workspace_slots = await controller.ensure_optimizer_workspace(
                required_tabs=n_workers,
                bootstrap_symbol=remaining_pairs[0],
                broker=broker,
            )

            async with async_playwright() as pw:  # type: ignore[operator]
                try:
                    browser = await pw.chromium.connect_over_cdp(TRADINGVIEW_DESKTOP_CDP_URL)
                except Exception as exc:
                    raise RuntimeError(
                        f"Could not connect to TradingView Desktop CDP target at {TRADINGVIEW_DESKTOP_CDP_URL}: {exc}"
                    ) from exc

                log.info("Connected to TradingView Desktop CDP target at %s", TRADINGVIEW_DESKTOP_CDP_URL)
                pages = _prepare_mcp_backed_pages(browser, workspace_slots)

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
                    results_file=results_file,
                    results_lock=results_lock,
                    error_log=error_log,
                    mode=mode,
                    n_trials=n_trials,
                    dd_limit=dd_limit,
                    dry_run=dry_run,
                    runtime_state=runtime_state,
                    run_id=run_id,
                ),
                name=f"worker-{i}",
            )
            tasks.append(task)

        task_results = await asyncio.gather(*tasks, return_exceptions=True)
        for task_result in task_results:
            if isinstance(task_result, Exception):
                error_log.append({"symbol": "worker_task", "worker": -1, "error": str(task_result)})

        if browser is not None:
            await browser.close()
    except Exception:
        runtime_state.set_run_state(run_id=run_id, state="failed")
        raise

    elapsed = time.time() - start_time
    runtime_state.set_run_state(
        run_id=run_id,
        state="failed" if error_log else "completed",
    )
    output_paths = {
        "results_file": str(results_file),
        "legacy_results_file": str(LEGACY_PARALLEL_RESULTS_FILE),
    }
    log.info(f"\n{'='*60}")
    log.info(f"Parallel run complete in {elapsed:.1f}s")
    log.info(f"  Completed: {len(results)} pairs")
    log.info(f"  Failed: {len(error_log)} pairs")
    if error_log:
        log.warning(f"  Failed pairs: {[e['symbol'] for e in error_log]}")
    log.info(f"  Results: {results_file}")

    # Generate HTML report from parallel results
    if results:
        try:
            from .report import generate_html_report

            best_per_pair: dict[str, BacktestResult] = {}
            for symbol, data in results.items():
                best_per_pair[symbol] = BacktestResult(
                    symbol=symbol,
                    params=data.get("params", {}),
                    net_profit=data.get("net_profit", 0.0),
                    total_trades=data.get("total_trades", 0),
                    win_rate=data.get("win_rate", 0.0),
                    profit_factor=data.get("profit_factor", 0.0),
                    max_drawdown_pct=data.get("max_drawdown_pct", 0.0),
                    score=data.get("score", 0.0),
                    timestamp=data.get("timestamp", ""),
                )
            report_path = generate_html_report(
                best_per_pair=best_per_pair,
                all_results=list(best_per_pair.values()),
                dd_limit=dd_limit,
            )
            output_paths["report_path"] = str(report_path)
            log.info(f"  HTML Report: {report_path}")
            import webbrowser
            webbrowser.open(f"file://{report_path}")
        except Exception as e:
            log.warning(f"  Report generation failed: {e}")

    log.info(f"{'='*60}")
    runtime_state.record_run_event(
        run_id=run_id,
        event_type="run_finished",
        payload={
            "status": "failed" if error_log else "completed",
            "output_paths": output_paths,
            "error_count": len(error_log),
        },
    )
    emit_event(
        "run_finished",
        run_id=run_id,
        status="failed" if error_log else "completed",
        output_paths=output_paths,
        error_count=len(error_log),
    )

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
    parser.add_argument("--broker", choices=sorted(SUPPORTED_BROKERS), default="vantage", help="Broker dataset namespace")
    parser.add_argument("--dry-run", action="store_true", help="Test with fake results (2 pairs, 2 trials)")
    parser.add_argument("--reset", action="store_true", help="Clear existing results and start fresh")
    args = parser.parse_args()

    results_file = results_file_for_broker(args.broker)

    if args.reset and results_file.exists():
        results_file.unlink()
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
        broker=args.broker,
        raw_args=sys.argv[1:],
    ))


if __name__ == "__main__":
    main()
