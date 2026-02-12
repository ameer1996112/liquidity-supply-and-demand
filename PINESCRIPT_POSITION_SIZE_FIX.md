# PineScript Position Sizing Fix - Indices & Crypto

## The Problem

Your TradingView PineScript has **TWO critical bugs** for indices like NAS100:

### Bug #1: Position Sizing Doesn't Detect Indices ❌
**File:** [SND_Strategy.pine:1065-1080](scripts/pinescript/strategies/SND_Strategy.pine#L1065-L1080)

The `calc_pos_size_units()` function only detects:
- ✅ Gold (XAU), Silver (XAG)
- ✅ Crypto (BTC, ETH)
- ✅ JPY pairs
- ✅ Forex (USD quote/base)
- ❌ **NOT indices (NAS100, US30, SPX500)**

**Result:** NAS100 falls through to generic USD quote calculation → wrong position size

### Bug #2: Webhook Conversion Doesn't Handle Indices ❌
**File:** [SND_Utils.pine:units_to_lots()](scripts/pinescript/libraries/SND_Utils.pine)

```pine
export units_to_lots(float units, string ticker) =>
    float lot_size = FOREX_LOT_SIZE  // 100,000 ← Wrong for indices!
    if str.contains(ticker, "XAU") or str.contains(ticker, "GOLD")
        lot_size := GOLD_LOT_SIZE
    else if str.contains(ticker, "XAG") or str.contains(ticker, "SILVER")
        lot_size := SILVER_LOT_SIZE
    else if str.contains(ticker, "BTC") or str.contains(ticker, "ETH")
        lot_size := CRYPTO_LOT_SIZE
    // ❌ NO CASE FOR INDICES!
    units / lot_size
```

**Result:** NAS100 uses forex lot size (100,000) instead of index lot size (1)

## The Impact

**Example: NAS100 Trade**
- Account: $50,000
- Risk: 0.5% = $250
- Entry: $25,167.60
- Stop Loss: $25,104.40
- Distance: 63.2 points

**Current (WRONG):**
1. Pine calculates units as if it's forex: `units = 250 / 63.2 = ~4 units`
2. Pine converts to lots using forex lot size: `webhook_lots = 4 / 100,000 = 0.00004 lots` ❌
3. Backend receives 0.00004 lots → rounds to 0 → **REJECTED**

**Should Be:**
1. Pine detects NAS100 as index
2. Pine calculates: `units = 250 / 63.2 = ~4 contracts`
3. Pine converts using index lot size: `webhook_lots = 4 / 1 = 4.0 lots` ✅
4. Backend receives 4.0 lots → calculates $100,668 notional → **ACCEPTED** (within limits)

## The Fix

### Step 1: Fix Position Sizing (calc_pos_size_units)

**Location:** [SND_Strategy.pine:1065-1080](scripts/pinescript/strategies/SND_Strategy.pine#L1065-L1080)

**Add index detection BEFORE the USD quote check:**

```pine
// Detect symbol type (use local variables with different names to avoid shadowing)
bool local_is_gold = str.contains(ticker, "XAU") or str.contains(ticker, "GOLD")
bool local_is_silver = str.contains(ticker, "XAG") or str.contains(ticker, "SILVER")
bool local_is_crypto = str.contains(ticker, "BTC") or str.contains(ticker, "ETH")
bool local_is_index = str.contains(ticker, "NAS") or str.contains(ticker, "US30") or
                      str.contains(ticker, "SPX") or str.contains(ticker, "GER") or
                      str.contains(ticker, "UK100") or str.contains(ticker, "JPN225")  // ← ADD THIS
bool local_is_jpy_pair = str.contains(ticker, "JPY")
bool local_is_usd_base = str.startswith(ticker, "USD") and not str.endswith(ticker, "USD")
bool local_is_usd_quote = (str.contains(ticker, "USD") and not local_is_usd_base) or
                          local_is_gold or local_is_silver or local_is_crypto or local_is_index  // ← ADD local_is_index

// Case 1: USD Quote pairs + Indices (XAUUSD, EURUSD, NAS100, etc.)
// For these: 1 unit moving $1 = $1 profit/loss
if local_is_usd_quote and not local_is_jpy_pair
    position_units := risk_usd / effective_distance
```

### Step 2: Fix Webhook Conversion (units_to_lots)

**Location:** [SND_Utils.pine:units_to_lots()](scripts/pinescript/libraries/SND_Utils.pine)

**Add index detection:**

```pine
export units_to_lots(float units, string ticker) =>
    float lot_size = FOREX_LOT_SIZE  // Default forex (100,000)

    // Indices: NAS100, US30, SPX500, GER40, etc.
    if str.contains(ticker, "NAS") or str.contains(ticker, "US30") or
       str.contains(ticker, "SPX") or str.contains(ticker, "GER") or
       str.contains(ticker, "UK100") or str.contains(ticker, "JPN225") or
       str.contains(ticker, "AUS200") or str.contains(ticker, "HK50")
        lot_size := 1.0  // 1 contract = 1 lot for indices

    // Gold
    else if str.contains(ticker, "XAU") or str.contains(ticker, "GOLD")
        lot_size := GOLD_LOT_SIZE  // 100 oz per lot

    // Silver
    else if str.contains(ticker, "XAG") or str.contains(ticker, "SILVER")
        lot_size := SILVER_LOT_SIZE  // 5000 oz per lot

    // Crypto
    else if str.contains(ticker, "BTC") or str.contains(ticker, "ETH") or
            str.contains(ticker, "SOL") or str.contains(ticker, "ADA") or
            str.contains(ticker, "XRP") or str.contains(ticker, "LTC")
        lot_size := CRYPTO_LOT_SIZE  // 1 unit per lot

    units / lot_size
```

### Step 3: Add Index Lot Size Constant

**Location:** [SND_Strategy.pine:99-100](scripts/pinescript/strategies/SND_Strategy.pine#L99-L100)

**Add after existing constants:**

```pine
const float FOREX_LOT_SIZE = 100000.0
const float GOLD_LOT_SIZE = 100.0
const float INDEX_LOT_SIZE = 1.0  // ← ADD THIS
```

### Step 4: Update Contract Size Detection

**Location:** [SND_Strategy.pine:1255-1257](scripts/pinescript/strategies/SND_Strategy.pine#L1255-L1257)

**Already exists! Just verify:**

```pine
else if is_index  // Indices: NAS100, SPX, etc.
    contract_size := 1.0
    effective_min_units := 1  // Index: minimum 1 contract
```

## Verification Steps

### 1. Check Account Size Setting
Open TradingView → Strategy Settings → Inputs → **💰 Account Size ($)**
- ✅ Should be: **$50,000** (or your actual live account balance)
- ❌ Should NOT be: $10,000,000 (backtesting capital)

### 2. Check Risk Per Trade
Open TradingView → Strategy Settings → Inputs → **Risk Per Trade (%)**
- ✅ Recommended: **0.5%** (Balanced profile)
- ⚠️ Aggressive: **1.0%**

### 3. Apply Pine Fixes
1. Edit [SND_Strategy.pine](scripts/pinescript/strategies/SND_Strategy.pine)
2. Edit [SND_Utils.pine](scripts/pinescript/libraries/SND_Utils.pine)
3. Save changes
4. Re-publish libraries (if using @version imports)
5. Reload strategy in TradingView

### 4. Test with Paper Trading
- Enable webhook alerts
- Send test signal for NAS100
- Check backend logs for received lot size
- Should see: `size=X.XX lots` (not 0!)

## Expected Results After Fix

### Before Fix ❌
```
NAS100 Signal:
- Pine calculates: 4 units
- Pine converts: 0.00004 lots (using 100,000 forex lot size)
- Backend receives: 0 lots (rounds down)
- Status: REJECTED "Position size = 0"
```

### After Fix ✅
```
NAS100 Signal:
- Pine calculates: 4 contracts (correctly detects index)
- Pine converts: 4.0 lots (using 1.0 index lot size)
- Backend receives: 4.0 lots
- Backend calculates: $100,668 notional
- Status: ACCEPTED (or capped at max_lot_size from DB)
```

## Additional Recommended Changes

### 1. Add Index Detection Helper (Optional)

**Location:** Add near line 1045

```pine
// Helper: Detect if symbol is an index
is_index_symbol(string ticker) =>
    str.contains(ticker, "NAS") or str.contains(ticker, "US30") or
    str.contains(ticker, "SPX") or str.contains(ticker, "GER") or
    str.contains(ticker, "UK100") or str.contains(ticker, "JPN225") or
    str.contains(ticker, "AUS200") or str.contains(ticker, "HK50") or
    str.contains(ticker, "FRA40") or str.contains(ticker, "ESP35")
```

Then use:
```pine
bool local_is_index = is_index_symbol(ticker)
```

### 2. Add Debugging Output (Optional)

**Add after position size calculation:**

```pine
// Debug: Show calculated position size
if debug_mode
    log.info("Position Size Debug: " +
             "Symbol=" + ticker +
             " | Units=" + str.tostring(pos_qty_units) +
             " | Lots=" + str.tostring(webhook_lots) +
             " | Is Index=" + str.tostring(local_is_index))
```

### 3. Add Validation Checks

**Add before webhook send:**

```pine
// Validate webhook_lots is reasonable
if webhook_lots <= 0 or na(webhook_lots)
    if show_entry_labels
        label.new(bar_index, high, "⚠️ Invalid Lot Size: " + str.tostring(webhook_lots),
                  color = color.red, textcolor = color.white)
    // Skip webhook
    continue
```

## Testing Checklist

- [ ] Applied position sizing fix (Step 1)
- [ ] Applied webhook conversion fix (Step 2)
- [ ] Added index lot size constant (Step 3)
- [ ] Verified account_size_usd = $50,000 (not $10M)
- [ ] Verified risk_per_trade_pct = 0.5% (not 1.0%+)
- [ ] Re-published libraries
- [ ] Reloaded strategy in TradingView
- [ ] Sent test NAS100 signal
- [ ] Checked backend logs for received lot size
- [ ] Verified no more "Position size = 0" errors
- [ ] Verified lot size is reasonable (0.01-10 lots)

## Summary

**Two bugs fixed:**
1. ✅ **calc_pos_size_units()** now detects indices
2. ✅ **units_to_lots()** now uses correct lot size for indices

**Result:**
- NAS100, US30, SPX500 trades will calculate correct lot sizes
- Webhook will send reasonable lot sizes (not 0.00004)
- Backend will accept trades (not reject with "size = 0")

**Next:** Apply the backend fix (migration 012) to ensure proper pip value calculations!
