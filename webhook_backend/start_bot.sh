#!/bin/bash
# =============================================================================
# TradingView -> Discord Alert Bot Startup Script (Mac)
# =============================================================================

echo "============================================================"
echo "  TradingView -> Discord Alert Bot (Mac Edition)"
echo "============================================================"
echo ""

# Change to script directory
cd "$(dirname "$0")"

# Check if Python is available
if ! command -v python3 &> /dev/null; then
    echo "ERROR: Python 3 is not installed"
    echo "Install with: brew install python3"
    exit 1
fi

# Check if virtual environment exists
if [ -d "venv" ]; then
    echo "Activating virtual environment..."
    source venv/bin/activate
else
    echo "No virtual environment found."
    echo "TIP: Create one with: python3 -m venv venv && source venv/bin/activate && pip install -r requirements.txt"
    echo ""
fi

echo ""
echo "Starting trading bot..."
echo ""
echo "Webhook URL: http://localhost:5000/webhook"
echo "Health Check: http://localhost:5000/health"
echo ""
echo "To expose to TradingView, run in another terminal:"
echo "  ngrok http 5000"
echo ""
echo "Press Ctrl+C to stop the bot."
echo "============================================================"
echo ""

# Run the bot
python3 trading_bot.py
