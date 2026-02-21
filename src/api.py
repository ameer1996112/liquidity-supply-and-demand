"""
Signal Receiver (API) - Validate -> Push to Redis -> 200.
No database, no business logic, no trade execution.
"""

import json
import logging
import os
import re
from typing import Any

from fastapi import Depends, FastAPI, Header, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import ValidationError
from urllib.parse import parse_qs

from config import get_settings
from src.adapters.redis_queue import QUEUE_NAME, get_redis, push_payload
from src.core.signal import EntryWebhookPayload, ExitWebhookPayload

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


def _build_cors_origins() -> list[str]:
    origins = [
        "https://frontend-production-a7cf.up.railway.app",
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ]
    frontend_url = os.getenv("FRONTEND_URL", "").strip()
    if frontend_url and frontend_url not in origins:
        origins.append(frontend_url)
        logger.info("CORS: Added FRONTEND_URL origin: %s", frontend_url)
    return origins


from src.api_rules import router as rules_router
from src.api_risk import router as risk_router
from src.api_risk_monitor import router as risk_monitor_router
from src.api_admin import router as admin_router
from src.api_positions import router as positions_router
from src.api_alerts import router as alerts_router
from src.api_analytics import router as analytics_router
from src.api_evaluation import router as evaluation_router
from src.api_execution import router as execution_router
from src.api_portfolio import router as portfolio_router
from src.api_portfolio_control import router as portfolio_control_router
from src.api_prop_firm import router as prop_firm_router  # NEW: Prop firm metrics
app = FastAPI(title="Trading Webhook API", version="1.0.0")
app.include_router(rules_router)
app.include_router(risk_router)
app.include_router(risk_monitor_router)  # Read-only risk monitor
app.include_router(admin_router)
app.include_router(positions_router)
app.include_router(alerts_router)
app.include_router(analytics_router)
app.include_router(evaluation_router)
app.include_router(execution_router)
app.include_router(portfolio_router)
app.include_router(portfolio_control_router)  # Portfolio Command Center V2.0
app.include_router(prop_firm_router)  # Prop firm metrics
app.add_middleware(
    CORSMiddleware,
    allow_origins=_build_cors_origins(),
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS", "PATCH"],
    allow_headers=["*"],
    expose_headers=["*"],
    max_age=600,
)


@app.on_event("startup")
def _fail_fast_config():
    settings = get_settings()
    
    # ══════════════════════════════════════════════════════════
    # CRITICAL: Redis Health Check (Fail-Fast)
    # ══════════════════════════════════════════════════════════
    # If Redis is down, the API cannot queue webhooks. Crash immediately
    # rather than accepting requests that can't be processed.
    from src.adapters.redis_queue import ping_redis
    
    if not ping_redis():
        logger.critical("❌ FATAL: Redis unreachable. Check REDIS_URL environment variable.")
        logger.critical("API will not start until Redis is available.")
        raise RuntimeError("Redis connection failed at startup. Cannot accept webhooks without queue.")
    
    logger.info("✅ Redis connection verified - Queue operational")
    redis_client = get_redis()

    # Initialize background sync worker if enabled
    try:
        from supabase import create_client
        from src.services.background_sync_worker import initialize_background_worker

        # Get supabase client
        key = (settings.supabase_service_role_key or settings.supabase_key or "").strip().strip('"\'')
        if settings.supabase_url and key:
            sb_client = create_client(settings.supabase_url, key)

            # Initialize worker
            sync_enabled = getattr(settings, 'account_sync_enabled', False)
            sync_interval = getattr(settings, 'account_sync_interval_seconds', 60)

            if sync_enabled:
                logger.info(f"Initializing background sync worker (interval: {sync_interval}s)...")
                initialize_background_worker(
                    supabase_client=sb_client,
                    sync_enabled=sync_enabled,
                    sync_interval_seconds=sync_interval,
                    redis_client=redis_client,
                    cache_ttl_seconds=30,
                )
            else:
                logger.info("Background sync worker disabled (ACCOUNT_SYNC_ENABLED=false)")
        else:
            logger.warning("Supabase not configured, background sync disabled")

    except Exception as e:
        logger.error(f"Failed to initialize background sync worker: {e}")
        # Don't fail startup if worker init fails


@app.on_event("shutdown")
def _shutdown_worker():
    """Shutdown background worker gracefully."""
    try:
        from src.services.background_sync_worker import shutdown_background_worker
        logger.info("Shutting down background sync worker...")
        shutdown_background_worker()
    except Exception as e:
        logger.error(f"Error during worker shutdown: {e}")


def validate_webhook_secret(request: Request, secret: str | None) -> None:
    settings = get_settings()
    if not settings.webhook_secret:
        return
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


def _validate_webhook_payload(data: dict[str, Any]) -> dict[str, Any]:
    if not data or not isinstance(data, dict):
        raise RequestValidationError(errors=[{"type": "value_error", "loc": ("body",), "msg": "Empty or invalid body"}])
    event_type = data.get("event_type")
    if event_type == "exit":
        try:
            ExitWebhookPayload.model_validate(data)
        except ValidationError as e:
            raise RequestValidationError(errors=e.errors()) from e
    else:
        try:
            EntryWebhookPayload.model_validate(data)
        except ValidationError as e:
            raise RequestValidationError(errors=e.errors()) from e
    return data


async def get_webhook_payload(
    request: Request,
    x_webhook_secret: str | None = Header(None),
) -> dict[str, Any]:
    validate_webhook_secret(request, x_webhook_secret)
    raw = await request.body()
    raw_preview = raw[:500] if len(raw) > 500 else raw
    logger.info("Webhook raw body (len=%d, content_type=%s): %s", len(raw), request.headers.get("content-type", ""), raw_preview.decode("utf-8", errors="replace"))
    try:
        data = parse_body(raw)
    except HTTPException:
        raise
    if data is None:
        raise RequestValidationError(errors=[{"type": "value_error", "loc": ("body",), "msg": "Body could not be parsed"}])
    if not isinstance(data, dict):
        raise RequestValidationError(errors=[{"type": "value_error", "loc": ("body",), "msg": "Body must be a JSON object"}])
    return _validate_webhook_payload(data)


@app.get("/health")
def health():
    return {"status": "ok", "service": "api"}


# ---------------------------------------------------------------------------
# AI / ML Configuration endpoint
# ---------------------------------------------------------------------------

@app.get("/config/ai")
def get_ai_config():
    """Return current AI/ML/RAG configuration (read-only)."""
    s = get_settings()
    return {
        "ai": {
            "ai_filter_enabled": s.ai_filter_enabled,
            "ai_provider": s.ai_provider,
            "ai_model": s.ai_model,
            "ai_base_url": s.ai_base_url,
            "ai_min_confidence": s.ai_min_confidence,
            "ai_timeout_seconds": s.ai_timeout_seconds,
            "ai_api_key_set": bool(s.ai_api_key.get_secret_value()),
        },
        "ml": {
            "ml_guardian_enabled": s.ml_guardian_enabled,
            "ml_min_confidence": s.ml_min_confidence,
        },
        "ensemble": {
            "enable_llm_filter": s.enable_llm_filter,
            "run_shadow_mode": s.run_shadow_mode,
        },
        "execution": {
            "execution_mode": s.execution_mode,
            "run_mode": s.run_mode,
            "live_trading_enabled": s.live_trading_enabled,
            "live_shadow": s.live_shadow,
            "trading_kill_switch": s.trading_kill_switch,
            "meta_api_configured": bool(s.meta_api_token and s.meta_api_account_id),
            "meta_api_region": s.meta_api_region,
        },
        "risk": {
            "trinity_enabled": s.trinity_enabled,
            "trinity_max_daily_loss_pct": s.trinity_max_daily_loss_pct,
            "trinity_max_drawdown_pct": s.trinity_max_drawdown_pct,
            "trinity_max_risk_per_trade_pct": s.trinity_max_risk_per_trade_pct,
            "trinity_max_positions": s.trinity_max_positions,
            "risk_percent": s.risk_percent,
            "account_balance": s.account_balance,
            "enable_risk_scaling": s.enable_risk_scaling,
            "risk_mode": s.risk_mode,
        },
    }


@app.post("/webhook")
async def webhook(payload: dict[str, Any] = Depends(get_webhook_payload)):
    # Safety default: treat signals without explicit run_mode as PAPER
    payload.setdefault("run_mode", "PAPER")
    symbol = payload.get("symbol", payload.get("zone_id", "N/A"))
    run_mode = payload["run_mode"]
    logger.info("Signal: %s | Mode: %s", symbol, run_mode)
    payload_str = json.dumps(payload)
    push_payload(payload_str)
    logger.info("Queued payload (len=%d)", len(payload_str))
    return JSONResponse(status_code=200, content={"status": "queued"})
