# SND Strategy Logic Audit: Python vs Pine

## Strategy Logic Alignment Summary

**What’s aligned with your Pine logic today**

| Area | Python behavior |
|------|-----------------|
| **Zone creation** | Same patterns (bullish/bearish reversal, accuracy zones) |
| **Entry models** | FLIP, DirClose, BreakOfCandle (same order) |
| **Touch condition** | Demand: low inside zone; Supply: high inside zone |
| **Priming** | Requires liquidity sweep + target swept + caused sweep |
| **Historical zones** | Blocked – no entries from backfill zones |
| **Time filters** | Dead zone (xx:50–xx:00), trading hours (7–22) |
| **Exits** | SL, TP, time-based (max bars held) |

**Known differences (simplified in Python)**

| Area | Pine | Python |
|------|------|--------|
| **Liquidity** | Pivot-based inducement/target | 10-bar lookback high/low |
| **touchedPreSweep** | Zone touched before sweep = invalid | Not tracked |
| **liq_entry_max_dist** | Zone within 50 pips of liquidity | Not enforced |
| **Timezone** | Asia/Jerusalem | UTC |
| **Candle direction** | Bullish OR hammer / Bearish OR inv. hammer | Only body direction |

---

## Critical Pine Rules (from validate_entry_conditions)

| Rule | Pine | Python | Status |
|------|------|--------|--------|
| **Block historical zones** | `z.isHistorical` → cannot enter | Skip zones with `is_historical=True` | ✅ Fixed |
| **causedSweep** | Zone must have caused the sweep | Set when liquidity sweep detected | ✅ Fixed |
| **targetSwept** | Target (high for demand, low for supply) must be swept | Set via liq_high_price/liq_low_price | ✅ Fixed |
| **require_liquidity_sweep** | liquidityValid + liquiditySwept + targetSwept | liquidity_swept + target_swept + caused_sweep | ✅ Fixed |
| **Touch in zone** | Demand: low inside [z.bottom, z.top]; Supply: high inside | Demand: low in [z.bottom,z.top]; Supply: high in zone | ✅ Fixed |
| **touchedPreSweep** | Zone touched before sweep = invalid | Not tracked | ⚠️ Missing |
| **liq_entry_max_dist** | Zone within 50 pips of liquidity | Not enforced | ⚠️ Missing |
| **Trading hours** | Asia/Jerusalem 7-22 | UTC 7-22 | ⚠️ Different TZ |
| **correct_direction** | Bullish OR hammer for demand; Bearish OR inv. hammer for supply | Only body direction | ⚠️ Simplified |

## Entry Model (Pine matches)

- Flip, DirClose, BreakOfCandle ✓
- HTF flip at :00, :15, :30, :45 ✓

## Liquidity (Simplified in Python)

- **Pine**: Pivot-based inducement/target, f_scan_demand_liquidity, f_check_demand_sweeps
- **Python**: 10-bar lookback high/low for sweep detection
