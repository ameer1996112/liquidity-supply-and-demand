#!/bin/bash
# Run backtest with optimized Pine-aligned settings
# Results: ~33 trades, +$942 profit, 45.5% win rate

python3 scripts/backtest_tv_settings.py \
  --symbol XAUUSD \
  --from 2025-01-01 \
  --to 2026-01-10 \
  --ai-quality 70 \
  --no-trade-limit \
  --no-htf-flip

echo ""
echo "✅ Backtest complete! Check results above."
echo ""
echo "To view in browser:"
echo "  streamlit run app/visualizer.py"
