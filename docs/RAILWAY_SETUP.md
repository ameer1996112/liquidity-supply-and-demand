# Railway Environment Variables Setup

## How to Add Variables

1. **Navigate to your Worker service** in Railway dashboard
2. Click **"Variables"** tab
3. Click **"+ New Variable"** button
4. Add each variable below

---

## Required Variables for Dynamic Risk (v6.6)

### New Variables to Add:

| Variable Name     | Value     | Description                               |
| ----------------- | --------- | ----------------------------------------- |
| `ACCOUNT_BALANCE` | `10000.0` | Your trading account balance in USD       |
| `RISK_PERCENT`    | `0.5`     | Risk per trade as percentage (0.5 = 0.5%) |

### Existing Variables (verify they exist):

| Variable Name               | Your Value                | Description                          |
| --------------------------- | ------------------------- | ------------------------------------ |
| `SUPABASE_URL`              | `https://xxx.supabase.co` | Your Supabase project URL            |
| `SUPABASE_SERVICE_ROLE_KEY` | `eyJxxx...`               | Service role key (for bypassing RLS) |
| `REDIS_URL`                 | `redis://...`             | Your Railway Redis connection URL    |
| `WEBHOOK_SECRET`            | `c817492a...`             | Secret for validating webhooks       |
| `LIVE_TRADING_ENABLED`      | `false`                   | Keep as `false` for paper trading    |

---

## After Adding Variables

1. Railway will **automatically redeploy** your worker
2. Wait ~1-2 minutes for deployment to complete
3. Check the **Deploy Logs** tab - you should see:

```
🚀 WORKER v6.6 (DYNAMIC RISK MODE) STARTED
  Account Balance: $10,000
  Risk Per Trade: 0.5%
  Correlation Limit: 3 positions
  ML Confidence: 50%
  Kill-Switch: OFF
  LIVE_TRADING: false (DRY_RUN)
  AI Brain: LOADED
  Guard Strategy: FAIL-SAFE (reject on error)
```

4. If you see **"DYNAMIC RISK MODE"** ✅ you're good!
5. If you still see **"SAFE MODE"** ❌ the variables weren't loaded

---

## Common Issues

### Variable Not Loading?

- Make sure there are **no spaces** around the `=` sign
- Use **numbers only** (no `$` or `,` symbols)
  - ✅ `10000.0`
  - ❌ `$10,000.00`

### Deployment Failed?

- Check **Build Logs** for Python errors
- Variables are loaded at **runtime**, so build should succeed even if variables are missing

### Still Showing v6.5?

- Your code changes haven't deployed yet
- Make sure you **committed and pushed** to GitHub/Railway

---

## Quick Command (if using Railway CLI)

```bash
railway variables set ACCOUNT_BALANCE=10000.0
railway variables set RISK_PERCENT=0.5
```

Then check:

```bash
railway logs
```
