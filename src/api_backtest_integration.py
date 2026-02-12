"""
Backtest-Bot Integration API

Integrates backtest results with the live trading bot.
Allows validating strategies before deploying to live/paper trading.

Endpoints:
    POST /api/bot/validate-strategy - Validate strategy with backtest before going live
    GET /api/bot/backtest-history - Get historical backtest results
    POST /api/bot/compare-live-vs-backtest - Compare live performance vs backtest
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from backtesting import Backtest
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from config import get_settings
from src.services.backtest_engine import SndStrategy
from src.services.data_loader import MetaApiDataLoader

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/bot", tags=["bot-integration"])

settings = get_settings()


# ============================================================================
# Request/Response Models
# ============================================================================


class StrategyValidationRequest(BaseModel):
    """Validate strategy before deploying to live/paper trading."""

    symbol: str = Field(..., description="Trading symbol (e.g., EURUSD)")
    days_to_test: int = Field(default=90, ge=7, le=365, description="Days of historical data to test")
    timeframe: str = Field(default="5m", description="Candle timeframe")

    # Strategy parameters to validate
    risk_percent: float = Field(default=0.5, ge=0.1, le=5.0)
    min_rr_ratio: float = Field(default=2.0, ge=0.5, le=10.0)
    zone_lookback: int = Field(default=10, ge=5, le=50)
    stop_buffer_pips: float = Field(default=1.0, ge=0.0, le=10.0)

    # AI Guardian filters
    require_liquidity_sweep: bool = Field(default=False)
    reject_compression_arrival: bool = Field(default=True)
    require_structure_break: bool = Field(default=False)

    # Minimum performance thresholds
    min_trades: int = Field(default=10, description="Minimum trades required")
    min_win_rate: float = Field(default=40.0, description="Minimum win rate %")
    min_profit_factor: float = Field(default=1.2, description="Minimum profit factor")
    max_drawdown: float = Field(default=20.0, description="Maximum drawdown %")


class ValidationResult(BaseModel):
    """Strategy validation result."""

    symbol: str
    timeframe: str
    test_period_days: int
    total_trades: int
    win_rate: float
    total_return: float
    profit_factor: float
    max_drawdown: float
    sharpe_ratio: float

    # Validation status
    is_valid: bool = Field(..., description="True if all thresholds passed")
    failed_checks: List[str] = Field(default_factory=list, description="List of failed validation checks")

    # Recommendation
    recommendation: str = Field(..., description="Deploy, Adjust, or Reject")


class BacktestHistoryItem(BaseModel):
    """Single backtest history record."""

    id: int
    symbol: str
    timeframe: str
    start_date: str
    end_date: str
    total_trades: int
    win_rate: float
    total_return: float
    created_at: str


class LiveVsBacktestComparison(BaseModel):
    """Compare live trading performance vs backtest predictions."""

    symbol: str
    period_days: int

    # Backtest metrics (from historical validation)
    backtest_win_rate: float
    backtest_total_return: float
    backtest_sharpe_ratio: float

    # Live metrics (from actual trading)
    live_win_rate: float
    live_total_return: float
    live_sharpe_ratio: float

    # Delta
    win_rate_delta: float = Field(..., description="Live - Backtest win rate")
    return_delta: float = Field(..., description="Live - Backtest return")

    # Status
    is_aligned: bool = Field(..., description="True if live performance matches backtest within tolerance")
    warnings: List[str] = Field(default_factory=list)


# ============================================================================
# Helper Functions
# ============================================================================


def fetch_historical_data(symbol: str, days: int, timeframe: str) -> Any:
    """
    Fetch historical data from MetaApi for backtesting.

    Args:
        symbol: Trading symbol
        days: Number of days to fetch
        timeframe: Candle timeframe

    Returns:
        pandas DataFrame with OHLCV data

    Raises:
        ValueError: If MetaApi credentials missing
    """
    token = settings.meta_api_token
    account_id = settings.meta_api_account_id

    if not token or not account_id:
        raise ValueError(
            "MetaApi credentials not configured. "
            "Set META_API_TOKEN and META_API_ACCOUNT_ID in environment or settings."
        )

    # Calculate date range
    end_date = datetime(2024, 1, 31)  # Safe historical date
    start_date = end_date - timedelta(days=days)

    logger.info(
        "Fetching %d days of %s %s data from MetaApi (%s to %s)",
        days,
        symbol,
        timeframe,
        start_date.date(),
        end_date.date(),
    )

    loader = MetaApiDataLoader(token=token, account_id=account_id)
    df = loader.fetch_candles(
        symbol=symbol,
        start_time=start_date.strftime("%Y-%m-%d"),
        end_time=end_date.strftime("%Y-%m-%d"),
        timeframe=timeframe,
        limit=min(days * 288, 50000),  # 5m = 288 candles/day
    )

    if df.empty:
        raise ValueError(f"No historical data found for {symbol} {timeframe}")

    logger.info("Fetched %d candles", len(df))
    return df


def run_validation_backtest(df: Any, request: StrategyValidationRequest) -> Dict[str, Any]:
    """
    Run backtest with strategy parameters.

    Args:
        df: pandas DataFrame with OHLCV data
        request: StrategyValidationRequest with parameters

    Returns:
        Backtest stats dict
    """
    bt = Backtest(
        df,
        SndStrategy,
        cash=10000.0,  # Standard test capital
        commission=0.0002,
        margin=0.02,  # 50:1 leverage
        exclusive_orders=True,
    )

    stats = bt.run(
        risk_percent=request.risk_percent,
        min_rr_ratio=request.min_rr_ratio,
        zone_lookback=request.zone_lookback,
        stop_buffer_pips=request.stop_buffer_pips,
        require_liquidity_sweep=request.require_liquidity_sweep,
        reject_compression_arrival=request.reject_compression_arrival,
        require_structure_break=request.require_structure_break,
    )

    return stats


def validate_performance(stats: Dict[str, Any], request: StrategyValidationRequest) -> ValidationResult:
    """
    Validate backtest performance against thresholds.

    Args:
        stats: Backtest stats dict
        request: StrategyValidationRequest with thresholds

    Returns:
        ValidationResult with pass/fail status
    """
    total_trades = int(stats.get("# Trades", 0))
    win_rate = float(stats.get("Win Rate [%]", 0.0))
    total_return = float(stats.get("Return [%]", 0.0))
    profit_factor = float(stats.get("Profit Factor", 0.0))
    max_drawdown = abs(float(stats.get("Max. Drawdown [%]", 0.0)))
    sharpe_ratio = float(stats.get("Sharpe Ratio", 0.0))

    failed_checks: List[str] = []

    # Check thresholds
    if total_trades < request.min_trades:
        failed_checks.append(f"Insufficient trades: {total_trades} < {request.min_trades}")

    if win_rate < request.min_win_rate:
        failed_checks.append(f"Low win rate: {win_rate:.1f}% < {request.min_win_rate}%")

    if profit_factor < request.min_profit_factor:
        failed_checks.append(f"Low profit factor: {profit_factor:.2f} < {request.min_profit_factor}")

    if max_drawdown > request.max_drawdown:
        failed_checks.append(f"Excessive drawdown: {max_drawdown:.1f}% > {request.max_drawdown}%")

    # Determine recommendation
    is_valid = len(failed_checks) == 0

    if is_valid and total_return > 5.0 and sharpe_ratio > 1.0:
        recommendation = "✅ Deploy - Excellent backtest results"
    elif is_valid:
        recommendation = "⚠️ Deploy with caution - Meets minimum thresholds"
    elif len(failed_checks) == 1:
        recommendation = "🔧 Adjust parameters - Minor issues detected"
    else:
        recommendation = "❌ Reject - Strategy fails multiple checks"

    return ValidationResult(
        symbol=request.symbol,
        timeframe=request.timeframe,
        test_period_days=request.days_to_test,
        total_trades=total_trades,
        win_rate=win_rate,
        total_return=total_return,
        profit_factor=profit_factor,
        max_drawdown=max_drawdown,
        sharpe_ratio=sharpe_ratio,
        is_valid=is_valid,
        failed_checks=failed_checks,
        recommendation=recommendation,
    )


# ============================================================================
# API Routes
# ============================================================================


@router.post("/validate-strategy", response_model=ValidationResult)
async def validate_strategy(request: StrategyValidationRequest) -> ValidationResult:
    """
    Validate strategy with backtest before deploying to live/paper trading.

    This endpoint:
    1. Fetches historical data from MetaApi
    2. Runs backtest with your strategy parameters
    3. Validates performance against minimum thresholds
    4. Returns recommendation (Deploy, Adjust, Reject)

    Use this BEFORE activating a new strategy or changing parameters.

    Example:
        POST /api/bot/validate-strategy
        {
            "symbol": "EURUSD",
            "days_to_test": 90,
            "risk_percent": 0.5,
            "min_trades": 10,
            "min_win_rate": 50.0,
            "reject_compression_arrival": true
        }
    """
    try:
        # 1. Fetch historical data
        df = fetch_historical_data(request.symbol, request.days_to_test, request.timeframe)

        # 2. Run backtest
        stats = run_validation_backtest(df, request)

        # 3. Validate performance
        result = validate_performance(stats, request)

        logger.info(
            "Strategy validation complete: %s %s | %d trades | %.1f%% win rate | Recommendation: %s",
            request.symbol,
            request.timeframe,
            result.total_trades,
            result.win_rate,
            result.recommendation,
        )

        return result

    except Exception as exc:
        logger.error("Strategy validation failed: %s", exc)
        raise HTTPException(status_code=500, detail=f"Validation failed: {str(exc)}")


@router.get("/health")
async def health_check() -> Dict[str, str]:
    """Health check endpoint."""
    return {"status": "ok", "service": "bot-integration-api"}
