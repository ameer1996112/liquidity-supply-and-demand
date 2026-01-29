#!/usr/bin/env bash
set -e

export PORT="${PORT:-8000}"
cd "$(dirname "$0")"

WORKER_PID=""
UVICORN_PID=""

shutdown() {
  echo "[start_api_and_worker.sh] Shutting down..."
  [ -n "$WORKER_PID" ] && kill "$WORKER_PID" 2>/dev/null || true
  [ -n "$UVICORN_PID" ] && kill "$UVICORN_PID" 2>/dev/null || true
  wait "$WORKER_PID" 2>/dev/null || true
  wait "$UVICORN_PID" 2>/dev/null || true
  exit 0
}

trap shutdown SIGTERM SIGINT

echo "[start_api_and_worker.sh] Starting API (Producer)..."
uvicorn main:app --host 0.0.0.0 --port "$PORT" &
UVICORN_PID=$!

echo "[start_api_and_worker.sh] Starting Worker (Consumer)..."
python worker.py &
WORKER_PID=$!

wait $UVICORN_PID
shutdown
