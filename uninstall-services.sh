#!/usr/bin/env bash
# uninstall-services.sh — Remove TradeOps macOS LaunchAgents

set -euo pipefail

PLIST_DIR="$HOME/Library/LaunchAgents"

for LABEL in com.tradeops.api com.tradeops.worker; do
  PLIST="$PLIST_DIR/$LABEL.plist"
  if [ -f "$PLIST" ]; then
    launchctl unload "$PLIST" 2>/dev/null && echo "✅ $LABEL unloaded" || echo "⚠ $LABEL was not loaded"
    rm -f "$PLIST"
    echo "   Removed $PLIST"
  else
    echo "⚠ $PLIST not found — already removed?"
  fi
done

echo ""
echo "Services removed. Backend will no longer auto-start on login."
