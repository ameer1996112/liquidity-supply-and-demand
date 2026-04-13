#!/usr/bin/env python3
"""
local_agent.py — Polling-based local agent for the TradingView optimizer.

Runs on your Mac, polls the Railway backend for queued optimizer runs,
auto-launches Chrome with CDP, executes the optimizer, and reports progress.

Usage:
    python -m scripts.optimizer.local_agent

Requires ADMIN_API_KEY and API_URL in .env (or environment variables).
"""

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
from urllib.request import Request, urlopen
from urllib.error import URLError

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

log = logging.getLogger("optimizer-agent")

# ── Env loading ──────────────────────────────────────────────────────────────


def _maybe_reexec_into_venv() -> None:
    """Prefer repo venv interpreter so playwright/deps resolve consistently."""
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
            api_post("/api/optimizer/agent/heartbeat", {
                "chrome_ready": chrome_is_alive(),
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

    log.info("=" * 60)
    log.info("Picked up run %s", run_id)
    log.info("  mode=%s workers=%d trials=%d dd_limit=%.1f dry_run=%s",
             mode, workers, n_trials, dd_limit, dry_run)
    log.info("  pairs=%s", ",".join(pairs))
    log.info("=" * 60)

    # Ensure Chrome is ready (unless dry run)
    if not dry_run:
        # Preflight: runner requires playwright in the current interpreter.
        try:
            import playwright.async_api  # noqa: F401
        except Exception:
            log.error("Cannot start run — playwright not installed in agent python (%s)", sys.executable)
            api_patch(
                f"/api/optimizer/runs/{run_id}",
                {
                    "status": "failed",
                    "summary": {
                        "error_message": "playwright not installed on local agent. Install in venv: python3 -m pip install playwright && python3 -m playwright install chromium",
                    },
                },
            )
            api_post(
                f"/api/optimizer/runs/{run_id}/events",
                {
                    "event_type": "run_finished",
                    "payload": {
                        "message": "playwright missing on local agent python",
                        "status": "failed",
                        "python": sys.executable,
                    },
                },
            )
            return

        if not ensure_chrome():
            log.error("Cannot start run — Chrome CDP not available")
            api_patch(f"/api/optimizer/runs/{run_id}", {
                "status": "failed",
                "summary": {"error_message": "Chrome CDP not available on local machine"},
            })
            api_post(f"/api/optimizer/runs/{run_id}/events", {
                "event_type": "run_finished",
                "payload": {"message": "Chrome CDP not available", "status": "failed"},
            })
            return

    # Mark run as running
    api_patch(f"/api/optimizer/runs/{run_id}", {"status": "running"})
    api_post(f"/api/optimizer/runs/{run_id}/events", {
        "event_type": "run_started",
        "payload": {"mode": mode, "workers": workers, "agent_version": AGENT_VERSION},
    })

    # Build command
    command = [
        sys.executable, "-m", "scripts.optimizer.parallel_runner",
        "--workers", str(workers),
        "--mode", mode,
        "--trials", str(n_trials),
        "--dd-limit", str(dd_limit),
        "--pairs", ",".join(pairs),
    ]
    if dry_run:
        command.append("--dry-run")

    env = {**os.environ, "PYTHONPATH": os.environ.get("PYTHONPATH", ".")}

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
    try:
        event = json.loads(line)
    except json.JSONDecodeError:
        # Plain log line
        api_post(f"/api/optimizer/runs/{run_id}/events", {
            "event_type": "log",
            "payload": {"message": line},
        })
        return

    if not isinstance(event, dict) or "event_type" not in event:
        api_post(f"/api/optimizer/runs/{run_id}/events", {
            "event_type": "log",
            "payload": {"message": line},
        })
        return

    event_type = event["event_type"]
    symbol = event.get("symbol")
    worker_id = event.get("worker_id")

    # Push event to timeline
    api_post(f"/api/optimizer/runs/{run_id}/events", {
        "event_type": event_type,
        "worker_id": worker_id,
        "symbol": symbol,
        "payload": {k: v for k, v in event.items() if k not in {"event_type", "run_id"}},
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
    log.info("║  Optimizer Local Agent v%s                    ║", AGENT_VERSION)
    log.info("║  API: %s", API_URL)
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
