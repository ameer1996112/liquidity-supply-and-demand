"""Market data proxy — avoids CORS by fetching Yahoo Finance server-side."""

import logging
from typing import Any

import yfinance as yf
from fastapi import APIRouter, HTTPException, Query

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/market", tags=["market"])


@router.get("/chart/{symbol}")
async def proxy_yahoo_chart(
    symbol: str,
    interval: str = Query("1d", description="Chart interval"),
    range_: str = Query("1d", alias="range", description="Time range"),
) -> dict[str, Any]:
    """
    Proxy Yahoo Finance chart data to avoid CORS in the browser.
    Returns price/change data for the given symbol.
    """
    try:
        ticker = yf.Ticker(symbol)
        info = ticker.fast_info
        price = getattr(info, "last_price", None)
        prev_close = getattr(info, "previous_close", None)
        change = (price - prev_close) if price is not None and prev_close is not None else None
        change_pct = (change / prev_close * 100) if prev_close and change is not None else None
        return {
            "symbol": symbol,
            "price": price,
            "change": change,
            "changePct": change_pct,
        }
    except Exception as e:
        logger.warning("yfinance chart error for %s: %s", symbol, e)
        raise HTTPException(status_code=502, detail="Market data unavailable")


@router.get("/prices")
async def batch_prices(
    symbols: str = Query(..., description="Comma-separated Yahoo symbols (e.g. GC=F,EURUSD=X)"),
    interval: str = Query("1d"),
    range_: str = Query("1d", alias="range"),
) -> list[dict[str, Any]]:
    """
    Batch-fetch price data for multiple symbols. Returns a list of
    { symbol, price, change, changePct } for each symbol.
    """
    sym_list = [s.strip() for s in symbols.split(",") if s.strip()]
    if not sym_list:
        raise HTTPException(status_code=400, detail="At least one symbol required")

    results = []
    for sym in sym_list:
        try:
            ticker = yf.Ticker(sym)
            info = ticker.fast_info
            price = getattr(info, "last_price", None)
            prev_close = getattr(info, "previous_close", None)
            change = (price - prev_close) if price is not None and prev_close is not None else None
            change_pct = (
                (change / prev_close * 100) if prev_close and prev_close != 0 and change is not None else None
            )
            results.append({
                "symbol": sym,
                "yahooId": sym,
                "price": price,
                "change": change,
                "changePct": change_pct,
            })
        except Exception as e:
            logger.debug("Failed to fetch %s: %s", sym, e)
            results.append({
                "symbol": sym,
                "yahooId": sym,
                "price": None,
                "change": None,
                "changePct": None,
            })

    return results
