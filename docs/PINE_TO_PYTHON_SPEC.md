# Pine Script → Python Backtest Specification

This document maps **SND_Strategy.pine** logic to the Python backtest so results match TradingView.

---

## 1. Demand Zone Creation (How Zones Are Drawn)

### 1.1 Pattern Detection (Recent Bars)

Demand zones are created when price reverses from bearish to bullish. Pine uses `barstate.isconfirmed` and `bar_index > 10`.

| Pattern | Condition | Base Bar | `createZone` args |
|---------|-----------|----------|-------------------|
| 3+1 | `bullish(0) bullish(1) bullish(2) bearish(3)` | bar_index - 3 | (3, true, false, 1, 3, id) |
| 2+1 | `bullish(0) bullish(1) bearish(2)` | bar_index - 2 | (2, true, false, 1, 2, id) |
| 1+1 | `bullish(0) bearish(1)` | bar_index - 1 | (1, true, false, 1, 1, id) |

`baseIdx` = offset from current bar (e.g. 3 means base at `bar_index - 3`).

### 1.2 Historical Scan (Backfill)

On first bar after `bar_index > 50`, scan backward from `i = 2` to `min(100, bar_index)`:

| Pattern | Condition | Base Bar |
|---------|-----------|----------|
| 3+1 | `bearish(i) bullish(i-1) bullish(i-2) bullish(i-3)` | bar_index - i |
| 2+1 | `bearish(i) bullish(i-1) bullish(i-2)` | bar_index - i |
| 1+1 | `bearish(i) bullish(i-1)` | bar_index - i |

Historical zones get `isHistorical = true` and are **blocked from entry**.

### 1.3 Base Bar Deduplication

Pine uses `time[baseIdx]` (timestamp) in `used_demand_base_times` / `used_supply_base_times`.  
Python uses `pd.Timestamp(base_time).timestamp()` — equivalent.

### 1.4 Zone Coordinates

| Type | Condition | Top | Bottom |
|------|-----------|-----|--------|
| **Accuracy** (demand) | `high[baseIdx] > high[reactionIdx]` | baseOpen | baseLow |
| **Normal** (demand) | else | baseHigh | baseLow |

`reactionIdx = baseIdx - 1` (candle that started the move after the zone candle).

### 1.5 Supply Zone Patterns

Same logic, inverted:

- Recent: `bearish(0) bearish(1) bullish(2)` etc.
- Historical: `bullish(i) bearish(i-1) bearish(i-2)` etc.

---

## 2. Liquidity Detection (When Liquidity Happens)

### 2.1 Pine Logic (Inducement Model)

Pine uses **3-candle Makuchaku pivots** and **inducement linking** (`use_inducement_linking = true`).

**Demand zone:**
- **Inducement (liqLow)**: Lowest 3-candle pivot **LOW** that is **above** zone top (`pLow > z.top`)
- **Target (liqHigh)**: **Absolute highest HIGH** in range `[createdBarIndex ... inducementBar - 1]`
- `structureSweepLevel` = liqHighPrice (what must be swept for entry)

**Supply zone:**
- **Inducement (liqHigh)**: Highest 3-candle pivot **HIGH** that is **below** zone bottom (`pHigh < z.bottom`)
- **Target (liqLow)**: **Absolute lowest LOW** in range `[createdBarIndex ... inducementBar - 1]`
- `structureSweepLevel` = liqLowPrice

### 2.2 3-Candle Pivot (Makuchaku)

```pine
// Pivot LOW: low[1] < low[0] AND low[1] < low[2]
Core.is_makuchaku_pvt_low(low, off) => low[off+1] < low[off] and low[off+1] < low[off+2]

// Pivot HIGH: high[1] > high[0] AND high[1] > high[2]
Core.is_makuchaku_pvt_high(high, off) => high[off+1] > high[off] and high[off+1] > high[off+2]
```

Pivot is at bar `bar_index - (off + 1)`.

### 2.3 Inducement Sweep (Demand)

- When: `low <= z.liqLowPrice + sweepTolerance` (sweepTolerance = 0.5 pips)
- Sets: `liquiditySwept = true`, `liquiditySweptBarIndex = bar_index`, `causedSweep = true`

### 2.4 Target Sweep (Demand)

- When: `high >= z.liqHighPrice - targetSweepTolerance` (0.5 pips)
- Sets: `targetSwept = true`, `targetSweptBarIndex = bar_index`
- Both inducement and target must be swept before priming.

### 2.5 Python Gap

Python currently uses:
- `lookback_high = max(high over 10 bars)`, `lookback_low = min(low over 10 bars)`
- `detect_liquidity_sweep(current_high, current_low, lookback_high, lookback_low, is_demand)` → `current_low <= lookback_low` for demand
- Sets `liq_high_price = h`, `liq_low_price = l` from same lookback

This does **not** match Pine:
- Pine uses pivot-based inducement above zone + absolute target high before inducement
- Python uses generic 10-bar low/high

---

## 3. Zone Mitigation & touchedPreSweep

### 3.1 Strict Mitigation (Before Sweep)

Zone is killed if **any** of these occur **before** liquidity sweep:

1. `closes_inside` — close inside zone
2. `breaches_zone` — demand: low < z.bottom; supply: high > z.top
3. `wicks_into_zone` — demand: low in [z.bottom, z.top]; supply: high in zone

If killed: `mitigated = true`, `touchedPreSweep = true`. Zone **never** becomes primed.

### 3.2 Exception

If current bar **simultaneously** sweeps target (`high > structureSweepLevel` for demand), do **not** mitigate.

### 3.3 Python Gap

- Python does **not** track `touchedPreSweep`
- Python does **not** run mitigation logic (no `closes_inside`, `breaches_zone`, `wicks_into_zone`)

---

## 4. Priming Conditions (When Zone Becomes Ready)

All must be true:

| Condition | Demand | Supply |
|-----------|--------|--------|
| `liquidityValid` | Pivot scan completed | Same |
| `liquiditySwept` | low ≤ inducement low | high ≥ inducement high |
| `targetSwept` | high ≥ target high | low ≤ target low |
| `causedSweep` | Set when sweep detected | Same |
| `touchedPreSweep` | Must be false | Same |
| `isHistorical` | Must be false | Same |
| Touch in zone | low in [z.bottom, z.top] | high in zone |
| `touchCount <= 1` | First touch only | Same |
| `bar_index >= liquiditySweptBarIndex` | — | — |
| `targetSweptBarIndex` set | — | — |
| `liq_entry_max_dist` | Zone within N pips of liquidity | Same |
| 24h freshness | `time - startTime <= 24h` | Same |

### 4.1 Liquidity Distance

- Demand: `liqLowPrice - z.top` in pips ≤ `effective_liq_entry_max_dist`
- Supply: `z.bottom - liqHighPrice` in pips ≤ `effective_liq_entry_max_dist`
- Skipped for indices.

---

## 5. Entry Models (Priority Order)

1. **FLIP**: `close > open` and `close[1] < open[1]`; if `require_htf_flip`: also at :00, :15, :30, :45
2. **BREAK_CANDLE**: `(open > primedRefClose OR high > primedRefHigh)` and `close > open` and not flip
3. **DIR_CLOSE**: `close > open` OR bullish hammer (lower wick ≥ 60% range, body ≤ 30%)

Python currently does **not** check hammer; only body direction.

---

## 6. Zone Invalidation (After Creation)

| Condition | Demand | Supply |
|-----------|--------|--------|
| Time | `time - startTime > 24h` | Same |
| Close inside | bearish close inside zone | bullish close inside zone |
| Close beyond | close < z.bottom | close > z.top |
| Wick (if `invalidate_on_wick`) | low < z.bottom | high > z.top |

---

## 7. Implementation Checklist

| Item | Pine | Python | Status |
|------|------|--------|--------|
| Zone creation patterns | ✓ | ✓ | ✅ Aligned |
| Accuracy zones | ✓ | ✓ | ✅ Aligned |
| Base dedup (time) | ✓ | ✓ | ✅ Aligned |
| **Pivot liquidity** | f_scan_demand_liquidity | 10-bar lookback | ❌ Gap |
| **Inducement/target** | liqLow above zone, liqHigh from range | Generic high/low | ❌ Gap |
| **Inducement sweep** | low ≤ liqLow + 0.5 pip | current_low ≤ lookback_low | ⚠️ Different |
| **Target sweep** | high ≥ liqHigh - 0.5 pip | high ≥ liq_high | ⚠️ Different semantics |
| **touchedPreSweep** | Mitigation before sweep | Not tracked | ❌ Missing |
| **Mitigation** | closes/breach/wicks before sweep | Not implemented | ❌ Missing |
| **liq_entry_max_dist** | Enforced | Not enforced | ❌ Missing |
| Entry models | Flip, Break, DirClose | ✓ | ✅ Aligned |
| Hammer pattern | DirClose accepts hammer | Body only | ⚠️ Simplified |
| Timezone | Asia/Jerusalem | UTC | ⚠️ Different |
| 24h freshness | ✓ | Not checked | ❌ Missing |

---

## 8. Visual: Demand Zone + Liquidity Flow

```
Price
  ^
  |     ┌── Target (liqHigh) = highest high in [createdBar ... inducementBar-1]
  |     │
  |     │  ╭─ Inducement (liqLow) = lowest pivot LOW above zone
  |     │  │
  |  ┌──┴──┴─ Zone top
  |  │  D-Zone
  |  └── Zone bottom
  |
  +──────────────────────────────────> Bar index
           createdBar    inducementBar
  
  Entry flow:
  1. Zone created
  2. Inducement pivot found above zone
  3. Target = max high between zone and inducement
  4. Price sweeps inducement (low ≤ liqLow) → liquiditySwept
  5. Price sweeps target (high ≥ liqHigh) → targetSwept
  6. Price touches zone (low in zone) → primed
  7. Bullish close / flip / break → ENTRY
```

---

## 9. Next Steps

1. **Port `f_scan_demand_liquidity`** and `f_scan_supply_liquidity` to Python
2. **Port `f_check_demand_sweeps`** and `f_check_supply_sweeps`
3. Add **mitigation** and **touchedPreSweep** tracking
4. Enforce **liq_entry_max_dist**
5. Add **24h freshness** check
6. Optionally add **hammer** pattern for DIR_CLOSE
