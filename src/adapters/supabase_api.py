"""
Shared Supabase client for API endpoints with auto-reconnect.

Handles HTTP/2 ConnectionTerminated errors by recreating the client
when the connection is stale. All API modules should use get_api_supabase()
instead of managing their own _client global.
"""

import logging
import time

logger = logging.getLogger(__name__)

_client = None
_created_at: float = 0.0
_MAX_AGE_SECONDS = 45  # Recreate client every 45s to avoid stale HTTP/2 connections


def get_api_supabase():
    """Get a Supabase client for API use with auto-reconnect.

    Recreates the client if:
      - It hasn't been created yet
      - It's older than 5 minutes (prevents stale HTTP/2 connections)
      - It was explicitly reset via reset_api_supabase()
    """
    global _client, _created_at

    now = time.time()
    if _client is not None and (now - _created_at) < _MAX_AGE_SECONDS:
        return _client

    from config import get_settings
    from supabase import create_client
    from fastapi import HTTPException

    s = get_settings()
    raw_key = s.supabase_service_role_key or s.supabase_key or ""
    key = raw_key.strip().strip('"\'').strip()
    if key.upper().startswith("SUPA") and "=" in key[:50]:
        key = key.split("=", 1)[-1].strip().strip('"\'').strip()
        
    if not s.supabase_url or not key:
        raise HTTPException(status_code=503, detail="Supabase not configured")

    _client = create_client(s.supabase_url, key)
    _created_at = now
    return _client


def reset_api_supabase():
    """Force-reset the cached client (call on connection errors)."""
    global _client, _created_at
    _client = None
    _created_at = 0.0


def is_supabase_connection_error(exc: BaseException) -> bool:
    """True if the exception indicates a transient Supabase/HTTP connection error worth retrying."""
    err_str = str(exc).lower()
    code = getattr(exc, "code", None)
    return (
        "connectionterminated" in err_str
        or "remoteprotocolerror" in err_str
        or "server disconnected" in err_str
        or "disconnect" in err_str
        or "connection" in err_str
        or code in {502, 503, 504}
        or "bad gateway" in err_str
        or "gateway timeout" in err_str
        or "cloudflare" in err_str
        or "json could not be generated" in err_str
    )


def supabase_query(fn):
    """Decorator that retries Supabase queries once on connection errors.

    Usage:
        @supabase_query
        def get_something():
            sb = get_api_supabase()
            return sb.table("foo").select("*").execute()
    """
    import functools

    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        try:
            return fn(*args, **kwargs)
        except Exception as e:
            # Retry on HTTP/2 connection errors (RemoteProtocolError, Server disconnected, etc.)
            retryable = is_supabase_connection_error(e)
            if retryable:
                logger.warning("Supabase connection error in %s, reconnecting: %s", fn.__name__, type(e).__name__)
                reset_api_supabase()
                return fn(*args, **kwargs)
            raise

    return wrapper
