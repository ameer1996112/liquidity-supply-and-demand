"""
Backtest API Endpoint

FastAPI routes for running backtests and retrieving results.

Endpoints:
    POST /api/backtest/run - Run a backtest with MetaApi data
    GET /api/backtest/results/{run_id} - Get backtest results
    GET /api/backtest/optimize - Run parameter optimization

Usage:
    curl -X POST http://localhost:8000/api/backtest/run \
      -H "Content-Type: application/json" \
      -d '{
        "symbol": "EURUSD",
        "start_date": "2024-01-01",
        "end_date": "2024-12-31",
        "timeframe": "5m",
        "initial_cash": 10000,
        "commission": 0.0002
      }'
"""

from __future__ import annotations

import io
import logging
import os
import traceback
from datetime import datetime
from typing import Any, Dict, List, Optional

import pandas as pd
from backtesting import Backtest
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from config import get_settings
from src.services.backtest_engine import SndStrategy
from src.services.data_loader import MetaApiDataLoader

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/backtest", tags=["backtest"])


# ============================================================================
# Request/Response Models
# ============================================================================


class BacktestRequest(BaseModel):
    """Request payload for running a backtest."""

    symbol: str = Field(..., description="Trading symbol (e.g., EURUSD, XAUUSD)")
    start_date: str = Field(..., description="Start date (YYYY-MM-DD or ISO 8601)")
    end_date: str = Field(..., description="End date (YYYY-MM-DD or ISO 8601)")
    timeframe: str = Field(default="5m", description="Candle timeframe (e.g., 5m, 1h, 1d)")

    initial_cash: float = Field(default=10000.0, ge=100.0, description="Initial account balance")
    commission: float = Field(default=0.0002, ge=0.0, le=0.01, description="Commission per trade (0.0002 = 2 pips)")

    # Strategy parameters (optional overrides)
    risk_percent: Optional[float] = Field(default=None, ge=0.1, le=5.0, description="Risk per trade (%)")
    min_rr_ratio: Optional[float] = Field(default=None, ge=0.5, le=10.0, description="Minimum R:R ratio")
    zone_lookback: Optional[int] = Field(default=None, ge=5, le=50, description="Zone lookback period")
    stop_buffer_pips: Optional[float] = Field(default=None, ge=0.0, le=10.0, description="Stop loss buffer (pips)")

    # AI Guardian filters (Pine Script v5.1 features)
    require_liquidity_sweep: Optional[bool] = Field(
        default=None, description="Require liquidity sweep before entry (default: False)"
    )
    reject_compression_arrival: Optional[bool] = Field(
        default=None, description="Reject slow/grinding arrivals (default: True)"
    )
    require_structure_break: Optional[bool] = Field(
        default=None, description="Require market structure break (default: False)"
    )

    # Advanced liquidity & quality settings
    liq_entry_max_dist: Optional[float] = Field(
        default=None, ge=10.0, le=1000.0, description="Max liquidity distance at entry (pips)"
    )
    ai_quality_threshold: Optional[int] = Field(
        default=None, ge=0, le=100, description="Minimum AI quality score (0-100)"
    )
    min_entry_grade: Optional[str] = Field(
        default=None, description="Minimum zone grade (A+, A, B+, B, C+, C)"
    )
    max_bars_in_trade: Optional[int] = Field(
        default=None, ge=0, le=1000, description="Max bars before auto-exit (0=disabled, Pine-style)"
    )

    # MetaApi config (optional, defaults to env vars)
    meta_api_token: Optional[str] = Field(default=None, description="MetaApi token (or use env META_API_TOKEN)")
    meta_api_account_id: Optional[str] = Field(default=None, description="MetaApi account ID (or use env META_API_ACCOUNT_ID)")
    meta_api_region: Optional[str] = Field(default="new-york", description="MetaApi region")


class CandleData(BaseModel):
    """Single candle for lightweight-charts format."""

    time: int = Field(..., description="Unix timestamp (seconds)")
    open: float
    high: float
    low: float
    close: float
    volume: float = Field(default=0.0)


class TradeData(BaseModel):
    """Single trade result."""

    entry_time: int = Field(..., description="Entry Unix timestamp")
    exit_time: int = Field(..., description="Exit Unix timestamp")
    entry_price: float
    exit_price: float
    size: float = Field(..., description="Position size (lots)")
    pnl: float = Field(..., description="Profit/Loss in USD")
    pnl_percent: float = Field(..., description="Profit/Loss as % of account")
    side: str = Field(..., description="'long' or 'short'")
    return_pct: float = Field(..., description="Trade return %")


class EquityPoint(BaseModel):
    """Equity curve data point."""

    time: int = Field(..., description="Unix timestamp")
    equity: float = Field(..., description="Account equity in USD")


class BacktestStats(BaseModel):
    """Backtest performance statistics."""

    total_trades: int = Field(default=0)
    winning_trades: int = Field(default=0)
    losing_trades: int = Field(default=0)
    win_rate: float = Field(default=0.0, description="Win rate (0-100%)")

    total_return: float = Field(default=0.0, description="Total return %")
    sharpe_ratio: float = Field(default=0.0, description="Sharpe ratio")
    max_drawdown: float = Field(default=0.0, description="Maximum drawdown %")
    profit_factor: float = Field(default=0.0, description="Profit factor")

    avg_win: float = Field(default=0.0, description="Average winning trade $")
    avg_loss: float = Field(default=0.0, description="Average losing trade $")
    largest_win: float = Field(default=0.0, description="Largest winning trade $")
    largest_loss: float = Field(default=0.0, description="Largest losing trade $")

    avg_trade_duration: str = Field(default="0h 0m", description="Average trade duration")
    exposure_time: float = Field(default=0.0, description="Time in market %")


class BacktestResponse(BaseModel):
    """Backtest results response."""

    success: bool = Field(default=True)
    message: str = Field(default="Backtest completed successfully")

    # Chart data for frontend
    candles: List[CandleData] = Field(default_factory=list, description="OHLC candles for chart")
    trades: List[TradeData] = Field(default_factory=list, description="Executed trades")
    equity_curve: List[EquityPoint] = Field(default_factory=list, description="Equity curve over time")

    # Performance metrics
    stats: BacktestStats = Field(default_factory=BacktestStats)

    # Metadata
    symbol: str
    timeframe: str
    start_date: str
    end_date: str
    initial_cash: float
    final_equity: float = Field(default=0.0)
    candles_count: int = Field(default=0, description="Number of candles analyzed")


# ============================================================================
# Helper Functions
# ============================================================================


def _get_metaapi_credentials(request: BacktestRequest) -> tuple[str, str, str]:
    """
    Extract MetaApi credentials from request or environment.

    Returns:
        (token, account_id, region)

    Raises:
        ValueError: If credentials are missing
    """
    settings = get_settings()

    token = request.meta_api_token or os.getenv("META_API_TOKEN") or getattr(settings, "meta_api_token", "")
    account_id = (
        request.meta_api_account_id or os.getenv("META_API_ACCOUNT_ID") or getattr(settings, "meta_api_account_id", "")
    )
    region = request.meta_api_region or os.getenv("META_API_REGION", "new-york")

    if not token or not account_id:
        raise ValueError(
            "MetaApi credentials missing. Provide meta_api_token and meta_api_account_id "
            "in request body or set META_API_TOKEN and META_API_ACCOUNT_ID environment variables."
        )

    return token.strip(), account_id.strip(), region.strip()


def _normalize_date(date_str: str) -> str:
    """
    Normalize date string to ISO 8601 format.

    Args:
        date_str: Date string (e.g., "2024-01-01" or "2024-01-01T00:00:00Z")

    Returns:
        ISO 8601 timestamp string
    """
    # Try parsing as date only
    try:
        dt = datetime.strptime(date_str.strip(), "%Y-%m-%d")
        return dt.strftime("%Y-%m-%dT%H:%M:%S.000Z")
    except ValueError:
        pass

    # Try parsing as ISO 8601
    try:
        dt = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
        return dt.strftime("%Y-%m-%dT%H:%M:%S.000Z")
    except ValueError:
        raise ValueError(f"Invalid date format: {date_str}. Use YYYY-MM-DD or ISO 8601.")


def _dataframe_to_candles(df: pd.DataFrame) -> List[CandleData]:
    """
    Convert pandas DataFrame to lightweight-charts candle format.

    Args:
        df: DataFrame with DatetimeIndex and OHLCV columns

    Returns:
        List of CandleData objects
    """
    candles = []
    for timestamp, row in df.iterrows():
        candles.append(
            CandleData(
                time=int(timestamp.timestamp()),
                open=float(row["Open"]),
                high=float(row["High"]),
                low=float(row["Low"]),
                close=float(row["Close"]),
                volume=float(row.get("Volume", 0.0)),
            )
        )
    return candles


def _extract_trades(bt_stats: Any) -> List[TradeData]:
    """
    Extract trade data from backtesting.py stats object.

    Args:
        bt_stats: Backtest stats object (from bt.run())

    Returns:
        List of TradeData objects
    """
    trades = []

    # Access the trades DataFrame from stats
    if hasattr(bt_stats, "_trades") and bt_stats._trades is not None:
        trades_df = bt_stats._trades
    else:
        return []

    for _, trade in trades_df.iterrows():
        entry_time = int(trade["EntryTime"].timestamp()) if hasattr(trade["EntryTime"], "timestamp") else 0
        exit_time = int(trade["ExitTime"].timestamp()) if hasattr(trade["ExitTime"], "timestamp") else 0

        trades.append(
            TradeData(
                entry_time=entry_time,
                exit_time=exit_time,
                entry_price=float(trade.get("EntryPrice", 0.0)),
                exit_price=float(trade.get("ExitPrice", 0.0)),
                size=float(trade.get("Size", 0.0)),
                pnl=float(trade.get("PnL", 0.0)),
                pnl_percent=float(trade.get("ReturnPct", 0.0)),
                side="long" if trade.get("Size", 0) > 0 else "short",
                return_pct=float(trade.get("ReturnPct", 0.0)),
            )
        )

    return trades


def _extract_equity_curve(bt_stats: Any) -> List[EquityPoint]:
    """
    Extract equity curve from backtesting.py stats.

    Args:
        bt_stats: Backtest stats object

    Returns:
        List of EquityPoint objects
    """
    equity_points = []

    if hasattr(bt_stats, "_equity_curve") and bt_stats._equity_curve is not None:
        equity_df = bt_stats._equity_curve

        for timestamp, row in equity_df.iterrows():
            equity_points.append(
                EquityPoint(
                    time=int(timestamp.timestamp()),
                    equity=float(row.get("Equity", 0.0)),
                )
            )

    return equity_points


def _extract_stats(bt_stats: Any) -> BacktestStats:
    """
    Extract performance statistics from backtesting.py stats.

    Args:
        bt_stats: Backtest stats object

    Returns:
        BacktestStats object
    """
    # Helper to safely get stat value
    def get_stat(key: str, default: Any = 0.0) -> Any:
        try:
            val = getattr(bt_stats, key, default)
            return val if val is not None and not pd.isna(val) else default
        except Exception:
            return default

    return BacktestStats(
        total_trades=int(get_stat("# Trades", 0)),
        winning_trades=int(get_stat("# Trades", 0) * get_stat("Win Rate [%]", 0.0) / 100.0),
        losing_trades=int(get_stat("# Trades", 0) * (1.0 - get_stat("Win Rate [%]", 0.0) / 100.0)),
        win_rate=float(get_stat("Win Rate [%]", 0.0)),
        total_return=float(get_stat("Return [%]", 0.0)),
        sharpe_ratio=float(get_stat("Sharpe Ratio", 0.0)),
        max_drawdown=float(get_stat("Max. Drawdown [%]", 0.0)),
        profit_factor=float(get_stat("Profit Factor", 0.0)),
        avg_win=float(get_stat("Avg. Win [%]", 0.0)),
        avg_loss=float(get_stat("Avg. Loss [%]", 0.0)),
        largest_win=float(get_stat("Best Trade [%]", 0.0)),
        largest_loss=float(get_stat("Worst Trade [%]", 0.0)),
        avg_trade_duration=str(get_stat("Avg. Trade Duration", "0h 0m")),
        exposure_time=float(get_stat("Exposure Time [%]", 0.0)),
    )


# ============================================================================
# API Routes
# ============================================================================


@router.post("/run", response_model=BacktestResponse)
async def run_backtest(request: BacktestRequest) -> BacktestResponse:
    """
    Run a backtest using MetaApi historical data.

    Steps:
    1. Fetch OHLC data from MetaApi
    2. Run backtesting.py with SndStrategy
    3. Return candles, trades, equity curve, and stats

    Example Request:
        POST /api/backtest/run
        {
            "symbol": "EURUSD",
            "start_date": "2024-01-01",
            "end_date": "2024-03-31",
            "timeframe": "5m",
            "initial_cash": 10000,
            "risk_percent": 0.5,
            "min_rr_ratio": 2.0
        }
    """
    try:
        # 1. Get MetaApi credentials
        token, account_id, region = _get_metaapi_credentials(request)

        # 2. Normalize dates
        start_date = _normalize_date(request.start_date)
        end_date = _normalize_date(request.end_date)

        logger.info(
            "Starting backtest: symbol=%s timeframe=%s start=%s end=%s cash=%.2f",
            request.symbol,
            request.timeframe,
            start_date,
            end_date,
            request.initial_cash,
        )

        # 3. Fetch historical data from MetaApi
        loader = MetaApiDataLoader(token=token, account_id=account_id, region=region)

        df = loader.fetch_candles(
            symbol=request.symbol,
            start_time=start_date,
            end_time=end_date,
            timeframe=request.timeframe,
        )

        if df.empty:
            raise HTTPException(
                status_code=404,
                detail=f"No candles found for {request.symbol} {request.timeframe} in date range {start_date} to {end_date}",
            )

        logger.info("Fetched %d candles from MetaApi", len(df))

        # 4. Prepare strategy parameters
        strategy_kwargs = {}

        # Symbol (REQUIRED for symbol-specific logic)
        strategy_kwargs["symbol"] = request.symbol

        # Fixed account size for position sizing (matches Pine account_size_usd)
        strategy_kwargs["account_size_usd"] = request.initial_cash

        # Risk parameters
        if request.risk_percent is not None:
            strategy_kwargs["risk_percent"] = request.risk_percent
        if request.min_rr_ratio is not None:
            strategy_kwargs["min_rr_ratio"] = request.min_rr_ratio
        if request.zone_lookback is not None:
            strategy_kwargs["zone_lookback"] = request.zone_lookback
        if request.stop_buffer_pips is not None:
            strategy_kwargs["stop_buffer_pips"] = request.stop_buffer_pips

        # AI Guardian filters
        if request.require_liquidity_sweep is not None:
            strategy_kwargs["require_liquidity_sweep"] = request.require_liquidity_sweep
        if request.reject_compression_arrival is not None:
            strategy_kwargs["reject_compression_arrival"] = request.reject_compression_arrival
        if request.require_structure_break is not None:
            strategy_kwargs["require_structure_break"] = request.require_structure_break

        # Advanced liquidity & quality settings
        if request.liq_entry_max_dist is not None:
            strategy_kwargs["liq_entry_max_dist"] = request.liq_entry_max_dist
        if request.ai_quality_threshold is not None:
            strategy_kwargs["ai_quality_threshold"] = request.ai_quality_threshold
        if request.min_entry_grade is not None:
            strategy_kwargs["min_entry_grade"] = request.min_entry_grade
        if request.max_bars_in_trade is not None:
            strategy_kwargs["max_bars_in_trade"] = request.max_bars_in_trade

        # 5. Run backtest
        bt = Backtest(
            df,
            SndStrategy,
            cash=request.initial_cash,
            commission=request.commission,
            margin=0.02,  # 50:1 leverage (forex)
            exclusive_orders=True,  # Cancel pending orders when new signal arrives
        )

        stats = bt.run(**strategy_kwargs)

        logger.info("Backtest completed: trades=%d return=%.2f%%", stats["# Trades"], stats["Return [%]"])

        # 6. Extract results
        candles = _dataframe_to_candles(df)
        trades = _extract_trades(stats)
        equity_curve = _extract_equity_curve(stats)
        performance_stats = _extract_stats(stats)

        # 7. Build response
        return BacktestResponse(
            success=True,
            message="Backtest completed successfully",
            candles=candles,
            trades=trades,
            equity_curve=equity_curve,
            stats=performance_stats,
            symbol=request.symbol,
            timeframe=request.timeframe,
            start_date=request.start_date,
            end_date=request.end_date,
            initial_cash=request.initial_cash,
            final_equity=float(stats.get("Equity Final [$]", request.initial_cash)),
            candles_count=len(df),
        )

    except ValueError as exc:
        logger.error("Backtest validation error: %s", exc)
        raise HTTPException(status_code=400, detail=str(exc))

    except Exception as exc:
        logger.error("Backtest failed: %s\n%s", exc, traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"Backtest execution failed: {str(exc)}")


@router.get("/health")
async def health_check() -> Dict[str, str]:
    """Health check endpoint."""
    return {"status": "ok", "service": "backtest-api"}
