# Quick Fix: Positions Not Showing

## Problem
Open position (GBPCAD) in MetaTrader is not showing in:
- ✗ Dashboard "Active Positions" section
- ✗ Accounts page "Broker Positions"
- ✗ Accounts page "Database Positions"

## Root Cause
**MetaAPI credentials are empty in your .env file**

Current state:
```bash
META_API_TOKEN=          # ← EMPTY
META_API_ACCOUNT_ID=     # ← EMPTY
```

## Fix (2 Steps)

### Step 1: Add Your MetaAPI Credentials

Edit this file: `/Users/ameeramer/dev/projects/galilsoftware/sources/trading/.env`

Replace the empty META_API lines with your actual credentials:

```bash
META_API_TOKEN=eyJhbGciOiJSUzUxMiIsInR5cCI6IkpXVCJ9.YOUR_ACTUAL_TOKEN_HERE
META_API_ACCOUNT_ID=1a2b3c4d-5e6f-7g8h-9i0j-1k2l3m4n5o6p
META_API_REGION=london
META_API_LIVE_EXECUTION=false
```

**Where to get these:**

1. **Get Token:**
   - Visit: https://app.metaapi.cloud/
   - Go to: Settings → API Tokens
   - Copy your token (starts with `eyJ...`)

2. **Get Account ID:**
   - Visit: https://app.metaapi.cloud/accounts
   - Click your MetaTrader account
   - Copy the Account ID (UUID format)

### Step 2: Restart Backend

```bash
# Stop the backend (Ctrl+C if running)
# Then restart:
cd /Users/ameeramer/dev/projects/galilsoftware/sources/trading
python -m src.worker  # or however you normally start it
```

## Verify the Fix

### Option 1: Run Diagnostic
```bash
cd /Users/ameeramer/dev/projects/galilsoftware/sources/trading-bot-v2/apps/backend
python diagnose_positions.py
```

Should now show:
```
✓ META_API_TOKEN: Set (123 chars)
✓ META_API_ACCOUNT_ID: Set
✓ Account State: DEPLOYED
✓ Connection Status: CONNECTED
✓ Found 1 open position(s):
  Position #1:
    Symbol: GBPCAD
    Side: sell
    ...
```

### Option 2: Check Dashboard
1. Refresh http://localhost:3000 (or your frontend URL)
2. GBPCAD position should appear in "Active Positions"
3. Navigate to Accounts → ACG-DEMO
4. Position should show in "Broker Positions (1)"

### Option 3: Test API Directly
```bash
curl http://localhost:8000/api/v1/webhook/trades/open?mode=live | jq
```

Should return:
```json
{
  "trades": [
    {
      "symbol": "GBPCAD",
      "side": "sell",
      "volume": 0.XX,
      "floating_pnl": XX.XX,
      ...
    }
  ],
  "count": 1,
  "source": "metaapi"  ← Important: should say "metaapi" not "database"
}
```

## Why This Fixes It

### Before (MetaAPI not configured):
```
Frontend calls API → API tries MetaAPI → Fails (no credentials)
                   → Falls back to Database → No OPEN trades found
                   → Returns empty []
                   → Dashboard shows "No active positions"
```

### After (MetaAPI configured):
```
Frontend calls API → API calls MetaAPI → Success! Fetches GBPCAD position
                   → Returns position data
                   → Dashboard displays position ✓
```

## Understanding Position Sources

Your system has **two** position sources:

| Source | Contains | Use Case |
|--------|----------|----------|
| **MetaAPI** (Primary) | ALL open positions<br>(manual + bot-created) | Real-time position display<br>Live P&L tracking |
| **Database** (Fallback) | Only bot-created trades<br>(via TradingView webhook) | Historical analytics<br>Guard rail tracking<br>AI vote logs |

### Why GBPCAD is not in database:
- Database has 0 OPEN trades (all 11,962 trades are CLOSED)
- This means GBPCAD was either:
  - Opened manually in MetaTrader, OR
  - Opened before bot deployment, OR
  - Bot trade execution record was not saved

### Why you still see it after fixing MetaAPI:
- MetaAPI fetches **live** positions directly from MetaTrader broker
- Includes positions opened by any method (manual or automated)
- Once configured, ALL positions will show in dashboard

## Next Steps After Fix

### 1. Verify Position Monitor is Running
Check backend logs for:
```
[PosMon] Position monitor started (interval=30s)
```

This service syncs position closures from MetaAPI → Database.

### 2. Test Position Closure Detection
1. Close GBPCAD position in MetaTrader (manually or hit SL/TP)
2. Within 30 seconds, position should disappear from dashboard
3. Check database - trade should be marked as CLOSED

### 3. Test Bot-Created Position
1. Send a TradingView webhook signal
2. Position should appear in BOTH:
   - Dashboard (via MetaAPI)
   - Database (snd_trades table with meta_order_id set)

## Troubleshooting

### Still not showing after fix:

**Check Account ID matches:**
```bash
# Your .env Account ID must match the MT account with the position
# If you have multiple MT accounts in MetaAPI, verify you're using the right one
```

**Check MetaAPI account status:**
```bash
python diagnose_positions.py
# Look for:
# State: DEPLOYED (not UNDEPLOYED)
# Connection: CONNECTED (not DISCONNECTED)
```

**Check backend is using the new .env:**
```bash
# Make sure you restarted the backend after editing .env
# Old process won't pick up new env vars
```

## Files Modified/Created

- ✓ Created: `diagnose_positions.py` - Diagnostic tool
- ✓ Created: `FIX_POSITIONS_NOT_SHOWING.md` - Detailed guide
- ✓ Created: `QUICK_FIX.md` - This file (quick reference)
- → **TO DO:** Edit `.env` file with your credentials

## Need the detailed guide?

See: [FIX_POSITIONS_NOT_SHOWING.md](../trading-bot-v2/apps/backend/FIX_POSITIONS_NOT_SHOWING.md)
