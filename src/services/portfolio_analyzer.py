"""
Portfolio Analyzer Service

Calculates portfolio-level risk metrics including VaR, CVaR, correlation matrices,
and risk contribution analysis.
"""

import logging
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple
import numpy as np
from datetime import datetime, timezone

from src.services.historical_returns import HistoricalReturnsService

logger = logging.getLogger(__name__)


@dataclass
class Position:
    """Represents an active trading position."""
    symbol: str
    side: str  # "long" or "short"
    entry_price: float
    current_price: float
    size: float  # Position size in lots
    pnl_usd: float
    notional_value: float  # Position value in USD


@dataclass
class PortfolioRiskMetrics:
    """Portfolio-level risk metrics."""
    var_95_1d: float  # 1-day VaR at 95% confidence (USD)
    var_99_1d: float  # 1-day VaR at 99% confidence (USD)
    cvar_95: float  # Conditional VaR at 95% (USD)
    portfolio_volatility: float  # Annualized portfolio volatility (%)
    sharpe_ratio: Optional[float]  # Sharpe ratio (if PnL history available)
    total_exposure: float  # Total notional exposure (USD)
    net_exposure: float  # Net exposure accounting for long/short (USD)
    position_count: int
    correlation_avg: float  # Average pairwise correlation
    max_correlation: float  # Max pairwise correlation


@dataclass
class RiskContribution:
    """Risk contribution of a single position to portfolio VaR."""
    symbol: str
    var_contribution_usd: float  # Absolute contribution to VaR (USD)
    var_contribution_pct: float  # % of total VaR
    marginal_var: float  # Change in VaR if position removed


@dataclass
class HedgeSuggestion:
    """Suggested hedge to reduce portfolio risk."""
    symbol: str
    correlation_with_portfolio: float
    expected_var_reduction_pct: float
    reason: str


class PortfolioAnalyzer:
    """Analyzes portfolio-level risk using modern portfolio theory."""

    def __init__(
        self,
        historical_returns_service: Optional[HistoricalReturnsService] = None
    ):
        """
        Initialize portfolio analyzer.

        Args:
            historical_returns_service: Service for fetching historical returns
        """
        self.returns_service = historical_returns_service or HistoricalReturnsService()

    def calculate_var(
        self,
        positions: List[Position],
        confidence: float = 0.95,
        horizon_days: int = 1,
        lookback_days: int = 30
    ) -> Optional[float]:
        """
        Calculate Value at Risk using historical simulation.

        Args:
            positions: List of active positions
            confidence: Confidence level (0.95 = 95%)
            horizon_days: Time horizon in days
            lookback_days: Historical lookback period

        Returns:
            VaR in USD (negative value = potential loss), or None if calculation fails
        """
        if not positions:
            return 0.0

        symbols = [p.symbol for p in positions]

        # Get historical returns matrix
        returns_matrix = self.returns_service.get_returns_matrix(symbols, lookback_days)

        if returns_matrix is None:
            logger.warning("Failed to get returns matrix for VaR calculation")
            return None

        # Position weights (notional values)
        weights = np.array([p.notional_value for p in positions])

        # Calculate portfolio returns for each historical day
        # returns_matrix shape: (days, n_symbols)
        # For long positions: portfolio_return = sum(weight_i * return_i)
        # For short positions: flip the sign of returns

        position_signs = np.array([1.0 if p.side.lower() == "long" else -1.0 for p in positions])
        signed_returns = returns_matrix * position_signs

        # Portfolio P&L for each historical day
        portfolio_pnl = signed_returns @ weights / 100.0  # Convert % to absolute

        # Scale to horizon if needed
        if horizon_days > 1:
            portfolio_pnl *= np.sqrt(horizon_days)

        # VaR is the percentile of losses (negative returns)
        var_percentile = (1 - confidence) * 100
        var_value = np.percentile(portfolio_pnl, var_percentile)

        return float(var_value)

    def calculate_cvar(
        self,
        positions: List[Position],
        confidence: float = 0.95,
        horizon_days: int = 1,
        lookback_days: int = 30
    ) -> Optional[float]:
        """
        Calculate Conditional VaR (Expected Shortfall) - average loss beyond VaR.

        Args:
            positions: List of active positions
            confidence: Confidence level
            horizon_days: Time horizon in days
            lookback_days: Historical lookback period

        Returns:
            CVaR in USD (negative value), or None if calculation fails
        """
        if not positions:
            return 0.0

        symbols = [p.symbol for p in positions]
        returns_matrix = self.returns_service.get_returns_matrix(symbols, lookback_days)

        if returns_matrix is None:
            return None

        weights = np.array([p.notional_value for p in positions])
        position_signs = np.array([1.0 if p.side.lower() == "long" else -1.0 for p in positions])
        signed_returns = returns_matrix * position_signs

        portfolio_pnl = signed_returns @ weights / 100.0

        if horizon_days > 1:
            portfolio_pnl *= np.sqrt(horizon_days)

        # CVaR = average of all losses worse than VaR
        var_percentile = (1 - confidence) * 100
        var_threshold = np.percentile(portfolio_pnl, var_percentile)

        # Get all scenarios worse than VaR
        tail_losses = portfolio_pnl[portfolio_pnl <= var_threshold]

        if len(tail_losses) == 0:
            return float(var_threshold)

        cvar_value = np.mean(tail_losses)
        return float(cvar_value)

    def get_correlation_matrix(
        self,
        positions: List[Position],
        lookback_days: int = 30
    ) -> Optional[np.ndarray]:
        """
        Calculate correlation matrix for active positions.

        Args:
            positions: List of active positions
            lookback_days: Historical lookback period

        Returns:
            NxN correlation matrix, or None if calculation fails
        """
        if len(positions) < 2:
            return np.array([[1.0]])

        symbols = [p.symbol for p in positions]
        return self.returns_service.get_correlation_matrix(symbols, lookback_days)

    def calculate_portfolio_volatility(
        self,
        positions: List[Position],
        lookback_days: int = 30
    ) -> Optional[float]:
        """
        Calculate annualized portfolio volatility using covariance matrix.
        Formula: σ_p = sqrt(w^T * Σ * w)

        Args:
            positions: List of active positions
            lookback_days: Historical lookback period

        Returns:
            Annualized volatility (%), or None if calculation fails
        """
        if not positions:
            return 0.0

        symbols = [p.symbol for p in positions]
        cov_matrix = self.returns_service.get_covariance_matrix(symbols, lookback_days)

        if cov_matrix is None:
            return None

        # Position weights (as fraction of total exposure)
        total_notional = sum(p.notional_value for p in positions)
        if total_notional == 0:
            return 0.0

        weights = np.array([p.notional_value / total_notional for p in positions])

        # Portfolio variance: w^T * Σ * w
        portfolio_variance = weights @ cov_matrix @ weights

        # Annualized volatility (assuming 252 trading days)
        portfolio_vol = np.sqrt(portfolio_variance) * np.sqrt(252)

        return float(portfolio_vol)

    def compute_risk_contribution(
        self,
        positions: List[Position],
        portfolio_var: float,
        lookback_days: int = 30
    ) -> List[RiskContribution]:
        """
        Calculate marginal VaR contribution for each position.

        Args:
            positions: List of active positions
            portfolio_var: Current portfolio VaR
            lookback_days: Historical lookback period

        Returns:
            List of risk contributions per position
        """
        if not positions or portfolio_var == 0:
            return []

        risk_contributions = []

        # Calculate VaR without each position
        for i, position in enumerate(positions):
            # Create portfolio without this position
            other_positions = positions[:i] + positions[i+1:]

            # Calculate VaR without this position
            var_without = self.calculate_var(other_positions, lookback_days=lookback_days)

            if var_without is None:
                marginal_var = 0.0
            else:
                marginal_var = portfolio_var - var_without

            # Contribution as percentage
            contrib_pct = (abs(marginal_var) / abs(portfolio_var) * 100) if portfolio_var != 0 else 0.0

            risk_contributions.append(
                RiskContribution(
                    symbol=position.symbol,
                    var_contribution_usd=marginal_var,
                    var_contribution_pct=contrib_pct,
                    marginal_var=marginal_var
                )
            )

        return risk_contributions

    def get_portfolio_metrics(
        self,
        positions: List[Position],
        lookback_days: int = 30
    ) -> Optional[PortfolioRiskMetrics]:
        """
        Calculate comprehensive portfolio risk metrics.

        Args:
            positions: List of active positions
            lookback_days: Historical lookback period

        Returns:
            PortfolioRiskMetrics object, or None if calculation fails
        """
        if not positions:
            return PortfolioRiskMetrics(
                var_95_1d=0.0,
                var_99_1d=0.0,
                cvar_95=0.0,
                portfolio_volatility=0.0,
                sharpe_ratio=None,
                total_exposure=0.0,
                net_exposure=0.0,
                position_count=0,
                correlation_avg=0.0,
                max_correlation=0.0
            )

        # Calculate VaR at different confidence levels
        var_95 = self.calculate_var(positions, confidence=0.95, lookback_days=lookback_days)
        var_99 = self.calculate_var(positions, confidence=0.99, lookback_days=lookback_days)
        cvar_95 = self.calculate_cvar(positions, confidence=0.95, lookback_days=lookback_days)

        # Calculate volatility
        portfolio_vol = self.calculate_portfolio_volatility(positions, lookback_days)

        # Calculate exposures
        total_exposure = sum(p.notional_value for p in positions)
        long_exposure = sum(p.notional_value for p in positions if p.side.lower() == "long")
        short_exposure = sum(p.notional_value for p in positions if p.side.lower() == "short")
        net_exposure = long_exposure - short_exposure

        # Calculate correlation metrics
        corr_matrix = self.get_correlation_matrix(positions, lookback_days)

        correlation_avg = 0.0
        max_correlation = 0.0

        if corr_matrix is not None and len(positions) > 1:
            # Get upper triangle (excluding diagonal)
            n = len(positions)
            correlations = []
            for i in range(n):
                for j in range(i + 1, n):
                    correlations.append(corr_matrix[i, j])

            if correlations:
                correlation_avg = float(np.mean(correlations))
                max_correlation = float(np.max(correlations))

        return PortfolioRiskMetrics(
            var_95_1d=var_95 if var_95 is not None else 0.0,
            var_99_1d=var_99 if var_99 is not None else 0.0,
            cvar_95=cvar_95 if cvar_95 is not None else 0.0,
            portfolio_volatility=portfolio_vol if portfolio_vol is not None else 0.0,
            sharpe_ratio=None,  # Would need returns history
            total_exposure=total_exposure,
            net_exposure=net_exposure,
            position_count=len(positions),
            correlation_avg=correlation_avg,
            max_correlation=max_correlation
        )

    def suggest_hedge(
        self,
        positions: List[Position],
        target_var_reduction: float = 0.2,
        lookback_days: int = 30
    ) -> Optional[HedgeSuggestion]:
        """
        Suggest a hedge instrument to reduce portfolio risk.

        Args:
            positions: List of active positions
            target_var_reduction: Target VaR reduction (0.2 = 20%)
            lookback_days: Historical lookback period

        Returns:
            HedgeSuggestion, or None if no good hedge found
        """
        if not positions:
            return None

        # List of common hedge instruments
        HEDGE_INSTRUMENTS = {
            "XAUUSD": "Gold hedge against currency volatility",
            "USDCHF": "Safe haven currency",
            "USDJPY": "Negatively correlated with risk assets",
        }

        current_symbols = {p.symbol for p in positions}
        best_hedge = None
        best_correlation = 1.0

        # Find instrument with lowest/negative correlation
        for hedge_symbol, reason in HEDGE_INSTRUMENTS.items():
            if hedge_symbol in current_symbols:
                continue

            # Calculate correlation with portfolio
            portfolio_symbols = [p.symbol for p in positions]
            all_symbols = portfolio_symbols + [hedge_symbol]

            corr_matrix = self.returns_service.get_correlation_matrix(all_symbols, lookback_days)

            if corr_matrix is None:
                continue

            # Correlation of hedge with each position
            hedge_idx = len(portfolio_symbols)
            hedge_correlations = corr_matrix[:-1, hedge_idx]

            # Average correlation with portfolio
            avg_corr = float(np.mean(hedge_correlations))

            if avg_corr < best_correlation:
                best_correlation = avg_corr
                best_hedge = HedgeSuggestion(
                    symbol=hedge_symbol,
                    correlation_with_portfolio=avg_corr,
                    expected_var_reduction_pct=target_var_reduction * 100,
                    reason=reason
                )

        return best_hedge

    def check_concentration_risk(
        self,
        positions: List[Position],
        max_single_position_pct: float = 0.3
    ) -> Tuple[bool, List[str]]:
        """
        Check for concentration risk (single position too large).

        Args:
            positions: List of active positions
            max_single_position_pct: Max position size as % of total exposure

        Returns:
            (is_concentrated, list of concentrated symbols)
        """
        if not positions:
            return False, []

        total_exposure = sum(p.notional_value for p in positions)

        if total_exposure == 0:
            return False, []

        concentrated_symbols = []

        for position in positions:
            position_pct = position.notional_value / total_exposure

            if position_pct > max_single_position_pct:
                concentrated_symbols.append(
                    f"{position.symbol} ({position_pct * 100:.1f}%)"
                )

        return len(concentrated_symbols) > 0, concentrated_symbols

    def save_snapshot(
        self,
        supabase_client,
        positions: List[Position],
        metrics: PortfolioRiskMetrics,
        run_mode: str,
        account_name: Optional[str] = None,
        account_balance: Optional[float] = None,
        daily_pnl: Optional[float] = None,
        var_limit_usd: Optional[float] = None,
        var_utilization_pct: Optional[float] = None,
        lookback_days: int = 30
    ) -> Optional[int]:
        """
        Persist portfolio snapshot to database for historical trend analysis.

        Args:
            supabase_client: Supabase client instance
            positions: List of active positions
            metrics: Pre-calculated portfolio metrics
            run_mode: Execution mode (LIVE, PAPER, DRY_RUN)
            account_name: Optional account name for multi-account support
            account_balance: Current account balance
            daily_pnl: Daily profit/loss
            var_limit_usd: VaR limit in USD
            var_utilization_pct: VaR utilization percentage
            lookback_days: Historical lookback period

        Returns:
            Snapshot ID if successful, None otherwise
        """
        try:
            # Build positions array
            positions_json = [
                {
                    "symbol": p.symbol,
                    "side": p.side,
                    "size": p.size,
                    "entry_price": p.entry_price,
                    "current_price": p.current_price,
                    "pnl_usd": p.pnl_usd,
                    "notional_value": p.notional_value,
                }
                for p in positions
            ]

            # Build correlation matrix JSON
            correlation_matrix_json = {}
            if len(positions) > 1:
                corr_matrix = self.get_correlation_matrix(positions, lookback_days)
                if corr_matrix is not None:
                    symbols = [p.symbol for p in positions]
                    correlation_matrix_json = {
                        "symbols": symbols,
                        "matrix": corr_matrix.tolist(),
                    }

            # Build sector exposure JSON
            sector_exposure_json = self._calculate_sector_exposure(positions)

            # Build risk contribution JSON
            risk_contribution_json = {}
            if metrics.var_95_1d != 0 and len(positions) > 0:
                risk_contributions = self.compute_risk_contribution(
                    positions, metrics.var_95_1d, lookback_days
                )
                risk_contribution_json = {
                    rc.symbol: {
                        "contribution_usd": rc.var_contribution_usd,
                        "contribution_pct": rc.var_contribution_pct,
                        "marginal_var": rc.marginal_var,
                    }
                    for rc in risk_contributions
                }

            # Insert into database
            snapshot_data = {
                "total_equity": account_balance or 0.0,
                "account_balance": account_balance,
                "daily_pnl": daily_pnl,
                "var_95_1d": metrics.var_95_1d,
                "var_99_1d": metrics.var_99_1d,
                "cvar_95": metrics.cvar_95,
                "var_limit_usd": var_limit_usd,
                "var_utilization_pct": var_utilization_pct,
                "portfolio_vol": metrics.portfolio_volatility,
                "sharpe_ratio": metrics.sharpe_ratio,
                "total_exposure": metrics.total_exposure,
                "net_exposure": metrics.net_exposure,
                "position_count": metrics.position_count,
                "correlation_avg": metrics.correlation_avg,
                "max_correlation": metrics.max_correlation,
                "positions": positions_json,
                "correlation_matrix": correlation_matrix_json,
                "sector_exposure": sector_exposure_json,
                "risk_contribution": risk_contribution_json,
                "run_mode": run_mode,
                "account_name": account_name,
            }

            result = supabase_client.table("portfolio_snapshots").insert(snapshot_data).execute()

            if result.data and len(result.data) > 0:
                snapshot_id = result.data[0].get("id")
                logger.info(
                    f"Portfolio snapshot saved: ID={snapshot_id}, account={account_name}, "
                    f"VaR={metrics.var_95_1d:.2f}, positions={len(positions)}"
                )
                return snapshot_id
            else:
                logger.warning("Portfolio snapshot insert returned no data")
                return None

        except Exception as e:
            logger.error(f"Failed to save portfolio snapshot: {e}", exc_info=True)
            return None

    def _calculate_sector_exposure(self, positions: List[Position]) -> Dict[str, Any]:
        """
        Calculate sector exposure breakdown from positions.

        Args:
            positions: List of active positions

        Returns:
            Dict with sector exposure data
        """
        # Sector classification map (simplified)
        SECTOR_MAP = {
            "EURUSD": "forex_majors",
            "GBPUSD": "forex_majors",
            "USDJPY": "forex_jpy",
            "EURJPY": "forex_jpy",
            "GBPJPY": "forex_jpy",
            "EURGBP": "forex_eur",
            "XAUUSD": "precious_metals",
            "XAGUSD": "precious_metals",
            "US30": "indices_us",
            "NAS100": "indices_us",
            "SPX500": "indices_us",
            "GER30": "indices_eu",
            "UK100": "indices_eu",
            "JPN225": "indices_asia",
            "BTCUSD": "crypto",
            "ETHUSD": "crypto",
        }

        sector_exposure: Dict[str, Dict[str, float]] = {}
        total_exposure = sum(p.notional_value for p in positions)

        for position in positions:
            sector = SECTOR_MAP.get(position.symbol, "other")

            if sector not in sector_exposure:
                sector_exposure[sector] = {
                    "exposure_usd": 0.0,
                    "exposure_pct": 0.0,
                }

            sector_exposure[sector]["exposure_usd"] += position.notional_value

        # Calculate percentages
        if total_exposure > 0:
            for sector_data in sector_exposure.values():
                sector_data["exposure_pct"] = (
                    sector_data["exposure_usd"] / total_exposure * 100
                )

        return sector_exposure
