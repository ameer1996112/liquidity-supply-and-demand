#!/usr/bin/env bash
# install-services.sh — Register TradeOps API + Worker as macOS LaunchAgents
# Usage: ./install-services.sh
# Uninstall: ./uninstall-services.sh

set -euo pipefail

DIR=$(cd "$(dirname "$0")" && pwd)
VENV="$DIR/venv/bin/activate"
LOG_DIR="$HOME/.tradeops/logs"
PLIST_DIR="$HOME/Library/LaunchAgents"

echo "TradeOps Service Installer"
echo "  Project: $DIR"
echo "  Logs:    $LOG_DIR"
echo "  Plists:  $PLIST_DIR"
echo ""

mkdir -p "$LOG_DIR" "$PLIST_DIR"

# ── API plist ──────────────────────────────────────────────────────────────────
cat > "$PLIST_DIR/com.tradeops.api.plist" <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>com.tradeops.api</string>
  <key>ProgramArguments</key>
  <array>
    <string>/bin/bash</string>
    <string>-c</string>
    <string>source $VENV &amp;&amp; PYTHONPATH=$DIR python3 -m uvicorn src.api:app --host 0.0.0.0 --port 8000</string>
  </array>
  <key>WorkingDirectory</key>
  <string>$DIR</string>
  <key>RunAtLoad</key>
  <true/>
  <key>KeepAlive</key>
  <true/>
  <key>StandardOutPath</key>
  <string>$LOG_DIR/api.log</string>
  <key>StandardErrorPath</key>
  <string>$LOG_DIR/api.error.log</string>
  <key>ThrottleInterval</key>
  <integer>5</integer>
  <key>EnvironmentVariables</key>
  <dict>
    <key>PYTHONPATH</key>
    <string>$DIR</string>
  </dict>
</dict>
</plist>
PLIST

# ── Worker plist ───────────────────────────────────────────────────────────────
cat > "$PLIST_DIR/com.tradeops.worker.plist" <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>com.tradeops.worker</string>
  <key>ProgramArguments</key>
  <array>
    <string>/bin/bash</string>
    <string>-c</string>
    <string>source $VENV &amp;&amp; PYTHONPATH=$DIR python3 -m src.worker</string>
  </array>
  <key>WorkingDirectory</key>
  <string>$DIR</string>
  <key>RunAtLoad</key>
  <true/>
  <key>KeepAlive</key>
  <true/>
  <key>StandardOutPath</key>
  <string>$LOG_DIR/worker.log</string>
  <key>StandardErrorPath</key>
  <string>$LOG_DIR/worker.error.log</string>
  <key>ThrottleInterval</key>
  <integer>5</integer>
  <key>EnvironmentVariables</key>
  <dict>
    <key>PYTHONPATH</key>
    <string>$DIR</string>
  </dict>
</dict>
</plist>
PLIST

# ── Load services ──────────────────────────────────────────────────────────────
for LABEL in com.tradeops.api com.tradeops.worker; do
  PLIST="$PLIST_DIR/$LABEL.plist"
  launchctl unload "$PLIST" 2>/dev/null || true
  launchctl load -w "$PLIST"
  echo "✅ $LABEL loaded"
done

echo ""
echo "Services installed and running."
echo ""
echo "Useful commands:"
echo "  Status:    launchctl list | grep tradeops"
echo "  API logs:  tail -f $LOG_DIR/api.log"
echo "  Worker:    tail -f $LOG_DIR/worker.log"
echo "  Uninstall: ./uninstall-services.sh"
