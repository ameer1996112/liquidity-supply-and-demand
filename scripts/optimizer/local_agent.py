#!/usr/bin/env python3
"""
local_agent.py — Polling-based local agent for TradingView automation.

Runs on your Mac, polls the Railway backend for queued optimizer runs or
queued alert batches, auto-launches Chrome with CDP, executes the selected
runner, and reports progress.

Usage:
    python -m scripts.optimizer.local_agent

Requires ADMIN_API_KEY and API_URL in .env (or environment variables).
"""

import asyncio
import json
import logging
import os
import signal
import ssl
import subprocess
import sys
import time
import threading
from pathlib import Path
from typing import Any
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError

try:
    import certifi
    _SSL_CTX = ssl.create_default_context(cafile=certifi.where())
except ImportError:
    _SSL_CTX = ssl.create_default_context()

# ── Config ───────────────────────────────────────────────────────────────────

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DOTENV_PATH = PROJECT_ROOT / ".env"

POLL_INTERVAL = 10        # seconds between queue checks
HEARTBEAT_INTERVAL = 30   # seconds between heartbeat pings
CANCEL_CHECK_INTERVAL = 5 # seconds between cancel checks during a run
CHROME_LAUNCH_TIMEOUT = 15
CDP_PORT = 9222
AGENT_VERSION = "1.0.0"
LOCAL_AGENT_TARGET = os.environ.get("LOCAL_AGENT_TARGET", "both").strip().lower()
ALERT_AGENT_TARGETS = {"alert", "alert-setup", "alerts"}
OPTIMIZER_AGENT_TARGETS = {"optimizer", "optimize", "runs"}
OPTIMIZER_RUN_BLOCKED_BACKOFF_SECONDS = 60.0

log = logging.getLogger("optimizer-agent")

_optimizer_run_blocked_events: dict[str, tuple[str, float]] = {}

from scripts.optimizer.alert_runner import (  # noqa: E402
    AlertBatchCancelled,
    AlertBatchRunner,
    TradingViewAlertBrowser,
    TradingViewMcpAlertRunner,
    load_batch_from_api_payload,
)
from scripts.optimizer.optimizer_mcp import OptimizerMcpController  # noqa: E402

# ── Env loading ──────────────────────────────────────────────────────────────


def _maybe_reexec_into_venv() -> None:
    """Prefer repo venv interpreter so playwright/deps resolve consistently."""
    if "PYTEST_CURRENT_TEST" in os.environ or "pytest" in Path(sys.argv[0]).name:
        return
    if os.environ.get("_OPTIMIZER_VENV_ACTIVE") == "1":
        return

    venv_py = PROJECT_ROOT / "venv" / "bin" / "python3"
    if not venv_py.exists():
        return

    current = Path(sys.executable).resolve()
    target = venv_py.resolve()
    if current == target:
        os.environ["_OPTIMIZER_VENV_ACTIVE"] = "1"
        return

    os.environ["_OPTIMIZER_VENV_ACTIVE"] = "1"
    os.environ["PYTHONPATH"] = os.environ.get("PYTHONPATH") or str(PROJECT_ROOT)
    os.execv(str(target), [str(target), "-m", "scripts.optimizer.local_agent", *sys.argv[1:]])


def _load_env() -> None:
    """Load .env file into os.environ (minimal, no dependencies)."""
    if not DOTENV_PATH.exists():
        return
    for line in DOTENV_PATH.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key not in os.environ:
            os.environ[key] = value


_load_env()
_maybe_reexec_into_venv()

API_URL = (
    os.environ.get("API_URL")
    or os.environ.get("BACKEND_URL")
    or os.environ.get("NEXT_PUBLIC_API_URL")
    or ""
).rstrip("/")
ADMIN_KEY = os.environ.get("ADMIN_API_KEY", "")

if not API_URL:
    print("ERROR: API_URL not set. Add to .env:")
    print('  API_URL="https://grand-learning-production-bc96.up.railway.app"')
    sys.exit(1)
if not ADMIN_KEY:
    print("ERROR: ADMIN_API_KEY not set in .env")
    sys.exit(1)


# ── HTTP helpers ─────────────────────────────────────────────────────────────


def _api(method: str, path: str, body: dict | None = None) -> dict | None:
    """Minimal HTTP helper — no dependencies beyond stdlib."""
    url = f"{API_URL}{path}"
    data = json.dumps(body).encode() if body else None
    req = Request(url, data=data, method=method)
    req.add_header("Content-Type", "application/json")
    req.add_header("X-Admin-API-Key", ADMIN_KEY)
    try:
        with urlopen(req, timeout=15, context=_SSL_CTX) as resp:
            return json.loads(resp.read().decode())
    except HTTPError as e:
        # Log response body for fast diagnosis (admin-only endpoints).
        try:
            body = e.read().decode(errors="replace")
        except Exception:
            body = ""
        snippet = body[:800].replace("\n", " ").strip()
        log.warning("API %s %s failed: HTTP %s %s", method, path, getattr(e, "code", "?"), snippet)
        return None
    except URLError as e:
        log.warning("API %s %s failed: %s", method, path, e)
        return None
    except Exception as e:
        log.warning("API %s %s error: %s", method, path, e)
        return None


def api_get(path: str) -> dict | None:
    return _api("GET", path)


def api_post(path: str, body: dict | None = None) -> dict | None:
    return _api("POST", path, body)


def api_patch(path: str, body: dict) -> dict | None:
    return _api("PATCH", path, body)


def _should_poll_alert_batches() -> bool:
    return LOCAL_AGENT_TARGET in ALERT_AGENT_TARGETS or LOCAL_AGENT_TARGET == "both"


def _should_poll_optimizer_runs() -> bool:
    return LOCAL_AGENT_TARGET in OPTIMIZER_AGENT_TARGETS or LOCAL_AGENT_TARGET == "both"


def _playwright_available() -> bool:
    try:
        import playwright.async_api  # noqa: F401
        return True
    except Exception:
        return False


def _normalize_broker(value: str | None) -> str:
    normalized = (value or "vantage").strip().lower()
    if normalized not in {"vantage", "oanda", "fxcm"}:
        raise ValueError(f"Unsupported broker: {value}")
    return normalized


def _should_report_optimizer_run_blocked(run_id: str, reason: str) -> bool:
    last_reason, last_reported_at = _optimizer_run_blocked_events.get(run_id, (None, 0.0))
    now = time.monotonic()
    if reason != last_reason or now - last_reported_at >= OPTIMIZER_RUN_BLOCKED_BACKOFF_SECONDS:
        _optimizer_run_blocked_events[run_id] = (reason, now)
        return True
    return False


def _report_optimizer_run_blocked(run_id: str, reason: str, *, workers: int, dry_run: bool) -> None:
    """Record a non-terminal optimizer readiness blocker for diagnostics."""
    if not _should_report_optimizer_run_blocked(run_id, reason):
        log.debug("Suppressing duplicate optimizer blocked event for run %s: %s", run_id, reason)
        return

    log.warning("Optimizer run %s is not ready yet: %s", run_id, reason)
    api_post(
        f"/api/optimizer/runs/{run_id}/events",
        {
            "event_type": "log",
            "payload": {
                "level": "warning",
                "message": reason,
                "status": "queued",
                "workers": workers,
                "dry_run": dry_run,
                "python": sys.executable,
            },
        },
    )


async def _ensure_optimizer_run_ready(workers: int) -> tuple[bool, str]:
    """Check the local optimizer prereqs needed before claiming a run.

    This probe must stay read-only: it should never open new TradingView tabs
    while deciding whether to claim a queued optimizer run.
    """
    if not _playwright_available():
        return (
            False,
            "playwright not installed on local agent python. "
            "Install in venv: python3 -m pip install playwright && python3 -m playwright install chromium",
        )

    controller = OptimizerMcpController()
    try:
        await controller.ensure_ready()
        tabs = await controller._list_workspace_tabs()
    except Exception as exc:
        return False, str(exc)

    available_tabs = max(len(tabs), 0)
    if available_tabs < workers:
        return (
            False,
            f"TradingView MCP currently exposes {available_tabs} tab(s); requested {workers}",
        )
    return True, ""


# ── Chrome management ────────────────────────────────────────────────────────


def chrome_is_alive() -> bool:
    """Check if Chrome CDP is reachable on the expected port."""
    try:
        req = Request(f"http://127.0.0.1:{CDP_PORT}/json/version")
        with urlopen(req, timeout=3) as resp:  # localhost, no SSL needed
            return resp.status == 200
    except Exception:
        return False


def launch_chrome() -> bool:
    """Launch Chrome via start-chrome.sh and wait for CDP to be ready."""
    script = PROJECT_ROOT / "scripts" / "optimizer" / "start-chrome.sh"
    if not script.exists():
        log.error("start-chrome.sh not found at %s", script)
        return False

    log.info("Launching Chrome with CDP on port %d...", CDP_PORT)
    try:
        subprocess.Popen(
            ["bash", str(script)],
            cwd=str(PROJECT_ROOT),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except Exception as e:
        log.error("Failed to launch Chrome: %s", e)
        return False

    # Wait for CDP to be ready
    for _ in range(CHROME_LAUNCH_TIMEOUT):
        time.sleep(1)
        if chrome_is_alive():
            log.info("Chrome CDP ready on port %d", CDP_PORT)
            return True

    log.error("Chrome CDP not ready after %ds", CHROME_LAUNCH_TIMEOUT)
    return False


def ensure_chrome() -> bool:
    """Ensure Chrome CDP is running, launching if needed."""
    if chrome_is_alive():
        return True
    return launch_chrome()


# ── Heartbeat ────────────────────────────────────────────────────────────────


def heartbeat_loop(stop_event: threading.Event) -> None:
    """Send periodic heartbeats to the backend."""
    while not stop_event.is_set():
        try:
            desktop_ready = chrome_is_alive()
            api_post("/api/optimizer/agent/heartbeat", {
                "desktop_ready": desktop_ready,
                "chrome_ready": desktop_ready,
                "agent_version": AGENT_VERSION,
            })
        except Exception as e:
            log.debug("Heartbeat failed: %s", e)
        stop_event.wait(HEARTBEAT_INTERVAL)


# ── Run execution ────────────────────────────────────────────────────────────


def execute_run(run: dict) -> None:
    """Execute a single optimizer run."""
    run_id = run["id"]
    mode = run.get("mode", "bayesian")
    workers = run.get("workers", 3)
    pairs = run.get("pairs", [])
    n_trials = run.get("n_trials", 25)
    dd_limit = run.get("dd_limit", 6.0)
    dry_run = run.get("dry_run", False)
    broker = _normalize_broker(run.get("broker"))
    backtest_range = str(run.get("backtest_range") or "365d").strip().lower()

    log.info("=" * 60)
    log.info("Picked up run %s", run_id)
    log.info("  mode=%s workers=%d trials=%d dd_limit=%.1f dry_run=%s backtest_range=%s",
             mode, workers, n_trials, dd_limit, dry_run, backtest_range)
    log.info("  pairs=%s", ",".join(pairs))
    log.info("=" * 60)

    if not dry_run:
        ready, reason = asyncio.run(_ensure_optimizer_run_ready(workers))
        if not ready:
            _report_optimizer_run_blocked(run_id, reason, workers=workers, dry_run=dry_run)
            return

    # Mark run as running
    api_patch(f"/api/optimizer/runs/{run_id}", {"status": "running"})
    api_post(f"/api/optimizer/runs/{run_id}/events", {
        "event_type": "run_started",
        "payload": {
            "mode": mode,
            "workers": workers,
            "broker": broker,
            "backtest_range": backtest_range,
            "agent_version": AGENT_VERSION,
        },
    })

    # Build command
    command = [
        sys.executable, "-m", "scripts.optimizer.parallel_runner",
        "--workers", str(workers),
        "--mode", mode,
        "--trials", str(n_trials),
        "--dd-limit", str(dd_limit),
        "--pairs", ",".join(pairs),
        "--broker", broker,
        "--backtest-range", backtest_range,
        "--results-label", run_id,
    ]
    if dry_run:
        command.append("--dry-run")

    env = {**os.environ, "PYTHONPATH": os.environ.get("PYTHONPATH", "."), "PYTHONUNBUFFERED": "1"}

    log.info("Spawning: %s", " ".join(command))
    process = subprocess.Popen(
        command,
        cwd=str(PROJECT_ROOT),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
        env=env,
    )

    # Monitor subprocess output + check for cancellation
    cancelled = False
    try:
        _stream_and_report(run_id, process)
    except _RunCancelled:
        cancelled = True
        log.info("Run %s cancelled by user", run_id)
        process.terminate()
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()

    exit_code = process.wait()

    if cancelled:
        # Status already set to cancelled by the backend
        return

    # Check if the backend already set a terminal status (e.g. via run_finished event)
    current = api_get(f"/api/optimizer/runs/{run_id}")
    if current and current.get("status") in {"completed", "failed", "cancelled"}:
        log.info("Run %s already has terminal status: %s", run_id, current["status"])
        return

    final_status = "completed" if exit_code == 0 else "failed"
    api_patch(f"/api/optimizer/runs/{run_id}", {"status": final_status})
    log.info("Run %s finished with status: %s (exit code %d)", run_id, final_status, exit_code)


def _report_alert_event(batch_id: str, event_type: str, pair: str | None = None, payload: dict[str, Any] | None = None) -> None:
    payload = payload or {}
    api_post(
        f"/api/alert-setup/batches/{batch_id}/events",
        {
            "event_type": event_type,
            "pair": pair,
            "payload": payload,
        },
    )
    if event_type == "pair_started" and pair:
        api_patch(
            f"/api/alert-setup/batches/{batch_id}/results/{pair}",
            {"status": "running"},
        )
    elif event_type == "alert_created" and pair:
        updates = {
            "alert_name": payload.get("alert_name"),
            "alert_id": payload.get("alert_id"),
            "config_snapshot": payload.get("config_snapshot"),
            "params": (payload.get("config_snapshot") or {}).get("params")
            if isinstance(payload.get("config_snapshot"), dict)
            else None,
        }
        api_patch(
            f"/api/alert-setup/batches/{batch_id}/results/{pair}",
            {k: v for k, v in updates.items() if v is not None},
        )
    elif event_type == "pair_completed" and pair:
        skipped_existing = bool(payload.get("skipped_existing"))
        updates = {
            "status": "skipped" if skipped_existing else "created",
            "alert_name": payload.get("alert_name"),
            "alert_id": payload.get("alert_id"),
            "config_snapshot": payload.get("config_snapshot"),
            "params": payload.get("params"),
            "error_message": None,
        }
        api_patch(
            f"/api/alert-setup/batches/{batch_id}/results/{pair}",
            {k: v for k, v in updates.items() if v is not None},
        )
    elif event_type == "pair_failed" and pair:
        api_patch(
            f"/api/alert-setup/batches/{batch_id}/results/{pair}",
            {
                "status": "failed",
                "error_message": payload.get("error_message"),
            },
        )
    elif event_type in {"batch_finished", "batch_cancelled"}:
        status = payload.get("status") or ("cancelled" if event_type == "batch_cancelled" else "completed")
        api_patch(
            f"/api/alert-setup/batches/{batch_id}",
            {
                "status": status,
                "summary": payload.get("summary") or {},
            },
        )


async def _execute_alert_batch(batch: dict[str, Any], stop_event: threading.Event) -> None:
    batch = load_batch_from_api_payload(batch)
    batch_id = batch["id"]
    source_mode = batch.get("source_mode", "approved")
    timeframe = batch.get("timeframe")
    pairs = batch.get("pairs") or []
    if not pairs:
        raise ValueError("alert batch must include at least one pair")

    log.info("=" * 60)
    log.info("Picked up alert batch %s", batch_id)
    log.info("  source_mode=%s timeframe=%s pairs=%s", source_mode, timeframe, ",".join(pairs))
    log.info("=" * 60)

    if not ensure_chrome():
        log.error("Cannot start alert batch — Chrome CDP not available")
        api_patch(
            f"/api/alert-setup/batches/{batch_id}",
            {
                "status": "failed",
                "summary": {"error_message": "Chrome CDP not available on local machine"},
            },
        )
        api_post(
            f"/api/alert-setup/batches/{batch_id}/events",
            {
                "event_type": "batch_finished",
                "payload": {
                    "message": "Chrome CDP not available",
                    "status": "failed",
                    "summary": {"error_message": "Chrome CDP not available on local machine"},
                },
            },
        )
        return

    playwright_ready = _playwright_available()
    mcp_ready, mcp_reason = await TradingViewMcpAlertRunner.healthcheck()
    if not mcp_ready and not playwright_ready:
        message = (
            "Neither TradingView MCP nor Playwright alert automation is available. "
            f"MCP health: {mcp_reason}. "
            "To enable fallback install Playwright in the venv: "
            "python3 -m pip install playwright && python3 -m playwright install chromium"
        )
        log.error("Cannot start alert batch — %s", message)
        api_patch(
            f"/api/alert-setup/batches/{batch_id}",
            {
                "status": "failed",
                "summary": {
                    "error_message": message,
                    "python": sys.executable,
                    "total_pairs": len(pairs),
                    "pending_pairs": len(pairs),
                    "running_pairs": 0,
                    "completed_pairs": 0,
                    "failed_pairs": 0,
                    "cancelled_pairs": 0,
                    "created_alerts": 0,
                },
            },
        )
        api_post(
            f"/api/alert-setup/batches/{batch_id}/events",
            {
                "event_type": "batch_finished",
                "payload": {
                    "message": message,
                    "status": "failed",
                    "summary": {"error_message": message, "python": sys.executable},
                },
            },
        )
        return

    api_patch(f"/api/alert-setup/batches/{batch_id}", {"status": "running"})
    api_post(
        f"/api/alert-setup/batches/{batch_id}/events",
        {
            "event_type": "log",
            "payload": {
                "message": f"Alert runner picked up batch {batch_id}",
                "source_mode": source_mode,
                "timeframe": timeframe,
                "pairs": pairs,
                "preferred_backend": "mcp" if mcp_ready else "playwright",
                "playwright_ready": playwright_ready,
                "mcp_ready": mcp_ready,
                "mcp_reason": mcp_reason,
            },
        },
    )

    if mcp_ready:
        runner = AlertBatchRunner(
            browser_factory=lambda: TradingViewMcpAlertRunner(
                fallback_factory=(lambda: TradingViewAlertBrowser(chrome_port=CDP_PORT))
                if playwright_ready
                else None,
            )
        )
    else:
        runner = AlertBatchRunner(
            browser_factory=lambda: TradingViewAlertBrowser(chrome_port=CDP_PORT)
        )

    def should_stop() -> bool:
        if stop_event.is_set():
            return True
        current = api_get(f"/api/alert-setup/batches/{batch_id}")
        return bool(current and current.get("status") == "cancelled")

    def emit_event(event_type: str, pair: str | None, payload: dict[str, Any]) -> None:
        _report_alert_event(batch_id, event_type, pair=pair, payload=payload)

    try:
        await runner.run(batch, emit_event=emit_event, should_stop=should_stop)
    except AlertBatchCancelled:
        api_post(
            f"/api/alert-setup/batches/{batch_id}/events",
            {
                "event_type": "batch_finished",
                "payload": {
                    "status": "cancelled",
                    "summary": {"error_message": "cancelled by user"},
                },
            },
        )
        api_patch(
            f"/api/alert-setup/batches/{batch_id}",
            {
                "status": "cancelled",
                "summary": {"error_message": "cancelled by user"},
            },
        )
        return
    except Exception as e:
        log.error("Alert batch %s failed: %s", batch_id, e, exc_info=True)
        api_post(
            f"/api/alert-setup/batches/{batch_id}/events",
            {
                "event_type": "batch_finished",
                "payload": {
                    "status": "failed",
                    "summary": {"error_message": str(e)},
                },
            },
        )
        api_patch(
            f"/api/alert-setup/batches/{batch_id}",
            {
                "status": "failed",
                "summary": {"error_message": str(e)},
            },
        )
        return


class _RunCancelled(Exception):
    pass


def _stream_and_report(run_id: str, process: subprocess.Popen) -> None:
    """Read process stdout line by line, parse events, push to API."""
    import select

    last_cancel_check = time.time()

    while process.poll() is None:
        # Use select to avoid blocking forever — check cancel periodically
        if process.stdout is None:
            break
        ready, _, _ = select.select([process.stdout], [], [], CANCEL_CHECK_INTERVAL)

        if ready:
            line = process.stdout.readline()
            if not line:
                break
            line = line.strip()
            if not line:
                continue
            _process_line(run_id, line)

        # Periodic cancel check
        now = time.time()
        if now - last_cancel_check >= CANCEL_CHECK_INTERVAL:
            last_cancel_check = now
            run = api_get(f"/api/optimizer/runs/{run_id}")
            if run and run.get("status") == "cancelled":
                raise _RunCancelled()

    # Drain remaining output
    if process.stdout:
        for raw_line in process.stdout:
            line = raw_line.strip()
            if line:
                _process_line(run_id, line)


def _process_line(run_id: str, line: str) -> None:
    """Parse a single line of optimizer output and push to API."""
    def _safe_post_event(body: dict[str, Any]) -> None:
        try:
            api_post(f"/api/optimizer/runs/{run_id}/events", body)
        except Exception as exc:
            log.warning("Failed to forward optimizer run output for run %s: %s", run_id, exc)

    try:
        event = json.loads(line)
    except json.JSONDecodeError:
        # Plain log line
        log.info("[run %s] %s", run_id, line)
        _safe_post_event({
            "event_type": "log",
            "payload": {"message": line},
        })
        return

    if not isinstance(event, dict) or "event_type" not in event:
        log.info("[run %s] %s", run_id, line)
        _safe_post_event({
            "event_type": "log",
            "payload": {"message": line},
        })
        return

    event_type = event["event_type"]
    symbol = event.get("symbol")
    worker_id = event.get("worker_id")
    log_payload = {k: v for k, v in event.items() if k not in {"event_type", "run_id"}}

    if event_type in {"pair_failed", "run_finished"}:
        log.error("[run %s] %s %s", run_id, event_type, log_payload)
    else:
        log.info("[run %s] %s %s", run_id, event_type, log_payload)

    # Push event to timeline
    _safe_post_event({
        "event_type": event_type,
        "worker_id": worker_id,
        "symbol": symbol,
        "payload": log_payload,
    })

    # Update per-symbol results
    if event_type == "pair_started" and symbol:
        api_patch(f"/api/optimizer/runs/{run_id}/results/{symbol}", {
            "status": "running",
        })
    elif event_type == "pair_completed" and symbol:
        api_patch(f"/api/optimizer/runs/{run_id}/results/{symbol}", {
            "status": "completed",
            "params": event.get("params"),
            "metrics": event.get("metrics"),
        })
    elif event_type == "pair_failed" and symbol:
        api_patch(f"/api/optimizer/runs/{run_id}/results/{symbol}", {
            "status": "failed",
            "error_message": event.get("error_message"),
        })
    elif event_type == "run_finished":
        status = event.get("status", "completed")
        api_patch(f"/api/optimizer/runs/{run_id}", {
            "status": status,
            "summary": {"output_paths": event.get("output_paths", {})},
        })


# ── Main loop ────────────────────────────────────────────────────────────────


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
        datefmt="%H:%M:%S",
    )

    log.info("╔══════════════════════════════════════════════════╗")
    log.info("║  Local Agent v%s                               ║", AGENT_VERSION)
    log.info("║  API: %s", API_URL)
    if LOCAL_AGENT_TARGET == "both":
        log.info("║  Target: optimizer + alert setup                ║")
    elif _should_poll_alert_batches():
        log.info("║  Target: alert setup batches                    ║")
    else:
        log.info("║  Target: optimizer runs                         ║")
    log.info("║  Polling every %ds for queued runs              ║", POLL_INTERVAL)
    log.info("╚══════════════════════════════════════════════════╝")

    # Start heartbeat thread
    stop_event = threading.Event()
    heartbeat_thread = threading.Thread(
        target=heartbeat_loop,
        args=(stop_event,),
        daemon=True,
        name="heartbeat",
    )
    heartbeat_thread.start()

    # Handle graceful shutdown
    def _shutdown(signum, frame):
        log.info("Shutting down agent...")
        stop_event.set()
        sys.exit(0)

    signal.signal(signal.SIGINT, _shutdown)
    signal.signal(signal.SIGTERM, _shutdown)

    # Main poll loop
    while not stop_event.is_set():
        try:
            if _should_poll_alert_batches():
                resp = api_get("/api/alert-setup/batches?status=queued&limit=1")
                batches = (resp or {}).get("batches", [])
                if batches:
                    batch = batches[0]
                    asyncio.run(_execute_alert_batch(batch, stop_event))
                    stop_event.wait(POLL_INTERVAL)
                    continue
                elif LOCAL_AGENT_TARGET in ALERT_AGENT_TARGETS:
                    log.debug("No queued alert batches")

            if _should_poll_optimizer_runs():
                resp = api_get("/api/optimizer/runs?status=queued&limit=1")
                runs = (resp or {}).get("runs", [])

                if runs:
                    run = runs[0]  # Oldest queued run
                    execute_run(run)
                else:
                    log.debug("No queued runs")
        except Exception as e:
            log.error("Poll loop error: %s", e, exc_info=True)

        stop_event.wait(POLL_INTERVAL)


if __name__ == "__main__":
    main()
