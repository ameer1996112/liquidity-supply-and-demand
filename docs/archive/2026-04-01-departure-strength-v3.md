# Departure Strength v3 Implementation Plan

> **For Antigravity:** REQUIRED WORKFLOW: Use `.agent/workflows/execute-plan.md` to execute this plan in single-flow mode.

**Goal:** Rewrite `calculate_departure_strength` in SND_Core.pine with 6 pure price-action components replacing the old 3-component (magnitude/body/volume) scoring.

**Architecture:** Single function rewrite in `SND_Core.pine`. No changes to the strategy file or caller signatures — the function signature and return type stay identical. The 6 new components are computed inside the existing per-candle loop (components 1-4) plus two zone-level checks outside the loop (components 5-6).

**Tech Stack:** Pine Script v6, TradingView Library

---

### Task 1: Rewrite `calculate_departure_strength` in SND_Core.pine

**Files:**
- Modify: `scripts/pinescript/libraries/SND_Core.pine:397-482`

**Step 1: Replace the function body**

Replace lines 397-482 with the new 6-component implementation. The function signature stays identical:

```pine
export calculate_departure_strength(int base_end_idx, bool isDemand, series float src_high, series float src_low, series float src_open, series float src_close, series float src_volume, series float vol_sma_20, float atr14 = 0.0) =>
    if base_end_idx < 1
        50.0  // Not enough history (need at least 1 departure candle)
    else
        int departure_candles = math.min(3, base_end_idx)  // Analyze up to 3 candles

        // SAFETY: Ensure we don't exceed Pine Script's 10000 bar limit
        int max_lookback = 10000

        // ── Context range: 20 bars BEFORE the base for instrument-agnostic normalization ──
        float ctx_high = src_high[base_end_idx]
        float ctx_low  = src_low[base_end_idx]
        int   ctx_bars = math.min(20, max_lookback - base_end_idx - 1)

        for j = 1 to ctx_bars
            int ctx_idx = base_end_idx + j
            if ctx_idx < max_lookback
                if src_high[ctx_idx] > ctx_high
                    ctx_high := src_high[ctx_idx]
                if src_low[ctx_idx] < ctx_low
                    ctx_low := src_low[ctx_idx]

        // Fallback to ATR-derived range if rolling context is degenerate
        float rolling_range = ctx_high - ctx_low
        float ref_range = rolling_range > 0.0 ? rolling_range : (atr14 > 0.0 ? atr14 * 10.0 : 1.0)

        // ── Per-candle scoring (Components 1-4) ────────────────────────────────────────
        float best_candle_score = 0.0
        float total_score       = 0.0
        int   qualifying_count  = 0
        int   correct_dir_count = 0   // Component 6: Directionality counter

        for i = 1 to departure_candles
            int candle_idx = base_end_idx - i
            if candle_idx >= 0 and candle_idx < max_lookback
                float candle_high   = src_high[candle_idx]
                float candle_low    = src_low[candle_idx]
                float candle_open   = src_open[candle_idx]
                float candle_close  = src_close[candle_idx]

                float candle_range = candle_high - candle_low
                float body_size    = math.abs(candle_close - candle_open)
                float body_percent = candle_range > 0 ? body_size / candle_range : 0.0

                // Track direction for Component 6
                bool correct_direction = isDemand ? (candle_close > candle_open) : (candle_close < candle_open)
                if correct_direction
                    correct_dir_count += 1

                // Only score candles moving in the correct departure direction
                if correct_direction and candle_range > 0

                    // === COMPONENT 1: Magnitude (30pts) — Log curve ===
                    float range_ratio = candle_range / (ref_range * 0.10)
                    float magnitude_score = math.min(math.log(1 + range_ratio) / math.log(3), 1.0) * 30.0

                    // === COMPONENT 2: Body Dominance (15pts) ===
                    float dominance_score = body_percent * 15.0

                    // === COMPONENT 3: Wick Rejection (15pts) ===
                    // Measure wick on the DEPARTURE side (side price is leaving from)
                    float departure_wick = 0.0
                    if isDemand
                        // Bullish departure: lower wick should be small
                        departure_wick := math.min(candle_open, candle_close) - candle_low
                    else
                        // Bearish departure: upper wick should be small
                        departure_wick := candle_high - math.max(candle_open, candle_close)
                    float wick_ratio = departure_wick / candle_range
                    float wick_score = (1.0 - wick_ratio) * 15.0

                    // === COMPONENT 4: Close Position (15pts) ===
                    // Where does candle close within its range?
                    float close_position = (candle_close - candle_low) / candle_range
                    // Demand: close near high (1.0) = good. Supply: close near low (0.0) = good.
                    float relevant_position = isDemand ? close_position : (1.0 - close_position)
                    float close_score = relevant_position * 15.0

                    float candle_strength = magnitude_score + dominance_score + wick_score + close_score

                    qualifying_count += 1
                    total_score      += candle_strength
                    if candle_strength > best_candle_score
                        best_candle_score := candle_strength

        // ── Component 5: FVG Creation (15pts) — Zone-level check ──────────────────────
        // Checks if departure candles created a Fair Value Gap (imbalance)
        // Requires at least 2 departure candles (base_end_idx >= 2)
        float fvg_score = 0.0
        if base_end_idx >= 2
            // A = base candle [base_end_idx], C = departure candle 2 [base_end_idx - 2]
            float candle_a_high = src_high[base_end_idx]
            float candle_a_low  = src_low[base_end_idx]
            float candle_c_high = src_high[base_end_idx - 2]
            float candle_c_low  = src_low[base_end_idx - 2]

            if isDemand
                // Bullish FVG: C's low > A's high (gap above)
                if candle_c_low > candle_a_high
                    fvg_score := 15.0
            else
                // Bearish FVG: C's high < A's low (gap below)
                if candle_c_high < candle_a_low
                    fvg_score := 15.0

        // ── Component 6: Directionality (10pts) — From loop counter ───────────────────
        float dir_score = 0.0
        if departure_candles > 0
            float dir_ratio = correct_dir_count / departure_candles
            if dir_ratio >= 1.0
                dir_score := 10.0   // All candles correct direction
            else if dir_ratio >= 0.66
                dir_score := 6.0    // 2/3 correct
            else if dir_ratio > 0.0
                dir_score := 3.0    // 1/3 correct
            // 0/3 = 0pts

        // ── Multi-candle accumulation (unchanged) ─────────────────────────────────────
        float extra_bonus = qualifying_count > 1 ? (total_score - best_candle_score) * 0.40 : 0.0
        float per_candle_total = best_candle_score + extra_bonus

        // ── Final composite score ─────────────────────────────────────────────────────
        // Per-candle components (1-4) max = 75pts via accumulation
        // Zone-level components (5-6) max = 25pts
        float raw_score = per_candle_total + fvg_score + dir_score

        // Floor of 5.0 to avoid masking weak departures, cap at 100
        float departure_strength = math.min(math.max(raw_score, 5.0), 100.0)
        departure_strength
```

**Step 2: Verify no signature changes**

The function signature `calculate_departure_strength(int, bool, series float, series float, series float, series float, series float, series float, float)` is unchanged. The `src_volume` and `vol_sma_20` parameters are kept in the signature (unused but required to avoid breaking callers). All callers in `SND_Strategy.pine` continue to work without modification.

**Step 3: Publish library in TradingView**

1. Open `SND_Core` library in TradingView Pine Editor
2. Replace function body with the code above
3. Click "Publish" → "Update" to push new version

**Step 4: Recompile strategy**

1. Open `SND_Strategy` in TradingView Pine Editor
2. Click "Save" to recompile against updated library
3. Verify no compilation errors

**Step 5: Visual verification**

1. Check webhook alert payloads — `departure_strength` should now show varied values (not all 50)
2. Look at generated signals on the chart:
   - Strong departures (big candle + FVG + clean wicks) should score 70+
   - Weak departures (small candle, wrong direction wicks) should score < 40
3. Check dashboard display shows realistic departure_strength values

**Step 6: Commit**

```bash
git add scripts/pinescript/libraries/SND_Core.pine
git commit -m "feat: departure strength v3 — 6-component pure price action scoring

- Replace 3-component (magnitude/body/volume) with 6-component scoring
- Drop Forex tick volume (noisy/unreliable)
- Add: Wick Rejection (15pts) — small departure-side wick = decisive
- Add: Close Position (15pts) — closing at range extreme = conviction
- Add: FVG Creation (15pts) — institutional imbalance detection
- Add: Directionality (10pts) — sustained momentum across candles
- Fix: Magnitude uses log curve instead of linear cap (fixes score clustering)
- Fix: Guard condition < 1 instead of < 3 (was forcing 50.0 for most zones)
- Zero extra loops — all computed within existing iteration"
```
