# Migration 013 Application Guide

## Summary

Migration 013 adds essential columns to the `account_strategies` table for enhanced account management:

- `provider` - Account provider (FTMO, PropFirm, MyFundedFX, Personal, etc.)
- `account_type` - Account type (Eval, Funded, or Personal)
- `meta_api_account_id` - Direct MetaAPI account ID
- `meta_api_token_env_key` - Environment variable name for MetaAPI token
- `last_sync_time` - Last successful sync timestamp
- `connection_status` - Connection status (connected, disconnected, error, not_configured)

## Why This Migration Is Needed

### Backend Errors
The backend is trying to query `meta_api_account_id` which doesn't exist yet:
```
ERROR: column account_strategies.meta_api_account_id does not exist
```

### Frontend Errors
The frontend is trying to display `account_type` and `provider` properties that aren't in the database yet.

## Changes Made (Automated Fixes)

✅ **Fixed Frontend TypeScript Types** ([api.ts:374-390](frontend/src/lib/api.ts#L374-L390))
- Added `provider?: string` to `AccountComparisonApi`
- Added `account_type?: 'Eval' | 'Funded' | 'Personal'` to `AccountComparisonApi`

✅ **Fixed FastAPI Deprecation Warning** ([api_analytics.py:166](src/api_analytics.py#L166))
- Changed `regex=` to `pattern=` in Query parameter

## Migration Application Methods

### Option 1: Supabase Studio (Recommended)

1. Go to [Supabase Dashboard](https://supabase.com/dashboard)
2. Select your project: **iuxxebonaamwpgiwqkeq**
3. Click **SQL Editor** in the left sidebar
4. Create a new query
5. Copy the contents of [migrations/013_account_enhancements.sql](migrations/013_account_enhancements.sql)
6. Paste into the SQL editor
7. Click **Run** (or press Cmd+Enter)
8. Verify success by checking the results panel

### Option 2: Using psql (Direct Database Connection)

If you have direct database access credentials:

```bash
# Set your database URL
export DATABASE_URL="postgresql://postgres:[password]@[host]:[port]/postgres"

# Apply migration
psql "$DATABASE_URL" -f migrations/013_account_enhancements.sql
```

### Option 3: Railway (If Deployed There)

1. Go to your Railway project dashboard
2. Click on the **Postgres** service
3. Open the **Query** tab
4. Copy the contents of [migrations/013_account_enhancements.sql](migrations/013_account_enhancements.sql)
5. Paste into the query editor
6. Click **Run Query**

## Verification

After applying the migration, verify it was successful:

### Method 1: Supabase Studio

```sql
SELECT
    column_name,
    data_type,
    is_nullable,
    column_default
FROM information_schema.columns
WHERE table_name = 'account_strategies'
  AND column_name IN ('provider', 'account_type', 'meta_api_account_id', 'connection_status')
ORDER BY column_name;
```

Expected result: 4 rows showing the new columns.

### Method 2: Backend Logs

After applying the migration:

1. Restart your backend service (Railway will auto-restart)
2. Check the logs - the errors should be gone:
   ```
   ❌ Before: column account_strategies.meta_api_account_id does not exist
   ✅ After: INFO - Synced account FTMO - Demo - 50k successfully
   ```

### Method 3: Frontend Build

After applying the migration and redeploying:

1. The Next.js build should succeed
2. No more TypeScript errors about `account_type`
3. Account detail pages will display provider and account type badges

## Post-Migration Steps

Once the migration is applied:

1. **Update existing accounts** (optional but recommended):
   ```sql
   -- Set account type for your FTMO demo account
   UPDATE account_strategies
   SET
     provider = 'FTMO',
     account_type = 'Eval',
     connection_status = 'not_configured'
   WHERE account_name = 'FTMO - Demo - 50k';
   ```

2. **Configure MetaAPI connection** (if using direct connection):
   ```sql
   -- Add MetaAPI account ID to bypass broker_profile lookup
   UPDATE account_strategies
   SET
     meta_api_account_id = 'your-meta-api-account-id',
     meta_api_token_env_key = 'META_API_TOKEN'
   WHERE account_name = 'FTMO - Demo - 50k';
   ```

3. **Redeploy frontend** (Railway):
   - The frontend should automatically redeploy after the git push
   - Verify the build succeeds with no TypeScript errors

## Files Modified

- ✅ [frontend/src/lib/api.ts](frontend/src/lib/api.ts#L374-L390) - Added `provider` and `account_type` to TypeScript interfaces
- ✅ [src/api_analytics.py](src/api_analytics.py#L166) - Fixed FastAPI deprecation warning
- 📄 [migrations/013_account_enhancements.sql](migrations/013_account_enhancements.sql) - Ready to apply

## Migration SQL Preview

```sql
-- Add new columns to account_strategies
ALTER TABLE public.account_strategies
  ADD COLUMN IF NOT EXISTS provider VARCHAR(50) DEFAULT 'Personal',
  ADD COLUMN IF NOT EXISTS account_type VARCHAR(20) DEFAULT 'Personal'
    CHECK (account_type IN ('Eval', 'Funded', 'Personal')),
  ADD COLUMN IF NOT EXISTS meta_api_account_id TEXT,
  ADD COLUMN IF NOT EXISTS meta_api_token_env_key TEXT DEFAULT 'META_API_TOKEN',
  ADD COLUMN IF NOT EXISTS last_sync_time TIMESTAMPTZ,
  ADD COLUMN IF NOT EXISTS connection_status VARCHAR(20) DEFAULT 'not_configured'
    CHECK (connection_status IN ('connected', 'disconnected', 'error', 'not_configured'));

-- Create indexes for filtering
CREATE INDEX IF NOT EXISTS idx_account_strategies_provider
  ON public.account_strategies(provider);

CREATE INDEX IF NOT EXISTS idx_account_strategies_type
  ON public.account_strategies(account_type);

CREATE INDEX IF NOT EXISTS idx_account_strategies_connection
  ON public.account_strategies(connection_status);
```

## Rollback (If Needed)

If you need to rollback this migration:

```sql
-- Drop columns (WARNING: This will delete data)
ALTER TABLE public.account_strategies
  DROP COLUMN IF EXISTS provider,
  DROP COLUMN IF EXISTS account_type,
  DROP COLUMN IF EXISTS meta_api_account_id,
  DROP COLUMN IF EXISTS meta_api_token_env_key,
  DROP COLUMN IF EXISTS last_sync_time,
  DROP COLUMN IF EXISTS connection_status;

-- Drop indexes
DROP INDEX IF EXISTS idx_account_strategies_provider;
DROP INDEX IF EXISTS idx_account_strategies_type;
DROP INDEX IF EXISTS idx_account_strategies_connection;
```

## Support

If you encounter issues:

1. Check Supabase logs for SQL errors
2. Verify your database user has ALTER TABLE permissions
3. Check backend logs for connection errors
4. Ensure frontend rebuilds after git push

---

**Status**: Ready to apply ✅
**Migration File**: [migrations/013_account_enhancements.sql](migrations/013_account_enhancements.sql)
**Risk Level**: Low (adds columns with defaults, no data loss)
**Downtime**: None (uses `IF NOT EXISTS`, safe to re-run)
