from __future__ import annotations

import logging
from pathlib import Path

from fastapi import FastAPI, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from src.local_chart_provider_service import (
    fetch_live_chart_context,
    get_chart_provider_compatibility_status,
)


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("local_chart_provider")

ARTIFACTS_DIR = Path(__file__).resolve().parents[1] / "mcp" / "tradingview-mcp" / "screenshots"
ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)

app = FastAPI(title="Local TradingView MCP Provider", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_methods=["GET", "OPTIONS"],
    allow_headers=["*"],
)
app.mount("/provider-artifacts", StaticFiles(directory=ARTIFACTS_DIR), name="provider-artifacts")


def _attach_focus_image_url(payload: dict, request: Request) -> dict:
    setup_evidence = payload.get("setup_evidence")
    if not isinstance(setup_evidence, dict):
        return payload

    focus_image = setup_evidence.get("focus_image")
    if not isinstance(focus_image, dict):
        return payload

    image_path = focus_image.get("path")
    if not isinstance(image_path, str) or not image_path:
        return payload

    filename = Path(image_path).name
    focus_image["url"] = str(request.base_url).rstrip("/") + f"/provider-artifacts/{filename}"
    return payload


@app.get("/chart-context")
async def get_chart_context(
    request: Request,
    symbol: str = Query(...),
    timeframe: str = Query(...),
) -> dict:
    logger.info("chart-context request symbol=%s timeframe=%s", symbol, timeframe)
    payload = fetch_live_chart_context(symbol, timeframe)
    logger.info(
        "chart-context response actual_symbol=%s actual_timeframe=%s reason=%s",
        payload.get("symbol"),
        payload.get("timeframe"),
        payload.get("reason", ""),
    )
    return _attach_focus_image_url(payload, request)


@app.get("/health/compatibility")
async def get_compatibility_health() -> dict:
    payload = get_chart_provider_compatibility_status()
    logger.info(
        "compatibility-health status=%s version=%s enabled=%s",
        payload.get("status"),
        payload.get("tradingview_version"),
        payload.get("chart_context_enabled"),
    )
    return payload
