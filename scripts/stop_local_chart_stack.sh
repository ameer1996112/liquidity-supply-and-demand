#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
RUNTIME_DIR="$ROOT_DIR/.runtime/chart-stack"
PROVIDER_PID_FILE="$RUNTIME_DIR/provider.pid"
CLOUDFLARED_PID_FILE="$RUNTIME_DIR/cloudflared.pid"
STATE_FILE="$RUNTIME_DIR/state.env"

stop_pid_file() {
  local name="$1"
  local pid_file="$2"
  if [ ! -f "$pid_file" ]; then
    echo "[chart-stack] $name not running (no pid file)"
    return
  fi

  local pid
  pid="$(cat "$pid_file")"
  if kill -0 "$pid" 2>/dev/null; then
    kill "$pid"
    echo "[chart-stack] stopped $name (PID $pid)"
  else
    echo "[chart-stack] removing stale $name pid file"
  fi
  rm -f "$pid_file"
}

mkdir -p "$RUNTIME_DIR"
stop_pid_file "cloudflared" "$CLOUDFLARED_PID_FILE"
stop_pid_file "provider" "$PROVIDER_PID_FILE"
rm -f "$STATE_FILE"
echo "[chart-stack] TradingView left running by default"
