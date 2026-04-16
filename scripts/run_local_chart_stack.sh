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
CLOUDFLARED_BIN="${CHART_STACK_CLOUDFLARED_BIN:-cloudflared}"
REMOTE_CONFIG_SYNC_LOG="$RUNTIME_DIR/remote-config-sync.log"
FRESH_RESTART=0

case "${1:-}" in
  "")
    ;;
  --fresh)
    FRESH_RESTART=1
    ;;
  *)
    echo "[chart-stack] unknown argument: ${1}"
    echo "[chart-stack] usage: ./scripts/run_local_chart_stack.sh [--fresh]"
    exit 1
    ;;
esac

mkdir -p "$RUNTIME_DIR"
rm -f "$STATE_FILE"
cd "$ROOT_DIR"

if [ -f "$ROOT_DIR/.env" ]; then
  set -a
  # shellcheck disable=SC1091
  source "$ROOT_DIR/.env"
  set +a
fi

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

read_pid_file() {
  local pid_file="$1"
  [ -f "$pid_file" ] || return 1
  tr -d '[:space:]' < "$pid_file"
}

pid_is_running() {
  local pid_file="$1"
  [ -f "$pid_file" ] || return 1
  local pid
  pid="$(read_pid_file "$pid_file")"
  kill -0 "$pid" 2>/dev/null
}

cleanup_stale_pid() {
  local pid_file="$1"
  if [ -f "$pid_file" ] && ! pid_is_running "$pid_file"; then
    rm -f "$pid_file"
  fi
}

get_listener_pid() {
  local port="$1"
  lsof -tiTCP:"$port" -sTCP:LISTEN 2>/dev/null | head -n 1
}

stop_tracked_pid() {
  local name="$1"
  local pid_file="$2"
  if ! pid_is_running "$pid_file"; then
    rm -f "$pid_file"
    return 0
  fi

  local pid
  pid="$(read_pid_file "$pid_file")"
  kill "$pid"
  echo "[chart-stack] stopped tracked $name (PID $pid)"
  rm -f "$pid_file"
}

fresh_restart() {
  echo "[chart-stack] --fresh requested, restarting tracked provider and tunnel"
  stop_tracked_pid "cloudflared" "$CLOUDFLARED_PID_FILE"
  stop_tracked_pid "provider" "$PROVIDER_PID_FILE"
  rm -f "$STATE_FILE"
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

probe_provider() {
  curl -fsS "http://127.0.0.1:8765/chart-context?symbol=VANTAGE:AUDUSD&timeframe=5m"
}

provider_has_current_contract() {
  local response="$1"
  printf '%s' "$response" | grep -q '"provider_timestamp"' &&
    printf '%s' "$response" | grep -q '"zones"' &&
    printf '%s' "$response" | grep -q '"pine_labels"' &&
    printf '%s' "$response" | grep -q '"indicator_values"' &&
    printf '%s' "$response" | grep -q '"setup_evidence"'
}

provider_state() {
  cleanup_stale_pid "$PROVIDER_PID_FILE"

  local tracked_pid=""
  local listener_pid=""
  local response=""

  if pid_is_running "$PROVIDER_PID_FILE"; then
    tracked_pid="$(read_pid_file "$PROVIDER_PID_FILE")"
  fi

  listener_pid="$(get_listener_pid 8765 || true)"

  if [ -n "$tracked_pid" ] && [ "$tracked_pid" = "${listener_pid:-}" ]; then
    response="$(probe_provider 2>/dev/null || true)"
    if [ -z "$response" ]; then
      echo down
      return 0
    fi
    if provider_has_current_contract "$response"; then
      echo healthy
    else
      echo stale
    fi
    return 0
  fi

  if [ -n "${listener_pid:-}" ]; then
    echo conflict
    return 0
  fi

  echo down
}

ensure_provider() {
  local state
  state="$(provider_state)"

  case "$state" in
    healthy)
      echo "[chart-stack] provider healthy, reusing tracked process"
      return 0
      ;;
    stale)
      echo "[chart-stack] provider stale: missing setup_evidence; rerun with --fresh"
      exit 1
      ;;
    conflict)
      echo "[chart-stack] provider conflict on 8765: unmanaged PID $(get_listener_pid 8765)"
      echo "[chart-stack] stop the unmanaged process or rerun after clearing the port"
      exit 1
      ;;
    down)
      echo "[chart-stack] provider down, starting tracked process"
      : > "$PROVIDER_LOG"
      nohup env PYTHONPATH=. "$VENV_PYTHON" -m uvicorn src.local_chart_provider_app:app --host 127.0.0.1 --port 8765 \
        >> "$PROVIDER_LOG" 2>&1 &
      echo $! > "$PROVIDER_PID_FILE"
      ;;
    *)
      echo "[chart-stack] unknown provider state: $state"
      exit 1
      ;;
  esac

  local response=""
  for _ in $(seq 1 20); do
    response="$(probe_provider 2>/dev/null || true)"
    if [ -n "$response" ] && provider_has_current_contract "$response"; then
      echo "[chart-stack] provider ready with current contract"
      return 0
    fi
    sleep 1
  done

  echo "[chart-stack] provider failed to satisfy current contract; see $PROVIDER_LOG"
  exit 1
}

extract_tunnel_url() {
  if [ ! -f "$CLOUDFLARED_LOG" ]; then
    return 1
  fi
  grep -Eo 'https://[a-zA-Z0-9.-]+\.trycloudflare\.com' "$CLOUDFLARED_LOG" | tail -1
}

tunnel_state() {
  cleanup_stale_pid "$CLOUDFLARED_PID_FILE"

  if pid_is_running "$CLOUDFLARED_PID_FILE"; then
    if extract_tunnel_url >/dev/null 2>&1; then
      echo healthy
    else
      echo stale
    fi
    return 0
  fi

  echo down
}

ensure_tunnel() {
  local state
  state="$(tunnel_state)"

  case "$state" in
    healthy)
      echo "[chart-stack] tunnel healthy, reusing tracked process"
      return 0
      ;;
    stale)
      stop_tracked_pid "cloudflared" "$CLOUDFLARED_PID_FILE"
      ;;
    down)
      ;;
    *)
      echo "[chart-stack] unknown tunnel state: $state"
      exit 1
      ;;
  esac

  require_command "$CLOUDFLARED_BIN"
  rm -f "$CLOUDFLARED_PID_FILE"
  : > "$CLOUDFLARED_LOG"
  echo "[chart-stack] starting cloudflared tunnel"
  nohup "$CLOUDFLARED_BIN" tunnel --url http://127.0.0.1:8765 >> "$CLOUDFLARED_LOG" 2>&1 &
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

sync_ai_operating_layer_provider() {
  local tunnel_url="$1"
  local supabase_url="${SUPABASE_URL:-}"
  local supabase_key="${SUPABASE_SERVICE_ROLE_KEY:-${SUPABASE_KEY:-}}"

  if [ -z "$supabase_url" ]; then
    echo "[chart-stack] remote provider sync skipped: SUPABASE_URL not set"
    return 0
  fi

  if [ -z "$supabase_key" ]; then
    echo "[chart-stack] remote provider sync skipped: SUPABASE_SERVICE_ROLE_KEY/SUPABASE_KEY not set"
    return 0
  fi

  if ! SUPABASE_URL="$supabase_url" SUPABASE_KEY="$supabase_key" TUNNEL_URL="$tunnel_url" "$VENV_PYTHON" - >>"$REMOTE_CONFIG_SYNC_LOG" 2>&1 <<'PY'
from supabase import create_client
import os

client = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_KEY"])
client.table("system_config").upsert(
    {
        "key": "ai_operating_layer_provider_base_url",
        "value": os.environ["TUNNEL_URL"].rstrip("/"),
    },
    on_conflict="key",
).execute()
PY
  then
    echo "[chart-stack] remote provider sync failed: unable to update Supabase system_config" | tee -a "$REMOTE_CONFIG_SYNC_LOG"
    return 0
  fi

  echo "[chart-stack] synced provider endpoint to remote AI operating layer config"
}

require_command curl
require_command lsof
require_command "$CLOUDFLARED_BIN"
if [ ! -x "$VENV_PYTHON" ]; then
  echo "[chart-stack] missing project venv python: $VENV_PYTHON"
  exit 1
fi

chmod +x "$ROOT_DIR/scripts/stop_local_chart_stack.sh"

if [ "$FRESH_RESTART" -eq 1 ]; then
  fresh_restart
fi

ensure_cdp
ensure_provider
ensure_tunnel

TUNNEL_URL="$(extract_tunnel_url)"
write_state "$TUNNEL_URL"
sync_ai_operating_layer_provider "$TUNNEL_URL"

echo "[chart-stack] CDP:        http://127.0.0.1:9222"
echo "[chart-stack] Provider:   http://127.0.0.1:8765"
echo "[chart-stack] Tunnel:     $TUNNEL_URL"
echo "[chart-stack] Logs:       .runtime/chart-stack/"
echo "[chart-stack] Note:       tunnel may take a few seconds to become reachable"
