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

  ./scripts/run_local_chart_stack.sh --fresh

  while true; do
    sleep "'"$CHECK_INTERVAL"'"
    ./scripts/run_local_chart_stack.sh
  done
'
