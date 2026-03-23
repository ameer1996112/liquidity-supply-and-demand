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

# 1. Idempotent full-stack mode — exits early so exec blocks below are NOT reached
if [ "$MODE" = "fullstack" ]; then
    LOG_DIR="$HOME/.tradeops/logs"
    mkdir -p "$LOG_DIR"

    # Redis
    if redis-cli ping 2>/dev/null | grep -q PONG; then
        echo "[start.sh] ✅ Redis already running"
    else
        redis-server --daemonize yes
        echo "[start.sh] ✅ Redis started"
    fi

    # API
    if lsof -ti:"$PORT" &>/dev/null; then
        echo "[start.sh] ✅ API already running on port $PORT"
    elif launchctl list 2>/dev/null | grep -q "com.tradeops.api"; then
        echo "[start.sh] ✅ API managed by launchd (running)"
    else
        source .venv/bin/activate 2>/dev/null || true
        python3 -m uvicorn src.api:app --host 0.0.0.0 --port "$PORT" --log-level info \
            >> "$LOG_DIR/api.log" 2>&1 &
        echo $! > /tmp/tradeops-api.pid
        echo "[start.sh] ✅ API started (PID $(cat /tmp/tradeops-api.pid)) → logs: $LOG_DIR/api.log"
    fi

    # Worker
    if pgrep -f "src.worker" &>/dev/null; then
        echo "[start.sh] ✅ Worker already running"
    elif launchctl list 2>/dev/null | grep -q "com.tradeops.worker"; then
        echo "[start.sh] ✅ Worker managed by launchd (running)"
    else
        source .venv/bin/activate 2>/dev/null || true
        python3 -m src.worker >> "$LOG_DIR/worker.log" 2>&1 &
        echo $! > /tmp/tradeops-worker.pid
        echo "[start.sh] ✅ Worker started (PID $(cat /tmp/tradeops-worker.pid)) → logs: $LOG_DIR/worker.log"
    fi

    # Jira app (hardcoded to port 3001 in jira/package.json)
    if [ -d "$ROOT_DIR/jira" ] && [ -f "$ROOT_DIR/jira/package.json" ]; then
        if lsof -ti:3001 &>/dev/null; then
            echo "[start.sh] ✅ Jira app already running on port 3001"
        else
            (cd "$ROOT_DIR/jira" && npm run dev >> "$LOG_DIR/jira.log" 2>&1) &
            echo "[start.sh] ✅ Jira app started → logs: $LOG_DIR/jira.log"
        fi
    fi

    # Main frontend (port 3000)
    if [ -d "$ROOT_DIR/frontend" ] && [ -f "$ROOT_DIR/frontend/package.json" ]; then
        if lsof -ti:3000 &>/dev/null; then
            echo "[start.sh] ✅ Frontend already running on port 3000"
        else
            (cd "$ROOT_DIR/frontend" && npm run dev >> "$LOG_DIR/frontend.log" 2>&1) &
            echo "[start.sh] ✅ Frontend started → logs: $LOG_DIR/frontend.log"
        fi
    fi

    echo ""
    echo "[start.sh] 🚀 Full stack running. Logs: $LOG_DIR/"
    echo "           API:     http://localhost:$PORT/health"
    echo "           Jira:    http://localhost:3200"
    echo "           Persist: ./install-services.sh"
    exit 0
fi

# 2. Handle legacy frontend startup (both/full modes — non-idempotent)
if [ "$MODE" = "full" ] || [ "$MODE" = "both" ]; then
    if [ "${FULL_STACK:-0}" = "1" ]; then
        if [ -d "$ROOT_DIR/frontend" ] && [ -f "$ROOT_DIR/frontend/package.json" ]; then
            FRONTEND_PORT="${FRONTEND_PORT:-3000}"
            echo "[start.sh] Starting Frontend (Next.js) on port $FRONTEND_PORT in background..."
            (cd "$ROOT_DIR/frontend" && PORT="$FRONTEND_PORT" npm run dev) &
            FRONTEND_PID=$!
            sleep 2
        fi
    fi
fi

# 3. Start Worker (non-fullstack modes)
if [ "$MODE" = "worker" ]; then
    echo "[start.sh] Starting Worker (Consumer) in FOREGROUND..."
    exec python3 -m src.worker
elif [ "$MODE" = "both" ]; then
    echo "[start.sh] Starting Worker (Consumer) in background..."
    python3 -m src.worker &
    WORKER_PID=$!
fi

# 4. Start API (non-fullstack modes — exec replaces this process)
if [ "$MODE" = "api" ] || [ "$MODE" = "both" ]; then
    echo "[start.sh] Starting API (Producer) on port $PORT..."
    exec python3 -m uvicorn src.api:app \
      --host 0.0.0.0 \
      --port "$PORT" \
      --log-level info
fi

# 4. Idempotent full-stack mode (covers INFRA-03, INFRA-04)
if [ "$MODE" = "fullstack" ]; then
    LOG_DIR="$HOME/.tradeops/logs"
    mkdir -p "$LOG_DIR"

    # Redis
    if redis-cli ping 2>/dev/null | grep -q PONG; then
        echo "[start.sh] ✅ Redis already running"
    else
        redis-server --daemonize yes
        echo "[start.sh] ✅ Redis started"
    fi

    # API
    if lsof -ti:"$PORT" &>/dev/null; then
        echo "[start.sh] ✅ API already running on port $PORT"
    elif launchctl list 2>/dev/null | grep -q "com.tradeops.api"; then
        launchctl start com.tradeops.api 2>/dev/null || true
        echo "[start.sh] ✅ API started via launchd"
    else
        python3 -m uvicorn src.api:app --host 0.0.0.0 --port "$PORT" --log-level info \
            >> "$LOG_DIR/api.log" 2>&1 &
        echo $! > /tmp/tradeops-api.pid
        echo "[start.sh] ✅ API started (PID $(cat /tmp/tradeops-api.pid)) → logs: $LOG_DIR/api.log"
    fi

    # Worker
    if pgrep -f "src.worker" &>/dev/null; then
        echo "[start.sh] ✅ Worker already running"
    elif launchctl list 2>/dev/null | grep -q "com.tradeops.worker"; then
        launchctl start com.tradeops.worker 2>/dev/null || true
        echo "[start.sh] ✅ Worker started via launchd"
    else
        python3 -m src.worker \
            >> "$LOG_DIR/worker.log" 2>&1 &
        echo $! > /tmp/tradeops-worker.pid
        echo "[start.sh] ✅ Worker started (PID $(cat /tmp/tradeops-worker.pid)) → logs: $LOG_DIR/worker.log"
    fi

    # Jira app (hardcoded to port 3001 in jira/package.json — --port flag ignores PORT env)
    if [ -d "$ROOT_DIR/jira" ] && [ -f "$ROOT_DIR/jira/package.json" ]; then
        if lsof -ti:3001 &>/dev/null; then
            echo "[start.sh] ✅ Jira app already running on port 3001"
        else
            (cd "$ROOT_DIR/jira" && npm run dev >> "$LOG_DIR/jira.log" 2>&1) &
            echo "[start.sh] ✅ Jira app started → logs: $LOG_DIR/jira.log"
        fi
    fi
    if [ -d "$ROOT_DIR/frontend" ] && [ -f "$ROOT_DIR/frontend/package.json" ]; then
        if lsof -ti:3000 &>/dev/null; then
            echo "[start.sh] ✅ Frontend already running on port 3000"
        else
            (cd "$ROOT_DIR/frontend" && npm run dev >> "$LOG_DIR/frontend.log" 2>&1) &
            echo "[start.sh] ✅ Frontend started → logs: $LOG_DIR/frontend.log"
        fi
    fi

    echo ""
    echo "[start.sh] 🚀 Full stack running. Logs: $LOG_DIR/"
    echo "           API:     http://localhost:$PORT/health"
    echo "           Jira:    http://localhost:3001"
    echo "           Persist: ./install-services.sh"
    exit 0
fi

