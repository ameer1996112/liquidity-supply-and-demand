#!/usr/bin/env bash
set -e

# Set ROOT_DIR - Railway deploys to /app, local dev uses script location
if [ -d "/app/src" ]; then
  ROOT_DIR="/app"
else
  ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
fi

cd "$ROOT_DIR"
export PYTHONPATH="$ROOT_DIR:$PYTHONPATH"

# Load .env from project root so API and worker get SUPABASE_URL, REDIS_URL, etc.
# IMPORTANT: Load .env BEFORE applying PORT default so Railway's injected PORT
# (set in the process environment before this script runs) takes precedence over
# any PORT value inside .env.
if [ -f "$ROOT_DIR/.env" ]; then
  set -a
  source "$ROOT_DIR/.env"
  set +a
  echo "[start.sh] Loaded .env"
else
  echo "[start.sh] No .env found - set SUPABASE_URL and REDIS_URL in environment or create .env"
fi

# Railway injects PORT as a process-level env var before this script starts.
# Re-apply it now so it wins over any PORT value that was in .env.
# Fall back to 8000 for local dev where neither Railway nor .env sets PORT.
export PORT="${RAILWAY_PORT:-${PORT:-8000}}"

# Option A: Backend only (default). Option B: Full stack (frontend + backend).
# Usage: ./start.sh           → backend only
#        ./start.sh fullstack  → frontend (npm run dev) + backend
FULL_STACK="${FULL_STACK:-0}"
if [ "$1" = "fullstack" ] || [ "$1" = "full" ]; then
  FULL_STACK=1
fi

echo "[start.sh] ROOT_DIR=$ROOT_DIR"
echo "[start.sh] PYTHONPATH=$PYTHONPATH"
echo "[start.sh] PORT=$PORT"
echo "[start.sh] Mode: $([ "$FULL_STACK" = "1" ] && echo 'Full Stack (frontend + backend)' || echo 'Backend Only')"

# Use virtual environment if it exists (Railway deployment)
if [ -d "/app/venv" ]; then
  export PATH="/app/venv/bin:$PATH"
  echo "[start.sh] Using venv at /app/venv"
fi

# Verify config and src are importable
python3 -c "from config import get_settings; from src.api import app; from src import worker; print('[start.sh] Import check: OK')" || {
  echo "[start.sh] FATAL: Cannot import config/src - check PYTHONPATH"
  exit 1
}

WORKER_PID=""
UVICORN_PID=""
FRONTEND_PID=""

shutdown() {
  echo "[start.sh] Shutting down (SIGTERM/SIGINT)..."
  [ -n "$FRONTEND_PID" ] && kill "$FRONTEND_PID" 2>/dev/null || true
  [ -n "$WORKER_PID" ] && kill "$WORKER_PID" 2>/dev/null || true
  [ -n "$UVICORN_PID" ] && kill "$UVICORN_PID" 2>/dev/null || true
  wait "$FRONTEND_PID" 2>/dev/null || true
  wait "$WORKER_PID" 2>/dev/null || true
  wait "$UVICORN_PID" 2>/dev/null || true
  exit 0
}

trap shutdown SIGTERM SIGINT

# Start frontend (Next.js) in background if fullstack mode
if [ "$FULL_STACK" = "1" ]; then
  if [ -d "$ROOT_DIR/frontend" ] && [ -f "$ROOT_DIR/frontend/package.json" ]; then
    echo "[start.sh] Starting Frontend (Next.js) on port 3000..."
    (cd "$ROOT_DIR/frontend" && npm run dev) &
    FRONTEND_PID=$!
    echo "[start.sh] Frontend PID=$FRONTEND_PID"
    sleep 2
  else
    echo "[start.sh] WARN: frontend/ not found - skipping frontend"
  fi
fi

echo "[start.sh] Starting API (Producer)..."
python3 -m uvicorn src.api:app --host 0.0.0.0 --port "$PORT" &
UVICORN_PID=$!

echo "[start.sh] Starting Worker (Consumer)..."
python3 -m src.worker &
WORKER_PID=$!

# Wait for uvicorn (primary); if it exits, bring down worker and frontend too
wait $UVICORN_PID
shutdown
