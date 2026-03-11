# Prop Firm & Analytics Pages Fix Plan

## Issues Identified

### 1. **Daily PnL Mismatch (Prop Firm Page)**

**Alpha Capital Dashboard shows:**
- Mar 04: +$25 (100.0% win rate)
- Mar 05: +$1 (100.0% win rate)
- Mar 09: -$593 (20.0% win rate)
- Mar 10: -$479 (0.0% win rate)
- Mar 11: -$1,109 (0.0% win rate)

**TradeOps Database Reality:**
- Mar 04: No data in DB (ACG shows green day)
- Mar 05: **+$23.37** (2 wins, 3 losses) ✅ CORRECT
- Mar 09: **-$654.99** (1 win, 5 losses) ❌ ACG shows -$593
- Mar 10: **+$44.69** (2 wins, 5 losses) ❌ ACG shows -$479 AND WRONG WIN RATE
- Mar 11: **-$549.92** (0 wins, 2 losses) ❌ ACG shows -$1,109

**Root Causes:**
1. **Stale Position Contamination**: 7 "ghost" positions (IDs 160, 165-169, 171) were created on Mar 5 but never executed on broker. They show `pnl=$0.00` and `closed_at=2026-03-11`, contaminating March 11 data.

2. **Date Attribution Issue**: The cleanup script closed these stale positions on March 11, so they're counted in March 11's PnL even though they were created March 5 and never traded.

3. **PnL Calculation Source**: Prop firm page uses `trading_signals.pnl_usd` which now has ACTUAL broker PnL (after your recent fix), but ACG might be using a different calculation or cached data.

### 2. **Analytics Page Issues**

**Prop Firm Page Calendar View** (uses `CalendarPnlView` + MetaAPI trades):
- Shows correct daily PnL breakdown
- Merges Supabase signals with MetaAPI trade history
- Uses `metaApiHistory.trades` for actual broker data

**Analytics Page Breakdown** (uses `/analytics/breakdown` API):
- Uses `trading_signals` table with `status IN ('closed', 'executed')`
- Groups by hour/day/symbol using `created_at` timestamp
- Filters by `account_id` (optional)

**Potential Issues:**
- If Analytics page doesn't filter out the 7 stale positions
- Date grouping might use `created_at` instead of `closed_at`
- Might not be filtering by account properly

---

## Fix Strategy

### Phase 1: Database Cleanup ✅ DONE
- [x] Cleanup script closed 7 stale positions (IDs 160, 165-169, 171)
- [x] These now show `status=CLOSED`, `pnl_usd=$0.00`, `closed_at=2026-03-11`

### Phase 2: Prop Firm Page Fixes

#### Fix 1: Filter Out Zero-PnL Trades in Daily Grouping
**File**: [api_prop_firm.py](src/api_prop_firm.py)
**Location**: `/api/prop-firm/history` endpoint (lines 121-156)

**Change**: When calculating daily PnL, exclude trades with `pnl_usd = 0` or `pnl = 0` to prevent stale position contamination.

```python
# BEFORE
signals = _fetch_closed_signals(...)

# AFTER
signals = [s for s in _fetch_closed_signals(...) if (s.get('pnl_usd') or s.get('pnl') or 0) != 0]
```

#### Fix 2: Use `closed_at` Instead of `created_at` for Date Grouping
**File**: [CalendarPnlView.tsx](frontend/src/components/journal/CalendarPnlView.tsx)
**Issue**: Currently groups trades by signal creation date, not close date

**Change**: Update date extraction to use `closed_at` timestamp:
```tsx
// BEFORE
const d = format(new Date(s.created_at), 'MMM dd')

// AFTER
const d = format(new Date(s.closed_at || s.created_at), 'MMM dd')
```

#### Fix 3: MTMGuardian Daily PnL Calculation
**File**: [mtm_guardian.py](src/services/mtm_guardian.py)
**Issue**: Daily PnL should use `closed_at` date filter, not `created_at`

**Change**: Update daily PnL query to filter by `closed_at >= today_start`

### Phase 3: Analytics Page Fixes

#### Fix 1: Use `closed_at` for Date Grouping
**File**: [api_analytics.py](src/api_analytics.py)
**Lines**: 188-199 (hour_key, dow_key functions)

**Change**:
```python
# BEFORE - uses created_at
def hour_key(s):
    dt = datetime.fromisoformat(s["created_at"].replace("Z", "+00:00"))
    return f"{dt.hour:02d}:00"

def dow_key(s):
    dt = datetime.fromisoformat(s["created_at"].replace("Z", "+00:00"))
    return DAY_NAMES[dt.weekday()]

# AFTER - uses closed_at (falls back to created_at)
def hour_key(s):
    dt_str = s.get("closed_at") or s["created_at"]
    dt = datetime.fromisoformat(dt_str.replace("Z", "+00:00"))
    return f"{dt.hour:02d}:00"

def dow_key(s):
    dt_str = s.get("closed_at") or s["created_at"]
    dt = datetime.fromisoformat(dt_str.replace("Z", "+00:00"))
    return DAY_NAMES[dt.weekday()]
```

#### Fix 2: Filter Out Zero-PnL Trades
**File**: [api_analytics.py](src/api_analytics.py)
**Function**: `_fetch_closed_signals` (lines 34-86)

**Change**:
```python
# AFTER filtering for truly closed signals
def _is_truly_closed(s: dict) -> bool:
    status = (s.get("status") or "").lower()
    if status == "closed":
        # Additional check: exclude zero-PnL trades (stale positions)
        pnl = s.get("pnl_usd") or s.get("pnl") or 0
        if pnl == 0:
            return False
        return True
    # executed: must have pnl_usd or closed_at to count as a finished trade
    return s.get("pnl_usd") is not None or bool(s.get("closed_at"))

return [s for s in raw if _is_truly_closed(s)]
```

### Phase 4: Account Filter Verification

**Analytics Page** (`analytics/page.tsx`):
- Currently doesn't pass `account_id` to API
- Should add account selector like Prop Firm page

**Prop Firm Page** (`prop-firm/page.tsx`):
- ✅ Already has account selector
- ✅ Passes `resolvedAccount` to queries
- But MetaAPI trade merging might not filter by account

---

## Expected Results After Fixes

### Prop Firm Page Calendar
**March 2026 Daily PnL** (database truth):
- Mar 04: 0 trades (no data)
- Mar 05: **+$23.37** (5 trades: 2W/3L)
- Mar 09: **-$654.99** (6 trades: 1W/5L)
- Mar 10: **+$44.69** (7 trades: 2W/5L)
- Mar 11: **-$549.92** (2 trades: 0W/2L)

### Analytics Page Breakdown
- Hour-of-day analysis will use actual trade close time
- Day-of-week will reflect when trades were closed, not opened
- Zero-PnL stale positions won't skew stats

---

## Testing Checklist

- [ ] Prop Firm page shows correct daily PnL matching database
- [ ] Analytics breakdown uses `closed_at` for time grouping
- [ ] Zero-PnL trades excluded from all PnL calculations
- [ ] Account filter works correctly on both pages
- [ ] Calendar view matches Alpha Capital daily totals
- [ ] Best/worst day calculations are accurate

---

## Database Query to Verify Fix

```sql
-- Verify daily PnL by closed_at date (excludes zero-PnL stale positions)
SELECT
  DATE(closed_at) as trade_date,
  COUNT(*) as num_trades,
  SUM(CASE WHEN COALESCE(pnl_usd, pnl, 0) > 0 THEN 1 ELSE 0 END) as wins,
  SUM(CASE WHEN COALESCE(pnl_usd, pnl, 0) < 0 THEN 1 ELSE 0 END) as losses,
  ROUND(SUM(COALESCE(pnl_usd, pnl, 0))::numeric, 2) as total_pnl
FROM trading_signals
WHERE status = 'CLOSED'
  AND closed_at >= '2026-03-01'
  AND closed_at < '2026-03-12'
  AND COALESCE(pnl_usd, pnl, 0) != 0  -- Exclude zero-PnL stale positions
GROUP BY DATE(closed_at)
ORDER BY trade_date DESC;
```

**Expected Output:**
```
trade_date  | num_trades | wins | losses | total_pnl
------------|------------|------|--------|----------
2026-03-11  | 2          | 0    | 2      | -549.92
2026-03-10  | 7          | 2    | 5      | 44.69
2026-03-09  | 6          | 1    | 5      | -654.99
2026-03-05  | 5          | 2    | 3      | 23.37
```
