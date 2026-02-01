"""
Unit Tests for Pine Guardian Payload Validation

Tests the PineGuardian class which validates:
1. Signal payload structure (symbol, entry, sl, size)
2. Position size calculations matching Pine Script formulas
3. Daily limits (loss, profit, trade count)
4. Variance threshold for position size mismatch detection

These tests run without network calls.
"""

import pytest
from unittest.mock import patch

from backend.pine_guardian import (
    PineGuardian,
    ValidationResult,
    RejectionReason,
    FOREX_LOT_SIZE,
    GOLD_LOT_SIZE,
    MAX_POSITION_SIZE_LOTS,
    POSITION_SIZE_VARIANCE_THRESHOLD,
)


# ══════════════════════════════════════════════════════════
# FIXTURES
# ══════════════════════════════════════════════════════════


@pytest.fixture
def guardian():
    """Create PineGuardian with default settings."""
    return PineGuardian(
        account_balance=10_000.0,
        risk_per_trade_pct=0.5,
        max_daily_loss_pct=2.0,
        max_daily_profit_pct=5.0,
        max_trades_per_day=2,
        variance_threshold=0.05,  # 5%
    )


@pytest.fixture
def valid_signal():
    """Valid forex signal with appropriate sizing."""
    return {
        "symbol": "EURUSD",
        "entry": 1.0850,
        "sl": 1.0800,  # 50 pips SL
        "tp": 1.0950,
        "size": 0.10,  # 0.10 lots
    }


@pytest.fixture
def gold_signal():
    """Valid gold signal."""
    return {
        "symbol": "XAUUSD",
        "entry": 2000.00,
        "sl": 1995.00,  # $5 SL (500 pips)
        "tp": 2015.00,
        "size": 0.10,
    }


# ══════════════════════════════════════════════════════════
# HELPER FUNCTION TESTS
# ══════════════════════════════════════════════════════════


@pytest.mark.unit
class TestHelperFunctions:
    """Tests for PineGuardian helper functions."""

    def test_get_pip_size_forex(self, guardian):
        """Forex pairs should have 0.0001 pip size."""
        assert guardian.get_pip_size("EURUSD") == 0.0001
        assert guardian.get_pip_size("GBPUSD") == 0.0001

    def test_get_pip_size_jpy(self, guardian):
        """JPY pairs should have 0.01 pip size."""
        assert guardian.get_pip_size("USDJPY") == 0.01
        assert guardian.get_pip_size("EURJPY") == 0.01

    def test_get_pip_size_gold(self, guardian):
        """Gold should have 0.01 pip size."""
        assert guardian.get_pip_size("XAUUSD") == 0.01

    def test_get_pip_size_indices(self, guardian):
        """Indices should have 1.0 pip size."""
        assert guardian.get_pip_size("US30") == 1.0
        assert guardian.get_pip_size("NAS100") == 1.0

    def test_get_contract_size_forex(self, guardian):
        """Forex should have 100,000 unit contract size."""
        size, min_units = guardian.get_contract_size("EURUSD")
        assert size == FOREX_LOT_SIZE
        assert size == 100_000

    def test_get_contract_size_gold(self, guardian):
        """Gold should have 100 oz contract size."""
        size, min_units = guardian.get_contract_size("XAUUSD")
        assert size == GOLD_LOT_SIZE
        assert size == 100

    def test_is_jpy_pair(self, guardian):
        """Should detect JPY pairs correctly."""
        assert guardian.is_jpy_pair("USDJPY") is True
        assert guardian.is_jpy_pair("EURJPY") is True
        assert guardian.is_jpy_pair("EURUSD") is False

    def test_is_usd_quote(self, guardian):
        """Should detect USD quote pairs correctly."""
        assert guardian.is_usd_quote("EURUSD") is True
        assert guardian.is_usd_quote("XAUUSD") is True
        assert guardian.is_usd_quote("USDJPY") is False


# ══════════════════════════════════════════════════════════
# BASIC VALIDATION TESTS
# ══════════════════════════════════════════════════════════


@pytest.mark.unit
class TestBasicValidation:
    """Basic signal validation tests."""

    def test_rejects_missing_symbol(self, guardian):
        """Should reject signal without symbol."""
        signal = {
            "entry": 1.0850,
            "sl": 1.0800,
            "size": 0.10,
        }

        result = guardian.validate_signal(signal)

        assert result.is_valid is False
        assert result.rejection_reason == RejectionReason.INVALID_ENTRY

    def test_rejects_zero_entry(self, guardian):
        """Should reject signal with zero entry price."""
        signal = {
            "symbol": "EURUSD",
            "entry": 0,
            "sl": 1.0800,
            "size": 0.10,
        }

        result = guardian.validate_signal(signal)

        assert result.is_valid is False
        assert result.rejection_reason == RejectionReason.INVALID_ENTRY

    def test_rejects_zero_stop_loss(self, guardian):
        """Should reject signal with zero stop loss."""
        signal = {
            "symbol": "EURUSD",
            "entry": 1.0850,
            "sl": 0,
            "size": 0.10,
        }

        result = guardian.validate_signal(signal)

        assert result.is_valid is False
        assert result.rejection_reason == RejectionReason.INVALID_STOP_LOSS

    def test_rejects_negative_entry(self, guardian):
        """Should reject signal with negative entry price."""
        signal = {
            "symbol": "EURUSD",
            "entry": -1.0850,
            "sl": 1.0800,
            "size": 0.10,
        }

        result = guardian.validate_signal(signal)

        assert result.is_valid is False


# ══════════════════════════════════════════════════════════
# POSITION SIZE CALCULATION TESTS
# ══════════════════════════════════════════════════════════


@pytest.mark.unit
class TestPositionSizeCalculation:
    """Tests for position size calculation logic."""

    def test_calc_pos_size_lots_forex(self, guardian):
        """Should calculate correct lot size for forex."""
        # $10,000 balance, 0.5% risk = $50 risk
        # 50 pip SL, standard forex
        lots = guardian.calc_pos_size_lots(
            entry=1.0850,
            stop=1.0800,  # 50 pips
            balance=10_000.0,
            risk_pct=0.5,
            symbol="EURUSD",
        )

        # Should return a reasonable lot size
        assert lots >= 0.001
        assert lots <= 10.0

    def test_calc_pos_size_lots_gold(self, guardian):
        """Should calculate correct lot size for gold."""
        lots = guardian.calc_pos_size_lots(
            entry=2000.00,
            stop=1995.00,  # $5 / 500 pips
            balance=10_000.0,
            risk_pct=0.5,
            symbol="XAUUSD",
        )

        assert lots >= 0.001
        assert lots <= 10.0

    def test_calc_pos_size_rounds_to_three_decimals(self, guardian):
        """Lot size should be rounded to 0.001."""
        lots = guardian.calc_pos_size_lots(
            entry=1.0850,
            stop=1.0800,
            balance=10_000.0,
            risk_pct=0.5,
            symbol="EURUSD",
        )

        # Check it's rounded to 3 decimal places
        rounded = round(lots * 1000) / 1000
        assert lots == rounded

    def test_calc_pos_size_minimum_lot(self, guardian):
        """Should enforce minimum 0.001 lot size."""
        # Tiny risk should still return minimum lot
        lots = guardian.calc_pos_size_lots(
            entry=1.0850,
            stop=1.0849,  # 1 pip
            balance=100.0,  # Small balance
            risk_pct=0.01,  # Tiny risk
            symbol="EURUSD",
        )

        assert lots >= 0.001


# ══════════════════════════════════════════════════════════
# POSITION SIZE VARIANCE TESTS
# ══════════════════════════════════════════════════════════


@pytest.mark.unit
class TestPositionSizeVariance:
    """Tests for position size variance detection."""

    def test_rejects_position_size_mismatch(self, guardian):
        """Should reject when requested size varies too much from calculated."""
        # Force a mismatch by requesting much larger size than calculated
        signal = {
            "symbol": "EURUSD",
            "entry": 1.0850,
            "sl": 1.0800,
            "size": 5.0,  # Way too large
        }

        result = guardian.validate_signal(signal)

        assert result.is_valid is False
        assert result.rejection_reason == RejectionReason.POSITION_SIZE_MISMATCH

    def test_passes_position_size_within_variance(self, guardian):
        """Should pass when requested size is within variance threshold."""
        # Calculate the expected lot size first
        calculated = guardian.calc_pos_size_lots(
            entry=1.0850,
            stop=1.0800,
            balance=10_000.0,
            risk_pct=0.5,
            symbol="EURUSD",
        )

        # Request within 5% variance
        requested = calculated * 1.03  # 3% variance

        signal = {
            "symbol": "EURUSD",
            "entry": 1.0850,
            "sl": 1.0800,
            "size": requested,
        }

        result = guardian.validate_signal(signal)

        assert result.is_valid is True

    def test_variance_percentage_returned_in_result(self, guardian):
        """Result should include variance percentage."""
        signal = {
            "symbol": "EURUSD",
            "entry": 1.0850,
            "sl": 1.0800,
            "size": 0.10,
        }

        result = guardian.validate_signal(signal)

        assert result.variance_percent is not None
        assert result.calculated_lots is not None
        assert result.requested_lots is not None


# ══════════════════════════════════════════════════════════
# POSITION SIZE LIMITS TESTS
# ══════════════════════════════════════════════════════════


@pytest.mark.unit
class TestPositionSizeLimits:
    """Tests for min/max position size limits."""

    def test_rejects_position_too_large(self, guardian):
        """Should reject positions exceeding MAX_POSITION_SIZE_LOTS."""
        signal = {
            "symbol": "EURUSD",
            "entry": 1.0850,
            "sl": 1.0800,
            "size": 15.0,  # > 10.0 max
        }

        result = guardian.validate_signal(signal)

        assert result.is_valid is False
        assert result.rejection_reason == RejectionReason.POSITION_TOO_LARGE

    def test_max_position_size_is_10_lots(self):
        """Verify MAX_POSITION_SIZE_LOTS constant."""
        assert MAX_POSITION_SIZE_LOTS == 10.0

    def test_variance_threshold_is_5_percent(self):
        """Verify POSITION_SIZE_VARIANCE_THRESHOLD constant."""
        assert POSITION_SIZE_VARIANCE_THRESHOLD == 0.05


# ══════════════════════════════════════════════════════════
# DAILY LIMITS TESTS
# ══════════════════════════════════════════════════════════


@pytest.mark.unit
class TestDailyLimits:
    """Tests for daily limit enforcement."""

    def test_rejects_when_daily_loss_limit_exceeded(self, guardian, valid_signal):
        """Should reject when daily loss exceeds limit."""
        # Set daily start equity and simulate loss
        guardian.daily_start_equity = 10_000.0

        # Validate with balance showing > 2% loss
        result = guardian.validate_signal(valid_signal, current_balance=9_750.0)

        assert result.is_valid is False
        assert result.rejection_reason == RejectionReason.DAILY_LOSS_LIMIT_EXCEEDED

    def test_rejects_when_daily_profit_target_reached(self, guardian, valid_signal):
        """Should reject when daily profit target is reached."""
        guardian.daily_start_equity = 10_000.0

        # Validate with balance showing >= 5% profit
        result = guardian.validate_signal(valid_signal, current_balance=10_500.0)

        assert result.is_valid is False
        assert result.rejection_reason == RejectionReason.DAILY_PROFIT_TARGET_REACHED

    def test_rejects_when_max_trades_exceeded(self, guardian, valid_signal):
        """Should reject when max daily trades exceeded."""
        # Simulate 2 trades already taken
        guardian.current_day_trades = 2

        result = guardian.validate_signal(valid_signal)

        assert result.is_valid is False
        assert result.rejection_reason == RejectionReason.MAX_TRADES_EXCEEDED

    def test_passes_when_below_daily_limits(self, guardian, valid_signal):
        """Should pass when all daily limits are within range."""
        guardian.daily_start_equity = 10_000.0
        guardian.current_day_trades = 0

        # Calculate correct size
        calculated = guardian.calc_pos_size_lots(
            entry=valid_signal["entry"],
            stop=valid_signal["sl"],
            balance=10_000.0,
            risk_pct=0.5,
            symbol=valid_signal["symbol"],
        )
        valid_signal["size"] = calculated

        result = guardian.validate_signal(valid_signal, current_balance=10_000.0)

        assert result.is_valid is True


# ══════════════════════════════════════════════════════════
# 2ND TRADE RISK REDUCTION TESTS
# ══════════════════════════════════════════════════════════


@pytest.mark.unit
class TestSecondTradeRiskReduction:
    """Tests for 2nd trade 50% risk reduction logic."""

    def test_first_trade_uses_full_risk(self, guardian):
        """First trade should use full risk percentage."""
        guardian.current_day_trades = 0

        effective_risk = guardian.get_effective_risk_pct()

        assert effective_risk == 0.5

    def test_second_trade_uses_half_risk(self, guardian):
        """Second trade should use 50% of risk percentage."""
        guardian.current_day_trades = 1

        effective_risk = guardian.get_effective_risk_pct()

        assert effective_risk == 0.25  # 0.5 * 0.5

    def test_risk_reduction_only_when_max_is_2_trades(self):
        """Risk reduction should only apply when max_trades_per_day is 2."""
        guardian = PineGuardian(
            max_trades_per_day=3,  # Not 2
            risk_per_trade_pct=0.5,
        )
        guardian.current_day_trades = 1

        effective_risk = guardian.get_effective_risk_pct()

        # Should NOT reduce because max is not 2
        assert effective_risk == 0.5


# ══════════════════════════════════════════════════════════
# DAILY TRACKING TESTS
# ══════════════════════════════════════════════════════════


@pytest.mark.unit
class TestDailyTracking:
    """Tests for daily tracking functionality."""

    def test_reset_daily_clears_counters(self, guardian):
        """reset_daily() should clear daily counters."""
        guardian.daily_pnl = 500.0
        guardian.current_day_trades = 2

        guardian.reset_daily(current_equity=11_000.0)

        assert guardian.daily_start_equity == 11_000.0
        assert guardian.daily_pnl == 0.0
        assert guardian.current_day_trades == 0

    def test_record_trade_updates_counters(self, guardian):
        """record_trade() should update daily counters."""
        guardian.record_trade(pnl=100.0)

        assert guardian.daily_pnl == 100.0
        assert guardian.current_day_trades == 1

        guardian.record_trade(pnl=-50.0)

        assert guardian.daily_pnl == 50.0
        assert guardian.current_day_trades == 2

    def test_check_daily_loss_limit(self, guardian):
        """check_daily_loss_limit() should return correct boolean."""
        guardian.daily_start_equity = 10_000.0

        # Within limit
        assert guardian.check_daily_loss_limit(9_900.0) is True

        # At limit
        assert guardian.check_daily_loss_limit(9_800.0) is False  # 2% loss

        # Beyond limit
        assert guardian.check_daily_loss_limit(9_700.0) is False

    def test_check_daily_profit_target(self, guardian):
        """check_daily_profit_target() should return correct boolean."""
        guardian.daily_start_equity = 10_000.0

        # Below target
        assert guardian.check_daily_profit_target(10_400.0) is True

        # At target
        assert guardian.check_daily_profit_target(10_500.0) is False  # 5% profit

        # Above target
        assert guardian.check_daily_profit_target(10_600.0) is False

    def test_check_max_trades(self, guardian):
        """check_max_trades() should return correct boolean."""
        guardian.current_day_trades = 0
        assert guardian.check_max_trades() is True

        guardian.current_day_trades = 1
        assert guardian.check_max_trades() is True

        guardian.current_day_trades = 2
        assert guardian.check_max_trades() is False


# ══════════════════════════════════════════════════════════
# VALIDATION RESULT TESTS
# ══════════════════════════════════════════════════════════


@pytest.mark.unit
class TestValidationResult:
    """Tests for ValidationResult structure."""

    def test_valid_result_contains_details(self, guardian):
        """Valid result should contain calculation details."""
        calculated = guardian.calc_pos_size_lots(
            entry=1.0850,
            stop=1.0800,
            balance=10_000.0,
            risk_pct=0.5,
            symbol="EURUSD",
        )

        signal = {
            "symbol": "EURUSD",
            "entry": 1.0850,
            "sl": 1.0800,
            "size": calculated,
        }

        result = guardian.validate_signal(signal)

        assert result.is_valid is True
        assert result.calculated_lots is not None
        assert result.requested_lots is not None
        assert result.variance_percent is not None
        assert result.details is not None

    def test_invalid_result_contains_rejection_reason(self, guardian):
        """Invalid result should contain rejection details."""
        signal = {
            "symbol": "EURUSD",
            "entry": 0,
            "sl": 1.0800,
            "size": 0.10,
        }

        result = guardian.validate_signal(signal)

        assert result.is_valid is False
        assert result.rejection_reason is not None
        assert result.rejection_message is not None


# ══════════════════════════════════════════════════════════
# EDGE CASES
# ══════════════════════════════════════════════════════════


@pytest.mark.unit
class TestEdgeCases:
    """Edge case tests for PineGuardian."""

    def test_handles_empty_symbol(self, guardian):
        """Should handle empty symbol string."""
        signal = {
            "symbol": "",
            "entry": 1.0850,
            "sl": 1.0800,
            "size": 0.10,
        }

        result = guardian.validate_signal(signal)

        assert result.is_valid is False

    def test_handles_very_small_sl_distance(self, guardian):
        """Should handle very small SL distance (uses minimum)."""
        signal = {
            "symbol": "EURUSD",
            "entry": 1.08500,
            "sl": 1.08499,  # 0.1 pip
            "size": 0.10,
        }

        # Should not crash, should use minimum distance
        result = guardian.validate_signal(signal)

        # Result depends on whether size matches calculation
        assert result is not None

    def test_handles_string_numeric_values(self, guardian):
        """Should handle string numeric values in signal."""
        signal = {
            "symbol": "EURUSD",
            "entry": "1.0850",  # String
            "sl": "1.0800",  # String
            "size": "0.10",  # String
        }

        # Should convert strings to floats
        result = guardian.validate_signal(signal)

        # Should not crash
        assert result is not None

    def test_uses_provided_balance(self, guardian):
        """Should use provided balance instead of default."""
        calculated_default = guardian.calc_pos_size_lots(
            entry=1.0850,
            stop=1.0800,
            balance=10_000.0,
            risk_pct=0.5,
            symbol="EURUSD",
        )

        calculated_custom = guardian.calc_pos_size_lots(
            entry=1.0850,
            stop=1.0800,
            balance=20_000.0,  # Double balance
            risk_pct=0.5,
            symbol="EURUSD",
        )

        # Custom balance should result in different (larger) lot size
        assert calculated_custom > calculated_default
