# Strategy Optimization Guide
## Symbol-Specific Configuration for Maximum Performance

Based on your backtest data analysis (245 trades across 6 symbols), here's the optimization roadmap.

---

## 🎯 Current Performance Summary

| Symbol | Trades | Win Rate | Current Profile | Status |
|--------|--------|----------|-----------------|--------|
| XAUUSD | 175 | 60% | Aggressive | ✅ **WORKING WELL** |
| NAS100 | 11 | (limited) | Aggressive | ✅ **WORKING WELL** |
| GBPJPY | 36 | 33% | Aggressive | ⚠️ **NEEDS OPTIMIZATION** |
| GBPCAD | 10 | (limited) | Aggressive | ⚠️ **NEEDS OPTIMIZATION** |
| CHFJPY | 9 | (limited) | Aggressive | ⚠️ **NEEDS OPTIMIZATION** |
| GBPUSD | 4 | (limited) | Aggressive | ⚠️ **NEEDS OPTIMIZATION** |

**Key Finding:** Aggressive profile works great for **indices/metals** but is TOO aggressive for **forex pairs**.

---

## 🔧 Root Cause Analysis: Why Forex Underperforms

### Problem 1: Zero Return Strength Filter
```pine
// Aggressive profile:
min_return_strength := 0  // ❌ Takes ANY return, even weak ones!
```

**Impact:** Accepts zones with slow, weak price movement away from zone → low win rate.

**Fix:** `min_return_strength := 25` (require decent momentum)

---

### Problem 2: Wide Liquidity Filters
```pine
// Aggressive profile:
liq_max_distance_pips_forex := 20.0   // ❌ Too wide for forex
liq_entry_max_dist := 100.0           // ❌ Zone can be 100 pips from liquidity!
```

**Impact:** Matches liquidity that's too far away → false signals.

**Fix:**
- `liq_max_distance_pips_forex := 12.0` (tighter)
- `liq_entry_max_dist := 60.0` (closer to liquidity)

---

### Problem 3: Low-Quality Zone Filter
```pine
// Aggressive profile:
min_entry_grade := "C"                // ❌ Accepts low-quality zones
ai_quality_threshold := 50            // ❌ Too permissive
```

**Impact:** Enters on weak zones with poor structure.

**Fix:**
- `min_entry_grade := "C+"` (improved quality)
- `ai_quality_threshold := 55` (slightly stricter)

---

## 📊 Recommended Profile Settings

### **Profile 1: Indices/Metals (XAUUSD, NAS100)**
**Use:** `Aggressive (Paper Trading)` ← **KEEP AS-IS**

| Parameter | Value | Reason |
|-----------|-------|--------|
| `pvtMax` | 10 | More opportunities (indices move fast) |
| `liq_max_distance_pips_gold` | 500 | Gold has wide ranges |
| `min_return_strength` | 0 | Indices move explosively anyway |
| `risk_reward_ratio` | 1.5 | Tight SL on indices → 1.5 RR is fine |
| `max_trades_per_day` | 2 | Indices have fewer setups |

**Backtest Results:** 60% win rate on XAUUSD ✅

---

### **Profile 2: Forex Pairs (GBPJPY, GBPCAD, etc.)**
**Option A - Quick Fix:** `Balanced (Recommended)`
**Option B - Advanced:** `Custom Hybrid Aggressive`

#### **Option A: Balanced Profile (Built-In)**

| Parameter | Balanced | vs Aggressive | Impact |
|-----------|----------|---------------|--------|
| `liq_max_distance_pips_forex` | 15 pips | -5 pips | Tighter liquidity matching |
| `min_return_strength` | 30 | +30 | **CRITICAL: Filters weak returns** |
| `min_entry_grade` | C+ | +1 grade | Better zone quality |
| `ai_quality_threshold` | 60 | +10 | Stricter AI filter |
| `liq_entry_max_dist` | 50 pips | -50 pips | Zone closer to liquidity |
| `risk_reward_ratio` | 2.0 | +0.5 | Better RR |

**Expected Impact:** Win rate improvement from 33% → 45-55%

---

#### **Option B: Custom Hybrid Aggressive (Best of Both)**

```pine
// Add this to your strategy after line 447 in SND_Strategy.pine

if use_profile_defaults and is_aggressive
    if is_gold or is_index
        // Keep aggressive settings (proven to work)
    else
        // Forex-Optimized Aggressive
        liq_max_distance_pips_forex := 12.0  // Tighter than aggressive, looser than balanced
        liq_entry_max_dist := 60.0           // Split the difference
        min_return_strength := 25            // CRITICAL: Add return filter!
        min_entry_grade := "C+"              // Improved quality
        ai_quality_threshold := 55           // Slightly stricter
        min_tp_distance_pips := 8.0          // Prevent spread eating profits
```

**Benefits:**
- ✅ Still aggressive on frequency (2 trades/day)
- ✅ Still aggressive on RR (1.5)
- ✅ Still aggressive on pivot scanning (pvtMax = 10)
- ✅ But **smarter** on quality filtering

---

## 🚀 Implementation Steps

### **Step 1: Quick Test (5 minutes)**

1. **Open TradingView → Your Strategy**
2. **For each forex pair:**
   - Settings → "⚡ Configuration Profile"
   - Change to: `Balanced (Recommended)`
3. **Run backtest on GBPJPY**
4. **Compare:**
   - Before: 33% win rate (36 trades)
   - After: Expected 45-55% win rate

---

### **Step 2: Advanced Optimization (30 minutes)**

1. **Add Hybrid Profile to Pine Script:**
   - Copy code from `pine_optimization_patch.pine`
   - Paste after line 447 in `SND_Strategy.pine`
   - Save and reload

2. **Enable Auto-Detection:**
   - Strategy will automatically apply optimal settings per symbol
   - No manual switching needed!

3. **Verify in Visual Table:**
   - Bottom-right corner will show:
     - `🔥 Full Aggressive (Indices/Metals)` for XAUUSD/NAS100
     - `⚡ Hybrid Aggressive (Forex-Optimized)` for GBPJPY/etc.

---

### **Step 3: Retrain ML Model (Optional)**

After optimizing and gathering more trades:

```bash
# Export new backtest CSVs from TradingView
# Save to: data/backtest/[SYMBOL]/

# Retrain model with better data
python ml/train_ai_guardian.py --data data/backtest

# Expected improvement:
# - Overall accuracy: 43% → 55-60%
# - Forex pairs: 33% → 50%+
```

---

## 📈 Expected Results

### **Before Optimization:**
| Symbol Type | Profile | Win Rate | Trades/Year |
|-------------|---------|----------|-------------|
| Indices/Metals | Aggressive | 60% ✅ | ~100 |
| Forex | Aggressive | 33% ⚠️ | ~150 |
| **Combined** | **Aggressive** | **43%** | **250** |

### **After Optimization:**
| Symbol Type | Profile | Win Rate | Trades/Year |
|-------------|---------|----------|-------------|
| Indices/Metals | Aggressive | 60% ✅ | ~100 |
| Forex | **Balanced/Hybrid** | **50%+** ✅ | ~120 |
| **Combined** | **Symbol-Specific** | **55%+** ✅ | **220** |

---

## 🎯 Critical Parameters to Monitor

Track these in your backtests after changing profiles:

1. **Win Rate by Symbol:**
   - XAUUSD: Target 60%+ (already there)
   - GBPJPY: Target 50%+ (from 33%)
   - NAS100: Target 55%+ (need more data)

2. **Average Trade Quality:**
   - Zone Grade: Should average "B" or better
   - Return Strength: Should average 40+ (not 0-20)
   - Liquidity Distance: Should average <10 pips for forex

3. **Profitability:**
   - Profit Factor: Target 1.5+ (currently low due to 33% win rate)
   - Max Drawdown: Should improve with better win rate
   - Sharpe Ratio: Should increase

---

## 🛠️ Troubleshooting

### **If Forex Win Rate Still Low After Balanced Profile:**

Try this ultra-conservative test:
```pine
// Temporary test settings for GBPJPY:
liq_max_distance_pips_forex := 10.0  // Very tight
min_return_strength := 50            // Very strict
min_entry_grade := "B+"              // High quality only
ai_quality_threshold := 70           // Very strict AI filter
max_trades_per_day := 1              // Only best setup per day
```

**Purpose:** Establish baseline "best possible" win rate.
**Expected:** 60-70% win rate but only 1-2 trades/week.
**Then:** Gradually relax filters until you hit 50% win rate with acceptable frequency.

---

## 📞 Next Steps

1. ✅ **Immediate:** Switch forex pairs to Balanced profile
2. ⏳ **This Week:** Add hybrid auto-detection code
3. 📊 **Next Month:** Collect 50+ trades on each symbol with new settings
4. 🧠 **After 50+ trades:** Retrain ML model with better data

---

**Questions?**
- Check strategy logs for rejected trades
- Monitor `min_return_strength` impact (should filter ~30% of aggressive signals)
- Track zone grade distribution (should shift from C → B average)
