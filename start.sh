#!/usr/bin/env bash
set -e

# Use Railway's PORT (default 8000 for local)
export PORT="${PORT:-8000}"

# Set ROOT_DIR - Railway deploys to /app, local dev uses script location
if [ -d "/app/backend" ]; then
  ROOT_DIR="/app"
else
  ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
fi

cd "$ROOT_DIR"
export PYTHONPATH="$ROOT_DIR:$PYTHONPATH"

echo "[start.sh] ROOT_DIR=$ROOT_DIR"
echo "[start.sh] PYTHONPATH=$PYTHONPATH"
echo "[start.sh] PORT=$PORT"

# Use virtual environment if it exists (Railway deployment)
if [ -d "/app/venv" ]; then
  export PATH="/app/venv/bin:$PATH"
  echo "[start.sh] Using venv at /app/venv"
fi

# Verify backend module is importable
python3 -c "from backend.config import get_settings; print('[start.sh] Import check: OK')" || {
  echo "[start.sh] FATAL: Cannot import backend.config - check PYTHONPATH"
  exit 1
}

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
