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
import hashlib
import inspect
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
)
from .desktop_page import TradingViewDesktopPage
from .models import BacktestResult, NoDataForRangeError
from .optimizer_mcp import OptimizerMcpController, OptimizerWorkspaceSlot
from .param_contract import validate_optimizer_pine_contract
from .runtime_state import OptimizerRuntimeState
from .tab_worker import normalize_backtest_range, backtest_range_to_label

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
VALIDATE_MODES = {"validate", "multi_broker_validate"}


def _sanitize_results_label(label: str | None) -> str | None:
    if not label:
        return None
    cleaned = "".join(ch if ch.isalnum() or ch in {"-", "_"} else "_" for ch in label.strip())
    cleaned = cleaned.strip("_")
    return cleaned or None


def results_file_for_broker(broker: str, results_label: str | None = None) -> Path:
    normalized = broker.strip().lower()
    if normalized not in SUPPORTED_BROKERS:
        raise ValueError(f"Unsupported broker: {broker}")
    sanitized_label = _sanitize_results_label(results_label)
    if sanitized_label:
        return RESULTS_DIR / f"parallel_results_{normalized}_{sanitized_label}.json"
    return RESULTS_DIR / f"parallel_results_{normalized}.json"


def write_results_snapshot(
    results: dict[str, Any],
    results_file: Path,
    latest_results_file: Path | None = None,
) -> None:
    with open(results_file, "w") as handle:
        json.dump(results, handle, indent=2)
    if latest_results_file and latest_results_file != results_file:
        with open(latest_results_file, "w") as handle:
            json.dump(results, handle, indent=2)
    with open(LEGACY_PARALLEL_RESULTS_FILE, "w") as handle:
        json.dump(results, handle, indent=2)


def load_source_params_file(path: str | None) -> tuple[str | None, dict[str, dict[str, Any]]]:
    if not path:
        return None, {}
    with open(path) as handle:
        payload = json.load(handle)
    source_run_id = payload.get("source_run_id")
    raw_results = payload.get("results")
    if raw_results is None:
        raw_results = {
            symbol: data
            for symbol, data in payload.items()
            if isinstance(data, dict) and isinstance(data.get("params"), dict)
        }
    params_by_symbol: dict[str, dict[str, Any]] = {}
    if isinstance(raw_results, dict):
        for symbol, data in raw_results.items():
            if isinstance(data, dict) and isinstance(data.get("params"), dict):
                params_by_symbol[str(symbol).upper()] = dict(data["params"])
    elif isinstance(raw_results, list):
        for row in raw_results:
            if not isinstance(row, dict):
                continue
            symbol = str(row.get("symbol") or "").upper()
            params = row.get("params")
            if symbol and isinstance(params, dict):
                params_by_symbol[symbol] = dict(params)
    return source_run_id, params_by_symbol


def _result_metrics(result: BacktestResult, *, worker_id: int) -> dict[str, Any]:
    payload = {
        "score": result.score,
        "net_profit": result.net_profit,
        "win_rate": result.win_rate,
        "profit_factor": result.profit_factor,
        "max_drawdown_pct": result.max_drawdown_pct,
        "total_trades": result.total_trades,
        "worker_id": worker_id,
    }
    if result.verified_symbol:
        payload["verified_symbol"] = result.verified_symbol
    if result.validation_metrics:
        payload["validation_metrics"] = result.validation_metrics
    if result.result_truth.evidence_required:
        truth = result.result_truth.to_dict()
        payload["result_truth"] = truth
        payload["trust_status"] = truth["trust_status"]
    return payload


def _source_params_digest(source_params_by_symbol: dict[str, dict[str, Any]]) -> str:
    payload = json.dumps(source_params_by_symbol, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


def _resume_context(
    *,
    mode: str,
    broker: str,
    backtest_range: str,
    custom_start_date: str | None,
    custom_end_date: str | None,
    source_run_id: str | None,
    source_params_by_symbol: dict[str, dict[str, Any]],
    brokers: list[str] | None = None,
) -> dict[str, Any] | None:
    if mode not in VALIDATE_MODES:
        return None
    return {
        "mode": mode,
        "broker": broker,
        "brokers": sorted(brokers or []),
        "backtest_range": normalize_backtest_range(backtest_range),
        "custom_start_date": custom_start_date or "",
        "custom_end_date": custom_end_date or "",
        "source_run_id": source_run_id or "",
        "source_params_digest": _source_params_digest(source_params_by_symbol),
    }


def _filter_existing_results_for_context(
    existing_results: dict[str, Any],
    run_context: dict[str, Any] | None,
) -> dict[str, Any]:
    if not run_context:
        return existing_results
    filtered: dict[str, Any] = {}
    ignored: list[str] = []
    for symbol, data in existing_results.items():
        if isinstance(data, dict) and data.get("run_context") == run_context:
            filtered[symbol] = data
        else:
            ignored.append(symbol)
    if ignored:
        log.warning(
            "Ignoring existing validate result(s) with missing/different run context: %s",
            ignored,
        )
    return filtered


def _store_pair_result(
    results: dict[str, Any],
    *,
    symbol: str,
    broker: str,
    mode: str,
    source_run_id: str | None,
    params: dict[str, Any],
    status: str,
    metrics: dict[str, Any] | None = None,
    skip_reason: str | None = None,
    error_message: str | None = None,
    run_context: dict[str, Any] | None = None,
) -> None:
    metrics = metrics or {}
    if mode == "multi_broker_validate":
        entry = results.setdefault(
            symbol,
            {
                "status": "pending",
                "params": dict(params),
                "source_run_id": source_run_id,
                "run_context": run_context,
                "brokers": {},
            },
        )
        broker_payload = {"status": status, **metrics}
        if skip_reason:
            broker_payload["skip_reason"] = skip_reason
        if error_message:
            broker_payload["error_message"] = error_message
        entry["brokers"][broker] = broker_payload
        statuses = [payload.get("status") for payload in entry["brokers"].values()]
        if statuses and all(item == "completed" for item in statuses):
            entry["status"] = "completed"
        elif any(item == "failed" for item in statuses):
            entry["status"] = "failed"
        elif any(item == "running" for item in statuses):
            entry["status"] = "running"
        elif statuses and all(item == "skipped" for item in statuses):
            entry["status"] = "skipped"
        return

    results[symbol] = {
        "status": status,
        "params": dict(params),
        "source_run_id": source_run_id,
        **metrics,
        "timestamp": datetime.now().isoformat(),
    }
    if run_context:
        results[symbol]["run_context"] = run_context
    if skip_reason:
        results[symbol]["skip_reason"] = skip_reason
    if error_message:
        results[symbol]["error_message"] = error_message


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


def _prepare_mcp_backed_pages(slots: list[OptimizerWorkspaceSlot]) -> list[Any]:
    """Resolve Desktop-backed page shims from prepared MCP slots."""
    ordered_slots = sorted(slots, key=lambda slot: slot.index)
    return [
        TradingViewDesktopPage(tab_id=slot.tab_id, chart_id=slot.chart_id)
        for slot in ordered_slots
    ]


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
                f"https://www.tradingview.com/chart/{chart_id}/?symbol={quote(bootstrap_symbol.upper())}",
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
    broker: str = "vantage",
    backtest_range: str = "365d",
    runtime_state: OptimizerRuntimeState | None = None,
    run_id: str | None = None,
    worker_id: int | None = None,
    source_params: dict[str, Any] | None = None,
    source_params_digest: str | None = None,
    custom_start_date: str | None = None,
    custom_end_date: str | None = None,
) -> Optional[BacktestResult]:
    """
    Run optimization for one pair on a given page.
    In dry_run mode, returns a fake result after a short sleep.
    """
    if dry_run:
        await asyncio.sleep(2)
        if mode in VALIDATE_MODES and source_params is None:
            raise RuntimeError(f"No source params supplied for {symbol}")
        return BacktestResult(
            symbol=symbol,
            params=dict(source_params or {"dry_run": True}),
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
        broker=broker,
        bayesian_mode=(mode == "bayesian"),
        smart_mode=(mode == "smart"),
        fast_mode=(mode == "fast"),
        n_trials=n_trials,
        dd_limit=dd_limit,
        backtest_range=backtest_range,
    )
    opt_shell.page = page
    opt_shell.runtime_state = runtime_state
    opt_shell.run_id = run_id
    opt_shell.worker_id = worker_id
    opt_shell.worker_tab_id = getattr(page, "tab_id", None)
    opt_shell.custom_start_date = custom_start_date
    opt_shell.custom_end_date = custom_end_date
    opt_shell.source_params_digest = source_params_digest or ""

    # TabWorker signature is (page, optimizer) — not (optimizer, page, symbol)
    worker = TabWorker(page, opt_shell)

    if mode in VALIDATE_MODES:
        if source_params is None:
            raise RuntimeError(f"No source params supplied for {symbol}")
        return await worker.validate_pair(
            symbol,
            source_params,
            custom_start_date=custom_start_date,
            custom_end_date=custom_end_date,
        )
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
    latest_results_file: Path,
    results_lock: asyncio.Lock,
    error_log: list,
    broker: str,
    mode: str,
    n_trials: int,
    dd_limit: float,
    dry_run: bool,
    runtime_state: OptimizerRuntimeState | None,
    run_id: str | None,
    backtest_range: str = "365d",
    source_params_by_symbol: dict[str, dict[str, Any]] | None = None,
    source_run_id: str | None = None,
    custom_start_date: str | None = None,
    custom_end_date: str | None = None,
    run_context: dict[str, Any] | None = None,
) -> None:
    """Worker coroutine: pulls pairs from queue, optimizes, saves results."""
    tab_id = getattr(page, "tab_id", "none")
    if hasattr(page, "bind_worker"):
        page.bind_worker(worker_id)
    log.info("[worker-%s tab=%s] Started", worker_id, tab_id)

    while True:
        try:
            queue_item = pair_queue.get_nowait()
        except asyncio.QueueEmpty:
            break

        if isinstance(queue_item, dict):
            symbol = str(queue_item["symbol"]).upper()
            item_broker = str(queue_item.get("broker") or broker).lower()
        else:
            symbol = str(queue_item).upper()
            item_broker = broker

        retries = 0
        result = None
        source_params = (source_params_by_symbol or {}).get(symbol)

        while retries <= MAX_PAIR_RETRIES:
            try:
                log.info(
                    "[worker-%s tab=%s] Starting %s on %s (attempt %d)",
                    worker_id,
                    tab_id,
                    symbol,
                    item_broker,
                    retries + 1,
                )
                if runtime_state is not None and run_id is not None:
                    runtime_state.mark_pair_started(
                        run_id=run_id,
                        worker_id=worker_id,
                        symbol=symbol,
                    )
                    runtime_state.record_run_event(
                        run_id=run_id,
                        event_type="pair_started",
                        payload={"worker_id": worker_id, "symbol": symbol, "broker": item_broker, "attempt": retries + 1},
                    )
                    emit_event(
                        "pair_started",
                        run_id=run_id,
                        worker_id=worker_id,
                        symbol=symbol,
                        broker=item_broker,
                        attempt=retries + 1,
                    )
                start = time.time()
                optimize_kwargs = {
                    "broker": item_broker,
                    "backtest_range": backtest_range,
                    "runtime_state": runtime_state,
                    "run_id": run_id,
                    "worker_id": worker_id,
                }
                if custom_start_date or custom_end_date:
                    optimize_kwargs.update(
                        {
                            "custom_start_date": custom_start_date,
                            "custom_end_date": custom_end_date,
                        }
                    )
                if mode in VALIDATE_MODES:
                    optimize_kwargs.update(
                        {
                            "source_params": source_params,
                        }
                    )
                    if "source_params_digest" in inspect.signature(optimize_pair_on_page).parameters:
                        optimize_kwargs["source_params_digest"] = (run_context or {}).get("source_params_digest", "")
                result = await optimize_pair_on_page(
                    page,
                    symbol,
                    mode,
                    n_trials,
                    dd_limit,
                    dry_run,
                    **optimize_kwargs,
                )
                if result is None:
                    raise RuntimeError(
                        f"No valid optimization result produced for {symbol}"
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
                        "broker": item_broker,
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
            except NoDataForRangeError as e:
                message = str(e)
                log.warning(f"[worker-{worker_id}] SKIP {symbol} on {item_broker}: {message}")
                async with results_lock:
                    _store_pair_result(
                        results,
                        symbol=symbol,
                        broker=item_broker,
                        mode=mode,
                        source_run_id=source_run_id,
                        params=source_params or {},
                        status="skipped",
                        skip_reason=message,
                        run_context=run_context,
                    )
                    write_results_snapshot(
                        results,
                        results_file,
                        latest_results_file=latest_results_file,
                    )
                if runtime_state is not None and run_id is not None:
                    payload = {
                        "worker_id": worker_id,
                        "symbol": symbol,
                        "broker": item_broker,
                        "skip_reason": message,
                    }
                    runtime_state.record_run_event(
                        run_id=run_id,
                        event_type="pair_skipped",
                        payload=payload,
                    )
                    emit_event("pair_skipped", run_id=run_id, **payload)
                result = None
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
                    async with results_lock:
                        _store_pair_result(
                            results,
                            symbol=symbol,
                            broker=item_broker,
                            mode=mode,
                            source_run_id=source_run_id,
                            params=source_params or {},
                            status="failed",
                            error_message=str(e),
                            run_context=run_context,
                        )
                        write_results_snapshot(
                            results,
                            results_file,
                            latest_results_file=latest_results_file,
                        )
                    if runtime_state is not None and run_id is not None:
                        payload = {
                            "worker_id": worker_id,
                            "symbol": symbol,
                            "broker": item_broker,
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
                metrics = _result_metrics(result, worker_id=worker_id)
                _store_pair_result(
                    results,
                    symbol=symbol,
                    broker=item_broker,
                    mode=mode,
                    source_run_id=source_run_id,
                    params=result.params,
                    status="completed",
                    metrics=metrics,
                    run_context=run_context,
                )
                # Write results incrementally — never lose completed work
                write_results_snapshot(
                    results,
                    results_file,
                    latest_results_file=latest_results_file,
                )

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
    backtest_range: str = "365d",
    raw_args: list[str] | None = None,
    results_label: str | None = None,
    source_params_file: str | None = None,
    source_run_id: str | None = None,
    brokers: list[str] | None = None,
    custom_start_date: str | None = None,
    custom_end_date: str | None = None,
) -> dict:
    """
    Main coordinator: prepares TradingView Desktop tabs, distributes pairs to workers, collects results.
    """
    setup_logging()
    if mode not in VALIDATE_MODES:
        validate_optimizer_pine_contract(logger=log)
    results_file = results_file_for_broker(broker, results_label)
    latest_results_file = results_file_for_broker(broker)
    backtest_range = normalize_backtest_range(backtest_range)
    backtest_range_label = backtest_range_to_label(backtest_range)
    loaded_source_run_id, source_params_by_symbol = load_source_params_file(source_params_file)
    source_run_id = source_run_id or loaded_source_run_id
    selected_brokers = [item.strip().lower() for item in (brokers or [broker]) if item.strip()]
    if mode == "multi_broker_validate":
        invalid = sorted(set(selected_brokers) - SUPPORTED_BROKERS)
        if invalid:
            raise ValueError(f"Unsupported brokers: {', '.join(invalid)}")
    else:
        selected_brokers = [broker]
    if mode in VALIDATE_MODES:
        missing_params = [symbol for symbol in pairs if symbol not in source_params_by_symbol]
        if missing_params:
            log.warning("Skipping pairs missing source params: %s", missing_params)
        pairs = [symbol for symbol in pairs if symbol in source_params_by_symbol]
        if not pairs:
            raise ValueError("No requested pairs have source params")
    run_context = _resume_context(
        mode=mode,
        broker=broker,
        brokers=selected_brokers,
        backtest_range=backtest_range,
        custom_start_date=custom_start_date,
        custom_end_date=custom_end_date,
        source_run_id=source_run_id,
        source_params_by_symbol=source_params_by_symbol,
    )

    log.info(f"Parallel optimizer starting")
    log.info(
        f"  Pairs: {len(pairs)} | Workers: {n_workers} | Mode: {mode} | "
        f"Broker: {broker} | Backtest range: {backtest_range_label}"
    )
    if results_label:
        log.info(f"  Results label: {results_label}")
    if dry_run:
        log.info("  DRY RUN MODE — no real TradingView interaction")

    # Load existing results to skip already-completed pairs
    existing_results = {}
    if results_file.exists():
        try:
            with open(results_file) as f:
                existing_results = json.load(f)
            existing_results = _filter_existing_results_for_context(existing_results, run_context)
            log.info(f"Resuming — {len(existing_results)} pairs already completed")
        except Exception:
            pass

    if mode == "multi_broker_validate":
        remaining_pairs = []
        for symbol in pairs:
            existing_brokers = set((existing_results.get(symbol) or {}).get("brokers") or {})
            for run_broker in selected_brokers:
                if run_broker not in existing_brokers:
                    remaining_pairs.append({"symbol": symbol, "broker": run_broker})
    else:
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
        payload={
            "mode": mode,
            "workers": n_workers,
            "pairs": remaining_pairs,
            "dry_run": dry_run,
            "broker": broker,
            "backtest_range": backtest_range_label,
        },
    )
    emit_event(
        "run_started",
        run_id=run_id,
        mode=mode,
        workers=n_workers,
        pairs=remaining_pairs,
        dry_run=dry_run,
        broker=broker,
        backtest_range=backtest_range_label,
    )

    # Build queue
    pair_queue: asyncio.Queue = asyncio.Queue()
    for pair in remaining_pairs:
        await pair_queue.put(pair)

    start_time = time.time()

    try:
        if dry_run:
            # Dry-run mode never touches a real page; keep it browserless so it works
            # even when Playwright browsers are not installed locally.
            pages = [None] * n_workers
        else:
            controller = OptimizerMcpController()
            workspace_slots = await controller.ensure_optimizer_workspace(
                required_tabs=n_workers,
                bootstrap_symbol=remaining_pairs[0]["symbol"] if isinstance(remaining_pairs[0], dict) else remaining_pairs[0],
                broker=broker,
            )
            pages = _prepare_mcp_backed_pages(workspace_slots)
            if len(pages) != n_workers:
                raise RuntimeError(
                    "Requested "
                    f"{n_workers} worker(s) but MCP prepared {len(pages)} "
                    "TradingView Desktop session(s)"
                )
            log.info("Prepared %d TradingView Desktop MCP session(s)", len(pages))

        # Stagger worker starts to avoid race conditions
        tasks = []
        for i, page in enumerate(pages):
            if i > 0:
                await asyncio.sleep(WORKER_STARTUP_DELAY)
            task = asyncio.create_task(
                worker_task(
                    worker_id=i,
                    page=page,
                    pair_queue=pair_queue,
                    results=results,
                    results_file=results_file,
                    latest_results_file=latest_results_file,
                    results_lock=results_lock,
                    error_log=error_log,
                    broker=broker,
                    backtest_range=backtest_range,
                    mode=mode,
                    n_trials=n_trials,
                    dd_limit=dd_limit,
                    dry_run=dry_run,
                    runtime_state=runtime_state,
                    run_id=run_id,
                    source_params_by_symbol=source_params_by_symbol,
                    source_run_id=source_run_id,
                    custom_start_date=custom_start_date,
                    custom_end_date=custom_end_date,
                    run_context=run_context,
                ),
                name=f"worker-{i}",
            )
            tasks.append(task)

        task_results = await asyncio.gather(*tasks, return_exceptions=True)
        for task_result in task_results:
            if isinstance(task_result, Exception):
                error_log.append({"symbol": "worker_task", "worker": -1, "error": str(task_result)})
    except Exception:
        runtime_state.set_run_state(run_id=run_id, state="failed")
        raise

    elapsed = time.time() - start_time
    status_counts: dict[str, int] = {}
    for value in results.values():
        if isinstance(value, dict):
            status = str(value.get("status") or "unknown")
            status_counts[status] = status_counts.get(status, 0) + 1
    completed_count = status_counts.get("completed", 0)
    skipped_count = status_counts.get("skipped", 0)
    failed_result_count = status_counts.get("failed", 0)
    final_state = (
        "failed"
        if completed_count == 0 and (error_log or skipped_count or failed_result_count)
        else "completed"
    )
    runtime_state.set_run_state(run_id=run_id, state=final_state)
    output_paths = {
        "results_file": str(results_file),
        "latest_results_file": str(latest_results_file),
        "legacy_results_file": str(LEGACY_PARALLEL_RESULTS_FILE),
    }
    log.info(f"\n{'='*60}")
    log.info(f"Parallel run complete in {elapsed:.1f}s")
    log.info(f"  Completed: {completed_count} pairs")
    if skipped_count:
        log.info(f"  Skipped: {skipped_count} pairs")
    log.info(f"  Failed: {len(error_log) + failed_result_count} pairs")
    if error_log:
        log.warning(f"  Failed pairs: {[e['symbol'] for e in error_log]}")
    log.info(f"  Results: {results_file}")
    if latest_results_file != results_file:
        log.info(f"  Latest snapshot: {latest_results_file}")

    # Generate HTML report from parallel results
    completed_results = {
        symbol: data
        for symbol, data in results.items()
        if isinstance(data, dict) and data.get("status") == "completed"
    }
    if completed_results and mode != "multi_broker_validate":
        try:
            from .report import generate_html_report

            best_per_pair: dict[str, BacktestResult] = {}
            for symbol, data in completed_results.items():
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
            "status": final_state,
            "output_paths": output_paths,
            "error_count": len(error_log),
        },
    )
    emit_event(
        "run_finished",
        run_id=run_id,
        status=final_state,
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
    parser.add_argument("--mode", choices=["bayesian", "smart", "fast", "full", "validate", "multi_broker_validate"], default="bayesian")
    parser.add_argument("--trials", type=int, default=N_BAYESIAN_TRIALS, help="Optuna trials per pair")
    parser.add_argument("--dd-limit", type=float, default=PROP_FIRM_MAX_DD_PCT, help="Max drawdown percent")
    parser.add_argument("--pairs", type=str, help="Comma-separated list of pairs (default: all)")
    parser.add_argument("--broker", choices=sorted(SUPPORTED_BROKERS), default="vantage", help="Broker dataset namespace")
    parser.add_argument(
        "--backtest-range",
        choices=["30d", "90d", "365d", "all", "custom"],
        default="365d",
        help="TradingView backtest window preset or custom",
    )
    parser.add_argument("--custom-start-date", type=str, help="Custom backtest start date (YYYY-MM-DD)")
    parser.add_argument("--custom-end-date", type=str, help="Custom backtest end date (YYYY-MM-DD)")
    parser.add_argument("--source-run-id", type=str, help="Source optimizer run for validate modes")
    parser.add_argument("--source-params-file", type=str, help="JSON file containing source params by pair")
    parser.add_argument("--brokers", type=str, help="Comma-separated brokers for multi_broker_validate")
    parser.add_argument("--results-label", type=str, help="Optional run-specific suffix for the results filename")
    parser.add_argument("--dry-run", action="store_true", help="Test with fake results (2 pairs, 2 trials)")
    parser.add_argument("--reset", action="store_true", help="Clear existing results and start fresh")
    args = parser.parse_args()

    results_file = results_file_for_broker(args.broker, args.results_label)
    latest_results_file = results_file_for_broker(args.broker)

    if args.reset and results_file.exists():
        results_file.unlink()
        if latest_results_file != results_file and latest_results_file.exists():
            latest_results_file.unlink()
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
        backtest_range=args.backtest_range,
        raw_args=sys.argv[1:],
        results_label=args.results_label,
        source_params_file=args.source_params_file,
        source_run_id=args.source_run_id,
        brokers=[item.strip() for item in args.brokers.split(",")] if args.brokers else None,
        custom_start_date=args.custom_start_date,
        custom_end_date=args.custom_end_date,
    ))


if __name__ == "__main__":
    main()
