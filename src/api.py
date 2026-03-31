"""
Signal Receiver (API) - Validate -> Push to Redis -> 200.
No database, no business logic, no trade execution.
"""

import json
import logging
import os
import re
import time
import uuid
from typing import Any

from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, Header, HTTPException, Request, WebSocket
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ValidationError
from urllib.parse import parse_qs

# ── Rate limiting (slowapi) ───────────────────────────────────────────────────
try:
    from slowapi import Limiter, _rate_limit_exceeded_handler
    from slowapi.util import get_remote_address
    from slowapi.errors import RateLimitExceeded
    _limiter = Limiter(key_func=get_remote_address, default_limits=["200/minute"])
    _RATE_LIMIT_AVAILABLE = True
except ImportError:
    _limiter = None  # type: ignore[assignment]
    _RATE_LIMIT_AVAILABLE = False
    logging.getLogger(__name__).warning("slowapi not installed — rate limiting disabled")

from config import get_settings
from config.logging_config import configure_logging, get_logger
from src.adapters.redis_queue import get_redis
from src.core.transport import get_transport
from src.core.signal import validate_webhook_payload


def _require_admin_key(
    x_admin_api_key: str | None = Header(None, alias="X-Admin-API-Key"),
    authorization: str | None = Header(None),
) -> None:
    """Dependency that enforces ADMIN_API_KEY on privileged operator routes."""
    settings = get_settings()
    expected = (settings.admin_api_key or "").strip()
    if not expected:
        raise HTTPException(
            status_code=503,
            detail="Admin API key not configured. Set ADMIN_API_KEY in environment.",
        )
    # Accept key via X-Admin-API-Key header or Authorization: Bearer <key>
    provided = (x_admin_api_key or "").strip()
    if not provided and authorization:
        provided = authorization.replace("Bearer ", "").strip()
    if not provided or provided != expected:
        raise HTTPException(status_code=403, detail="Forbidden: invalid admin API key")

configure_logging()
logger = get_logger("trinity.api")

# ── System trading mode cache ────────────────────────────────────────────────
# Loaded from system_config table, cached for 30 seconds to avoid DB hit on
# every incoming webhook signal.
_system_mode_cache: dict = {"value": None, "loaded_at": 0.0}
_SYSTEM_MODE_CACHE_TTL = 30  # seconds


def _get_system_trading_mode() -> str:
    """Return the current system-level trading mode, using a 30s in-memory cache."""
    now = time.time()
    if now - _system_mode_cache["loaded_at"] < _SYSTEM_MODE_CACHE_TTL and _system_mode_cache["value"]:
        return _system_mode_cache["value"]
    try:
        from src.adapters.supabase_api import get_api_supabase as _get_supabase
        sb = _get_supabase()
        result = (
            sb.table("system_config")
            .select("value")
            .eq("key", "trading_mode")
            .single()
            .execute()
        )
        mode = result.data["value"] if result.data else "PAPER"
    except Exception as e:
        logger.warning(f"Could not load system trading mode from DB, using fallback: {e}")
        from config.settings import get_settings
        mode = get_settings().run_mode or "PAPER"
    _system_mode_cache["value"] = mode
    _system_mode_cache["loaded_at"] = now
    logger.debug(f"System trading mode loaded: {mode}")
    return mode


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

    cors_env = os.getenv("CORS_ORIGINS", "").strip()
    if cors_env:
        origins.extend([o.strip() for o in cors_env.split(",") if o.strip()])

    return origins


from src.api_rules import router as rules_router
from src.api_risk import router as risk_router
from src.api_risk_monitor import router as risk_monitor_router
from src.api_admin import router as admin_router
from src.api_positions import router as positions_router
from src.api_alerts import router as alerts_router
from src.api_analytics import router as analytics_router
from src.api_analytics_signals_perf import router as analytics_signals_perf_router  # v1.1: ANALYTICS-01-03
from src.api_health_trading import router as health_trading_router  # v1.1: HEALTH-01-03
from src.api_evaluation import router as evaluation_router
from src.api_execution import router as execution_router
from src.api_portfolio import router as portfolio_router
from src.api_portfolio_control import router as portfolio_control_router
from src.api_prop_firm import router as prop_firm_router  # NEW: Prop firm metrics
from src.api_prop_firm_v1 import router as prop_firm_v1_router # Phase 1 Endpoints
from src.api_traces import router as traces_router       # Sprint 2.1: latency traces
from src.api_accounts import router as accounts_router   # Sprint 2.3: multi-account
from src.api_ai_runs import router as ai_runs_router     # Sprint 3.3: debate ai_run
from src.api_backtests import router as backtests_router # Sprint 4.1: Backtest Lab
from src.api_strategies import router as strategies_router # Sprint 4.4: Strategy configs
from src.api_webhook_read import router as webhook_read_router  # E2E: signals/recent, trades/open, stats/summary
from src.api_copilot import router as copilot_router           # AI Copilot: natural language queries
from src.api_market import router as market_router             # Market data proxy (Yahoo Finance CORS bypass)
from src.api_funding import router as funding_router           # Funding: daily PnL and stats for prop firm UI
from src.api_config import router as config_router             # System config: trading mode control
from src.api_tickets import router as tickets_router           # Ticket tracker: Jira-style task/bug board
from src.api_incidents import router as incidents_router       # Incident auto-tickets: worker errors, test failures, ML drift
from src.api_agent_status import router as agent_status_router # v1.2: UI-02: Agent operational state
from src.api_broker_profiles import router as broker_profiles_router  # Multi-account MetaAPI management
from src.api_dashboard import router as dashboard_router
from src.api_notifications import router as notifications_router  # DEV-73: notification settings

@asynccontextmanager
async def _lifespan(app: FastAPI):  # noqa: ARG001
    """Replaces deprecated @app.on_event('startup'/'shutdown')."""
    # ── STARTUP ──────────────────────────────────────────────────────────────
    _fail_fast_config()
    await _start_metaapi_streaming()
    yield
    # ── SHUTDOWN ─────────────────────────────────────────────────────────────
    _shutdown_worker()
    _stop_metaapi_streaming()


app = FastAPI(title="Trading Webhook API", version="1.0.0", lifespan=_lifespan)

# Attach rate limiter state and error handler
if _RATE_LIMIT_AVAILABLE and _limiter is not None:
    app.state.limiter = _limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)  # type: ignore[arg-type]

app.include_router(rules_router)
app.include_router(risk_router)
app.include_router(risk_monitor_router)  # Read-only risk monitor
app.include_router(admin_router, dependencies=[Depends(_require_admin_key)])
app.include_router(positions_router)
app.include_router(alerts_router)
app.include_router(analytics_router)
app.include_router(analytics_signals_perf_router)  # v1.1 signals-perf
app.include_router(health_trading_router)  # v1.1 trading health
app.include_router(evaluation_router)
app.include_router(execution_router)
app.include_router(portfolio_router)
app.include_router(portfolio_control_router)  # Portfolio Command Center V2.0
app.include_router(prop_firm_router)  # Prop firm metrics
app.include_router(prop_firm_v1_router) # Phase 1 API Endpoints
app.include_router(traces_router)     # Sprint 2.1: pipeline latency traces
app.include_router(accounts_router)  # Sprint 2.3: multi-account routing
app.include_router(ai_runs_router)   # Sprint 3.3: debate ai_run
app.include_router(backtests_router) # Sprint 4.1: Backtest Lab
app.include_router(strategies_router) # Sprint 4.4: Strategy-as-data configs
app.include_router(webhook_read_router)  # E2E: /api/v1/webhook/signals/recent, trades/open, stats/summary
app.include_router(copilot_router)       # AI Copilot: /api/copilot/chat
app.include_router(market_router)         # Market data proxy: /api/market/*
app.include_router(funding_router)        # Funding: /api/v1/funding/daily-pnl, stats
app.include_router(config_router, dependencies=[Depends(_require_admin_key)])         # System config: /api/v1/config/trading-mode
app.include_router(tickets_router)        # Ticket tracker: /api/tickets
app.include_router(incidents_router)      # Incident auto-tickets: /api/incidents
app.include_router(agent_status_router)   # v1.2: Agent status: /api/agent/status
app.include_router(broker_profiles_router, dependencies=[Depends(_require_admin_key)])  # Multi-account MetaAPI credential management
app.include_router(dashboard_router)        # DEV-61: dashboard summary aggregation
app.include_router(notifications_router)    # DEV-73: notification settings (routing, whitelist, audit log)
app.add_middleware(
    CORSMiddleware,
    allow_origins=_build_cors_origins(),
    allow_origin_regex=os.getenv("CORS_ORIGIN_REGEX", r"https://.*\.up\.railway\.app"),
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS", "PATCH"],
    allow_headers=["*"],
    expose_headers=["*"],
    max_age=600,
)

import time as _time_mod
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request as _StarletteRequest
from starlette.responses import Response as _StarletteResponse

_req_logger = get_logger("trinity.api.requests")

class _RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Log method, path, status, and duration for every request at DEBUG level."""

    async def dispatch(self, request: _StarletteRequest, call_next: Any) -> _StarletteResponse:
        t0 = _time_mod.perf_counter()
        response = await call_next(request)
        ms = ((_time_mod.perf_counter() - t0) * 1000)
        _req_logger.debug(
            "%s %s → %d (%.0fms)",
            request.method,
            request.url.path,
            response.status_code,
            ms,
        )
        return response

app.add_middleware(_RequestLoggingMiddleware)


def _fail_fast_config():
    settings = get_settings()
    
    # ══════════════════════════════════════════════════════════
    # CRITICAL: Transport Health Check (Fail-Fast)
    # ══════════════════════════════════════════════════════════
    # If the signal transport is down, the API cannot queue webhooks.
    # Crash immediately rather than accepting requests that can't be processed.
    import time as _time

    transport = get_transport()
    _transport_ok = False
    for _attempt in range(1, 6):
        if transport.ping():
            _transport_ok = True
            break
        logger.warning("Transport not ready (attempt %d/5) — retrying in 3s...", _attempt)
        _time.sleep(3)

    if not _transport_ok:
        logger.critical("FATAL: Signal transport unreachable after 5 attempts.")
        raise RuntimeError("Signal transport connection failed at startup. Cannot accept webhooks without queue.")

    logger.info("Signal transport verified - Queue operational (%s)", type(transport).__name__)

    # ── Explicit Redis ping with actionable error message ─────────────────────
    try:
        import redis as _redis_lib
        from urllib.parse import urlparse as _urlparse
        _redis_url = settings.redis_url
        _r = _redis_lib.from_url(_redis_url, socket_connect_timeout=3)
        _r.ping()
        _parsed = _urlparse(_redis_url)
        _safe_url = f"{_parsed.scheme}://{_parsed.hostname}:{_parsed.port or 6379}"
        logger.info("Redis connection OK: %s", _safe_url)
    except Exception as _redis_exc:
        logger.error(
            "❌ Redis not reachable: %s\n"
            "  → Start with: redis-server --daemonize yes\n"
            "  → Or set REDIS_URL in .env",
            _redis_exc,
        )
        raise RuntimeError(f"Redis required but unavailable: {_redis_exc}") from _redis_exc

    redis_client = get_redis()

    # Initialize background sync worker if enabled
    try:
        from supabase import create_client
        from src.services.background_sync_worker import initialize_background_worker

        # Get supabase client
        raw_key = settings.supabase_service_role_key or settings.supabase_key or ""
        key = raw_key.strip().strip('"\'').strip()
        if key.upper().startswith("SUPA") and "=" in key[:50]:
            key = key.split("=", 1)[-1].strip().strip('"\'').strip()

        if settings.supabase_url and key:
            sb_client = create_client(settings.supabase_url, key)

            # Validate active strategy configs (Sprint 4.4).
            # Any invalid active strategy should hard-fail startup so we never
            # run with unsafe strategy-as-data.
            # NOTE: validate_active_strategies_startup raises RuntimeError on
            # invalid configs.  We let it propagate (crash the API) intentionally.
            from src.services.strategy_config import validate_active_strategies_startup
            validate_active_strategies_startup(sb_client)

            # Initialize worker
            sync_enabled = getattr(settings, "account_sync_enabled", False)
            sync_interval = getattr(settings, "account_sync_interval_seconds", 60)

            if sync_enabled:
                logger.info(
                    f"Initializing background sync worker (interval: {sync_interval}s)..."
                )
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

    except RuntimeError:
        raise  # Strategy validation failure — crash on purpose
    except Exception as e:
        logger.error(f"Failed to initialize background sync worker: {e}")


def _shutdown_worker():
    """Shutdown background worker gracefully."""
    try:
        from src.services.background_sync_worker import shutdown_background_worker
        logger.info("Shutting down background sync worker...")
        shutdown_background_worker()
    except Exception as e:
        logger.error(f"Error during worker shutdown: {e}")


async def _start_metaapi_streaming() -> None:
    """
    Start the MetaApi real-time streaming service (DEV-39).

    Controlled by METAAPI_STREAMING_ENABLED env var (default: true when
    META_API_TOKEN and META_API_ACCOUNT_ID are set).
    The streaming listener catches deal-exit events and writes Net PnL
    (profit + swap + commission) directly to the DB — Supabase Realtime
    then pushes the update to the frontend automatically.
    """
    import os
    if os.getenv("METAAPI_STREAMING_ENABLED", "true").lower() in ("false", "0", "no"):
        logger.info("MetaApi streaming disabled (METAAPI_STREAMING_ENABLED=false)")
        return

    try:
        from supabase import create_client
        from src.services.metaapi_streaming_service import start_streaming
        from src.core.metaapi_credentials import get_primary_credentials

        settings = get_settings()
        token, account_id, _ = get_primary_credentials()

        if not token or not account_id:
            logger.info(
                "MetaApi streaming not started: no MetaAPI credentials found in broker_profiles"
            )
            return

        raw_key = settings.supabase_service_role_key or settings.supabase_key or ""
        key = raw_key.strip().strip('"\'').strip()
        if key.upper().startswith("SUPA") and "=" in key[:50]:
            key = key.split("=", 1)[-1].strip().strip('"\'').strip()

        if not settings.supabase_url or not key:
            logger.warning("MetaApi streaming: Supabase not configured, cannot update DB")
            return

        sb_client = create_client(settings.supabase_url, key)
        start_streaming(token, account_id, sb_client)
        logger.info("MetaApi streaming service started (real-time deal events active)")

    except Exception as exc:
        logger.error("Failed to start MetaApi streaming service: %s", exc)


def _stop_metaapi_streaming() -> None:
    """Stop the MetaApi streaming service gracefully."""
    try:
        from src.services.metaapi_streaming_service import stop_streaming
        stop_streaming()
    except Exception as exc:
        logger.error("Error stopping MetaApi streaming: %s", exc)


def validate_webhook_secret(request: Request, secret: str | None) -> None:
    """Validate the webhook secret using constant-time comparison.

    Accepts the secret via:
    - X-Webhook-Secret header
    - Authorization: Bearer <secret> header
    - ?secret= query param (legacy TradingView support)

    If WEBHOOK_SECRET is unset the request is rejected — callers must configure
    a secret before the endpoint will accept any payload.
    """
    import hmac as _hmac
    settings = get_settings()
    expected = (settings.webhook_secret or "").strip().strip('"').strip("'")
    if not expected:
        raise HTTPException(
            status_code=503,
            detail="Webhook secret not configured. Set WEBHOOK_SECRET in environment.",
        )
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
    provided = provided.strip('"').strip("'")
    if not provided or not _hmac.compare_digest(provided, expected):
        raise HTTPException(status_code=401, detail="Invalid webhook secret")


# TradingView {{time}} outputs ISO date like 2026-03-04T15:55:54Z; unquoted it breaks JSON.
# Quote unquoted ISO date values so parse succeeds.
_ISO_DATE_PATTERN = re.compile(
    r'(:\s*)(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z)(\s*[,}\]])'
)


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
    # Fix unquoted TradingView {{time}} (ISO date) so JSON parses
    candidate = _ISO_DATE_PATTERN.sub(r'\1"\2"\3', candidate)
    try:
        return json.loads(candidate, strict=False)
    except json.JSONDecodeError as e:
        raise HTTPException(status_code=400, detail=f"Invalid JSON: {e}")


def _validate_webhook_payload(data: dict[str, Any]) -> dict[str, Any]:
    """
    FastAPI-specific wrapper around the core webhook validator.

    Converts pydantic.ValidationError / ValueError into FastAPI's
    RequestValidationError while delegating the actual schema logic to
    src.core.signal.validate_webhook_payload so the API and worker share
    identical rules (Sprint 6.2).
    """
    if not data or not isinstance(data, dict):
        raise RequestValidationError(
            errors=[
                {
                    "type": "value_error",
                    "loc": ("body",),
                    "msg": "Empty or invalid body",
                }
            ]
        )
    try:
        return validate_webhook_payload(data)
    except ValidationError as e:
        # Pydantic-style validation error → FastAPI wrapper
        raise RequestValidationError(errors=e.errors()) from e
    except ValueError as e:
        # Non-pydantic value errors (e.g. type guards in core validator)
        raise RequestValidationError(
            errors=[
                {
                    "type": "value_error",
                    "loc": ("body",),
                    "msg": str(e),
                }
            ]
        ) from e


async def get_webhook_payload(
    request: Request,
    x_webhook_secret: str | None = Header(None),
) -> dict[str, Any]:
    validate_webhook_secret(request, x_webhook_secret)
    raw = await request.body()
    raw_preview = raw[:500] if len(raw) > 500 else raw
    logger.debug("Webhook raw body (len=%d, content_type=%s): %s", len(raw), request.headers.get("content-type", ""), raw_preview.decode("utf-8", errors="replace"))
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
    return {"status": "healthy", "service": "api"}


# ---------------------------------------------------------------------------
# AI / ML Configuration endpoint
# ---------------------------------------------------------------------------

def _get_effective_ai_mode():
    """Sprint 3.4: DB override takes precedence over env."""
    try:
        from src.services.ai_mode_override import get_ai_mode_override
        override = get_ai_mode_override()
        if override:
            return override
    except Exception:
        pass
    return getattr(get_settings(), "ai_mode", "shadow")


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
            "ai_enabled": getattr(s, "ai_enabled", True),
            "ai_mode": _get_effective_ai_mode(),
            "ai_quick_model": getattr(s, "ai_quick_model", ""),
            "ai_deep_model": getattr(s, "ai_deep_model", ""),
        },
        "execution": {
            "execution_mode": s.execution_mode,
            "run_mode": s.run_mode,
            "live_trading_enabled": s.live_trading_enabled,
            "live_shadow": s.live_shadow,
            "trading_kill_switch": s.trading_kill_switch,
            "meta_api_configured": False,  # credentials now in broker_profiles DB
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


# ---------------------------------------------------------------------------
# Sprint 3.4: Strategy graduation pipeline
# ---------------------------------------------------------------------------

@app.get("/config/ai/graduation")
def get_graduation_status():
    """Return shadow vs actual metrics and readiness to enable enforce."""
    from src.services.graduation_service import (
        compute_shadow_metrics,
        check_graduation_readiness,
    )
    from src.adapters.supabase import supabase

    s = get_settings()
    min_sample = getattr(s, "ai_graduation_min_sample_size", 50)
    min_edge = getattr(s, "ai_graduation_min_edge_pct", 5.0)

    metrics = compute_shadow_metrics(supabase, min_days=30)
    readiness = check_graduation_readiness(metrics, min_sample, min_edge)
    return readiness


class SetAiModeBody(BaseModel):
    mode: str
    reason: str = ""
    created_by: str = ""


@app.patch("/config/ai/mode")
def set_ai_mode_endpoint(body: SetAiModeBody):
    """
    Set AI mode (shadow | enforce). Enforce only allowed when graduation ready.
    Full audit log in ai_mode_toggles.
    """
    from src.services.ai_mode_override import set_ai_mode, invalidate_cache
    from src.services.graduation_service import (
        compute_shadow_metrics,
        check_graduation_readiness,
    )
    from src.adapters.supabase import supabase

    to_mode = (body.mode or "").strip().lower()
    if to_mode not in ("shadow", "enforce"):
        raise HTTPException(status_code=400, detail="mode must be 'shadow' or 'enforce'")

    current = _get_effective_ai_mode()
    if to_mode == current:
        return {"status": "ok", "mode": to_mode, "message": "Already in this mode"}

    if to_mode == "enforce":
        s = get_settings()
        min_sample = getattr(s, "ai_graduation_min_sample_size", 50)
        min_edge = getattr(s, "ai_graduation_min_edge_pct", 5.0)
        metrics = compute_shadow_metrics(supabase, min_days=30)
        readiness = check_graduation_readiness(metrics, min_sample, min_edge)
        if not readiness["ready"]:
            raise HTTPException(
                status_code=403,
                detail={
                    "message": "Cannot enable enforce: graduation not ready",
                    "reason": readiness["reason"],
                    "readiness": readiness,
                },
            )

    ok = set_ai_mode(
        to_mode,
        supabase=supabase,
        from_mode=current,
        reason=body.reason or "api",
        created_by=body.created_by or "",
    )
    if not ok:
        raise HTTPException(status_code=500, detail="Failed to update ai_mode")
    invalidate_cache()
    return {"status": "ok", "mode": to_mode}


@app.get("/config/ai/mode-toggles")
def get_ai_mode_toggles(limit: int = 50):
    """Full audit log of AI mode toggles."""
    from fastapi import HTTPException
    from src.adapters.supabase import supabase

    if not supabase:
        raise HTTPException(status_code=503, detail="Database unavailable")
    try:
        resp = (
            supabase.table("ai_mode_toggles")
            .select("*")
            .order("created_at", desc=True)
            .limit(min(limit, 200))
            .execute()
        )
        return {"toggles": resp.data or []}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.websocket("/ws/debate")
async def debate_ws(websocket: WebSocket):
    """
    Stream MAS Council Room debate logs to the frontend AI Terminal.

    The worker Supervisor publishes each step (quant score, risk check,
    final decision) to Redis pub/sub channel `trading:debate_logs`.
    This endpoint subscribes and forwards every message to connected clients.
    """
    await websocket.accept()
    logger.info("[WS] /ws/debate client connected: %s", websocket.client)
    _r = None
    pubsub = None
    try:
        import redis.asyncio as aioredis
        from config import get_settings as _gs
        _r = aioredis.from_url(_gs().redis_url, decode_responses=True)
        pubsub = _r.pubsub()
        await pubsub.subscribe("trading:debate_logs")
        async for raw in pubsub.listen():
            if raw["type"] != "message":
                continue
            try:
                await websocket.send_text(raw["data"])
            except Exception:
                break
    except Exception as exc:
        logger.warning("[WS] /ws/debate error: %s", exc)
    finally:
        if pubsub:
            try:
                await pubsub.unsubscribe("trading:debate_logs")
            except Exception:
                pass
        if _r:
            try:
                await _r.aclose()
            except Exception:
                pass
        logger.info("[WS] /ws/debate client disconnected")


def _webhook_rate_limit(request: Request, payload: dict[str, Any] = Depends(get_webhook_payload)) -> dict[str, Any]:
    """Dependency passthrough — exists so the rate-limit decorator has a sync target."""
    return payload


# Apply rate limit only when slowapi is available
_webhook_limit = (_limiter.limit("60/minute") if _RATE_LIMIT_AVAILABLE and _limiter else lambda f: f)


@app.post("/webhook")
@_webhook_limit
async def webhook(request: Request, payload: dict[str, Any] = Depends(get_webhook_payload)):
    """
    TradingView webhook receiver.
    Rate limited to 60 requests/minute per IP (prevents replay/flood attacks).
    The webhook secret provides authentication; rate limiting adds a second layer.
    """
    # ── Run-mode resolution (in priority order) ──────────────────────────────
    #
    # 1. Payload explicitly contains run_mode → honour it (Pine/manual override)
    # 2. Payload contains force_paper=true    → force PAPER (manual debug)
    # 3. Otherwise                            → default to LIVE
    #
    # NOTE: We no longer rely on the User-Agent header to detect TradingView
    # because Railway's reverse proxy rewrites / strips it, making "TradingView"
    # undetectable and causing every signal to be forced into PAPER mode.
    #
    # The webhook endpoint is only reachable with the correct webhook secret, so
    # defaulting to LIVE here is safe — manual callers who want PAPER must send
    # `force_paper: true` in the payload body.

    user_agent = request.headers.get("User-Agent", "")
    is_tradingview = "TradingView" in user_agent  # kept for logging only

    # System-level trading mode: loaded from system_config DB table (cached 30s).
    # This is the single authoritative source of truth — Pine Script's hardcoded
    # "run_mode":"PAPER" is always ignored in favour of the operator-controlled mode.
    system_mode = _get_system_trading_mode()
    payload["run_mode"] = system_mode
    payload["_signal_source"] = "tradingview" if is_tradingview else "webhook"
    logger.info("Run-mode: %s (system config, UA=%s)", system_mode, user_agent[:60] or "<empty>")

    symbol = payload.get("symbol", payload.get("zone_id", "N/A"))
    run_mode = payload["run_mode"]


    # Account routing: resolve target account + stamp onto payload for tracking.
    # NOTE: queue_key is always signals:default regardless of account_id — the
    # worker selects accounts internally by matching broker_profiles on run_mode.
    # Per-account queue partitioning is NOT used because the worker only polls
    # signals:default, causing signals with account_id to get stuck permanently.
    from src.core.account_router import AccountRouter as _AccountRouter, DEFAULT_QUEUE_KEY
    _router = _AccountRouter()
    account_id = _router.resolve_account_id(payload)
    payload["_account_id"] = account_id
    queue_key = DEFAULT_QUEUE_KEY  # Always use signals:default

    # Persist at API level so signal appears in frontend even if worker never processes it (entry only)
    event_type = (payload.get("event_type") or "").strip().lower()
    action = (str(payload.get("action") or "")).strip().lower()
    is_exit = event_type == "exit" or action == "exit"
    receipt_id = str(uuid.uuid4())
    correlation_id = str(uuid.uuid4())
    payload["_webhook_receipt_id"] = receipt_id
    # _correlation_id links the Council ai_run to this signal.
    # The worker uses this to call persist_debate() and link_ai_run_to_signal().
    payload["_correlation_id"] = correlation_id
    if not is_exit:
        try:
            from src.adapters.supabase import get_supabase
            from config import get_settings as _gs
            s = _gs()
            sb = get_supabase()
            row = {
                "symbol": payload.get("symbol", "UNKNOWN"),
                "side": payload.get("side", "buy"),
                "size": float(payload.get("size", 0.01)),
                "entry": float(payload.get("entry", 0)) if payload.get("entry") else None,
                "sl": float(payload.get("sl", 0)) if payload.get("sl") else None,
                "tp": float(payload.get("tp", 0)) if payload.get("tp") else None,
                "status": "received",
                "notes": "Received by API, awaiting worker",
                "run_mode": run_mode,
                "account_id": account_id,
                "webhook_receipt_id": receipt_id,
                "account_balance": float(payload.get("account_balance", s.account_balance)),
            }
            if payload.get("trade_key"):
                row["trade_key"] = payload["trade_key"]
            sb.table("trading_signals").insert(row).execute()
            logger.info("API persisted signal (receipt_id=%s) for frontend visibility", receipt_id[:8])
        except Exception as e:
            logger.warning("API persist failed (non-fatal): %s", e)

    logger.info("Signal: %s | Mode: %s | Account: %s | Queue: %s", symbol, run_mode, account_id, queue_key)
    payload_str = json.dumps(payload)
    get_transport().enqueue(payload_str, queue_key=queue_key)
    return JSONResponse(status_code=200, content={"status": "queued", "account_id": account_id})


@app.post("/webhook/test")
async def webhook_test(
    request: Request,
    x_webhook_secret: str | None = Header(None),
):
    """
    Phase 12: Dry-run webhook endpoint for TradingView integration testing.

    Accepts the same JSON payload as POST /webhook but:
    - Does NOT push to Redis / MessageQueue
    - Does NOT write to trading_signals table
    - Does NOT execute any trades

    Returns a detailed diagnostic:
    - Parsed and validated fields
    - Which guard rails would fire (staleness, trading hours, RR ratio)
    - Computed lot size from risk engine
    - Any rejection reason

    Use this endpoint to test your TradingView alert format before enabling live trading.
    """
    validate_webhook_secret(request, x_webhook_secret)
    raw = await request.body()
    try:
        data = parse_body(raw)
    except HTTPException as e:
        return JSONResponse(status_code=400, content={"error": e.detail, "parsed": False})

    # Schema validation
    try:
        _validate_webhook_payload(data)
        schema_ok = True
        schema_error = None
    except RequestValidationError as e:
        schema_ok = False
        schema_error = str(e)

    result: dict[str, Any] = {
        "dry_run": True,
        "schema_valid": schema_ok,
        "schema_error": schema_error,
        "parsed_fields": {
            "symbol": data.get("symbol"),
            "side": data.get("side"),
            "entry": data.get("entry"),
            "sl": data.get("sl"),
            "tp": data.get("tp"),
            "size": data.get("size"),
            "rr_ratio": data.get("rr_ratio"),
            "bar_time": data.get("bar_time"),
            "zone_id": data.get("zone_id"),
            "signal_time": data.get("signal_time"),
            "run_mode": data.get("run_mode"),
            "event_type": data.get("event_type"),
            "action": data.get("action"),
        },
        "guards": {},
        "risk_engine": {},
        "would_execute": False,
    }

    if not schema_ok:
        return JSONResponse(status_code=200, content=result)

    # Guard rail simulation
    s = get_settings()
    guards: dict[str, Any] = {}

    # Staleness check
    try:
        from src.core.guard_rails.staleness_guard import StalenessGuard
        sg = StalenessGuard()
        stale_result = sg.check(data)
        guards["staleness"] = {
            "passed": stale_result is None,
            "reason": stale_result,
        }
    except Exception as exc:
        guards["staleness"] = {"passed": None, "error": str(exc)}

    # Trading hours check (local timezone, auto-DST)
    bar_time = data.get("bar_time")
    pine_start = getattr(s, "pine_trading_start_hour_local", getattr(s, "pine_trading_start_hour", 0))
    pine_end = getattr(s, "pine_trading_end_hour_local", getattr(s, "pine_trading_end_hour", 23))
    tz_name = getattr(s, "pine_trading_timezone", "UTC")
    if bar_time and (pine_start != 0 or pine_end != 23):
        try:
            import pytz as _pytz
            from datetime import datetime, timezone
            dt_utc = datetime.fromisoformat(str(bar_time).replace("Z", "+00:00"))
            if dt_utc.tzinfo is None:
                dt_utc = dt_utc.replace(tzinfo=timezone.utc)
            local_tz = _pytz.timezone(tz_name)
            dt_local = dt_utc.astimezone(local_tz)
            in_hours = pine_start <= dt_local.hour < pine_end
            guards["trading_hours"] = {
                "passed": in_hours,
                "bar_hour_local": dt_local.hour,
                "timezone": tz_name,
                "allowed_range": f"{pine_start}:00–{pine_end}:00 {tz_name}",
                "reason": None if in_hours else f"Outside trading hours: local_hour={dt_local.hour}",
            }
        except Exception as exc:
            guards["trading_hours"] = {"passed": None, "error": str(exc)}
    else:
        guards["trading_hours"] = {"passed": True, "note": "No bar_time or trading hours filter disabled"}

    # RR ratio check
    rr = data.get("rr_ratio")
    min_rr = getattr(s, "min_rr_ratio", 0.0)
    if rr is not None and min_rr > 0:
        rr_ok = float(rr) >= min_rr
        guards["rr_ratio"] = {
            "passed": rr_ok,
            "provided": float(rr),
            "minimum": min_rr,
            "reason": None if rr_ok else f"R:R {rr} < minimum {min_rr}",
        }
    else:
        guards["rr_ratio"] = {
            "passed": True,
            "note": f"min_rr_ratio={min_rr} (disabled=0)" if min_rr == 0 else f"rr_ratio not provided in payload",
        }

    result["guards"] = guards

    # Risk engine simulation
    try:
        from src.core.risk_engine import calculate_lot_size
        entry = float(data.get("entry") or 0)
        sl = float(data.get("sl") or 0)
        symbol = str(data.get("symbol", "")).upper()
        if entry and sl and symbol:
            lot_result = calculate_lot_size(
                account_balance=float(s.account_balance),
                risk_percent=float(s.risk_percent),
                entry=entry,
                sl=sl,
                symbol=symbol,
                risk_multiplier=1.0,
            )
            result["risk_engine"] = {
                "account_balance": s.account_balance,
                "risk_percent": s.risk_percent,
                "computed_lot_size": lot_result.get("final_lots") if isinstance(lot_result, dict) else str(lot_result),
                "sl_distance": abs(entry - sl),
                "note": "Size from Pine Script payload is used as-is when risk engine is not overriding",
            }
    except Exception as exc:
        result["risk_engine"] = {"error": str(exc)}

    # Overall pass/fail
    all_passed = all(
        g.get("passed") is True
        for g in guards.values()
        if g.get("passed") is not None
    )
    result["would_execute"] = schema_ok and all_passed
    result["rejection_reason"] = next(
        (g["reason"] for g in guards.values() if g.get("reason")),
        None,
    )

    return JSONResponse(status_code=200, content=result)




@app.post("/api/backtest/import")
async def backtest_import(
    request: Request,
    x_webhook_secret: str | None = Header(None),
):
    """
    Import historical backtest results from TradingView Strategy Tester (CSV/JSON export).

    Accepts a JSON array of trade records. Each record is saved to trading_signals
    with run_mode='BACKTEST' and status='backtest' — no MetaTrader orders are placed.

    Required header: X-Webhook-Secret (same secret as /webhook)

    Example body:
    [
      {"symbol": "EURUSD", "side": "buy", "entry": 1.18573, "sl": 1.17273,
       "tp": 1.20573, "size": 0.5, "signal_time": "2026-01-15T10:00:00Z",
       "outcome": "win", "pnl_usd": 125.00}
    ]
    """
    validate_webhook_secret(request, x_webhook_secret)

    try:
        body = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON body")

    if not isinstance(body, list):
        raise HTTPException(status_code=400, detail="Body must be a JSON array of trade records")

    if not body:
        return JSONResponse(status_code=200, content={"imported": 0})

    from src.adapters.supabase import get_supabase
    sb = get_supabase()
    rows = []
    for record in body:
        if not isinstance(record, dict):
            continue
        row = {
            "symbol": str(record.get("symbol", "UNKNOWN")).upper(),
            "side": str(record.get("side", "buy")).lower(),
            "size": float(record.get("size", 0.01)),
            "entry": float(record["entry"]) if record.get("entry") else None,
            "sl": float(record["sl"]) if record.get("sl") else None,
            "tp": float(record["tp"]) if record.get("tp") else None,
            "run_mode": "BACKTEST",
            "status": "backtest",
            "account_name": "Backtest",
            "notes": f"Imported via backtest export. outcome={record.get('outcome', 'unknown')}",
        }
        if record.get("signal_time"):
            row["signal_time"] = str(record["signal_time"])
        if record.get("pnl_usd") is not None:
            row["pnl_usd"] = float(record["pnl_usd"])
        if record.get("trade_key"):
            row["trade_key"] = str(record["trade_key"])
        rows.append(row)

    if not rows:
        return JSONResponse(status_code=200, content={"imported": 0})

    try:
        sb.table("trading_signals").insert(rows).execute()
        logger.info("Backtest import: inserted %d records", len(rows))
    except Exception as e:
        logger.error("Backtest import DB insert failed: %s", e)
        raise HTTPException(status_code=500, detail=f"DB insert failed: {e}")

    return JSONResponse(status_code=200, content={"imported": len(rows)})
