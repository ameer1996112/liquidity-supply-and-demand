# Departure Strength v3.1 — Multi-Candle Consolidation Base + Enhanced Scoring

## Problem

v3 (6-component scoring) fixed the bug and dropped noisy tick volume, but has structural issues:

1. **Components 3 & 4 are highly correlated** — Wick Rejection (15pts) and Close Position (15pts) measure nearly the same thing. 30pts (30%) allocated to one concept inflates scores.
2. **FVG scoring is binary** — 0 or 15pts. A 1-pip gap and a 50-pip gap score identically.
3. **Multi-candle accumulation is overpowered** — 40% bonus means 2-3 decent candles saturate at 100pts.
4. **Fallback of 50.0 is dangerous** — Zones with insufficient data appear "average" to downstream filters.
5. **Missing compression ratio** — No relationship between departure size and base size.
6. **Single-candle base only** — The system only detects RBR/DBD with 1 base candle, missing institutional consolidation zones.

## Design Goals

- Detect multi-candle consolidation bases (institutional accumulation zones)
- Fix score differentiation by resolving correlated components and overpowered accumulation
- Add compression ratio and time accumulation as scoring factors
- Graduate FVG scoring based on gap size
- Zero breaking changes to webhook payloads or backend

## Decision Log

| # | Decision | Alternatives Considered | Rationale |
|---|---|---|---|
| 1 | Consolidation detection lives in `createZone` (Approach A) | Detection in SND_Core (B), Separate pre-pass (C) | Consolidation is a zone-level structural concept — strategy's job. Library stays a pure scoring engine. |
| 2 | Dynamic backward scan with 15-candle safety cap | Fixed 3-5 candle scan | 15 candles = ~1 hour of 5min data. Dynamic finds real cluster boundaries; cap prevents Pine timeouts. |
| 3 | Consolidation candle criteria: Range <= ATR(14) AND body < 50% range AND contained | ATR-only, body-only, range-relative | Combination catches true indecision candles. ATR normalizes across sessions/pairs. Body rule filters slow trends. |
| 4 | Merge Wick Rejection + Close Position into single "Candle Quality" (15pts) | Keep separate but reweight | They're mathematically correlated — merging eliminates inflation without losing signal. |
| 5 | Add Compression Ratio (15pts) with log curve | Linear ratio, binary threshold | Log curve handles news candles gracefully. ratio 1.0→7.5pts, 3.0+→15pts. |
| 6 | Add Time Accumulation (10pts) with stepped scoring | Continuous, log-scaled | Stepped is clearer: 1-2 candles=0, 3-4=4, 5-7=7, 8+=10. Difference between 1 and 2 matters less than 2 vs 8. |
| 7 | Graduate FVG scoring by gap_size/ref_range | Keep binary, use ATR-relative | ref_range is already computed in the function. 5% of context = full score normalizes across pairs. |
| 8 | Reduce multi-candle bonus from 0.40 to 0.15 | 0.20, 0.25 | 0.15 means 3 perfect candles reach ~84.5 per-candle (reachable 100 only with FVG+Dir+Time). |
| 9 | Lower fallback from 50.0 to 10.0 | 0.0, 5.0, sentinel -1 | 10.0 is above the floor (5.0) but clearly signals "insufficient data" without being confused with average. |
| 10 | Pass both `base_width` and `candlesInBase` to scoring function | base_width only, base_start_idx only | Both are needed: width for compression ratio, candle count for time accumulation scoring. |
| 11 | Accuracy zones use cluster boundaries with base candle open as proximal line | Accuracy on base candle only | Protects the cluster extreme while tightening entry to the momentum shift point. Failsafe if inverted. |

## Approved Design

### Part 1: Consolidation Detection in `createZone` (SND_Strategy.pine)

After identifying the base candle at `baseIdx`, scan backward to find consolidation cluster:

```
Initialize: clusterHigh = high[baseIdx], clusterLow = low[baseIdx], candlesInBase = 1

For j = 1 to 15:
  scanIdx = baseIdx + j
  candle_range = high[scanIdx] - low[scanIdx]
  body_size = abs(close[scanIdx] - open[scanIdx])

  Rule 1 (Range):     candle_range > atr14           → STOP
  Rule 2 (Body):      body_size >= 0.5 * candle_range → STOP  
  Rule 3 (Sideways):  close[scanIdx] entirely outside adjacent candle's range → STOP

  Expand: clusterHigh = max(clusterHigh, high[scanIdx])
          clusterLow = min(clusterLow, low[scanIdx])
          candlesInBase += 1
```

Zone boundaries:
- **Standard zones:** zTop = clusterHigh, zBottom = clusterLow
- **Accuracy zones (demand):** zTop = open[baseIdx], zBottom = clusterLow
- **Accuracy zones (supply):** zTop = clusterHigh, zBottom = open[baseIdx]
- **Failsafe:** if zTop <= zBottom, fall back to clusterHigh / clusterLow

### Part 2: Updated Departure Strength Scoring (SND_Core.pine)

#### New Signature
```pine
calculate_departure_strength(int base_end_idx, bool isDemand,
  series float src_high, series float src_low, series float src_open, series float src_close,
  series float src_volume, series float vol_sma_20, float atr14 = 0.0,
  float base_width = 0.0, int candlesInBase = 1)
```

#### Component Breakdown (100pts)

| # | Component | Points | Type | Description |
|---|---|---|---|---|
| 1 | Magnitude | 25pts | Per-candle | Log curve: candle size vs 20-bar context range |
| 2 | Body Dominance | 10pts | Per-candle | Body as % of total range |
| 3 | Candle Quality | 15pts | Per-candle | Merged wick rejection + close position |
| 4 | Compression Ratio | 15pts | Zone-level | Departure range vs base width (log curve) |
| 5 | FVG Creation | 15pts | Zone-level | Graduated by gap size / context range |
| 6 | Directionality | 10pts | Zone-level | Consecutive correct-direction candles |
| 7 | Time Accumulation | 10pts | Zone-level | Candles in base bonus |

#### Multi-Candle Accumulation
- Best candle score (components 1-3) drives primary score
- Additional qualifying candles contribute **15%** bonus (down from 40%)
- Zone-level components (4-7) added once

#### Floor & Cap
- Floor: 5.0
- Cap: 100.0
- Fallback (insufficient data): 10.0

## Files Changed

| File | Change |
|---|---|
| `scripts/pinescript/strategies/SND_Strategy.pine` | Add consolidation backward scan in `createZone`, update zone boundaries, pass `base_width` and `candlesInBase` |
| `scripts/pinescript/libraries/SND_Core.pine` | Rewrite `calculate_departure_strength` with 7 components, new signature |

## Verification

1. Recompile SND_Core library in TradingView
2. Recompile SND_Strategy strategy
3. Verify zones now have wider boundaries for consolidation clusters
4. Verify departure_strength shows wider score distribution
5. Check webhook payloads contain accurate departure_strength
6. Visual spot-check:
   - Multi-candle consolidation + strong departure + FVG → should score 80+
   - Single-candle base + weak departure → should score < 30
   - Insufficient data → should score 10.0 (not 50)
