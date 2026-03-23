---
created: 2026-03-23T10:16:19.000Z
title: Upgrade departure_strength calculation to fix NAS100/XAUUSD filtering
area: ui
files:
  - scripts/pinescript/libraries/SND_Core.pine:387-455
---

## Problem

The `departure_strength` filter was incorrectly rejecting valid NAS100 and XAUUSD trades
that had visually strong departure candles. Example: zone D-18452 scored 28.33 vs a 40.0
threshold despite showing multiple big consecutive bullish candles leaving the zone.

Two root causes:
1. **Single-candle max**: The function only kept the single strongest departure candle score
   (max of 3). A zone with 3 consecutive strong bullish candles scored the same as one with
   only 1 average candle.
2. **ATR normalization underscored NAS100/XAUUSD**: Magnitude was computed as `body_size / ATR`.
   When ATR is 80–150 pts (NAS100) or 10–20 pts (XAUUSD), even a strong 30-pt / 5-pt body
   only yields 0.2–0.6× ATR → 4–12 pts out of 40. Forex with smaller ATRs was not penalized
   as heavily, creating an instrument bias.

## Solution

**COMPLETED** — Implemented in `scripts/pinescript/libraries/SND_Core.pine`.

Changes made:
1. **Rolling-range normalization**: Replaced `body_size / ATR` with `candle_range / (20-bar_rolling_range × 0.10)`.
   A departure candle covering ≥10% of the recent 20-bar high-low range = full magnitude score.
   Works correctly for all instruments regardless of absolute price scale.
2. **Multi-candle accumulation**: Extra qualifying candles (beyond the best) each add 40% of
   their score as a bonus. Zones with 2–3 consecutive strong departure candles now score materially
   higher than single-candle departures.
3. **Floor lowered** from 10 → 5 to avoid masking genuinely weak departures.

Requires Pine Script library republish + strategy reload in TradingView to take effect.
