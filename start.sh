#!/usr/bin/env bash
set -e

# Use Railway's PORT (default 8000 for local)
export PORT="${PORT:-8000}"

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT_DIR"
export PYTHONPATH="$ROOT_DIR"

# Use virtual environment if it exists (Railway deployment)
if [ -d "/app/venv" ]; then
  export PATH="/app/venv/bin:$PATH"
fi

WORKER_PID=""
UVICORN_PID=""

shutdown() {
  echo "[start.sh] Shutting down (SIGTERM/SIGINT)..."
  [ -n "$WORKER_PID" ] && kill "$WORKER_PID" 2>/dev/null || true
  [ -n "$UVICORN_PID" ] && kill "$UVICORN_PID" 2>/dev/null || true
  wait "$WORKER_PID" 2>/dev/null || true
  wait "$UVICORN_PID" 2>/dev/null || true
  exit 0
}

trap shutdown SIGTERM SIGINT

echo "[start.sh] Starting API (Producer)..."
python3 -m uvicorn backend.main:app --host 0.0.0.0 --port "$PORT" &
UVICORN_PID=$!

echo "[start.sh] Starting Worker (Consumer)..."
python3 -m backend.worker &
WORKER_PID=$!

# Wait for uvicorn (primary); if it exits, bring down worker too
wait $UVICORN_PID
shutdown
