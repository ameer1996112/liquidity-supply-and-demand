# Trading System E2E Test Suite

Automated end-to-end testing for the trading system with Discord notifications.

## 🚀 Quick Start

### 1. Install Dependencies

```bash
cd tests
pip install -r requirements-test.txt
```

### 2. Configure Environment

```bash
# Copy example config
cp .env.example .env

# Edit .env with your values
nano .env
```

Required variables:
- `WEBHOOK_URL` - Your Railway webhook URL
- `WEBHOOK_PASSPHRASE` - Your webhook passphrase
- `SUPABASE_URL` - Your Supabase project URL
- `SUPABASE_ANON_KEY` - Your Supabase anon key
- `DISCORD_WEBHOOK_URL` - (Optional) Discord webhook for notifications

### 3. Run Tests

**Full Test Suite (Recommended):**
```bash
python e2e_test.py
```

**Quick Test (Basic Validation):**
```bash
chmod +x quick_test.sh
./quick_test.sh
```

---

## 📋 Test Suite Overview

The full E2E test suite runs 7 comprehensive tests:

| Test | Description | Critical |
|------|-------------|----------|
| 1. Health Check | Verifies server is online and responding | ✅ Yes |
| 2. Entry Webhook | Tests entry webhook with all 18 AI features | ⚠️ Important |
| 3. Database Entry | Validates entry data in Supabase | ✅ Yes |
| 4. Exit Webhook | Tests exit webhook with telemetry data | ⚠️ Important |
| 5. Database Exit | Validates exit data in Supabase | ✅ Yes |
| 6. Data Integrity | Verifies entry-exit linkage via zone_id | ⚠️ Important |
| 7. Cleanup | Removes test data from database | ℹ️ Housekeeping |

---

## 🎨 Output Examples

### ✅ All Tests Passing

```
======================================================================
                  🚀 TRADING SYSTEM E2E TEST SUITE
======================================================================
Target:      https://grand-learning-production-bc96.up.railway.app
Time:        2026-01-22 12:00:00
Environment: production
======================================================================

🧪 TEST: Health Check
ℹ️  INFO: Checking https://grand-learning-production-bc96.up.railway.app/health
✅ PASS: Server is healthy: {'status': 'healthy', 'timestamp': '...'}

🧪 TEST: Entry Webhook (V7.1 Features)
ℹ️  INFO: Sending entry webhook for zone_id=99999
✅ PASS: AI Prediction: HIGH_PROBABILITY (confidence: 0.78)
✅ PASS: Entry webhook accepted

🧪 TEST: Database Entry Verification
ℹ️  INFO: Waiting 2 seconds for database write...
ℹ️  INFO: Querying trading_signals table for zone_id=99999
✅ PASS: Critical fields validated
✅ PASS: All 18 V7.1 features present
✅ PASS: Liquidity flags validated
✅ PASS: Entry verified in database: zone_id=99999, created_at=2026-01-22...

🧪 TEST: Exit Webhook
ℹ️  INFO: Sending exit webhook for zone_id=99999
✅ PASS: Exit webhook accepted

🧪 TEST: Database Exit Verification
ℹ️  INFO: Waiting 2 seconds for database write...
ℹ️  INFO: Querying exit_telemetry table for zone_id=99999
✅ PASS: Exit verified in database: zone_id=99999, outcome=win

🧪 TEST: Data Integrity (Entry + Exit Link)
ℹ️  INFO: Fetching linked entry and exit data
✅ PASS: Entry and exit linked by zone_id
✅ PASS: Timestamps valid (exit after entry)
✅ PASS: Data integrity verified: Entry and Exit properly linked

🧪 TEST: Cleanup Test Data
ℹ️  INFO: Deleting test data for zone_id=99999
✅ PASS: Test entry deleted
✅ PASS: Test exit deleted
✅ PASS: Cleanup verified: Test data removed

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
Duration: 12.5s
======================================================================

✅ ALL TESTS PASSED - SYSTEM OPERATIONAL
```

### ❌ Tests Failing

```
======================================================================
                  🚀 TRADING SYSTEM E2E TEST SUITE
======================================================================
Target:      https://grand-learning-production-bc96.up.railway.app
Time:        2026-01-22 12:00:00
Environment: production
======================================================================

🧪 TEST: Health Check
✅ PASS: Server is healthy: {'status': 'healthy', 'timestamp': '...'}

🧪 TEST: Entry Webhook (V7.1 Features)
❌ FAIL: Entry webhook failed: HTTPError: 401 Unauthorized

🧪 TEST: Database Entry Verification
❌ FAIL: Database entry verification failed: Entry not found in database

[... remaining tests ...]

======================================================================
                           📊 TEST SUMMARY
======================================================================
✅ PASS - Health Check
❌ FAIL - Entry Webhook
❌ FAIL - Database Entry
✅ PASS - Exit Webhook
✅ PASS - Database Exit
✅ PASS - Data Integrity
✅ PASS - Cleanup
======================================================================
Result: 5/7 tests passed (71%)
Duration: 15.2s
======================================================================

❌ SOME TESTS FAILED - CHECK LOGS ABOVE
```

---

## 📱 Discord Notifications

When `DISCORD_WEBHOOK_URL` is set, you'll receive Discord notifications:

### Test Start Notification
```
🧪 E2E Tests Started
Running automated tests on `https://grand-learning-production-bc96.up.railway.app`

Environment: production
Trigger: Manual
Timestamp: 2026-01-22 12:00:00 UTC
```

### Success Notification
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
⏱️ Duration: 12.5s
```

### Failure Notification
```
⚠️ E2E Tests Complete: SOME TESTS FAILED
Test suite finished with 5/7 passing tests

✅ Health Check - Passed
❌ Entry Webhook - Failed
❌ Database Entry - Failed
✅ Exit Webhook - Passed
✅ Database Exit - Passed
✅ Data Integrity - Passed
✅ Cleanup - Passed

📊 Summary
5/7 tests passed (71%)
⏱️ Duration: 15.2s
```

### Critical Failure Alert
```
🚨 Critical Test Failure
Test Database Entry failed with critical error

Error:
```
Entry not found in database
```

Action Required:
Check logs and verify system health immediately
```

---

## 🔧 Advanced Usage

### Run Tests After Deploy (Railway)

Add to Railway service → Settings → Deploy → Post-Deploy Command:
```bash
python tests/e2e_test.py
```

### Run Tests on Schedule (GitHub Actions)

Create `.github/workflows/e2e-test.yml`:
```yaml
name: E2E Tests

on:
  schedule:
    - cron: '0 */6 * * *'  # Every 6 hours
  workflow_dispatch:

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-python@v4
        with:
          python-version: '3.11'
      - run: pip install -r tests/requirements-test.txt
      - env:
          WEBHOOK_URL: ${{ secrets.WEBHOOK_URL }}
          WEBHOOK_PASSPHRASE: ${{ secrets.WEBHOOK_PASSPHRASE }}
          SUPABASE_URL: ${{ secrets.SUPABASE_URL }}
          SUPABASE_ANON_KEY: ${{ secrets.SUPABASE_ANON_KEY }}
          DISCORD_WEBHOOK_URL: ${{ secrets.DISCORD_WEBHOOK_URL }}
        run: python tests/e2e_test.py
```

### Run Tests in CI/CD Pipeline

```bash
# In your deploy script
git push railway main
sleep 30  # Wait for deployment
python tests/e2e_test.py || exit 1
```

---

## 🐛 Troubleshooting

### Test Fails: "WEBHOOK_PASSPHRASE not set"
**Solution:** Set the environment variable:
```bash
export WEBHOOK_PASSPHRASE=your_passphrase_here
```

### Test Fails: "Failed to connect to Supabase"
**Solution:** Check your Supabase credentials:
```bash
echo $SUPABASE_URL
echo $SUPABASE_ANON_KEY
```

### Test Fails: "Entry not found in database"
**Solution:**
1. Check Railway logs for webhook errors
2. Verify Supabase connection in bot logs
3. Run SQL query manually:
   ```sql
   SELECT * FROM trading_signals
   WHERE zone_id = 99999
   ORDER BY created_at DESC LIMIT 1;
   ```

### Discord Notifications Not Sending
**Solution:**
1. Verify webhook URL format: `https://discord.com/api/webhooks/...`
2. Test webhook manually:
   ```bash
   curl -X POST $DISCORD_WEBHOOK_URL \
     -H "Content-Type: application/json" \
     -d '{"content": "Test message"}'
   ```

---

## 📊 Test Data

The test suite uses zone_id `99999` to avoid conflicts with real trades.

**Test Entry:**
- Symbol: EURUSD
- Side: buy
- Entry: 1.08500
- SL: 1.08400
- TP: 1.08700
- All 18 V7.1 AI features populated

**Test Exit:**
- Outcome: win
- Bars Held: 18
- P&L: 2.0R
- Exit Type: tp_hit
- MAE: 3.5 pips

**Cleanup:** All test data is automatically deleted after tests complete.

---

## 🔐 Security Notes

- Never commit `.env` file to git
- Use environment variables for secrets in production
- Discord webhooks are public URLs - don't share them
- Supabase anon key is safe to use (RLS policies protect data)

---

## 📝 License

Part of the Trading System project. See main LICENSE file.
