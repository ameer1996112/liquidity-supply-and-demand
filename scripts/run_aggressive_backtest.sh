#!/bin/bash
# Run backtest with EXACT TradingView Aggressive Profile settings
# This matches the Pine Script Aggressive profile from lines 434-447

python3 scripts/run_aggressive_backtest.py \
  --symbol XAUUSD \
  --from 2025-01-01 \
  --to 2026-02-10

echo ""
echo "✅ Backtest complete with Aggressive Profile!"
echo ""
echo "To view in browser:"
echo "  streamlit run app/visualizer.py"
