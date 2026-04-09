# Discord Alert System Fixes

## Summary
Fix 3 issues in the Discord/alert system to improve reliability and monitoring.

## Issue #1: Discord Webhook 404 Handling

### Problem
Discord webhooks can be deleted or become invalid, causing 404 "Unknown Webhook code 10015" errors that crash or spam logs.

### Solution
Add webhook URL validation and 404 handling following the existing `send_guard_notification()` pattern.

### Implementation Details

**File: `src/adapters/discord.py`**

1. **Add webhook URL validation function** (before `send_discord()`):
```python
def _is_valid_discord_webhook(url: str) -> bool:
    """Validate Discord webhook URL format."""
    if not url or not isinstance(url, str):
        return False
    return url.startswith("https://discord.com/api/webhooks/") or \
           url.startswith("https://discordapp.com/api/webhooks/")
```

2. **Update `send_discord()`** to validate webhook before sending and handle 404:
```python
def send_discord(
    symbol: str,
    side: str,
    entry: str,
    sl: str,
    tp: str,
    webhook_url: Optional[str] = None,
    data: Optional[Dict[str, Any]] = None,
) -> Optional[str]:
    # ... existing code ...
    
    # Validate webhook URL
    webhook_url = webhook_url or settings.DISCORD_WEBHOOK
    if not _is_valid_discord_webhook(webhook_url):
        logger.warning(f"Invalid or missing Discord webhook URL: {webhook_url}")
        return f"WEBHOOK_INVALID: {webhook_url}"
    
    # ... after the response check ...
    if response.status_code == 404:
        logger.error(f"Discord webhook 404 - webhook may be deleted: {webhook_url[:50]}...")
        return f"WEBHOOK_NOT_FOUND: {webhook_url[:50]}..."
    elif response.status_code != 204:
        logger.error(f"Discord error {response.status_code}: {response.text}")
        return f"DISCORD_ERROR: {response.status_code}"
```

3. **Update `send_telegram()`** with same pattern for Telegram bot token validation.

4. **Update `send_discord_async()` and `send_telegram_async()`** to:
   - Check webhook validity in async executor thread
   - Downgrade 404 errors to warning level (like `send_guard_notification_async` does)
   - Return appropriate error strings instead of raising exceptions

## Issue #2: Fix KeyError on Missing Trade Data Fields

### Problem
Direct dictionary access like `data["sl"]` causes `KeyError: 'sl'` when fields are missing from webhook payload.

### Solution
Replace all direct dict access with `.get()` pattern and provide sensible defaults.

### Implementation Details

**File: `src/adapters/discord.py`**

**In `send_discord()` function (around lines 96-127):**

Change from:
```python
sl = data["sl"]
side = data["side"]
entry = data["entry"]
tp = data["tp"]
symbol = data["symbol"]
```

To:
```python
sl = data.get("sl", "N/A")
side = data.get("side", "Unknown")
entry = data.get("entry", "N/A")
tp = data.get("tp", "N/A")
symbol = data.get("symbol", "Unknown")
```

**In `send_telegram()` function (around lines 222-230):**

Apply same pattern:
```python
sl = data.get("sl", "N/A")
side = data.get("side", "Unknown")
entry = data.get("entry", "N/A")
tp = data.get("tp", "N/A")
symbol = data.get("symbol", "Unknown")
```

**In `send_discord_and_thread_async()`** - already uses `.get()` correctly, verify this remains unchanged.

**Also check `dispatch_payload()`** (lines 829-903) for any similar patterns and fix if needed.

## Issue #3: Dead Letter Queue Monitoring

### Problem
No visibility when signals fail and accumulate in dead letter queue.

### Solution
Add monitoring function that checks dead letter queue count and triggers alerts when > 0.

### Implementation Details

**File: `src/services/alert_service.py`**

1. **Add new function to check dead letter queue:**
```python
import redis
from typing import Tuple

async def check_dead_letter_queue(redis_client: Optional[redis.Redis] = None) -> Tuple[int, bool]:
    """
    Check dead letter queue for failed signals.
    
    Returns:
        Tuple of (count, has_failed_items)
    """
    try:
        from src.adapters.supabase import get_supabase
        
        supabase = get_supabase()
        # Query dead_letter_queue table or check Redis dead letter list
        # Assuming dead letter queue is tracked in Redis or Supabase
        
        # For Redis pattern (most likely based on codebase):
        redis_client = redis_client or redis.Redis(
            host=settings.REDIS_HOST,
            port=settings.REDIS_PORT,
            password=settings.REDIS_PASSWORD or None,
            decode_responses=True
        )
        
        # Dead letter queue typically uses a suffix like ":dead" or ":failed"
        dead_letter_key = f"{settings.REDIS_SIGNAL_QUEUE}:dead"
        count = redis_client.llen(dead_letter_key)
        
        if count and count > 0:
            logger.warning(f"Dead letter queue has {count} failed signals")
            return count, True
        
        return 0, False
        
    except Exception as e:
        logger.error(f"Error checking dead letter queue: {e}")
        return 0, False
```

2. **Add alert trigger in `AlertService`:**
```python
class AlertService:
    # ... existing methods ...
    
    async def check_and_alert_on_dead_letters(self) -> None:
        """Check dead letter queue and create alert if items present."""
        count, has_failed = await check_dead_letter_queue()
        
        if has_failed and count > 0:
            alert_payload = AlertPayload(
                level=AlertLevel.WARNING,
                category="queue_health",
                title="Dead Letter Queue Alert",
                message=f"{count} signals failed and are in dead letter queue. Manual review required.",
                metadata={
                    "queue_count": count,
                    "action_required": "Review failed signals and reprocess or fix underlying issues"
                }
            )
            
            # Send to Discord if notifier configured
            if self._discord_notifier:
                await self._discord_notifier.send(alert_payload)
            
            # Also log to database
            await self.create_alert(alert_payload)
```

3. **Call dead letter check periodically** - either:
   - Add to worker main loop (run every N iterations)
   - Or add as scheduled task
   - Or expose as API endpoint for monitoring

**Recommended approach**: Add to worker main loop in `src/worker.py`:
```python
# In the main worker loop, every 50 signals processed:
if signals_processed % 50 == 0:
    alert_service = AlertService()
    await alert_service.check_and_alert_on_dead_letters()
```

## Testing Strategy

1. **Test webhook 404 handling**: Mock Discord response with 404, verify graceful error return
2. **Test missing fields**: Pass partial data dict, verify no KeyError and defaults used
3. **Test dead letter monitoring**: Add items to Redis dead letter list, verify alert created

## Files to Modify
- `src/adapters/discord.py` - Issues #1 and #2
- `src/services/alert_service.py` - Issue #3
- `src/worker.py` - Add dead letter check to main loop (if needed)

## Type Hints
All new functions must include proper type hints:
- `def _is_valid_discord_webhook(url: str) -> bool`
- `async def check_dead_letter_queue(...) -> Tuple[int, bool]`
- `async def check_and_alert_on_dead_letters(self) -> None`

## Async Pattern
- Maintain existing `ThreadPoolExecutor` pattern for Discord/Telegram notifications
- Use `async def` for AlertService methods
- Use `await` when calling async methods