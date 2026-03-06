"""
Pytest configuration for CI and local test runs.

Sets dummy environment variables BEFORE any src.* imports so that
config.Settings can be instantiated without real credentials.

Tests that need real external services must mock get_settings() or
the specific adapter they are testing (e.g. patch supabase, redis).
"""
import os
from unittest.mock import MagicMock

# ── Required fields in config.Settings (no default → ValidationError without these) ──
os.environ.setdefault("SUPABASE_URL", "http://dummy.supabase.test")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379")

# ── Leave Supabase keys EMPTY so _fail_fast_config() skips the Supabase
#    initialisation block (it guards with `if settings.supabase_url and key:`).
#    Tests that need a Supabase client must mock it themselves.
os.environ.setdefault("SUPABASE_KEY", "")
os.environ.setdefault("SUPABASE_SERVICE_ROLE_KEY", "")

# ── Use in-memory signal transport so tests never touch a real Redis queue ────
os.environ.setdefault("SIGNAL_TRANSPORT", "memory")

# ── Disable external integrations that would make real network calls ──────────
os.environ.setdefault("META_API_TOKEN", "")
os.environ.setdefault("META_API_ACCOUNT_ID", "")
os.environ.setdefault("AI_API_KEY", "dummy-ai-key")
os.environ.setdefault("DISCORD_WEBHOOK_URL", "")
os.environ.setdefault("TELEGRAM_BOT_TOKEN", "")

# ── Global safety-net: prevent any real Redis or Supabase network calls ───────
# Tests that need specific behaviour must patch at a finer scope themselves.
import pytest

@pytest.fixture(autouse=True)
def _mock_redis_client(monkeypatch):
    """Replace the lazy Redis client with a MagicMock for every test.

    This prevents get_redis() from attempting a real TCP connection to
    redis://localhost:6379 in CI where no Redis server is running.
    """
    mock_redis = MagicMock()
    mock_redis.ping.return_value = True
    mock_redis.rpush.return_value = 1
    mock_redis.blpop.return_value = None
    mock_redis.lrange.return_value = []
    mock_redis.llen.return_value = 0

    # Patch the module-level _redis singleton so get_redis() returns the mock
    import src.adapters.redis_queue as rq
    monkeypatch.setattr(rq, "_redis", mock_redis)
    yield mock_redis
    # monkeypatch automatically restores the original value after each test
