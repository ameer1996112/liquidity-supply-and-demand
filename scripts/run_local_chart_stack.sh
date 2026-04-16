#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
RUNTIME_DIR="$ROOT_DIR/.runtime/chart-stack"
PROVIDER_LOG="$RUNTIME_DIR/provider.log"
CLOUDFLARED_LOG="$RUNTIME_DIR/cloudflared.log"
PROVIDER_PID_FILE="$RUNTIME_DIR/provider.pid"
CLOUDFLARED_PID_FILE="$RUNTIME_DIR/cloudflared.pid"
STATE_FILE="$RUNTIME_DIR/state.env"
VENV_PYTHON="$ROOT_DIR/venv/bin/python"

mkdir -p "$RUNTIME_DIR"
rm -f "$STATE_FILE"
cd "$ROOT_DIR"
export PYTHONPATH="$ROOT_DIR:${PYTHONPATH:-}"

require_command() {
  local cmd="$1"
  if ! command -v "$cmd" >/dev/null 2>&1; then
    echo "[chart-stack] missing required command: $cmd"
    exit 1
  fi
}

wait_for_url() {
  local url="$1"
  local attempts="${2:-20}"
  for _ in $(seq 1 "$attempts"); do
    if curl -fsS "$url" >/dev/null 2>&1; then
      return 0
    fi
    sleep 1
  done
  return 1
}

pid_is_running() {
  local pid_file="$1"
  [ -f "$pid_file" ] || return 1
  local pid
  pid="$(cat "$pid_file")"
  kill -0 "$pid" 2>/dev/null
}

cleanup_stale_pid() {
  local pid_file="$1"
  if [ -f "$pid_file" ] && ! pid_is_running "$pid_file"; then
    rm -f "$pid_file"
  fi
}

ensure_cdp() {
  if curl -fsS "http://127.0.0.1:9222/json/version" >/dev/null 2>&1; then
    echo "[chart-stack] CDP already available"
    return 0
  fi

  echo "[chart-stack] launching TradingView with CDP"
  "$ROOT_DIR/mcp/tradingview-mcp/scripts/launch_tv_debug_mac.sh"

  if ! wait_for_url "http://127.0.0.1:9222/json/version" 20; then
    echo "[chart-stack] CDP did not become available"
    exit 1
  fi
}

ensure_provider() {
  cleanup_stale_pid "$PROVIDER_PID_FILE"

  if curl -fsS "http://127.0.0.1:8765/chart-context?symbol=VANTAGE:AUDUSD&timeframe=5m" >/dev/null 2>&1; then
    echo "[chart-stack] provider already available"
    return 0
  fi

  echo "[chart-stack] starting local provider"
  PYTHONPATH=. "$VENV_PYTHON" -m uvicorn src.local_chart_provider_app:app --host 127.0.0.1 --port 8765 \
    >> "$PROVIDER_LOG" 2>&1 &
  echo $! > "$PROVIDER_PID_FILE"

  if ! wait_for_url "http://127.0.0.1:8765/chart-context?symbol=VANTAGE:AUDUSD&timeframe=5m" 20; then
    echo "[chart-stack] provider failed to start; see $PROVIDER_LOG"
    exit 1
  fi
}

extract_tunnel_url() {
  if [ ! -f "$CLOUDFLARED_LOG" ]; then
    return 1
  fi
  grep -Eo 'https://[a-zA-Z0-9.-]+\.trycloudflare\.com' "$CLOUDFLARED_LOG" | tail -1
}

ensure_tunnel() {
  cleanup_stale_pid "$CLOUDFLARED_PID_FILE"

  if pid_is_running "$CLOUDFLARED_PID_FILE"; then
    echo "[chart-stack] cloudflared already running"
    return 0
  fi

  require_command cloudflared
  : > "$CLOUDFLARED_LOG"
  echo "[chart-stack] starting cloudflared tunnel"
  cloudflared tunnel --url http://127.0.0.1:8765 >> "$CLOUDFLARED_LOG" 2>&1 &
  echo $! > "$CLOUDFLARED_PID_FILE"

  for _ in $(seq 1 20); do
    if extract_tunnel_url >/dev/null 2>&1; then
      return 0
    fi 
    sleep 1
  done

  echo "[chart-stack] tunnel URL not detected; see $CLOUDFLARED_LOG"
  exit 1
}

write_state() {
  local tunnel_url="$1"
  cat > "$STATE_FILE" <<EOF
TUNNEL_URL=$tunnel_url
PROVIDER_URL=http://127.0.0.1:8765
CDP_URL=http://127.0.0.1:9222
EOF
}

require_command curl
if [ ! -x "$VENV_PYTHON" ]; then
  echo "[chart-stack] missing project venv python: $VENV_PYTHON"
  exit 1
fi

chmod +x "$ROOT_DIR/scripts/stop_local_chart_stack.sh"

ensure_cdp
ensure_provider
ensure_tunnel

TUNNEL_URL="$(extract_tunnel_url)"
write_state "$TUNNEL_URL"

echo "[chart-stack] CDP:        http://127.0.0.1:9222"
echo "[chart-stack] Provider:   http://127.0.0.1:8765"
echo "[chart-stack] Tunnel:     $TUNNEL_URL"
echo "[chart-stack] Logs:       .runtime/chart-stack/"
echo "[chart-stack] Note:       tunnel may take a few seconds to become reachable"
