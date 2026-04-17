#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CHECK_INTERVAL="${CHART_STACK_CHECK_INTERVAL:-30}"

export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin:${PATH:-}"
export CHART_STACK_CLOUDFLARED_BIN="${CHART_STACK_CLOUDFLARED_BIN:-/opt/homebrew/bin/cloudflared}"

cd "$ROOT_DIR"

cleanup() {
  ./scripts/stop_local_chart_stack.sh >/dev/null 2>&1 || true
}

trap cleanup EXIT INT TERM

/usr/bin/caffeinate -dims bash -lc '
  set -euo pipefail
  cd "'"$ROOT_DIR"'"

  bootstrap_chart_stack() {
    local bootstrap_mode="--fresh"
    while true; do
      if ./scripts/run_local_chart_stack.sh "$bootstrap_mode"; then
        return 0
      fi
      echo "[chart-stack] bootstrap failed; retrying in 10s"
      bootstrap_mode=""
      sleep 10
    done
  }

  bootstrap_chart_stack

  while true; do
    sleep "'"$CHECK_INTERVAL"'"
    if ! ./scripts/run_local_chart_stack.sh; then
      echo "[chart-stack] health check failed; retrying in 10s"
      sleep 10
    fi
  done
'
