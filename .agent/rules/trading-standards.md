---
trigger: always_on
---

# Liquidity Bot Engineering Standards

## 1. Pine Script Architecture
- Always use //@version=5.
- Use 'calc_on_every_tick=false' to optimize performance and prevent repaint-based false signals.
- Implement 'max_labels_count=500' to ensure supply/demand zones remain visible on historical data.

## 2. Liquidity Logic Requirements
- Demand Zones: Must be defined by a strong impulsive move away from a base; require a minimum 2:1 displacement ratio.
- Supply Zones: Must identify 'Order Blocks' using high-volume nodes; do not consider a zone valid unless it breaks a previous market structure (BOS).
- Mitigation: Automatically invalidate/hide zones once they have been 'tapped' or pierced by a wick (unless multi-touch logic is specified).

## 3. Risk Management (Mandatory)
- Every trade must have a Stop Loss (SL) placed 5 ticks beyond the supply/demand zone boundary.
- Minimum Risk-to-Reward (RR) must be 1:2; the agent should flag any logic that entries with a lower ratio.
- Implement a 'Volatility Filter' (e.g., ATR) to prevent entries during low-liquidity periods (Asian session or holidays).

## 4. Verification Workflow
- Before finalizing code, use the Browser Agent to check the 'List of Trades' in the TradingView Strategy Tester.
- Ensure 'Recalculate on every tick' is DISABLED in the settings to maintain backtest integrity.