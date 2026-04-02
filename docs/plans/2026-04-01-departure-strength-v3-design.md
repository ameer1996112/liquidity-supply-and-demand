# Departure Strength v3 — Enhanced Multi-Factor Scoring (SUPERSEDED by v3.1)

> **Note:** This design has been superseded by [v3.1](2026-04-02-departure-strength-v3.1-design.md) which adds multi-candle consolidation base detection, compression ratio, time accumulation scoring, graduated FVG, and fixes score saturation issues.

## Problem

The `calculate_departure_strength` function in `SND_Core.pine` suffered from two issues:

1. **Bug (fixed):** Guard condition `base_end_idx < 3` caused 50.0 fallback for most zones (baseIdx=1 or 2). Fixed by changing to `< 1`.
2. **Design weakness:** The 3-component scoring (Magnitude, Body Dominance, Volume) produces clustered scores with poor differentiation. Forex tick volume adds noise. Missing key institutional departure signals.

## Design Goals

- Better signal quality — score should predict trade outcomes
- More differentiation — wider score spread for meaningful filtering
- Add institutional departure signals (FVG, sustained momentum)
- Remove noisy Forex tick volume dependency
- Zero additional loops — all new components computed inside existing iteration

## Approved Design: 6-Component Pure Price Action Scoring

### Component Breakdown (100pts total)

| # | Component | Points | Description |
|---|---|---|---|
| 1 | Magnitude | 30pts | Candle size vs 20-bar rolling context range |
| 2 | Body Dominance | 15pts | Body as % of total range |
| 3 | Wick Rejection | 15pts | Small wick on departure side |
| 4 | Close Position | 15pts | Close at range extreme |
| 5 | FVG Creation | 15pts | Departure creates Fair Value Gap |
| 6 | Directionality | 10pts | Consecutive correct-direction candles |

### Component Details

#### 1. Magnitude (30pts)
Measures departure candle size relative to 20-bar rolling context range.

**Change from v2:** Replace linear `min(ratio, 1.0) * 40` with logarithmic curve:
```
ratio = candle_range / (ref_range * 0.10)
magnitude_score = min(log2(1 + ratio) / log2(3), 1.0) * 30
```
Produces smooth distribution: ratio 0.5→15pts, 1.0→19pts, 2.0→30pts.

#### 2. Body Dominance (15pts)
Unchanged logic: `body_percent * 15`. Reduced from 30pts.

#### 3. Wick Rejection (15pts) — NEW
Measures how small the wick is on the departure side (the side price is leaving FROM).

- Demand (bullish): lower wick should be small → `lower_wick = low - min(open, close)`
- Supply (bearish): upper wick should be small → `upper_wick = high - max(open, close)`

```
departure_wick = isDemand ? (candle_low - math.min(candle_open, candle_close)) : (math.max(candle_open, candle_close) - candle_high) // always negative for upper, use abs
departure_wick_ratio = departure_wick / candle_range
wick_score = (1.0 - departure_wick_ratio) * 15
```

Small departure-side wick = price left with no hesitation = high score.

#### 4. Close Position (15pts) — NEW
Measures where the candle closes within its range.

```
close_position = (candle_close - candle_low) / (candle_high - candle_low)
// Demand: close near high = 1.0 = good
// Supply: close near low = 0.0 = good (invert: 1.0 - close_position)
relevant_position = isDemand ? close_position : (1.0 - close_position)
close_score = relevant_position * 15
```

#### 5. FVG Creation (15pts) — NEW
Checks if departure candles created a Fair Value Gap (imbalance).

Requires ≥ 2 departure candles (baseIdx ≥ 2). Checks 3 consecutive candles: base candle (A), departure 1 (B), departure 2 (C).

```
// A = [base_end_idx], B = [base_end_idx - 1], C = [base_end_idx - 2]
// Bullish FVG: low[C] > high[A] — gap between C's low and A's high
// Bearish FVG: high[C] < low[A] — gap between C's high and A's low
```

If only 1 departure candle available (baseIdx=1), score = 0. This is correct — single-candle departures cannot create FVGs.

#### 6. Directionality (10pts) — NEW
Counts how many of the departure candles close in the correct direction.

Tracked inside the existing candle loop (zero extra cost):
- 3/3 correct direction = 10pts
- 2/3 = 6pts  
- 1/3 = 3pts
- 0/3 = 0pts

### Multi-Candle Accumulation (unchanged)
- Best candle's per-candle score (components 1-4) drives the primary score
- Additional qualifying candles contribute 40% bonus
- Components 5 (FVG) and 6 (Directionality) are zone-level, added once

### Floor & Cap
- Floor: 5.0 (unchanged)
- Cap: 100.0 (unchanged)

## Files Changed

| File | Change |
|---|---|
| `scripts/pinescript/libraries/SND_Core.pine` | Rewrite `calculate_departure_strength` with 6 components |

## Verification

- Recompile SND_Core library in TradingView
- Recompile SND_Strategy strategy
- Verify departure_strength values now show variation (not all 50)
- Check webhook payloads contain accurate departure_strength
- Visual spot-check: zones with strong departures (big candles, FVGs) should score 70+; weak departures should score <40
