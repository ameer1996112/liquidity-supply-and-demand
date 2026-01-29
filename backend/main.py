"""
Signal Receiver (API) - Zero-Drop Rule.
Only: Validate -> Push to Redis -> Return 200.
No database, no business logic, no trade execution.
"""

import json
import logging
import re
from typing import Any
from urllib.parse import parse_qs

from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.responses import JSONResponse

from config import get_settings

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

app = FastAPI(title="Trading Webhook API", version="1.0.0")


@app.on_event("startup")
def _fail_fast_config():
    """Fail fast on startup if required env (REDIS_URL, WEBHOOK_SECRET, SUPABASE_URL) is missing."""
    get_settings()
    get_redis()


# Redis client (lazy init)
_redis = None


def get_redis():
    global _redis
    if _redis is None:
        import redis
        s = get_settings()
        _redis = redis.from_url(s.redis_url, decode_responses=True)
    return _redis


def validate_webhook_secret(request: Request, secret: str | None) -> None:
    """Verify webhook secret if configured. Raises HTTPException if invalid.
    Accepts: X-Webhook-Secret header, Authorization: Bearer <secret>, or ?secret= in query (for TradingView).
    """
    settings = get_settings()
    if not settings.webhook_secret:
        return
    # Query param (TradingView can't send headers)
    query_secret = None
    if request.url.query:
        qs = parse_qs(request.url.query)
        secrets = qs.get("secret", qs.get("Secret", []))
        query_secret = secrets[0] if secrets else None
    provided = (
        (secret or "").strip()
        or (request.headers.get("X-Webhook-Secret") or "").strip()
        or (request.headers.get("Authorization") or "").replace("Bearer ", "").strip()
        or (request.query_params.get("secret") or "").strip()
        or (query_secret or "").strip()
    )
    expected = (settings.webhook_secret or "").strip().strip('"').strip("'")
    provided = provided.strip('"').strip("'")
    if not provided or provided != expected:
        raise HTTPException(status_code=401, detail="Invalid webhook secret")


def parse_body(raw: bytes) -> dict[str, Any]:
    """Parse JSON from request body. Handles TradingView placeholders and trailing commas."""
    raw_str = raw.decode("utf-8", errors="replace")
    try:
        return json.loads(raw_str)
    except json.JSONDecodeError:
        pass
    start = raw_str.find("{")
    if start < 0:
        raise HTTPException(status_code=400, detail="No JSON object found")
    end = raw_str.rfind("}") + 1
    candidate = raw_str[start:end]
    candidate = candidate.replace('"', '"').replace('"', '"')
    candidate = re.sub(r"\{\{.*?\}\}", "null", candidate, flags=re.DOTALL)
    candidate = re.sub(r",\s*([}\]])", r"\1", candidate)
    try:
        return json.loads(candidate, strict=False)
    except json.JSONDecodeError as e:
        raise HTTPException(status_code=400, detail=f"Invalid JSON: {e}")


def validate_entry_payload(data: dict) -> None:
    """Ensure required entry fields exist. Raises HTTPException if invalid."""
    required = ["symbol", "side", "entry", "sl", "tp", "size"]
    missing = [k for k in required if k not in data]
    if missing:
        raise HTTPException(status_code=400, detail=f"Missing fields: {missing}")
    if str(data.get("side", "")).lower() not in ("buy", "sell"):
        raise HTTPException(status_code=400, detail="Invalid side")


def validate_exit_payload(data: dict) -> None:
    """Ensure required exit fields exist."""
    required = ["event_type", "zone_id", "outcome", "bars_held", "close_price", "exit_type", "mae_pips"]
    missing = [k for k in required if k not in data]
    if missing:
        raise HTTPException(status_code=400, detail=f"Missing exit fields: {missing}")


QUEUE_NAME = "trading_queue"


@app.get("/health")
def health():
    """Liveness: API is up. Does not touch DB or Redis."""
    return {"status": "ok", "service": "api"}


@app.post("/webhook")
async def webhook(
    request: Request,
    x_webhook_secret: str | None = Header(None),
):
    """
    Receive TradingView (or other) webhook.
    Validate -> Push to Redis -> Return 200. No DB, no execution.
    """
    validate_webhook_secret(request, x_webhook_secret)

    raw = await request.body()
    data = parse_body(raw)

    # Exit events: same rule — validate and queue
    if data.get("event_type") == "exit":
        validate_exit_payload(data)
    else:
        validate_entry_payload(data)

    payload_str = json.dumps(data)
    r = get_redis()
    r.rpush(QUEUE_NAME, payload_str)
    logger.info("Queued payload (len=%d)", len(payload_str))

    return JSONResponse(
        status_code=200,
        content={"status": "queued"},
    )
