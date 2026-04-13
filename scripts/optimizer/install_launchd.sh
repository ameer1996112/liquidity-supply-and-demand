#!/usr/bin/env bash
# install_launchd.sh — install the optimizer watchdog LaunchAgent on macOS.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
RESULTS_DIR="$PROJECT_ROOT/scripts/optimization_results"
PLIST_PATH="${HOME}/Library/LaunchAgents/com.galil.optimizer-watchdog.plist"

mkdir -p "$RESULTS_DIR"
mkdir -p "$(dirname "$PLIST_PATH")"

PYTHON_BIN=""
for candidate in \
    "$PROJECT_ROOT/venv/bin/python3" \
    "$PROJECT_ROOT/.venv/bin/python3" \
    "/workspace/.venv/bin/python3"; do
    if [[ -x "$candidate" ]]; then
        PYTHON_BIN="$candidate"
        break
    fi
done

if [[ -z "$PYTHON_BIN" ]]; then
    PYTHON_BIN="$(command -v python3)"
fi

cat > "$PLIST_PATH" <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
  <dict>
    <key>Label</key>
    <string>com.galil.optimizer-watchdog</string>
    <key>ProgramArguments</key>
    <array>
      <string>$PYTHON_BIN</string>
      <string>-m</string>
      <string>scripts.optimizer.watchdog</string>
      <string>check</string>
    </array>
    <key>WorkingDirectory</key>
    <string>$PROJECT_ROOT</string>
    <key>EnvironmentVariables</key>
    <dict>
      <key>PYTHONPATH</key>
      <string>$PROJECT_ROOT</string>
    </dict>
    <key>RunAtLoad</key>
    <true/>
    <key>StartInterval</key>
    <integer>120</integer>
    <key>StandardOutPath</key>
    <string>$RESULTS_DIR/watchdog.stdout.log</string>
    <key>StandardErrorPath</key>
    <string>$RESULTS_DIR/watchdog.stderr.log</string>
  </dict>
</plist>
PLIST

launchctl unload "$PLIST_PATH" 2>/dev/null || true
launchctl load "$PLIST_PATH"
launchctl kickstart -k "gui/$(id -u)/com.galil.optimizer-watchdog"

echo "[install_launchd] Installed LaunchAgent at $PLIST_PATH"
echo "[install_launchd] Watchdog will run every 2 minutes."
