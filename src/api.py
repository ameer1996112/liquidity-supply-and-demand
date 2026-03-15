"""
Signal Receiver (API) - Validate -> Push to Redis -> 200.
No database, no business logic, no trade execution.
"""

import json
import logging
import os
import re
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
from config.logging_config import configure_logging
from src.adapters.redis_queue import get_redis
from src.core.transport import get_transport
from src.core.signal import EntryWebhookPayload, ExitWebhookPayload, validate_webhook_payload

configure_logging(level=logging.INFO, format_str="%(asctime)s - %(levelname)s - %(message)s")
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
from src.api_traces import router as traces_router       # Sprint 2.1: latency traces
from src.api_accounts import router as accounts_router   # Sprint 2.3: multi-account
from src.api_ai_runs import router as ai_runs_router     # Sprint 3.3: debate ai_run
from src.api_backtests import router as backtests_router # Sprint 4.1: Backtest Lab
from src.api_strategies import router as strategies_router # Sprint 4.4: Strategy configs
from src.api_webhook_read import router as webhook_read_router  # E2E: signals/recent, trades/open, stats/summary
from src.api_copilot import router as copilot_router           # AI Copilot: natural language queries
from src.api_market import router as market_router             # Market data proxy (Yahoo Finance CORS bypass)
from src.api_funding import router as funding_router           # Funding: daily PnL and stats for prop firm UI
from src.api_board import router as board_router               # Board: Kanban ticket management for AI agents

@asynccontextmanager
async def _lifespan(app: FastAPI):  # noqa: ARG001
    """Replaces deprecated @app.on_event('startup'/'shutdown')."""
    # ── STARTUP ──────────────────────────────────────────────────────────────
    _fail_fast_config()
    yield
    # ── SHUTDOWN ─────────────────────────────────────────────────────────────
    _shutdown_worker()


app = FastAPI(title="Trading Webhook API", version="1.0.0", lifespan=_lifespan)

# Attach rate limiter state and error handler
if _RATE_LIMIT_AVAILABLE and _limiter is not None:
    app.state.limiter = _limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)  # type: ignore[arg-type]

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
app.include_router(traces_router)     # Sprint 2.1: pipeline latency traces
app.include_router(accounts_router)  # Sprint 2.3: multi-account routing
app.include_router(ai_runs_router)   # Sprint 3.3: debate ai_run
app.include_router(backtests_router) # Sprint 4.1: Backtest Lab
app.include_router(strategies_router) # Sprint 4.4: Strategy-as-data configs
app.include_router(webhook_read_router)  # E2E: /api/v1/webhook/signals/recent, trades/open, stats/summary
app.include_router(copilot_router)       # AI Copilot: /api/copilot/chat
app.include_router(market_router)         # Market data proxy: /api/market/*
app.include_router(funding_router)        # Funding: /api/v1/funding/daily-pnl, stats
app.include_router(board_router)          # Board: /api/v1/board/tickets, agent-update
app.add_middleware(
    CORSMiddleware,
    allow_origins=_build_cors_origins(),
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS", "PATCH"],
    allow_headers=["*"],
    expose_headers=["*"],
    max_age=600,
)


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
    from fastapi import WebSocket as _WS
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

    # We ignore the explicit payload "run_mode" because the Pine Script
    # (SND_Utils) hardcodes `"run_mode":"PAPER"` in its webhook payload.
    # Instead, we rely entirely on 'force_paper' for manual overrides.
    if payload.get("force_paper"):
        payload["run_mode"] = "PAPER"
        payload["_signal_source"] = "manual"
        logger.info("Run-mode: PAPER (force_paper=true in payload)")
    else:
        # Default: this endpoint is protected by webhook secret and is called by
        # TradingView in production → LIVE.
        payload["run_mode"] = "LIVE"
        payload["_signal_source"] = "tradingview" if is_tradingview else "webhook"
        logger.info("Run-mode: LIVE (default, ignoring Pine payload, UA=%s)", user_agent[:60] or "<empty>")

    symbol = payload.get("symbol", payload.get("zone_id", "N/A"))
    run_mode = payload["run_mode"]


    # Account routing: resolve target account + queue key, stamp onto payload
    # before serialisation so the worker can read them without extra lookups.
    from src.core.account_router import AccountRouter as _AccountRouter
    _router = _AccountRouter()
    account_id = _router.resolve_account_id(payload)
    payload["_account_id"] = account_id
    queue_key = _router.queue_key_for(account_id)

    # Persist at API level so signal appears in frontend even if worker never processes it (entry only)
    event_type = (payload.get("event_type") or "").strip().lower()
    action = (str(payload.get("action") or "")).strip().lower()
    is_exit = event_type == "exit" or action == "exit"
    receipt_id = str(uuid.uuid4())
    payload["_webhook_receipt_id"] = receipt_id
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
    logger.info("Queued payload (len=%d)", len(payload_str))
    return JSONResponse(status_code=200, content={"status": "queued", "account_id": account_id})


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
