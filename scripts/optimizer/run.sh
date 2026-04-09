#!/usr/bin/env bash
# run.sh — Launch the optimizer under nohup and tail the log.
#
# Usage (recommended):
#   bash scripts/optimizer/run.sh --bayesian                      # all 33 pairs overnight
#   bash scripts/optimizer/run.sh --bayesian --pairs EURUSD       # single pair
#   bash scripts/optimizer/run.sh --bayesian --pairs EURUSD --n-trials 100
#
# Legacy modes:
#   bash scripts/optimizer/run.sh --fast
#   bash scripts/optimizer/run.sh --smart --pairs EURUSD,XAUUSD
#
# All arguments are forwarded to main.py unchanged.
# Log is written to: scripts/optimization_results/run_TIMESTAMP.log
# Ctrl-C detaches from the log — optimizer keeps running in background.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
RESULTS_DIR="$PROJECT_ROOT/scripts/optimization_results"

# ── Create output dir ──────────────────────────────────────────────────────────
mkdir -p "$RESULTS_DIR"

# ── Find and activate venv ────────────────────────────────────────────────────
# Check candidate locations in order of preference
VENV_PYTHON=""
for candidate in \
    "$PROJECT_ROOT/venv/bin/python3" \
    "$PROJECT_ROOT/.venv/bin/python3" \
    "/workspace/.venv/bin/python3"; do
    if [[ -x "$candidate" ]]; then
        VENV_PYTHON="$candidate"
        break
    fi
done

if [[ -n "$VENV_PYTHON" ]]; then
    VENV_DIR="$(dirname "$(dirname "$VENV_PYTHON")")"
    # shellcheck disable=SC1091
    source "$VENV_DIR/bin/activate"
    echo "[run.sh] venv activated: $VENV_DIR"
    PYTHON="$VENV_PYTHON"
else
    # Try to use whichever python3 has playwright installed
    for py in python3.11 python3.12 python3.13 python3 python; do
        if command -v "$py" &>/dev/null; then
            if "$py" -c "import playwright" 2>/dev/null; then
                PYTHON="$(command -v "$py")"
                echo "[run.sh] Using $PYTHON (has playwright)"
                break
            fi
        fi
    done

    if [[ -z "${PYTHON:-}" ]]; then
        echo ""
        echo "[run.sh] ERROR: Could not find a Python with playwright installed."
        echo "  Fix: cd $PROJECT_ROOT && python3 -m venv venv && venv/bin/pip install playwright"
        exit 1
    fi
fi

# ── Build log filename ─────────────────────────────────────────────────────────
TIMESTAMP="$(date +%Y%m%d_%H%M%S)"
LOG_FILE="$RESULTS_DIR/run_${TIMESTAMP}.log"

echo "[run.sh] Starting optimizer at $(date)"
echo "[run.sh] Python: $PYTHON"
echo "[run.sh] Log: $LOG_FILE"
echo "[run.sh] Args: $*"
echo ""

# ── Prevent macOS from sleeping ───────────────────────────────────────────────
# caffeinate -i keeps the system awake as long as the optimizer is running.
# It exits automatically when the optimizer finishes.
if command -v caffeinate &>/dev/null; then
    LAUNCHER="caffeinate -i"
    echo "[run.sh] Sleep prevention: caffeinate enabled (Mac won't sleep during run)"
else
    LAUNCHER=""
    echo "[run.sh] Warning: caffeinate not found — Mac may sleep during long runs"
fi

# ── Launch under nohup ────────────────────────────────────────────────────────
# Run as a Python *module* so relative imports in the package work correctly.
export PYTHONPATH="$PROJECT_ROOT"
export _OPTIMIZER_VENV_ACTIVE=1   # suppress venv re-exec inside main.py

nohup $LAUNCHER "$PYTHON" -m scripts.optimizer.main "$@" \
    >> "$LOG_FILE" 2>&1 &

PID=$!
echo "[run.sh] Optimizer running as PID $PID"
echo "         To stop:  kill $PID"
echo "         Log file: $LOG_FILE"
echo ""
echo "[run.sh] Tailing log (Ctrl-C to detach — optimizer keeps running):"
echo "─────────────────────────────────────────────────────────────────"

# Tail with a small delay so nohup has time to write the first lines
sleep 1
tail -f "$LOG_FILE"
