---
plan: "05-plan-1-launchd-services"
phase: "05"
wave: 1
depends_on: []
files_modified:
  - "install-services.sh"
  - "uninstall-services.sh"
  - "com.tradeops.api.plist"
  - "com.tradeops.worker.plist"
requirements:
  - INFRA-01
  - INFRA-02
autonomous: true
---

# Plan 1: macOS launchd Service Installation

## Goal
Create a `install-services.sh` script that generates and loads launchd plist files for the API and Worker so they auto-start on login and restart on crash.

## Tasks

<task id="1.1">
<action>
Create `install-services.sh` at the project root with exactly this content:

```bash
#!/usr/bin/env bash
# install-services.sh — Register TradeOps API + Worker as macOS LaunchAgents

set -euo pipefail

DIR=$(cd "$(dirname "$0")" && pwd)
VENV="$DIR/venv/bin/activate"
LOG_DIR="$HOME/.tradeops/logs"
PLIST_DIR="$HOME/Library/LaunchAgents"

mkdir -p "$LOG_DIR" "$PLIST_DIR"

# API plist
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
    <string>source $VENV && PYTHONPATH=$DIR python3 -m uvicorn src.api:app --host 0.0.0.0 --port 8000</string>
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
</dict>
</plist>
PLIST

# Worker plist
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
    <string>source $VENV && PYTHONPATH=$DIR python3 -m src.worker</string>
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
</dict>
</plist>
PLIST

# Load services
launchctl unload "$PLIST_DIR/com.tradeops.api.plist" 2>/dev/null || true
launchctl load -w "$PLIST_DIR/com.tradeops.api.plist"
echo "✅ com.tradeops.api loaded"

launchctl unload "$PLIST_DIR/com.tradeops.worker.plist" 2>/dev/null || true
launchctl load -w "$PLIST_DIR/com.tradeops.worker.plist"
echo "✅ com.tradeops.worker loaded"

echo ""
echo "Services installed. Logs: $LOG_DIR/"
echo "Status: launchctl list | grep tradeops"
echo "Uninstall: ./uninstall-services.sh"
```

Make it executable with `chmod +x install-services.sh`.
</action>
<read_first>
- start.sh (existing launcher patterns)
- venv/bin/activate (verify venv path is venv/ not .venv/)
</read_first>
<acceptance_criteria>
- install-services.sh exists at project root and is executable (chmod +x)
- File contains `com.tradeops.api` and `com.tradeops.worker` labels
- File contains `RunAtLoad` and `KeepAlive` keys set to true
- File contains `ThrottleInterval` set to 5
- Log paths reference `$HOME/.tradeops/logs/api.log` and `worker.log`
- File contains `launchctl load -w` for both plists
</acceptance_criteria>
</task>

<task id="1.2">
<action>
Create `uninstall-services.sh` at project root:

```bash
#!/usr/bin/env bash
# uninstall-services.sh — Remove TradeOps LaunchAgents

set -euo pipefail

PLIST_DIR="$HOME/Library/LaunchAgents"

launchctl unload "$PLIST_DIR/com.tradeops.api.plist" 2>/dev/null && echo "✅ com.tradeops.api unloaded" || echo "⚠ com.tradeops.api was not loaded"
launchctl unload "$PLIST_DIR/com.tradeops.worker.plist" 2>/dev/null && echo "✅ com.tradeops.worker unloaded" || echo "⚠ com.tradeops.worker was not loaded"

rm -f "$PLIST_DIR/com.tradeops.api.plist" "$PLIST_DIR/com.tradeops.worker.plist"
echo "Plist files removed."
```

Make executable with `chmod +x uninstall-services.sh`.
</action>
<read_first>
- install-services.sh (verify plist labels match)
</read_first>
<acceptance_criteria>
- uninstall-services.sh exists and is executable
- Contains `launchctl unload` for both plists
- Contains `rm -f` for both plist files in `$HOME/Library/LaunchAgents`
</acceptance_criteria>
</task>

## Verification

```bash
# Verify files created
test -x install-services.sh && echo "PASS: install-services.sh executable"
test -x uninstall-services.sh && echo "PASS: uninstall-services.sh executable"
grep -l "com.tradeops.api" install-services.sh && echo "PASS: API label present"
grep -l "KeepAlive" install-services.sh && echo "PASS: KeepAlive present"
grep -l "ThrottleInterval" install-services.sh && echo "PASS: ThrottleInterval present"
```

## Must-Haves
- [ ] install-services.sh generates and loads both plist files
- [ ] Backend survives terminal close after `./install-services.sh`
- [ ] Logs written to `~/.tradeops/logs/`
