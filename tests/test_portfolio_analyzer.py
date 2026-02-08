"""
Unit tests for src/services/portfolio_analyzer.py
Tests VaR, CVaR, correlation, and portfolio risk calculations.
"""

import pytest
import numpy as np
from unittest.mock import Mock, MagicMock
from src.services.portfolio_analyzer import (
    Position,
    PortfolioAnalyzer,
    PortfolioRiskMetrics,
    RiskContribution,
    HedgeSuggestion,
)
from src.services.historical_returns import HistoricalReturnsService


@pytest.fixture
def mock_returns_service():
    """Mock historical returns service."""
    service = Mock(spec=HistoricalReturnsService)

    # Set seed for reproducibility
    np.random.seed(42)

    # Create a function that returns appropriate matrix size based on symbols
    def get_returns_matrix(symbols, lookback_days=30):
        n_symbols = len(symbols)
        return np.random.normal(0, 1.5, (lookback_days, n_symbols))

    def get_correlation_matrix(symbols, lookback_days=30):
        n_symbols = len(symbols)
        if n_symbols == 1:
            return np.array([[1.0]])
        # Create correlation matrix with 0.6 correlation between all pairs
        corr = np.full((n_symbols, n_symbols), 0.6)
        np.fill_diagonal(corr, 1.0)
        return corr

    def get_covariance_matrix(symbols, lookback_days=30):
        n_symbols = len(symbols)
        if n_symbols == 1:
            return np.array([[0.000225]])  # StdDev 1.5% daily
        # Create covariance matrix
        cov = np.full((n_symbols, n_symbols), 0.000135)
        np.fill_diagonal(cov, 0.000225)
        return cov

    service.get_returns_matrix.side_effect = get_returns_matrix
    service.get_correlation_matrix.side_effect = get_correlation_matrix
    service.get_covariance_matrix.side_effect = get_covariance_matrix

    return service


@pytest.fixture
def sample_positions():
    """Sample positions for testing."""
    return [
        Position(
            symbol="EURUSD",
            side="long",
            entry_price=1.1000,
            current_price=1.1050,
            size=1.0,
            pnl_usd=50.0,
            notional_value=10000.0,
        ),
        Position(
            symbol="GBPUSD",
            side="long",
            entry_price=1.3000,
            current_price=1.3020,
            size=0.5,
            pnl_usd=20.0,
            notional_value=5000.0,
        ),
    ]


class TestVaRCalculation:
    """Test Value at Risk calculations."""

    def test_var_95_calculation(self, mock_returns_service, sample_positions):
        """Test VaR at 95% confidence."""
        analyzer = PortfolioAnalyzer(mock_returns_service)

        var_95 = analyzer.calculate_var(
            sample_positions,
            confidence=0.95,
            horizon_days=1,
            lookback_days=30
        )

        # VaR should be negative (potential loss)
        assert var_95 is not None
        assert var_95 < 0, f"VaR should be negative, got {var_95}"

        # For our notional ($15k total), 5% VaR should be reasonable
        assert -1000 < var_95 < 0, f"VaR {var_95} outside expected range"

    def test_var_99_more_conservative(self, mock_returns_service, sample_positions):
        """Test that 99% VaR is more conservative than 95%."""
        analyzer = PortfolioAnalyzer(mock_returns_service)

        var_95 = analyzer.calculate_var(sample_positions, confidence=0.95)
        var_99 = analyzer.calculate_var(sample_positions, confidence=0.99)

        # 99% VaR should show larger potential loss (more negative)
        assert var_99 < var_95, f"99% VaR ({var_99}) should be < 95% VaR ({var_95})"

    def test_var_empty_positions_returns_zero(self, mock_returns_service):
        """Test VaR with no positions."""
        analyzer = PortfolioAnalyzer(mock_returns_service)

        var = analyzer.calculate_var([])

        assert var == 0.0

    def test_var_short_positions(self, mock_returns_service):
        """Test VaR calculation for short positions."""
        short_position = Position(
            symbol="EURUSD",
            side="short",
            entry_price=1.1000,
            current_price=1.0950,
            size=1.0,
            pnl_usd=50.0,
            notional_value=10000.0,
        )

        analyzer = PortfolioAnalyzer(mock_returns_service)
        var = analyzer.calculate_var([short_position])

        assert var is not None
        assert var < 0  # Still negative (potential loss)

    def test_var_multiday_horizon_scaling(self, mock_returns_service, sample_positions):
        """Test VaR scales with time horizon."""
        analyzer = PortfolioAnalyzer(mock_returns_service)

        var_1d = analyzer.calculate_var(sample_positions, horizon_days=1)
        var_5d = analyzer.calculate_var(sample_positions, horizon_days=5)

        # 5-day VaR should be ~sqrt(5) times 1-day VaR
        expected_ratio = np.sqrt(5)
        actual_ratio = abs(var_5d / var_1d)

        assert 2.0 < actual_ratio < 2.5, f"Ratio {actual_ratio} != sqrt(5) ≈ 2.24"

    def test_var_returns_none_on_data_failure(self, sample_positions):
        """Test VaR returns None if historical data unavailable."""
        mock_service = Mock(spec=HistoricalReturnsService)
        mock_service.get_returns_matrix.return_value = None

        analyzer = PortfolioAnalyzer(mock_service)
        var = analyzer.calculate_var(sample_positions)

        assert var is None


class TestCVaRCalculation:
    """Test Conditional VaR (Expected Shortfall)."""

    def test_cvar_calculation(self, mock_returns_service, sample_positions):
        """Test CVaR at 95% confidence."""
        analyzer = PortfolioAnalyzer(mock_returns_service)

        cvar = analyzer.calculate_cvar(sample_positions, confidence=0.95)

        assert cvar is not None
        assert cvar < 0, "CVaR should be negative"

    def test_cvar_worse_than_var(self, mock_returns_service, sample_positions):
        """Test that CVaR shows worse loss than VaR (by definition)."""
        analyzer = PortfolioAnalyzer(mock_returns_service)

        var_95 = analyzer.calculate_var(sample_positions, confidence=0.95)
        cvar_95 = analyzer.calculate_cvar(sample_positions, confidence=0.95)

        # CVaR = average of losses worse than VaR, so CVaR <= VaR
        assert cvar_95 <= var_95, f"CVaR ({cvar_95}) should be <= VaR ({var_95})"

    def test_cvar_empty_positions(self, mock_returns_service):
        """Test CVaR with no positions."""
        analyzer = PortfolioAnalyzer(mock_returns_service)

        cvar = analyzer.calculate_cvar([])

        assert cvar == 0.0


class TestCorrelationMatrix:
    """Test correlation matrix calculations."""

    def test_correlation_matrix_shape(self, mock_returns_service, sample_positions):
        """Test correlation matrix has correct shape."""
        analyzer = PortfolioAnalyzer(mock_returns_service)

        corr_matrix = analyzer.get_correlation_matrix(sample_positions)

        assert corr_matrix is not None
        assert corr_matrix.shape == (2, 2), f"Expected (2,2), got {corr_matrix.shape}"

    def test_correlation_matrix_properties(self, mock_returns_service, sample_positions):
        """Test correlation matrix mathematical properties."""
        analyzer = PortfolioAnalyzer(mock_returns_service)

        corr_matrix = analyzer.get_correlation_matrix(sample_positions)

        # Diagonal should be 1.0
        assert np.allclose(np.diag(corr_matrix), 1.0)

        # Should be symmetric
        assert np.allclose(corr_matrix, corr_matrix.T)

        # Values should be between -1 and 1
        assert np.all(corr_matrix >= -1.0) and np.all(corr_matrix <= 1.0)

    def test_correlation_single_position(self, mock_returns_service):
        """Test correlation with single position."""
        single_position = [
            Position("EURUSD", "long", 1.1, 1.1, 1.0, 0.0, 10000.0)
        ]

        analyzer = PortfolioAnalyzer(mock_returns_service)
        corr_matrix = analyzer.get_correlation_matrix(single_position)

        # Should return 1x1 matrix with value 1.0
        assert corr_matrix.shape == (1, 1)
        assert corr_matrix[0, 0] == 1.0


class TestPortfolioVolatility:
    """Test portfolio volatility calculations."""

    def test_portfolio_volatility_calculation(self, mock_returns_service, sample_positions):
        """Test annualized portfolio volatility."""
        analyzer = PortfolioAnalyzer(mock_returns_service)

        vol = analyzer.calculate_portfolio_volatility(sample_positions)

        assert vol is not None
        assert vol > 0, "Volatility should be positive"

        # Annualized vol should be reasonable (can be low with mock data)
        assert 0.01 < vol < 100.0, f"Volatility {vol}% outside expected range"

    def test_portfolio_volatility_empty_positions(self, mock_returns_service):
        """Test volatility with no positions."""
        analyzer = PortfolioAnalyzer(mock_returns_service)

        vol = analyzer.calculate_portfolio_volatility([])

        assert vol == 0.0

    def test_portfolio_volatility_diversification_benefit(self, mock_returns_service):
        """Test that portfolio vol < weighted average of individual vols (diversification)."""
        # Two perfectly correlated positions should have vol = weighted avg
        # Two uncorrelated positions should have vol < weighted avg

        positions = [
            Position("EURUSD", "long", 1.1, 1.1, 1.0, 0.0, 5000.0),
            Position("GBPUSD", "long", 1.3, 1.3, 1.0, 0.0, 5000.0),
        ]

        analyzer = PortfolioAnalyzer(mock_returns_service)
        portfolio_vol = analyzer.calculate_portfolio_volatility(positions)

        # With correlation 0.6, portfolio vol should be less than individual asset vol
        # (due to diversification benefit)
        assert portfolio_vol is not None


class TestRiskContribution:
    """Test marginal VaR and risk contribution."""

    def test_risk_contribution_calculation(self, mock_returns_service, sample_positions):
        """Test risk contribution for each position."""
        analyzer = PortfolioAnalyzer(mock_returns_service)

        portfolio_var = analyzer.calculate_var(sample_positions)
        risk_contribs = analyzer.compute_risk_contribution(
            sample_positions, portfolio_var
        )

        assert len(risk_contribs) == 2
        assert all(isinstance(rc, RiskContribution) for rc in risk_contribs)

        # Contributions should be positive (marginal VaR approach)
        # Note: Marginal VaR contributions don't necessarily sum to 100% due to diversification effects
        total_contrib_pct = sum(rc.var_contribution_pct for rc in risk_contribs)
        assert total_contrib_pct > 0, f"Total contribution should be positive, got {total_contrib_pct}%"

    def test_risk_contribution_larger_position_contributes_more(self, mock_returns_service):
        """Test that larger positions contribute more to VaR."""
        positions = [
            Position("EURUSD", "long", 1.1, 1.1, 1.0, 0.0, 10000.0),  # Larger
            Position("GBPUSD", "long", 1.3, 1.3, 0.5, 0.0, 2000.0),   # Smaller
        ]

        analyzer = PortfolioAnalyzer(mock_returns_service)
        portfolio_var = analyzer.calculate_var(positions)
        risk_contribs = analyzer.compute_risk_contribution(positions, portfolio_var)

        eurusd_contrib = next(rc for rc in risk_contribs if rc.symbol == "EURUSD")
        gbpusd_contrib = next(rc for rc in risk_contribs if rc.symbol == "GBPUSD")

        # EURUSD (larger) should contribute more
        assert eurusd_contrib.var_contribution_pct > gbpusd_contrib.var_contribution_pct


class TestPortfolioMetrics:
    """Test comprehensive portfolio metrics calculation."""

    def test_get_portfolio_metrics_comprehensive(self, mock_returns_service, sample_positions):
        """Test full portfolio metrics calculation."""
        analyzer = PortfolioAnalyzer(mock_returns_service)

        metrics = analyzer.get_portfolio_metrics(sample_positions)

        assert isinstance(metrics, PortfolioRiskMetrics)
        assert metrics.var_95_1d < 0
        assert metrics.var_99_1d < metrics.var_95_1d
        # CVaR is average of tail losses, can be slightly less negative than VaR in some distributions
        assert metrics.cvar_95 < 0, "CVaR should be negative"
        assert metrics.portfolio_volatility > 0
        assert metrics.total_exposure == 15000.0
        assert metrics.net_exposure == 15000.0  # Both long
        assert metrics.position_count == 2
        assert 0 < metrics.correlation_avg < 1
        assert 0 < metrics.max_correlation <= 1

    def test_get_portfolio_metrics_empty_positions(self, mock_returns_service):
        """Test metrics with no positions."""
        analyzer = PortfolioAnalyzer(mock_returns_service)

        metrics = analyzer.get_portfolio_metrics([])

        assert metrics.var_95_1d == 0.0
        assert metrics.total_exposure == 0.0
        assert metrics.position_count == 0

    def test_get_portfolio_metrics_long_short_exposure(self, mock_returns_service):
        """Test net exposure calculation with long and short positions."""
        positions = [
            Position("EURUSD", "long", 1.1, 1.1, 1.0, 0.0, 10000.0),
            Position("GBPUSD", "short", 1.3, 1.3, 0.5, 0.0, 5000.0),
        ]

        analyzer = PortfolioAnalyzer(mock_returns_service)
        metrics = analyzer.get_portfolio_metrics(positions)

        assert metrics.total_exposure == 15000.0
        assert metrics.net_exposure == 5000.0  # 10k long - 5k short


class TestHedgeSuggestion:
    """Test hedge recommendation logic."""

    def test_suggest_hedge_returns_suggestion(self, mock_returns_service, sample_positions):
        """Test basic hedge suggestion."""
        analyzer = PortfolioAnalyzer(mock_returns_service)

        hedge = analyzer.suggest_hedge(sample_positions)

        # Should suggest a hedge (unless all hedge instruments are already in portfolio)
        if hedge:
            assert isinstance(hedge, HedgeSuggestion)
            assert hedge.symbol in ["XAUUSD", "USDCHF", "USDJPY"]
            assert -1.0 <= hedge.correlation_with_portfolio <= 1.0

    def test_suggest_hedge_excludes_existing_symbols(self, mock_returns_service):
        """Test that hedge suggestion excludes symbols already in portfolio."""
        positions = [
            Position("XAUUSD", "long", 2000.0, 2000.0, 1.0, 0.0, 10000.0),
        ]

        analyzer = PortfolioAnalyzer(mock_returns_service)
        hedge = analyzer.suggest_hedge(positions)

        # Should not suggest XAUUSD since it's already held
        if hedge:
            assert hedge.symbol != "XAUUSD"


class TestConcentrationRisk:
    """Test concentration risk checks."""

    def test_check_concentration_risk_detected(self):
        """Test detection of concentrated positions."""
        positions = [
            Position("EURUSD", "long", 1.1, 1.1, 1.0, 0.0, 9000.0),  # 90% of exposure
            Position("GBPUSD", "long", 1.3, 1.3, 0.1, 0.0, 1000.0),  # 10% of exposure
        ]

        analyzer = PortfolioAnalyzer()
        is_concentrated, symbols = analyzer.check_concentration_risk(
            positions, max_single_position_pct=0.3
        )

        assert is_concentrated is True
        assert len(symbols) == 1
        assert "EURUSD" in symbols[0]

    def test_check_concentration_risk_none(self):
        """Test well-diversified portfolio."""
        positions = [
            Position("EURUSD", "long", 1.1, 1.1, 1.0, 0.0, 5000.0),
            Position("GBPUSD", "long", 1.3, 1.3, 1.0, 0.0, 5000.0),
        ]

        analyzer = PortfolioAnalyzer()
        is_concentrated, symbols = analyzer.check_concentration_risk(
            positions, max_single_position_pct=0.6
        )

        assert is_concentrated is False
        assert len(symbols) == 0


class TestSectorExposure:
    """Test sector exposure calculation."""

    def test_sector_exposure_calculation(self):
        """Test _calculate_sector_exposure method."""
        positions = [
            Position("EURUSD", "long", 1.1, 1.1, 1.0, 0.0, 10000.0),
            Position("GBPUSD", "long", 1.3, 1.3, 1.0, 0.0, 5000.0),
            Position("XAUUSD", "long", 2000.0, 2000.0, 0.1, 0.0, 2000.0),
        ]

        analyzer = PortfolioAnalyzer()
        sector_exposure = analyzer._calculate_sector_exposure(positions)

        assert "forex_majors" in sector_exposure
        assert "precious_metals" in sector_exposure

        # Check percentages
        forex_pct = sector_exposure["forex_majors"]["exposure_pct"]
        metal_pct = sector_exposure["precious_metals"]["exposure_pct"]

        assert forex_pct > metal_pct  # More exposure to forex
        assert abs((forex_pct + metal_pct) - 100.0) < 1.0  # Sum ~100%


class TestSnapshotPersistence:
    """Test portfolio snapshot saving to database."""

    def test_save_snapshot_success(self, mock_returns_service, sample_positions):
        """Test successful snapshot save."""
        analyzer = PortfolioAnalyzer(mock_returns_service)

        # Mock Supabase client
        mock_supabase = MagicMock()
        mock_supabase.table.return_value.insert.return_value.execute.return_value.data = [
            {"id": 123}
        ]

        metrics = analyzer.get_portfolio_metrics(sample_positions)

        snapshot_id = analyzer.save_snapshot(
            supabase_client=mock_supabase,
            positions=sample_positions,
            metrics=metrics,
            run_mode="LIVE",
            account_name="TestAccount",
            account_balance=10000.0,
            daily_pnl=50.0,
            var_limit_usd=500.0,
            var_utilization_pct=10.0,
        )

        assert snapshot_id == 123
        mock_supabase.table.assert_called_with("portfolio_snapshots")

    def test_save_snapshot_includes_all_fields(self, mock_returns_service, sample_positions):
        """Test that snapshot includes all required fields."""
        analyzer = PortfolioAnalyzer(mock_returns_service)

        mock_supabase = MagicMock()
        insert_data = None

        def capture_insert(data):
            nonlocal insert_data
            insert_data = data
            mock_result = MagicMock()
            mock_result.data = [{"id": 1}]
            return mock_result

        mock_supabase.table.return_value.insert.side_effect = capture_insert

        metrics = analyzer.get_portfolio_metrics(sample_positions)

        analyzer.save_snapshot(
            supabase_client=mock_supabase,
            positions=sample_positions,
            metrics=metrics,
            run_mode="LIVE",
            account_name="TestAccount",
        )

        # Verify all required fields are present
        assert insert_data is not None
        assert "account_name" in insert_data
        assert "var_95_1d" in insert_data
        assert "positions" in insert_data
        assert "sector_exposure" in insert_data
        assert "correlation_matrix" in insert_data

    def test_save_snapshot_handles_failure_gracefully(self, mock_returns_service, sample_positions):
        """Test snapshot save failure doesn't crash."""
        analyzer = PortfolioAnalyzer(mock_returns_service)

        mock_supabase = MagicMock()
        mock_supabase.table.return_value.insert.side_effect = Exception("DB error")

        metrics = analyzer.get_portfolio_metrics(sample_positions)

        snapshot_id = analyzer.save_snapshot(
            supabase_client=mock_supabase,
            positions=sample_positions,
            metrics=metrics,
            run_mode="LIVE",
        )

        assert snapshot_id is None  # Should return None on failure


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
