#!/usr/bin/env bash
# run.sh — Launch the optimizer under nohup and tail the log.
#
# Usage (recommended — single-process):
#   bash scripts/optimizer/run.sh --bayesian                      # all 33 pairs overnight
#   bash scripts/optimizer/run.sh --bayesian --pairs EURUSD       # single pair
#   bash scripts/optimizer/run.sh --bayesian --pairs EURUSD --n-trials 100
#
# Parallel mode (N browser tabs at once):
#   bash scripts/optimizer/run.sh --parallel --workers 3 --bayesian
#   bash scripts/optimizer/run.sh --parallel --workers 3 --dry-run
#
# Legacy modes:
#   bash scripts/optimizer/run.sh --fast
#   bash scripts/optimizer/run.sh --smart --pairs EURUSD,XAUUSD
#
# All arguments (except --parallel) are forwarded to the chosen module.
# Log is written to: scripts/optimization_results/run_TIMESTAMP.log
# Ctrl-C detaches from the log — optimizer keeps running in background.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
RESULTS_DIR="$PROJECT_ROOT/scripts/optimization_results"

warn_low_space() {
    local path="$1"
    local label="$2"
    local available_kb
    available_kb="$(df -k "$path" | awk 'NR==2 {print $4}')"

    if [[ -z "$available_kb" ]]; then
        return 0
    fi

    # 5 GiB floor so overnight optimizer runs do not die looking "stuck".
    if (( available_kb < 5 * 1024 * 1024 )); then
        local available_gb
        available_gb="$(awk "BEGIN {printf \"%.1f\", $available_kb/1024/1024}")"
        echo "[run.sh] WARNING: Low disk space on $label (${available_gb} GiB free)."
        echo "[run.sh]          Previous optimizer runs failed with '[Errno 28] No space left on device'."
        echo "[run.sh]          Free space before starting a long overnight run."
    fi
}

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

warn_low_space "$PROJECT_ROOT" "project volume"
warn_low_space "$HOME" "home volume"
warn_low_space "/tmp" "tmp volume"

# ── Prevent macOS from sleeping ───────────────────────────────────────────────
# caffeinate flags:
#   -i  prevent idle sleep
#   -d  prevent display sleep (monitor stays on)
#   -s  prevent system sleep on AC power
if command -v caffeinate &>/dev/null; then
    LAUNCHER="caffeinate -ids"
    echo "[run.sh] Sleep prevention: caffeinate -ids (Mac + monitor won't sleep)"
else
    LAUNCHER=""
    echo "[run.sh] Warning: caffeinate not found — Mac may sleep during long runs"
fi

# ── Detect --parallel flag and translate mode shorthands ──────────────────────
# main.py accepts: --bayesian / --smart / --fast / --full
# parallel_runner.py accepts: --mode bayesian|smart|fast|full
# When --parallel is set we translate the shorthand flags automatically.
PARALLEL_MODE=0
RAW_ARGS=()
for arg in "$@"; do
    if [[ "$arg" == "--parallel" ]]; then
        PARALLEL_MODE=1
    else
        RAW_ARGS+=("$arg")
    fi
done

if [[ $PARALLEL_MODE -eq 1 ]]; then
    MODULE="scripts.optimizer.parallel_runner"
    echo "[run.sh] Mode: PARALLEL → $MODULE"
    # Translate --bayesian/--smart/--fast/--full → --mode X
    PASSABLE_ARGS=()
    i=0
    while [[ $i -lt ${#RAW_ARGS[@]} ]]; do
        arg="${RAW_ARGS[$i]}"
        case "$arg" in
            --bayesian) PASSABLE_ARGS+=("--mode" "bayesian") ;;
            --smart)    PASSABLE_ARGS+=("--mode" "smart")    ;;
            --fast)     PASSABLE_ARGS+=("--mode" "fast")     ;;
            --full)     PASSABLE_ARGS+=("--mode" "full")     ;;
            # --n-trials N → --trials N
            --n-trials)
                i=$(( i + 1 ))
                PASSABLE_ARGS+=("--trials" "${RAW_ARGS[$i]}")
                ;;
            *)          PASSABLE_ARGS+=("$arg")              ;;
        esac
        i=$(( i + 1 ))
    done
else
    MODULE="scripts.optimizer.main"
    PASSABLE_ARGS=("${RAW_ARGS[@]}")
    echo "[run.sh] Mode: sequential → $MODULE"
fi

# ── Launch under nohup ────────────────────────────────────────────────────────
# Run as a Python *module* so relative imports in the package work correctly.
export PYTHONPATH="$PROJECT_ROOT"
export _OPTIMIZER_VENV_ACTIVE=1   # suppress venv re-exec inside main.py

nohup $LAUNCHER "$PYTHON" -m "$MODULE" "${PASSABLE_ARGS[@]}" \
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
