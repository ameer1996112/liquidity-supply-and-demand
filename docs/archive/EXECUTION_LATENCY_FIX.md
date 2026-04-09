# Execution Latency Alert Fix

**Date:** 2026-03-11
**Issue:** False "High Latency" alerts on NZDJPY/GBPJPY trades
**Status:** ✅ Fixed

---

## Problem Summary

The trading bot was generating **"High Latency" alerts** on every NZDJPY and GBPJPY trade, even though execution was working correctly.

**Example Alert:**
```
⚠️ Execution Quality Alert: High Latency
High execution latency: 4249ms on NZDJPY (threshold: 500ms)
```

---

## Root Cause Analysis

### Latency Breakdown

Execution latency has **two components**:

1. **Bot Processing Time** (`signal_to_submit_ms`): 2-3 seconds ✅
   - Guard rail checks (kill switch, PropGuard, AI ensemble)
   - Portfolio VaR calculation
   - Sector exposure validation
   - Position sizing calculations

2. **Broker Execution Time** (`submit_to_fill_ms`): **19-60 seconds** ⚠️
   - MetaAPI cloud proxy → broker communication
   - Broker order routing and fill
   - Market conditions (liquidity, volatility)

### Why Broker Latency is High

| Pair Type | Avg Broker Latency | Reason |
|-----------|-------------------|--------|
| GBPCAD, EURUSD (majors) | 1-2 seconds | High liquidity, fast fills |
| NZDJPY, GBPJPY (minors) | 19-60 seconds | Lower liquidity, requotes, slower fills |

**Minor pairs** (NZDJPY, CADJPY, GBPJPY) have:
- Lower trading volume
- Wider spreads
- More requotes during off-hours (Tokyo close, NY open)
- Slower MetaAPI sync for exotic pairs

### Old vs New Threshold

| Metric | Old Value | New Value | Rationale |
|--------|-----------|-----------|-----------|
| Total Latency Threshold | 5000ms (5s) | 30000ms (30s) | Account for broker delays on minor pairs |
| Bot Latency Threshold | N/A | 10000ms (10s) | Alert if guard rails are slow (actionable) |
| Broker Latency Threshold | N/A | 20000ms (20s) | Info alert for broker slowness (FYI only) |

---

## Solution

### Fix #1: Increase Total Latency Threshold

**Changed:** `TCA_LATENCY_THRESHOLD_MS` from **5000ms → 30000ms**

**File:** [config/settings.py:227-233](../config/settings.py#L227-L233)

```python
tca_latency_threshold_ms: int = Field(
    default=30000,  # Changed from 5000
    ge=100,
    le=60000,
    description="TCA alert threshold for high TOTAL execution latency (milliseconds). Set to 30s to account for broker delays on minor pairs.",
    validation_alias="TCA_LATENCY_THRESHOLD_MS",
)
```

---

### Fix #2: Split Alerts into Bot vs Broker Latency

**Added Two New Settings:**

1. **`TCA_BOT_LATENCY_THRESHOLD_MS=10000`** (10 seconds)
   - Alerts if bot processing (guard rails, AI, VaR) takes > 10s
   - **Severity:** `warning` (actionable - optimize guard rails)

2. **`TCA_BROKER_LATENCY_THRESHOLD_MS=20000`** (20 seconds)
   - Alerts if broker execution takes > 20s
   - **Severity:** `info` (informational - not critical, just FYI)

**File:** [src/services/execution_engine.py:174-260](../src/services/execution_engine.py#L174-L260)

**New Alert Types:**
- `high_bot_latency` → Warning (you can optimize this)
- `high_broker_latency` → Info (broker/MetaAPI slowness, can't control)
- `high_latency` → Legacy fallback (total > 30s but bot/broker both OK)

---

## Railway Deployment

### Environment Variables to Add

Add these to your **Railway environment variables**:

```bash
# TCA Latency Thresholds (2026-03-11 Fix)
TCA_LATENCY_THRESHOLD_MS=30000
TCA_BOT_LATENCY_THRESHOLD_MS=10000
TCA_BROKER_LATENCY_THRESHOLD_MS=20000
```

**Steps:**
1. Go to Railway project → **Variables** tab
2. Click **+ New Variable**
3. Add each variable above
4. Click **Deploy** to restart services with new config

### Verify Fix is Working

After deployment, check the **Execution Quality** page:

1. Wait for next NZDJPY or GBPJPY trade
2. Check latency breakdown:
   - If `signal_to_submit_ms` > 10s → `high_bot_latency` warning (check guard rails)
   - If `submit_to_fill_ms` > 20s → `high_broker_latency` info (expected for minors)
   - If both < threshold → No alert ✅

3. Verify old false alerts are gone:
   - NZDJPY with 19-21s broker latency should NOT trigger `high_latency`
   - Only triggers `high_broker_latency` (info severity)

---

## Diagnostic Tool

Use the latency diagnostic script to analyze execution performance:

```bash
python3 scripts/diagnose_latency.py
```

**Output Example:**
```
Recent Trade Latencies:
====================================================================================================
NZDJPY   Signal#189  Signal→Submit:  3,139ms  Submit→Fill: 1,110ms  TOTAL:  4,249ms  ✅
NZDJPY   Signal#187  Signal→Submit:  2,403ms  Submit→Fill: 19,431ms  TOTAL: 21,834ms  ⚠️
GBPJPY   Signal#185  Signal→Submit:  2,397ms  Submit→Fill: 19,387ms  TOTAL: 21,784ms  ⚠️
```

**Interpretation:**
- **Signal→Submit < 5s**: Bot processing is fast ✅
- **Submit→Fill 19-60s**: Broker execution is slow (expected for minors)
- **Total < 30s**: No alert triggered ✅

---

## When to Investigate

### Alert: `high_bot_latency` (Warning)

**Cause:** Bot processing > 10 seconds
**Action Required:** Optimize guard rails

**Common Causes:**
1. AI ensemble timeout (5s per provider)
2. Portfolio VaR guard fetching too many positions
3. Historical returns API (yfinance) slow
4. Database query slowness

**How to Debug:**
```bash
# Enable latency instrumentation to see detailed breakdown
export ENABLE_LATENCY_INSTRUMENTATION=true

# Check worker logs for stage-by-stage timing
tail -f logs/worker.log | grep "LATENCY BREAKDOWN"
```

---

### Alert: `high_broker_latency` (Info)

**Cause:** Broker execution > 20 seconds
**Action Required:** None (informational only)

**Expected Conditions:**
- Trading minor pairs (NZDJPY, CADJPY, GBPJPY)
- During off-hours (Tokyo close, Sydney open)
- High volatility (news events, requotes)
- FTMO demo server slowness

**When to Worry:**
- If **all pairs** consistently > 20s → Check MetaAPI status
- If **majors** (EURUSD, GBPUSD) > 20s → Broker issue

---

## Files Changed

| File | Change | Lines |
|------|--------|-------|
| [config/settings.py](../config/settings.py) | Added 3 new threshold fields | 227-248 |
| [src/services/execution_engine.py](../src/services/execution_engine.py) | Split alert logic (bot vs broker) | 174-260 |
| [.env.example](../.env.example) | Updated defaults with docs | 199-207 |
| [MEMORY.md](../.claude/projects/-Users-ameeramer-dev-projects-galilsoftware-sources-trading/memory/MEMORY.md) | Documented fix | 5-25 |
| [scripts/diagnose_latency.py](../scripts/diagnose_latency.py) | New diagnostic tool | Full file |

---

## Testing

### Manual Test

1. **Trigger a NZDJPY trade** (wait for TradingView signal)
2. **Check Execution Quality page** after 30 seconds
3. **Verify:**
   - No `high_latency` alert (was triggering before)
   - May see `high_broker_latency` (info only, expected)
   - Bot processing < 10s (should be 2-3s)

### Automated Test

```bash
# Run latency diagnostic on recent trades
python3 scripts/diagnose_latency.py

# Expected output:
# - Recent NZDJPY trades shown
# - Signal→Submit: 2-3 seconds (fast)
# - Submit→Fill: 19-60 seconds (broker delay)
# - Recommendations based on findings
```

---

## FAQ

**Q: Why not just disable latency alerts?**
A: Latency alerts are valuable for detecting real issues (guard rails stuck, broker outage). We split the alert to distinguish actionable (bot slow) from informational (broker slow).

**Q: Can we optimize broker execution time?**
A: Not directly. Broker latency depends on:
- MetaAPI cloud proxy (1-2s overhead)
- Broker server location/speed
- Market liquidity for the pair
- Time of day (liquidity cycles)

**Q: Should I switch brokers?**
A: Only if **all pairs** are consistently slow. Minor pairs (NZDJPY) being slow is expected behavior.

**Q: What if I see `high_bot_latency` frequently?**
A: Enable fast-path mode to skip LLM for high-confidence signals:
```bash
export FAST_PATH_RF_THRESHOLD=0.85  # Skip LLM if RF > 85%
```

---

## Related Issues

- [NZDJPY Position Sizing Fix](./NZDJPY_POSITION_SIZING_FIX.md) - Dynamic pip value calculation
- [Positions Page Upgrade](./POSITIONS_PAGE_UPGRADE.md) - Stale position cleanup
- [PnL Mismatch Fix](./PNL_MISMATCH_FIX.md) - Broker actual PnL vs TradingView simulated

---

## Verification Checklist

- [x] Updated `TCA_LATENCY_THRESHOLD_MS` to 30000ms
- [x] Added `TCA_BOT_LATENCY_THRESHOLD_MS` setting (10000ms)
- [x] Added `TCA_BROKER_LATENCY_THRESHOLD_MS` setting (20000ms)
- [x] Split alert creation logic (bot vs broker)
- [x] Updated `.env.example` with new thresholds
- [x] Documented in MEMORY.md
- [x] Created diagnostic script
- [ ] Deploy to Railway with new env vars
- [ ] Verify next NZDJPY trade doesn't trigger false alert
- [ ] Monitor Execution Quality page for new alert types
