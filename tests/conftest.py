"""
Pytest configuration for CI and local test runs.

Sets dummy environment variables BEFORE any src.* imports so that
config.Settings can be instantiated without real credentials.

Tests that need real external services must mock get_settings() or
the specific adapter they are testing (e.g. patch supabase, redis).
"""
import os

# ── Required fields in config.Settings (no default → ValidationError without these) ──
os.environ.setdefault("SUPABASE_URL", "http://dummy.supabase.test")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379")

# ── Optional but commonly checked ─────────────────────────────────────────────
os.environ.setdefault("SUPABASE_KEY", "dummy-anon-key-for-testing")
os.environ.setdefault("SUPABASE_SERVICE_ROLE_KEY", "dummy-service-role-key")

# ── Use in-memory signal transport so tests never touch a real Redis queue ────
os.environ.setdefault("SIGNAL_TRANSPORT", "memory")

# ── Disable external integrations that would make real network calls ──────────
os.environ.setdefault("META_API_TOKEN", "")
os.environ.setdefault("META_API_ACCOUNT_ID", "")
os.environ.setdefault("AI_API_KEY", "dummy-ai-key")
os.environ.setdefault("DISCORD_WEBHOOK_URL", "")
os.environ.setdefault("TELEGRAM_BOT_TOKEN", "")
