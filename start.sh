#!/usr/bin/env bash
set -e

# Use Railway's PORT (default 8000 for local)
export PORT="${PORT:-8000}"

# Run from backend directory so main.py and worker.py are found
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT_DIR/backend"

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

echo "[start.sh] Starting Worker..."
python worker.py &
WORKER_PID=$!

echo "[start.sh] Starting API on 0.0.0.0:$PORT..."
uvicorn main:app --host 0.0.0.0 --port "$PORT" &
UVICORN_PID=$!

# Wait for uvicorn (primary process); if it exits, bring down worker too
wait $UVICORN_PID
shutdown
