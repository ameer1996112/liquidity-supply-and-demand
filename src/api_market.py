"""Market data proxy — avoids CORS by fetching Yahoo Finance server-side."""

import logging
from typing import Any

import requests
from fastapi import APIRouter, HTTPException, Query

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/market", tags=["market"])

YAHOO_CHART_URL = "https://query1.finance.yahoo.com/v8/finance/chart"


@router.get("/chart/{symbol}")
async def proxy_yahoo_chart(
    symbol: str,
    interval: str = Query("1d", description="Chart interval"),
    range_: str = Query("1d", alias="range", description="Time range"),
) -> dict[str, Any]:
    """
    Proxy Yahoo Finance chart API to avoid CORS in the browser.
    Returns the raw chart JSON for the given symbol.
    """
    url = f"{YAHOO_CHART_URL}/{symbol}"
    params = {"interval": interval, "range": range_}
    try:
        resp = requests.get(url, params=params, timeout=5)
        resp.raise_for_status()
        return resp.json()
    except requests.exceptions.Timeout:
        logger.warning("Yahoo Finance chart timeout for %s", symbol)
        raise HTTPException(status_code=504, detail="Market data timeout")
    except requests.exceptions.RequestException as e:
        logger.warning("Yahoo Finance chart error for %s: %s", symbol, e)
        raise HTTPException(status_code=502, detail="Market data unavailable")


@router.get("/prices")
async def batch_prices(
    symbols: str = Query(..., description="Comma-separated Yahoo symbols (e.g. GC=F,EURUSD=X)"),
    interval: str = Query("1d"),
    range_: str = Query("1d", alias="range"),
) -> list[dict[str, Any]]:
    """
    Batch-fetch chart data for multiple symbols. Returns a list of
    { symbol, yahooId, price, change, changePct } for each symbol.
    """
    sym_list = [s.strip() for s in symbols.split(",") if s.strip()]
    if not sym_list:
        raise HTTPException(status_code=400, detail="At least one symbol required")

    results = []
    for sym in sym_list:
        try:
            resp = requests.get(
                f"{YAHOO_CHART_URL}/{sym}",
                params={"interval": interval, "range": range_},
                timeout=5,
            )
            resp.raise_for_status()
            json_data = resp.json()
            meta = json_data.get("chart", {}).get("result", [{}])[0].get("meta", {})
            price = meta.get("regularMarketPrice")
            prev = meta.get("previousClose")
            change = (price or 0) - (prev or 0) if price is not None else None
            change_pct = (
                (change / prev * 100) if prev and prev != 0 and change is not None else None
            )
            results.append({
                "symbol": sym,
                "yahooId": sym,
                "price": price,
                "change": change,
                "changePct": change_pct,
            })
        except (requests.exceptions.RequestException, IndexError, KeyError) as e:
            logger.debug("Failed to fetch %s: %s", sym, e)
            results.append({
                "symbol": sym,
                "yahooId": sym,
                "price": None,
                "change": None,
                "changePct": None,
            })

    return results
