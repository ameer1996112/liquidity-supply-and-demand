# Quick Start Guide - Automated Testing

Get your test suite running in 3 minutes! ⚡

## 🚀 Setup (One-Time)

### Step 1: Run Setup Script
```bash
cd tests
./setup.sh
```

This will:
- ✅ Install dependencies (`requests`, `supabase`)
- ✅ Create `.env` configuration file
- ✅ Make scripts executable
- ✅ Verify your setup

### Step 2: Configure Environment

Edit the `.env` file:
```bash
nano .env
```

**Required** (get from your setup):
```bash
WEBHOOK_PASSPHRASE=your_actual_passphrase_here
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_ANON_KEY=your_supabase_anon_key_here
```

**Optional** (Discord notifications):
```bash
DISCORD_WEBHOOK_URL=https://discord.com/api/webhooks/YOUR_ID/YOUR_TOKEN
```

#### Where to Find These Values:

**1. WEBHOOK_PASSPHRASE**
- Same passphrase you use in your Pine Script
- Check your Pine Script settings or Railway environment variables

**2. SUPABASE_URL & SUPABASE_ANON_KEY**
- Go to: https://app.supabase.com/project/YOUR_PROJECT/settings/api
- Copy "Project URL" → `SUPABASE_URL`
- Copy "anon public" key → `SUPABASE_ANON_KEY`

**3. DISCORD_WEBHOOK_URL** (Optional)
- Discord Server → Channel → Edit Channel → Integrations → Webhooks
- Create Webhook → Copy Webhook URL

### Step 3: Test Configuration

```bash
python3 e2e_test.py
```

If you see errors about missing credentials, double-check your `.env` file.

---

## ✅ Run Tests

### Full Test Suite (Recommended)
```bash
python3 e2e_test.py
```

**Tests 7 things:**
1. ✅ Health Check
2. ✅ Entry Webhook
3. ✅ Database Entry
4. ✅ Exit Webhook
5. ✅ Database Exit
6. ✅ Data Integrity
7. ✅ Cleanup

**Duration:** ~12 seconds
**Notifications:** Discord (if configured)

### Quick Test (Fast Check)
```bash
./quick_test.sh
```

**Tests 3 things:**
1. ✅ Health Check
2. ✅ Entry Webhook
3. ✅ Exit Webhook

**Duration:** ~5 seconds
**Notifications:** None

---

## 📱 Expected Output

### Success ✅
```
======================================================================
                  🚀 TRADING SYSTEM E2E TEST SUITE
======================================================================
Target:      https://grand-learning-production-bc96.up.railway.app
Time:        2026-01-22 12:00:00
Environment: local
======================================================================

🧪 TEST: Health Check
✅ PASS: Server is healthy

🧪 TEST: Entry Webhook (V7.1 Features)
✅ PASS: AI Prediction: HIGH_PROBABILITY (confidence: 0.78)

[... 5 more tests ...]

======================================================================
                           📊 TEST SUMMARY
======================================================================
✅ PASS - Health Check
✅ PASS - Entry Webhook
✅ PASS - Database Entry
✅ PASS - Exit Webhook
✅ PASS - Database Exit
✅ PASS - Data Integrity
✅ PASS - Cleanup
======================================================================
Result: 7/7 tests passed (100%)
Duration: 12.3s
======================================================================

✅ ALL TESTS PASSED - SYSTEM OPERATIONAL
```

### Discord Notification 📱

If you configured Discord, you'll see a nice embed in your channel:

```
✅ E2E Tests Complete: ALL TESTS PASSED
Test suite finished with 7/7 passing tests

✅ Health Check - Passed
✅ Entry Webhook - Passed
✅ Database Entry - Passed
✅ Exit Webhook - Passed
✅ Database Exit - Passed
✅ Data Integrity - Passed
✅ Cleanup - Passed

📊 Summary
7/7 tests passed (100%)
⏱️ Duration: 12.3s
```

---

## 🔧 Troubleshooting

### Error: "WEBHOOK_PASSPHRASE not set"
**Fix:** Edit `.env` and set your passphrase
```bash
nano .env
# Set: WEBHOOK_PASSPHRASE=your_passphrase_here
```

### Error: "Failed to connect to Supabase"
**Fix:** Check your Supabase credentials in `.env`
```bash
# Verify these are correct:
echo $SUPABASE_URL
echo $SUPABASE_ANON_KEY
```

### Error: "Entry not found in database"
**Possible causes:**
1. Webhook failed (check Railway logs)
2. Database connection issue (check Supabase status)
3. Wrong credentials (verify `.env`)

**Debug:**
```bash
# Check Railway logs
railway logs --tail

# Test Supabase connection
python3 -c "from supabase import create_client; import os;
client = create_client(os.getenv('SUPABASE_URL'), os.getenv('SUPABASE_ANON_KEY'));
print('Connected!'); print(client.table('trading_signals').select('*').limit(1).execute())"
```

### Discord Notifications Not Working
**Fix:** Verify webhook URL format
```bash
# Should start with: https://discord.com/api/webhooks/
echo $DISCORD_WEBHOOK_URL

# Test manually:
curl -X POST $DISCORD_WEBHOOK_URL \
  -H "Content-Type: application/json" \
  -d '{"content": "Test from terminal"}'
```

---

## 🔄 Running After Deploy

### Option 1: Manual (After Railway Deploy)
```bash
# Wait for deployment to complete
sleep 30

# Run tests
python3 tests/e2e_test.py
```

### Option 2: Automatic (Railway Post-Deploy Hook)

**Railway Dashboard:**
1. Go to your service → Settings
2. Scroll to "Deploy"
3. Add **Post-Deploy Command**:
   ```bash
   python tests/e2e_test.py
   ```

**Or use `railway.json`:**
```json
{
  "hooks": {
    "postDeploy": "python tests/e2e_test.py"
  }
}
```

### Option 3: Scheduled (GitHub Actions)

Create `.github/workflows/e2e-test.yml`:
```yaml
name: E2E Tests
on:
  schedule:
    - cron: '0 */6 * * *'  # Every 6 hours
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-python@v4
      - run: pip install -r tests/requirements-test.txt
      - env:
          WEBHOOK_PASSPHRASE: ${{ secrets.WEBHOOK_PASSPHRASE }}
          SUPABASE_URL: ${{ secrets.SUPABASE_URL }}
          SUPABASE_ANON_KEY: ${{ secrets.SUPABASE_ANON_KEY }}
          DISCORD_WEBHOOK_URL: ${{ secrets.DISCORD_WEBHOOK_URL }}
        run: python tests/e2e_test.py
```

---

## 📊 What Gets Tested?

### Entry Webhook Test
- ✅ Sends test trade with all 18 V7.1 AI features
- ✅ Validates webhook response (200 OK)
- ✅ Checks AI prediction is generated
- ✅ Verifies zone_id returned

### Database Tests
- ✅ Confirms entry saved to `trading_signals` table
- ✅ Confirms exit saved to `exit_telemetry` table
- ✅ Validates all 18 AI features populated
- ✅ Checks liquidity flags (liq_swept, target_swept, caused_sweep)
- ✅ Verifies entry-exit linkage via zone_id
- ✅ Validates timestamps (exit after entry)

### Cleanup
- ✅ Removes test data (zone_id 99999)
- ✅ Verifies deletion successful

---

## 🎯 Success Criteria

Your system is **production-ready** when:

✅ All 7 tests pass (100%)
✅ Duration < 15 seconds
✅ Discord notifications received (if configured)
✅ No errors in Railway logs
✅ Data appears in Supabase tables

---

## 📚 More Info

- **Full README:** [README.md](./README.md)
- **Test Code:** [e2e_test.py](./e2e_test.py)
- **Quick Test:** [quick_test.sh](./quick_test.sh)

---

## 🆘 Still Need Help?

1. Check Railway logs: `railway logs --tail`
2. Check Supabase logs: Supabase Dashboard → Logs
3. Run with verbose output: `python3 e2e_test.py 2>&1 | tee test.log`
4. Review error messages in test output

**Common issues:**
- Wrong passphrase → Error 401
- Wrong Supabase URL → Connection failed
- Network issues → Timeout errors
- Discord webhook wrong → 404 Not Found

---

**Ready to test? Run this:**
```bash
cd tests
./setup.sh
nano .env          # Add your credentials
python3 e2e_test.py
```

🎉 **That's it! Your tests are now automated!**
