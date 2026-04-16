from __future__ import annotations

import logging

from fastapi import FastAPI, Query

from src.local_chart_provider_service import fetch_live_chart_context


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("local_chart_provider")

app = FastAPI(title="Local TradingView MCP Provider", version="0.1.0")


@app.get("/chart-context")
async def get_chart_context(
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
    return payload
