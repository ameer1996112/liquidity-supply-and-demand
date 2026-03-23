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
# Option C: Selective Mode (api, worker)
# Usage: ./start.sh [api|worker|full|both]
#        ./start.sh           → starts both API + Worker (backwards compat)
#        ./start.sh api       → starts ONLY API (foreground)
#        ./start.sh worker    → starts ONLY Worker (foreground)

MODE="${1:-both}"

echo "[start.sh] ROOT_DIR=$ROOT_DIR"
echo "[start.sh] PYTHONPATH=$PYTHONPATH"
echo "[start.sh] PORT=$PORT"
echo "[start.sh] MODE=$MODE"

# Use virtual environment if present (nixpacks legacy path)
if [ -d "/app/venv" ]; then
  export PATH="/app/venv/bin:$PATH"
  echo "[start.sh] Using venv at /app/venv"
fi

# Quick import-only smoke test
python3 -c "from config import get_settings; print('[start.sh] Config import: OK')" || {
  echo "[start.sh] FATAL: Cannot import config - check PYTHONPATH and dependencies"
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

# 1. Handle Full Stack / Frontend
if [ "$MODE" = "full" ] || [ "$MODE" = "fullstack" ] || [ "$MODE" = "both" ]; then
    if [ "$MODE" != "both" ] || [ "${FULL_STACK:-0}" = "1" ]; then
        if [ -d "$ROOT_DIR/frontend" ] && [ -f "$ROOT_DIR/frontend/package.json" ]; then
            FRONTEND_PORT="${FRONTEND_PORT:-3000}"
            echo "[start.sh] Starting Frontend (Next.js) on port $FRONTEND_PORT in background..."
            (cd "$ROOT_DIR/frontend" && PORT="$FRONTEND_PORT" npm run dev) &
            FRONTEND_PID=$!
            sleep 2
        fi
    fi
fi

# 2. Start Worker
if [ "$MODE" = "worker" ]; then
    echo "[start.sh] Starting Worker (Consumer) in FOREGROUND..."
    exec python3 -m src.worker
elif [ "$MODE" = "both" ]; then
    echo "[start.sh] Starting Worker (Consumer) in background..."
    python3 -m src.worker &
    WORKER_PID=$!
fi

# 3. Start API
if [ "$MODE" = "api" ] || [ "$MODE" = "both" ] || [ "$MODE" = "fullstack" ]; then
    echo "[start.sh] Starting API (Producer) on port $PORT..."
    exec python3 -m uvicorn src.api:app \
      --host 0.0.0.0 \
      --port "$PORT" \
      --log-level info
fi

