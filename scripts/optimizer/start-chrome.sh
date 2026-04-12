#!/usr/bin/env bash
# start-chrome.sh — Launch Chrome with CDP remote debugging on port 9222.
#
# macOS requires --user-data-dir for remote debugging to work.
# We use a persistent profile dir so your TradingView login is saved.
#
# Usage:
#   bash scripts/optimizer/start-chrome.sh          # launch with saved login
#   bash scripts/optimizer/start-chrome.sh --fresh  # wipe profile and start clean
#
# After running this script:
#   1. Log in to TradingView (only needed once — profile is saved)
#   2. Open 3 TradingView chart tabs (one per worker)
#   3. Run: bash scripts/optimizer/run.sh --parallel --workers 3 --bayesian

set -euo pipefail

PROFILE_DIR="${HOME}/.chrome-tv-optimizer"
CHROME="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
PORT=9222

if [[ "${1:-}" == "--fresh" ]]; then
    echo "[start-chrome] Wiping profile at $PROFILE_DIR"
    rm -rf "$PROFILE_DIR"
fi

mkdir -p "$PROFILE_DIR"

# Kill any existing Chrome using port 9222
if lsof -ti :$PORT &>/dev/null; then
    echo "[start-chrome] Killing existing process on port $PORT..."
    lsof -ti :$PORT | xargs kill -9 2>/dev/null || true
    sleep 1
fi

# Also kill any running Chrome instance to avoid conflicts
pkill -x "Google Chrome" 2>/dev/null || true
sleep 1

echo "[start-chrome] Launching Chrome with CDP on port $PORT"
echo "[start-chrome] Profile dir: $PROFILE_DIR (login saved here)"
echo ""

nohup "$CHROME" \
    --remote-debugging-port=$PORT \
    --user-data-dir="$PROFILE_DIR" \
    --no-first-run \
    --no-default-browser-check \
    > /tmp/chrome-cdp.log 2>&1 &

CHROME_PID=$!
echo "[start-chrome] Chrome PID: $CHROME_PID"

# Wait for CDP to become ready
echo -n "[start-chrome] Waiting for CDP..."
for i in $(seq 1 15); do
    if curl -s http://127.0.0.1:$PORT/json/version &>/dev/null; then
        echo " ready!"
        break
    fi
    echo -n "."
    sleep 1
done

# Verify
VERSION=$(curl -s http://127.0.0.1:$PORT/json/version | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('Browser','?'))" 2>/dev/null || echo "unknown")
echo ""
echo "╔════════════════════════════════════════════════════════╗"
echo "║  ✅ Chrome CDP ready: $VERSION"
echo "║  Port: $PORT | Profile: $PROFILE_DIR"
echo "╠════════════════════════════════════════════════════════╣"
echo "║  Next steps:                                           ║"
echo "║  1. Log in to TradingView (if first time)             ║"
echo "║  2. Open 3 TradingView chart tabs                     ║"
echo "║  3. Run the optimizer:                                 ║"
echo "║     bash scripts/optimizer/run.sh \\                  ║"
echo "║       --parallel --workers 3 --bayesian               ║"
echo "╚════════════════════════════════════════════════════════╝"
