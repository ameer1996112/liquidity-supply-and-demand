#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LABEL="com.ameer.trading.chart-stack"
TEMPLATE_PATH="$ROOT_DIR/support/launchd/${LABEL}.plist.template"
LAUNCH_AGENTS_DIR="$HOME/Library/LaunchAgents"
PLIST_PATH="$LAUNCH_AGENTS_DIR/${LABEL}.plist"
LOG_DIR="$HOME/Library/Logs/trading-chart-stack"
STDOUT_LOG="$LOG_DIR/stdout.log"
STDERR_LOG="$LOG_DIR/stderr.log"
WRAPPER_PATH="$ROOT_DIR/scripts/run_chart_stack_background.sh"
FALLBACK_PID_FILE="$ROOT_DIR/.runtime/chart-stack/background-supervisor.pid"

usage() {
  cat <<EOF
Usage: ./scripts/manage_chart_stack_launch_agent.sh <command>

Commands:
  install    Render the LaunchAgent plist, load it, and start the service
  start      Start the loaded service
  stop       Stop the running service
  restart    Restart the service
  status     Show plist presence and launchctl status
  uninstall  Stop, unload, and remove the installed plist
EOF
}

require_template() {
  if [ ! -f "$TEMPLATE_PATH" ]; then
    echo "[launch-agent] missing template: $TEMPLATE_PATH"
    exit 1
  fi
}

ensure_dirs() {
  mkdir -p "$LAUNCH_AGENTS_DIR" "$LOG_DIR" "$ROOT_DIR/.runtime/chart-stack"
}

read_fallback_pid() {
  [ -f "$FALLBACK_PID_FILE" ] || return 1
  tr -d '[:space:]' < "$FALLBACK_PID_FILE"
}

fallback_is_running() {
  local pid
  pid="$(read_fallback_pid)" || return 1
  kill -0 "$pid" 2>/dev/null
}

stop_fallback_if_running() {
  if fallback_is_running; then
    local pid
    pid="$(read_fallback_pid)"
    kill "$pid" >/dev/null 2>&1 || true
    echo "[launch-agent] stopped direct background supervisor (PID $pid)"
  fi
  rm -f "$FALLBACK_PID_FILE"
}

start_fallback_supervisor() {
  ensure_dirs
  nohup "$WRAPPER_PATH" >>"$STDOUT_LOG" 2>>"$STDERR_LOG" &
  echo $! > "$FALLBACK_PID_FILE"
  echo "[launch-agent] started direct background supervisor (PID $(read_fallback_pid))"
}

render_plist() {
  require_template
  ensure_dirs

  sed \
    -e "s|__WRAPPER_PATH__|$WRAPPER_PATH|g" \
    -e "s|__STDOUT_LOG__|$STDOUT_LOG|g" \
    -e "s|__STDERR_LOG__|$STDERR_LOG|g" \
    "$TEMPLATE_PATH" > "$PLIST_PATH"
}

bootout_if_loaded() {
  if service_is_loaded; then
    launchctl bootout "gui/$(id -u)/$LABEL" >/dev/null 2>&1 || \
      launchctl unload -w "$PLIST_PATH" >/dev/null 2>&1 || true
  fi
}

bootstrap_plist() {
  if launchctl bootstrap "gui/$(id -u)" "$PLIST_PATH" >/dev/null 2>&1 && service_is_loaded; then
    return 0
  fi
  if service_is_loaded; then
    return 0
  fi
  sleep 1
  if launchctl bootstrap "gui/$(id -u)" "$PLIST_PATH" >/dev/null 2>&1 && service_is_loaded; then
    return 0
  fi
  if service_is_loaded; then
    return 0
  fi
  sleep 1
  if launchctl bootstrap "gui/$(id -u)" "$PLIST_PATH" >/dev/null 2>&1 && service_is_loaded; then
    return 0
  fi
  if service_is_loaded; then
    return 0
  fi
  if launchctl load -w "$PLIST_PATH" >/dev/null 2>&1 && service_is_loaded; then
    return 0
  fi
  return 1
}

kickstart_service() {
  launchctl kickstart -k "gui/$(id -u)/$LABEL"
}

service_is_loaded() {
  launchctl print "gui/$(id -u)/$LABEL" >/dev/null 2>&1
}

print_status() {
  if [ -f "$PLIST_PATH" ]; then
    echo "[launch-agent] plist: $PLIST_PATH"
  else
    echo "[launch-agent] plist not installed"
  fi

  launchctl print "gui/$(id -u)/$LABEL" 2>/dev/null || echo "[launch-agent] service not loaded"
  if fallback_is_running; then
    echo "[launch-agent] direct background supervisor running (PID $(read_fallback_pid))"
  fi
}

command="${1:-}"

case "$command" in
  install)
    render_plist
    stop_fallback_if_running
    bootout_if_loaded
    if bootstrap_plist; then
      kickstart_service
      echo "[launch-agent] installed and started: $LABEL"
    else
      start_fallback_supervisor
      echo "[launch-agent] install fell back to direct background supervisor"
    fi
    echo "[launch-agent] logs: $LOG_DIR"
    ;;
  start)
    if [ ! -f "$PLIST_PATH" ]; then
      echo "[launch-agent] install the plist first with: ./scripts/manage_chart_stack_launch_agent.sh install"
      exit 1
    fi
    if ! service_is_loaded; then
      if ! bootstrap_plist; then
        start_fallback_supervisor
        echo "[launch-agent] start fell back to direct background supervisor"
        exit 0
      fi
    fi
    stop_fallback_if_running
    kickstart_service
    echo "[launch-agent] started: $LABEL"
    ;;
  stop)
    bootout_if_loaded
    stop_fallback_if_running
    echo "[launch-agent] stopped: $LABEL"
    ;;
  restart)
    if [ ! -f "$PLIST_PATH" ]; then
      echo "[launch-agent] install the plist first with: ./scripts/manage_chart_stack_launch_agent.sh install"
      exit 1
    fi
    stop_fallback_if_running
    if ! service_is_loaded; then
      if ! bootstrap_plist; then
        start_fallback_supervisor
        echo "[launch-agent] restart fell back to direct background supervisor"
        exit 0
      fi
    fi
    kickstart_service
    echo "[launch-agent] restarted: $LABEL"
    ;;
  status)
    print_status
    ;;
  uninstall)
    bootout_if_loaded
    stop_fallback_if_running
    rm -f "$PLIST_PATH"
    echo "[launch-agent] uninstalled: $LABEL"
    ;;
  *)
    usage
    exit 1
    ;;
esac
