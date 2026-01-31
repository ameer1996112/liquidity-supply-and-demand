#!/bin/bash
# WORKSPACE PURGE SCRIPT v1.0
# Cleans junk files while preserving essential data
# Run from root: chmod +x scripts/purge_workspace.sh && ./scripts/purge_workspace.sh

set -e

echo "STARTING DEEP CLEAN..."

# 1. Clean Backtest Data (Preserve only the 'Golden' datasets)
echo "   - Sanitizing Data Folder..."
BACKTEST_DIR="backend/backtest_data"

if [ -d "$BACKTEST_DIR" ]; then
    mkdir -p "$BACKTEST_DIR/temp_safe"

    # Move winners to safety
    [ -f "$BACKTEST_DIR/trades_NAS100.csv" ] && mv "$BACKTEST_DIR/trades_NAS100.csv" "$BACKTEST_DIR/temp_safe/"
    [ -f "$BACKTEST_DIR/trades_Notion_Manual.csv" ] && mv "$BACKTEST_DIR/trades_Notion_Manual.csv" "$BACKTEST_DIR/temp_safe/"

    # Nuke the rest
    rm -f "$BACKTEST_DIR"/*.csv 2>/dev/null || true

    # Restore winners
    mv "$BACKTEST_DIR/temp_safe"/* "$BACKTEST_DIR/" 2>/dev/null || true
    rmdir "$BACKTEST_DIR/temp_safe" 2>/dev/null || true

    echo "   - Backtest data sanitized"
fi

# 2. Purge Logs & Cache
echo "   - Removing Logs & PyCache..."
find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
find . -name "*.log" -delete 2>/dev/null || true
find . -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
find . -name ".DS_Store" -delete 2>/dev/null || true

# 3. Clean up any stale .pyc files
echo "   - Removing compiled Python files..."
find . -name "*.pyc" -delete 2>/dev/null || true

# 4. Remove empty directories in backtest_data
echo "   - Cleaning empty directories..."
find . -type d -empty -delete 2>/dev/null || true

echo ""
echo "WORKSPACE REFACTORED. READY FOR DEPLOYMENT."
