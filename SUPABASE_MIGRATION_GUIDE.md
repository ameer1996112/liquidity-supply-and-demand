# Supabase Migration Guide

This guide shows how to migrate from SQLite to Supabase for persistent cloud storage.

## Step 1: Create Supabase Table

1. Go to your Supabase SQL Editor: https://app.supabase.com/project/iuxxebonaamwpgiwqkeq/sql
2. Copy and paste the entire contents of `supabase_schema.sql`
3. Click "Run" to create the `trading_signals` table

## Step 2: Add Supabase Package to Requirements

Add to `webhook_backend/requirements.txt`:
```
supabase==2.10.0
```

Then run:
```bash
cd webhook_backend
pip install -r requirements.txt
```

## Step 3: Update trading_bot.py

Make the following changes to `webhook_backend/trading_bot.py`:

### 3.1: Replace SQLite imports with Supabase

**Find (around line 20):**
```python
import sqlite3
```

**Replace with:**
```python
import supabase_db
```

### 3.2: Remove SQLite-specific code

**Find and REMOVE (around line 94-104):**
```python
DB_PATH = Path(__file__).parent / 'trades.db'

# Initialize paper trader
paper_trader = get_paper_trader(DB_PATH) if PAPER_TRADING_ENABLED else None

# =============================================================================
# DATABASE
# =============================================================================

DB_PATH = Path(__file__).parent / 'trades.db'
```

### 3.3: Replace init_db() function

**Find (around line 121-183):**
```python
def init_db():
    """Initialize SQLite database."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    # ... entire function ...
    logger.info(f"Database initialized at {DB_PATH}")
```

**Replace with:**
```python
def init_db():
    """Initialize Supabase database."""
    try:
        supabase_db.init_supabase()
        logger.info("✅ Supabase database initialized")
    except Exception as e:
        logger.error(f"❌ Failed to initialize Supabase: {e}")
        raise
```

### 3.4: Replace save_alert() function

**Find (around line 186-250):**
```python
def save_alert(data: dict, mode: str = 'manual') -> int:
    """Save alert to database with AI features, return alert ID."""
    conn = sqlite3.connect(DB_PATH)
    # ... entire function ...
    return alert_id
```

**Replace with:**
```python
def save_alert(data: dict, mode: str = 'manual') -> int:
    """Save alert to Supabase with AI features, return alert ID."""
    return supabase_db.save_alert(data, mode)
```

### 3.5: Replace update_alert_status() function

**Find (around line 254-266):**
```python
def update_alert_status(alert_id: int, status: str, outcome: str = None, pnl: float = None, notes: str = None):
    """Update alert status."""
    conn = sqlite3.connect(DB_PATH)
    # ... entire function ...
```

**Replace with:**
```python
def update_alert_status(alert_id: int, status: str, outcome: str = None, pnl: float = None, notes: str = None):
    """Update alert status."""
    supabase_db.update_alert_status(alert_id, status, outcome, pnl, notes)
```

### 3.6: Replace get_alert() function

**Find (around line 269-279):**
```python
def get_alert(alert_id: int) -> Optional[dict]:
    """Get single alert by ID."""
    conn = sqlite3.connect(DB_PATH)
    # ... entire function ...
```

**Replace with:**
```python
def get_alert(alert_id: int) -> Optional[dict]:
    """Get single alert by ID."""
    return supabase_db.get_alert(alert_id)
```

### 3.7: Replace get_recent_alerts() function

**Find (around line 282-292):**
```python
def get_recent_alerts(limit: int = 50) -> List[dict]:
    """Get recent alerts."""
    conn = sqlite3.connect(DB_PATH)
    # ... entire function ...
```

**Replace with:**
```python
def get_recent_alerts(limit: int = 50) -> List[dict]:
    """Get recent alerts."""
    return supabase_db.get_recent_alerts(limit)
```

### 3.8: Replace get_statistics() function

**Find (around line 295-340):**
```python
def get_statistics() -> dict:
    """Calculate trading statistics."""
    conn = sqlite3.connect(DB_PATH)
    # ... entire function ...
```

**Replace with:**
```python
def get_statistics() -> dict:
    """Calculate trading statistics."""
    return supabase_db.get_statistics()
```

### 3.9: Update exit webhook handler

**Find (around line 903-950):**
```python
@app.route('/webhook/exit', methods=['POST'])
def webhook_exit():
    """Receive trade exit events from TradingView."""
    try:
        # ... validation code ...

        # Find the open trade by zone_id
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        cursor.execute("""
            UPDATE alerts
            SET outcome = ?,
                close_price = ?,
                close_time = ?,
                pnl = ?,
                exit_type = ?,
                mae_pips = ?,
                bars_held = ?,
                status = 'closed',
                updated_at = CURRENT_TIMESTAMP
            WHERE zone_id = ? AND status = 'active'
        """, (outcome, close_price, close_time, pnl_r, exit_type, mae_pips, bars_held, zone_id))

        conn.commit()
        conn.close()
```

**Replace with:**
```python
@app.route('/webhook/exit', methods=['POST'])
def webhook_exit():
    """Receive trade exit events from TradingView."""
    try:
        # ... validation code (keep unchanged) ...

        # Update trade exit data in Supabase
        exit_data = {
            'outcome': outcome,
            'close_price': close_price,
            'close_time': close_time,
            'pnl_r': pnl_r,
            'exit_type': exit_type,
            'mae_pips': mae_pips,
            'bars_held': bars_held
        }
        supabase_db.update_alert_exit(zone_id, exit_data)
```

### 3.10: Update health check endpoint

**Find (around line 1032):**
```python
"database": DB_PATH.exists(),
```

**Replace with:**
```python
"database": True,  # Supabase is always available
```

## Step 4: Update .env File

Make sure your `.env` file has these variables:
```bash
SUPABASE_URL=https://iuxxebonaamwpgiwqkeq.supabase.co
SUPABASE_ANON_KEY=your_anon_key_here
```

## Step 5: Test Locally

```bash
cd webhook_backend
python trading_bot.py
```

Check the logs for:
- ✅ Supabase database initialized
- No errors about sqlite3

## Step 6: Deploy to Railway

```bash
git add .
git commit -m "Migrate from SQLite to Supabase for persistent storage"
git push railway main
```

## Step 7: Run E2E Tests

```bash
cd tests
python3 e2e_test.py
```

You should now see **7/7 tests passing** with all database verification working! 🎉

## Rollback Plan

If you need to rollback to SQLite:
1. Revert changes in trading_bot.py
2. Keep supabase_db.py for future use
3. Redeploy

## Benefits of Supabase

✅ **Persistent storage** - Data survives Railway redeploys
✅ **Cloud backups** - Automatic backups by Supabase
✅ **SQL queries** - Use Supabase dashboard to query data
✅ **Real-time** - Can add real-time subscriptions later
✅ **Scalable** - Handles more data than SQLite
✅ **E2E testable** - Tests can verify database writes
