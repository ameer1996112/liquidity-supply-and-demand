"""
Unit Tests for Correlation Guardian (CorrelationManager)

Tests the CorrelationManager class which enforces:
1. Max positions (3 open positions)
2. Duplicate position blocking
3. Opposing hedge blocking
4. Currency over-exposure (max 2 same currency)
5. Correlation group limits

These tests run without network calls using fixture positions.
"""

import pytest
from datetime import datetime

from backend.correlation_manager import (
    CorrelationManager,
    CorrelationCheckResult,
    CorrelationRejectionReason,
    ActivePosition,
    extract_currencies,
    get_correlation_groups,
    CORRELATION_GROUPS,
    DEFAULT_MAX_OPEN_POSITIONS,
)


# ══════════════════════════════════════════════════════════
# FIXTURES
# ══════════════════════════════════════════════════════════


@pytest.fixture
def manager():
    """Create CorrelationManager with default settings."""
    return CorrelationManager(
        max_positions=3,
        max_same_currency_exposure=2,
        max_correlation_group_positions=1,
        allow_hedging=False,
    )


@pytest.fixture
def manager_with_hedging():
    """Create CorrelationManager that allows hedging."""
    return CorrelationManager(
        max_positions=3,
        max_same_currency_exposure=2,
        max_correlation_group_positions=1,
        allow_hedging=True,
    )


def make_position(symbol: str, side: str, size: float = 0.10) -> ActivePosition:
    """Helper to create ActivePosition."""
    return ActivePosition(
        symbol=symbol,
        side=side,
        size=size,
        entry_price=1.0000,
        entry_time=datetime.utcnow(),
    )


# ══════════════════════════════════════════════════════════
# HELPER FUNCTION TESTS
# ══════════════════════════════════════════════════════════


@pytest.mark.unit
class TestHelperFunctions:
    """Tests for currency extraction and correlation group functions."""

    def test_extract_currencies_standard_forex(self):
        """Should extract currencies from standard forex pairs."""
        base, quote = extract_currencies("EURUSD")
        assert base == "EUR"
        assert quote == "USD"

    def test_extract_currencies_jpy_pair(self):
        """Should extract currencies from JPY pairs."""
        base, quote = extract_currencies("USDJPY")
        assert base == "USD"
        assert quote == "JPY"

    def test_extract_currencies_gold(self):
        """Should handle gold symbol."""
        base, quote = extract_currencies("XAUUSD")
        assert base == "XAU"
        assert quote == "USD"

    def test_extract_currencies_silver(self):
        """Should handle silver symbol."""
        base, quote = extract_currencies("XAGUSD")
        assert base == "XAG"
        assert quote == "USD"

    def test_extract_currencies_indices_return_none(self):
        """Should return None for indices."""
        base, quote = extract_currencies("US30")
        assert base is None
        assert quote is None

        base, quote = extract_currencies("NAS100")
        assert base is None
        assert quote is None

    def test_extract_currencies_crypto(self):
        """Should handle crypto pairs."""
        base, quote = extract_currencies("BTCUSD")
        assert base == "BTC"
        assert quote == "USD"

    def test_get_correlation_groups_eurusd(self):
        """EURUSD should belong to eur_gbp group."""
        groups = get_correlation_groups("EURUSD")
        assert "eur_gbp" in groups

    def test_get_correlation_groups_gold(self):
        """Gold should belong to precious_metals group."""
        groups = get_correlation_groups("XAUUSD")
        assert "precious_metals" in groups

    def test_get_correlation_groups_usdjpy(self):
        """USDJPY should belong to multiple groups."""
        groups = get_correlation_groups("USDJPY")
        assert "usd_jpy_chf" in groups
        assert "jpy_crosses" in groups

    def test_get_correlation_groups_us30(self):
        """US30 should belong to us_indices group."""
        groups = get_correlation_groups("US30")
        assert "us_indices" in groups


# ══════════════════════════════════════════════════════════
# MAX POSITIONS TESTS
# ══════════════════════════════════════════════════════════


@pytest.mark.unit
class TestMaxPositions:
    """Tests for max positions limit (3)."""

    def test_passes_when_below_max_positions(self, manager):
        """Should pass when positions are below limit."""
        positions = [
            make_position("EURUSD", "buy"),
            make_position("GBPUSD", "sell"),
        ]

        result = manager.check("AUDUSD", "buy", active_positions=positions)

        assert result.passed is True

    def test_rejects_when_at_max_positions(self, manager, active_positions_full):
        """Should reject when already at max positions (3)."""
        result = manager.check("AUDUSD", "buy", active_positions=active_positions_full)

        assert result.passed is False
        assert result.rejection_reason == CorrelationRejectionReason.MAX_POSITIONS_REACHED.value

    def test_rejection_message_shows_position_count(self, manager, active_positions_full):
        """Rejection message should show current/max positions."""
        result = manager.check("AUDUSD", "buy", active_positions=active_positions_full)

        assert "3/3" in result.rejection_message or "3" in result.rejection_message

    def test_passes_with_zero_positions(self, manager):
        """Should pass when no positions are open."""
        result = manager.check("EURUSD", "buy", active_positions=[])

        assert result.passed is True

    def test_exposure_details_include_position_count(self, manager):
        """Exposure details should include position counts."""
        positions = [make_position("EURUSD", "buy")]

        result = manager.check("GBPUSD", "sell", active_positions=positions)

        assert result.exposure_details["total_positions"] == 1
        assert result.exposure_details["max_positions"] == 3


# ══════════════════════════════════════════════════════════
# DUPLICATE POSITION TESTS
# ══════════════════════════════════════════════════════════


@pytest.mark.unit
class TestDuplicatePosition:
    """Tests for duplicate position rejection."""

    def test_rejects_duplicate_same_symbol_same_side(self, manager):
        """Should reject duplicate position (same symbol, same side)."""
        positions = [make_position("EURUSD", "buy")]

        result = manager.check("EURUSD", "buy", active_positions=positions)

        assert result.passed is False
        assert result.rejection_reason == CorrelationRejectionReason.DUPLICATE_POSITION.value

    def test_passes_same_symbol_different_side_when_hedging_allowed(self, manager_with_hedging):
        """Should pass same symbol opposite side when hedging allowed."""
        positions = [make_position("EURUSD", "buy")]

        result = manager_with_hedging.check("EURUSD", "sell", active_positions=positions)

        assert result.passed is True

    def test_rejects_same_symbol_different_side_when_hedging_blocked(self, manager):
        """Should reject same symbol opposite side when hedging not allowed."""
        positions = [make_position("EURUSD", "buy")]

        result = manager.check("EURUSD", "sell", active_positions=positions)

        assert result.passed is False
        assert result.rejection_reason == CorrelationRejectionReason.OPPOSING_HEDGE.value

    def test_case_insensitive_symbol_matching(self, manager):
        """Symbol matching should be case-insensitive."""
        positions = [make_position("eurusd", "buy")]

        result = manager.check("EURUSD", "buy", active_positions=positions)

        assert result.passed is False
        assert result.rejection_reason == CorrelationRejectionReason.DUPLICATE_POSITION.value


# ══════════════════════════════════════════════════════════
# CURRENCY OVER-EXPOSURE TESTS
# ══════════════════════════════════════════════════════════


@pytest.mark.unit
class TestCurrencyOverExposure:
    """Tests for currency over-exposure limits."""

    def test_rejects_third_long_usd_exposure(self, manager):
        """Should reject 3rd long USD exposure (max 2)."""
        # Two long USD positions: buy EURUSD (short EUR, long USD base not direct)
        # Actually: buy EURUSD = long EUR, short USD
        # buy USDJPY = long USD, short JPY
        # buy USDCHF = long USD, short CHF
        positions = [
            make_position("USDJPY", "buy"),  # Long USD
            make_position("USDCHF", "buy"),  # Long USD
        ]

        # Another long USD trade should be blocked
        result = manager.check("USDCAD", "buy", active_positions=positions)

        assert result.passed is False
        assert result.rejection_reason == CorrelationRejectionReason.CURRENCY_OVER_EXPOSURE.value

    def test_passes_different_currency_exposure(self, manager):
        """Should pass when currencies are different."""
        positions = [
            make_position("EURUSD", "buy"),  # Long EUR, short USD
            make_position("GBPJPY", "buy"),  # Long GBP, short JPY
        ]

        # AUDUSD is different base currency
        result = manager.check("AUDUSD", "buy", active_positions=positions)

        assert result.passed is True

    def test_exposure_details_include_currencies(self, manager):
        """Exposure details should include currency breakdown."""
        positions = [make_position("USDJPY", "buy")]

        result = manager.check("EURUSD", "buy", active_positions=positions)

        assert "base_currency" in result.exposure_details
        assert "quote_currency" in result.exposure_details


# ══════════════════════════════════════════════════════════
# CORRELATION GROUP TESTS
# ══════════════════════════════════════════════════════════


@pytest.mark.unit
class TestCorrelationGroups:
    """Tests for correlation group limits."""

    def test_rejects_second_position_in_correlation_group(self, manager):
        """Should reject 2nd same-direction position in correlation group."""
        # EURUSD and GBPUSD are in eur_gbp group
        positions = [make_position("EURUSD", "buy")]

        result = manager.check("GBPUSD", "buy", active_positions=positions)

        assert result.passed is False
        assert result.rejection_reason == CorrelationRejectionReason.CORRELATION_GROUP_LIMIT.value

    def test_passes_opposite_direction_in_correlation_group(self, manager):
        """Should pass opposite direction in correlation group."""
        positions = [make_position("EURUSD", "buy")]

        # Selling GBPUSD is opposite direction, should pass
        result = manager.check("GBPUSD", "sell", active_positions=positions)

        # This might still fail due to other rules, but not correlation group
        # Actually, if it passes, the reason won't be correlation_group_limit
        if not result.passed:
            assert result.rejection_reason != CorrelationRejectionReason.CORRELATION_GROUP_LIMIT.value

    def test_rejects_second_precious_metal(self, manager):
        """Should reject 2nd same-direction precious metal."""
        positions = [make_position("XAUUSD", "buy")]

        result = manager.check("XAGUSD", "buy", active_positions=positions)

        assert result.passed is False
        assert result.rejection_reason == CorrelationRejectionReason.CORRELATION_GROUP_LIMIT.value

    def test_rejects_second_us_index(self, manager):
        """Should reject 2nd same-direction US index."""
        positions = [make_position("US30", "buy")]

        result = manager.check("NAS100", "buy", active_positions=positions)

        assert result.passed is False
        assert result.rejection_reason == CorrelationRejectionReason.CORRELATION_GROUP_LIMIT.value

    def test_passes_uncorrelated_symbols(self, manager):
        """Should pass for uncorrelated symbols."""
        positions = [make_position("EURUSD", "buy")]

        # AUDUSD is not in the same group as EURUSD
        result = manager.check("XAUUSD", "buy", active_positions=positions)

        # Should pass (different groups)
        assert result.passed is True

    def test_exposure_details_include_correlation_groups(self, manager):
        """Exposure details should include correlation group counts."""
        positions = [make_position("EURUSD", "buy")]

        result = manager.check("GBPUSD", "buy", active_positions=positions)

        assert "correlation_groups" in result.exposure_details


# ══════════════════════════════════════════════════════════
# 4TH TRADE REJECTION (Critical Test Case)
# ══════════════════════════════════════════════════════════


@pytest.mark.unit
class TestFourthTradeRejection:
    """Critical test: 4th active trade must be rejected."""

    def test_rejects_4th_trade_with_3_active(self, manager):
        """4th trade MUST be rejected when 3 are already active."""
        positions = [
            make_position("EURUSD", "buy"),
            make_position("USDJPY", "sell"),
            make_position("XAUUSD", "buy"),
        ]

        # Try to add 4th position - different symbol, different side
        result = manager.check("AUDUSD", "sell", active_positions=positions)

        assert result.passed is False
        assert result.rejection_reason == CorrelationRejectionReason.MAX_POSITIONS_REACHED.value

    def test_rejects_4th_trade_regardless_of_symbol(self, manager):
        """4th trade rejected regardless of what symbol it is."""
        positions = [
            make_position("EURUSD", "buy"),
            make_position("GBPUSD", "buy"),
            make_position("USDJPY", "buy"),
        ]

        # Try various symbols - all should fail
        for symbol in ["AUDUSD", "NZDUSD", "XAUUSD", "US30"]:
            result = manager.check(symbol, "buy", active_positions=positions)
            assert result.passed is False, f"Should reject {symbol}"
            assert result.rejection_reason == CorrelationRejectionReason.MAX_POSITIONS_REACHED.value

    def test_rejects_4th_trade_message_contains_reason(self, manager):
        """Rejection message should explain why 4th trade rejected."""
        positions = [
            make_position("EURUSD", "buy"),
            make_position("GBPUSD", "sell"),
            make_position("USDJPY", "buy"),
        ]

        result = manager.check("XAUUSD", "buy", active_positions=positions)

        assert "MAX" in result.rejection_message.upper() or "3" in result.rejection_message


# ══════════════════════════════════════════════════════════
# PORTFOLIO EXPOSURE ANALYSIS
# ══════════════════════════════════════════════════════════


@pytest.mark.unit
class TestPortfolioExposure:
    """Tests for portfolio exposure analysis."""

    def test_get_portfolio_exposure_empty(self, manager):
        """Should handle empty positions list."""
        exposure = manager.get_portfolio_exposure([])

        assert exposure["total_positions"] == 0
        assert exposure["by_symbol"] == {}

    def test_get_portfolio_exposure_multiple_positions(self, manager):
        """Should calculate exposure for multiple positions."""
        positions = [
            make_position("EURUSD", "buy"),
            make_position("GBPUSD", "sell"),
            make_position("USDJPY", "buy"),
        ]

        exposure = manager.get_portfolio_exposure(positions)

        assert exposure["total_positions"] == 3
        assert "EURUSD" in exposure["by_symbol"]
        assert "GBPUSD" in exposure["by_symbol"]
        assert "USDJPY" in exposure["by_symbol"]

    def test_get_portfolio_exposure_includes_currency_breakdown(self, manager):
        """Should include currency breakdown in exposure."""
        positions = [
            make_position("EURUSD", "buy"),  # Long EUR, Short USD
            make_position("USDJPY", "buy"),  # Long USD, Short JPY
        ]

        exposure = manager.get_portfolio_exposure(positions)

        assert "by_currency" in exposure
        assert "long" in exposure["by_currency"]
        assert "short" in exposure["by_currency"]


# ══════════════════════════════════════════════════════════
# EDGE CASES
# ══════════════════════════════════════════════════════════


@pytest.mark.unit
class TestEdgeCases:
    """Edge case tests for CorrelationManager."""

    def test_handles_none_active_positions(self, manager):
        """Should handle None active_positions (treat as empty)."""
        result = manager.check("EURUSD", "buy", active_positions=None)

        assert result.passed is True

    def test_handles_mixed_case_side(self, manager):
        """Should handle mixed case side values."""
        positions = [make_position("EURUSD", "BUY")]

        result = manager.check("EURUSD", "buy", active_positions=positions)

        assert result.passed is False  # Should detect duplicate

    def test_data_param_is_optional(self, manager):
        """data parameter should be optional."""
        result = manager.check("EURUSD", "buy", active_positions=[], data=None)

        assert result.passed is True

    def test_constants_match_expected_values(self):
        """Verify default constants match expected values."""
        assert DEFAULT_MAX_OPEN_POSITIONS == 3

    def test_correlation_groups_defined_correctly(self):
        """Verify correlation groups are properly defined."""
        assert "eur_gbp" in CORRELATION_GROUPS
        assert "precious_metals" in CORRELATION_GROUPS
        assert "us_indices" in CORRELATION_GROUPS

        assert "EURUSD" in CORRELATION_GROUPS["eur_gbp"]
        assert "GBPUSD" in CORRELATION_GROUPS["eur_gbp"]
        assert "XAUUSD" in CORRELATION_GROUPS["precious_metals"]
        assert "US30" in CORRELATION_GROUPS["us_indices"]
