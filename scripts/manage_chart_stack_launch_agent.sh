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
  mkdir -p "$LAUNCH_AGENTS_DIR" "$LOG_DIR"
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
    launchctl bootout "gui/$(id -u)/$LABEL" >/dev/null 2>&1 || true
  fi
}

bootstrap_plist() {
  if ! launchctl bootstrap "gui/$(id -u)" "$PLIST_PATH"; then
    sleep 1
    launchctl bootstrap "gui/$(id -u)" "$PLIST_PATH"
  fi
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
}

command="${1:-}"

case "$command" in
  install)
    render_plist
    bootout_if_loaded
    bootstrap_plist
    kickstart_service
    echo "[launch-agent] installed and started: $LABEL"
    echo "[launch-agent] logs: $LOG_DIR"
    ;;
  start)
    if [ ! -f "$PLIST_PATH" ]; then
      echo "[launch-agent] install the plist first with: ./scripts/manage_chart_stack_launch_agent.sh install"
      exit 1
    fi
    if ! service_is_loaded; then
      bootstrap_plist
    fi
    kickstart_service
    echo "[launch-agent] started: $LABEL"
    ;;
  stop)
    bootout_if_loaded
    echo "[launch-agent] stopped: $LABEL"
    ;;
  restart)
    if [ ! -f "$PLIST_PATH" ]; then
      echo "[launch-agent] install the plist first with: ./scripts/manage_chart_stack_launch_agent.sh install"
      exit 1
    fi
    bootout_if_loaded
    bootstrap_plist
    kickstart_service
    echo "[launch-agent] restarted: $LABEL"
    ;;
  status)
    print_status
    ;;
  uninstall)
    bootout_if_loaded
    rm -f "$PLIST_PATH"
    echo "[launch-agent] uninstalled: $LABEL"
    ;;
  *)
    usage
    exit 1
    ;;
esac
