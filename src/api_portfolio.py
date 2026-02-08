"""
Portfolio Risk Management API

Endpoints for portfolio-level risk metrics, VaR, correlation analysis,
sector exposure, and optimization recommendations.
"""

import logging
from typing import Dict, List, Optional
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from config import get_settings
from src.adapters import supabase
from src.services.portfolio_analyzer import (
    PortfolioAnalyzer,
    Position,
    PortfolioRiskMetrics,
)
from src.services.historical_returns import HistoricalReturnsService
from src.services.position_optimizer import PositionOptimizer
from src.core.guard_rails.sector_guard import SectorExposureGuard
from src.adapters.market_data import get_current_price

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/portfolio", tags=["Portfolio Risk"])

# Initialize services
returns_service = HistoricalReturnsService()
portfolio_analyzer = PortfolioAnalyzer(returns_service)
position_optimizer = PositionOptimizer()
sector_guard = SectorExposureGuard()

# ── Response Models ──────────────────────────────────────────

class PortfolioRiskDashboard(BaseModel):
    """Portfolio risk dashboard metrics."""
    var_95_1d: float
    var_99_1d: float
    cvar_95: float
    portfolio_volatility: float
    total_exposure: float
    net_exposure: float
    position_count: int
    correlation_avg: float
    max_correlation: float
    var_limit_usd: float
    var_utilization_pct: float
    positions: List[Dict]


class CorrelationMatrixResponse(BaseModel):
    """Correlation matrix with symbol labels."""
    symbols: List[str]
    matrix: List[List[float]]


class RiskContributionItem(BaseModel):
    """Risk contribution of a single position."""
    symbol: str
    var_contribution_usd: float
    var_contribution_pct: float


class SectorExposureItem(BaseModel):
    """Sector exposure details."""
    sector: str
    exposure_usd: float
    exposure_pct: float
    limit_pct: float
    utilization: float
    status: str  # "ok", "warning", "exceeded"


# ── Helper Functions ─────────────────────────────────────────

def get_active_positions_from_db() -> List[Position]:
    """Fetch active positions from database and convert to Position objects."""
    if not supabase.supabase:
        supabase.init_supabase()

    try:
        response = (
            supabase.supabase.table("trading_signals")
            .select("symbol, side, entry, size, status, pnl")
            .in_("status", ["active", "executed"])
            .execute()
        )

        positions = []

        for row in response.data:
            symbol = row.get("symbol", "")
            entry = float(row.get("entry", 0.0))
            size = float(row.get("size", 0.0))
            pnl = float(row.get("pnl", 0.0))

            # Get current price
            current_price = get_current_price(symbol)
            if current_price is None:
                current_price = entry

            # Calculate notional value
            notional = abs(size) * 100_000 * current_price  # Simplified for forex

            positions.append(
                Position(
                    symbol=symbol,
                    side=row.get("side", "long"),
                    entry_price=entry,
                    current_price=current_price,
                    size=size,
                    pnl_usd=pnl,
                    notional_value=notional,
                )
            )

        return positions

    except Exception as e:
        logger.error(f"Failed to fetch active positions: {e}")
        return []


def get_current_equity() -> float:
    """Get current account equity."""
    settings = get_settings()
    return settings.account_balance  # TODO: Fetch live equity


# ── API Endpoints ────────────────────────────────────────────

@router.get("/risk-dashboard", response_model=PortfolioRiskDashboard)
async def get_risk_dashboard(
    lookback_days: int = Query(default=30, ge=1, le=90, description="Historical lookback period")
):
    """
    Get comprehensive portfolio risk dashboard metrics.

    Returns VaR, CVaR, volatility, correlations, and position details.
    """
    try:
        positions = get_active_positions_from_db()
        current_equity = get_current_equity()
        settings = get_settings()

        # Calculate max VaR limit
        var_limit_usd = min(
            settings.portfolio_max_var_usd,
            current_equity * (settings.portfolio_max_var_pct / 100.0),
        )

        # Get portfolio metrics
        metrics = portfolio_analyzer.get_portfolio_metrics(positions, lookback_days)

        if metrics is None:
            raise HTTPException(status_code=500, detail="Failed to calculate portfolio metrics")

        # Calculate VaR utilization
        var_utilization = (abs(metrics.var_95_1d) / var_limit_usd * 100) if var_limit_usd > 0 else 0.0

        # Build position details
        position_details = [
            {
                "symbol": pos.symbol,
                "side": pos.side,
                "size": pos.size,
                "entry_price": pos.entry_price,
                "current_price": pos.current_price,
                "pnl_usd": pos.pnl_usd,
                "notional_value": pos.notional_value,
            }
            for pos in positions
        ]

        dashboard_response = PortfolioRiskDashboard(
            var_95_1d=metrics.var_95_1d,
            var_99_1d=metrics.var_99_1d,
            cvar_95=metrics.cvar_95,
            portfolio_volatility=metrics.portfolio_volatility,
            total_exposure=metrics.total_exposure,
            net_exposure=metrics.net_exposure,
            position_count=metrics.position_count,
            correlation_avg=metrics.correlation_avg,
            max_correlation=metrics.max_correlation,
            var_limit_usd=var_limit_usd,
            var_utilization_pct=var_utilization,
            positions=position_details,
        )

        # Save portfolio snapshot for historical analysis
        try:
            from src.adapters.supabase_client import get_supabase_client
            supabase = get_supabase_client()
            if supabase:
                portfolio_analyzer.save_snapshot(
                    supabase_client=supabase,
                    positions=positions,
                    metrics=metrics,
                    run_mode=settings.run_mode,
                    account_name=None,  # Aggregated portfolio snapshot
                    account_balance=current_equity,
                    daily_pnl=None,  # Could be calculated from positions
                    var_limit_usd=var_limit_usd,
                    var_utilization_pct=var_utilization,
                    lookback_days=lookback_days,
                )
        except Exception as snapshot_err:
            # Don't fail the request if snapshot save fails
            logger.warning(f"Failed to save portfolio snapshot: {snapshot_err}")

        return dashboard_response

    except Exception as e:
        logger.error(f"Error in risk dashboard: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/correlation-matrix", response_model=CorrelationMatrixResponse)
async def get_correlation_matrix(
    lookback_days: int = Query(default=30, ge=1, le=90, description="Historical lookback period")
):
    """
    Get correlation matrix for active positions.

    Returns NxN correlation matrix with symbol labels.
    """
    try:
        positions = get_active_positions_from_db()

        if not positions:
            return CorrelationMatrixResponse(symbols=[], matrix=[])

        symbols = [pos.symbol for pos in positions]
        corr_matrix = portfolio_analyzer.get_correlation_matrix(positions, lookback_days)

        if corr_matrix is None:
            raise HTTPException(status_code=500, detail="Failed to calculate correlation matrix")

        # Convert numpy array to list of lists
        matrix_list = corr_matrix.tolist()

        return CorrelationMatrixResponse(
            symbols=symbols,
            matrix=matrix_list,
        )

    except Exception as e:
        logger.error(f"Error in correlation matrix: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/risk-contribution", response_model=List[RiskContributionItem])
async def get_risk_contribution(
    lookback_days: int = Query(default=30, ge=1, le=90, description="Historical lookback period")
):
    """
    Get risk contribution analysis for each position.

    Shows how much each position contributes to portfolio VaR.
    """
    try:
        positions = get_active_positions_from_db()

        if not positions:
            return []

        # Calculate portfolio VaR
        portfolio_var = portfolio_analyzer.calculate_var(positions, lookback_days=lookback_days)

        if portfolio_var is None:
            raise HTTPException(status_code=500, detail="Failed to calculate VaR")

        # Calculate risk contributions
        contributions = portfolio_analyzer.compute_risk_contribution(
            positions,
            portfolio_var,
            lookback_days,
        )

        return [
            RiskContributionItem(
                symbol=contrib.symbol,
                var_contribution_usd=contrib.var_contribution_usd,
                var_contribution_pct=contrib.var_contribution_pct,
            )
            for contrib in contributions
        ]

    except Exception as e:
        logger.error(f"Error in risk contribution: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/sector-exposure", response_model=List[SectorExposureItem])
async def get_sector_exposure():
    """
    Get sector exposure breakdown.

    Shows exposure by sector with limits and utilization.
    """
    try:
        positions = get_active_positions_from_db()
        current_equity = get_current_equity()
        settings = get_settings()

        if not positions:
            return []

        # Build position dicts
        position_dicts = [
            {"symbol": pos.symbol, "notional_value": pos.notional_value}
            for pos in positions
        ]

        # Sector limits
        sector_limits = {
            "forex_majors": settings.sector_limit_forex_majors,
            "forex_jpy": settings.sector_limit_forex_jpy,
            "forex_eur": settings.sector_limit_forex_eur,
            "forex_gbp": settings.sector_limit_forex_gbp,
            "indices_us": settings.sector_limit_indices_us,
            "indices_eu": settings.sector_limit_indices_eu,
            "indices_asia": settings.sector_limit_indices_asia,
            "precious_metals": settings.sector_limit_precious_metals,
            "commodities": settings.sector_limit_commodities,
            "crypto": settings.sector_limit_crypto,
        }

        # Get utilization
        utilization = sector_guard.get_sector_utilization(
            position_dicts,
            sector_limits,
            current_equity,
        )

        # Build response
        result = []
        for sector, data in utilization.items():
            util_pct = data["utilization"]
            status = "ok"
            if util_pct >= 100:
                status = "exceeded"
            elif util_pct >= 80:
                status = "warning"

            result.append(
                SectorExposureItem(
                    sector=sector,
                    exposure_usd=data["exposure_usd"],
                    exposure_pct=data["exposure_pct"],
                    limit_pct=data["limit_pct"],
                    utilization=util_pct,
                    status=status,
                )
            )

        # Sort by utilization descending
        result.sort(key=lambda x: x.utilization, reverse=True)

        return result

    except Exception as e:
        logger.error(f"Error in sector exposure: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/settings")
async def get_portfolio_settings():
    """
    Get current portfolio risk management settings.

    Returns VaR limits, sector limits, Kelly settings, etc.
    """
    try:
        settings = get_settings()

        return {
            "portfolio_var_enabled": settings.portfolio_var_enabled,
            "portfolio_max_var_usd": settings.portfolio_max_var_usd,
            "portfolio_max_var_pct": settings.portfolio_max_var_pct,
            "kelly_enabled": settings.kelly_enabled,
            "kelly_fraction": settings.kelly_fraction,
            "correlation_matrix_enabled": settings.correlation_matrix_enabled,
            "max_avg_portfolio_correlation": settings.max_avg_portfolio_correlation,
            "sector_limits": {
                "forex_majors": settings.sector_limit_forex_majors,
                "forex_jpy": settings.sector_limit_forex_jpy,
                "forex_eur": settings.sector_limit_forex_eur,
                "forex_gbp": settings.sector_limit_forex_gbp,
                "indices_us": settings.sector_limit_indices_us,
                "indices_eu": settings.sector_limit_indices_eu,
                "indices_asia": settings.sector_limit_indices_asia,
                "precious_metals": settings.sector_limit_precious_metals,
                "commodities": settings.sector_limit_commodities,
                "crypto": settings.sector_limit_crypto,
            },
        }

    except Exception as e:
        logger.error(f"Error in settings: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
