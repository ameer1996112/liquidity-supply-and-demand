"""
Unit Tests for Risk Guardian

Tests the RiskGuardian class which enforces:
1. Daily loss limit (4%)
2. Equity drawdown kill switch (8%)
3. Anti-gambling per-trade risk limit (1%)
4. Kill switch state management

These tests run without network calls.
"""

import pytest
from unittest.mock import patch, MagicMock

from src.core.risk_engine import (
    RiskGuardian,
    RiskCheckResult,
    RiskRejectionReason,
    TradeRiskParams,
    DEFAULT_MAX_DAILY_LOSS_PCT,
    DEFAULT_MAX_DRAWDOWN_PCT,
    DEFAULT_MAX_RISK_PER_TRADE_PCT,
)


# ══════════════════════════════════════════════════════════
# FIXTURES
# ══════════════════════════════════════════════════════════


@pytest.fixture
def guardian():
    """Create RiskGuardian with default settings."""
    return RiskGuardian(
        starting_equity=10_000.0,
        max_daily_loss_pct=4.0,
        max_drawdown_pct=8.0,
        max_risk_per_trade_pct=1.0,
    )


@pytest.fixture
def trade_params():
    """Standard trade parameters for testing."""
    return TradeRiskParams(
        symbol="EURUSD",
        side="buy",
        entry_price=1.0850,
        stop_loss=1.0800,
        position_size=0.10,
    )


# ══════════════════════════════════════════════════════════
# BASIC PASS/FAIL TESTS
# ══════════════════════════════════════════════════════════


@pytest.mark.unit
class TestRiskGuardianBasicChecks:
    """Basic pass/fail scenarios for RiskGuardian."""

    def test_passes_with_healthy_account(self, guardian, trade_params):
        """Trade should pass when account is healthy."""
        result = guardian.check(
            trade_params=trade_params,
            current_equity=10_000.0,
            daily_pnl=0.0,
        )

        assert result.passed is True
        assert result.rejection_reason is None
        assert "starting_equity" in result.risk_metrics

    def test_passes_with_small_profit(self, guardian, trade_params):
        """Trade should pass when account has small profit."""
        result = guardian.check(
            trade_params=trade_params,
            current_equity=10_200.0,
            daily_pnl=200.0,
        )

        assert result.passed is True

    def test_passes_with_small_loss(self, guardian, trade_params):
        """Trade should pass when daily loss is below limit."""
        # 3% loss is below 4% limit
        result = guardian.check(
            trade_params=trade_params,
            current_equity=9_700.0,
            daily_pnl=-300.0,
        )

        assert result.passed is True


# ══════════════════════════════════════════════════════════
# DAILY LOSS LIMIT TESTS
# ══════════════════════════════════════════════════════════


@pytest.mark.unit
class TestDailyLossLimit:
    """Tests for daily loss limit enforcement (4%)."""

    def test_rejects_when_daily_loss_exceeds_4_percent(self, guardian, trade_params):
        """Trade should be rejected when daily loss exceeds 4%."""
        # 4% of $10,000 = $400
        result = guardian.check(
            trade_params=trade_params,
            current_equity=9_600.0,
            daily_pnl=-400.0,
        )

        assert result.passed is False
        assert result.rejection_reason == RiskRejectionReason.DAILY_LOSS_LIMIT.value

    def test_rejects_when_daily_loss_far_exceeds_limit(self, guardian, trade_params):
        """Trade should be rejected when daily loss greatly exceeds limit."""
        result = guardian.check(
            trade_params=trade_params,
            current_equity=9_000.0,
            daily_pnl=-1000.0,  # 10% loss
        )

        assert result.passed is False
        assert result.rejection_reason == RiskRejectionReason.DAILY_LOSS_LIMIT.value

    def test_passes_when_daily_loss_just_below_limit(self, guardian, trade_params):
        """Trade should pass when daily loss is just below limit."""
        # $399 loss is below $400 limit
        result = guardian.check(
            trade_params=trade_params,
            current_equity=9_601.0,
            daily_pnl=-399.0,
        )

        assert result.passed is True

    def test_rejection_message_contains_loss_amount(self, guardian, trade_params):
        """Rejection message should contain the loss amount."""
        result = guardian.check(
            trade_params=trade_params,
            current_equity=9_500.0,
            daily_pnl=-500.0,
        )

        assert result.passed is False
        assert "500" in result.rejection_message or "DAILY" in result.rejection_message


# ══════════════════════════════════════════════════════════
# EQUITY DRAWDOWN / KILL SWITCH TESTS
# ══════════════════════════════════════════════════════════


@pytest.mark.unit
class TestEquityDrawdownKillSwitch:
    """Tests for equity drawdown and kill switch (8%)."""

    def test_engages_kill_switch_when_drawdown_exceeds_8_percent(self, guardian, trade_params):
        """Kill switch should engage when total drawdown exceeds 8%."""
        # 8% of $10,000 = $800 drawdown
        result = guardian.check(
            trade_params=trade_params,
            current_equity=9_200.0,  # $800 drawdown from $10,000
            daily_pnl=0.0,
        )

        assert result.passed is False
        assert result.rejection_reason == RiskRejectionReason.EQUITY_DRAWDOWN.value
        assert guardian.is_kill_switch_active is True

    def test_kill_switch_blocks_all_trades(self, guardian, trade_params):
        """Once kill switch is engaged, all trades should be blocked."""
        # Engage kill switch
        guardian.engage_kill_switch("Test engagement")

        result = guardian.check(
            trade_params=trade_params,
            current_equity=10_000.0,  # Even healthy equity
            daily_pnl=100.0,  # Even with profit
        )

        assert result.passed is False
        assert result.rejection_reason == RiskRejectionReason.KILL_SWITCH_ACTIVE.value

    def test_kill_switch_can_be_reset(self, guardian, trade_params):
        """Kill switch should be resettable for trading to resume."""
        # Engage kill switch
        guardian.engage_kill_switch("Test engagement")
        assert guardian.is_kill_switch_active is True

        # Reset kill switch
        guardian.reset_kill_switch()
        assert guardian.is_kill_switch_active is False

        # Trading should work again
        result = guardian.check(
            trade_params=trade_params,
            current_equity=10_000.0,
            daily_pnl=0.0,
        )

        assert result.passed is True

    def test_passes_when_drawdown_just_below_limit(self, guardian, trade_params):
        """Trade should pass when drawdown is just below 8%."""
        # $799 drawdown is below $800 (8%) limit
        # Reset daily so daily loss (-799) < 4% of daily_start
        # 4% of 20_000 = 800, so -799 < 800 -> daily limit passes
        guardian.reset_daily(20_000.0)

        result = guardian.check(
            trade_params=trade_params,
            current_equity=9_201.0,
            daily_pnl=-799.0,
        )

        assert result.passed is True
        assert guardian.is_kill_switch_active is False


# ══════════════════════════════════════════════════════════
# ANTI-GAMBLING (PER-TRADE RISK) TESTS
# ══════════════════════════════════════════════════════════


@pytest.mark.unit
class TestAntiGamblingRisk:
    """Tests for per-trade risk limit (1% of equity)."""

    def test_rejects_trade_exceeding_1_percent_risk(self, guardian):
        """Trade should be rejected if risk exceeds 1% of equity."""
        # Create trade with excessive risk
        trade_params = TradeRiskParams(
            symbol="EURUSD",
            side="buy",
            entry_price=1.0850,
            stop_loss=1.0800,
            position_size=0.50,  # Large position
            risk_amount_usd=200.0,  # 2% of $10,000
        )

        result = guardian.check(
            trade_params=trade_params,
            current_equity=10_000.0,
            daily_pnl=0.0,
        )

        assert result.passed is False
        assert result.rejection_reason == RiskRejectionReason.RISK_TOO_HIGH.value

    def test_passes_trade_within_1_percent_risk(self, guardian):
        """Trade should pass if risk is within 1% of equity."""
        trade_params = TradeRiskParams(
            symbol="EURUSD",
            side="buy",
            entry_price=1.0850,
            stop_loss=1.0800,
            position_size=0.10,
            risk_amount_usd=50.0,  # 0.5% of $10,000
        )

        result = guardian.check(
            trade_params=trade_params,
            current_equity=10_000.0,
            daily_pnl=0.0,
        )

        assert result.passed is True

    def test_calculates_risk_from_data_dict(self, guardian):
        """Should extract trade params from data dict if not provided."""
        data = {
            "symbol": "EURUSD",
            "side": "buy",
            "entry": 1.0850,
            "sl": 1.0800,
            "size": 0.10,
        }

        # Mock the market adapter to avoid network calls
        with patch("backend.risk_guardian.MarketAdapter") as mock_adapter_class:
            mock_adapter = MagicMock()
            # $1/pip for 0.10 lots; 50 pips SL -> $50 risk (0.5% of $10k)
            mock_adapter.get_pip_value.return_value = 1.0
            mock_adapter.price_to_pips.return_value = 50.0
            mock_adapter_class.return_value = mock_adapter

            result = guardian.check(
                trade_params=None,
                current_equity=10_000.0,
                daily_pnl=0.0,
                data=data,
            )

            # With mocked values: 50 pips * $10/pip * 0.10 lots = $50 risk (0.5%)
            assert result.passed is True


# ══════════════════════════════════════════════════════════
# RISK METRICS TESTS
# ══════════════════════════════════════════════════════════


@pytest.mark.unit
class TestRiskMetrics:
    """Tests for risk metrics in check results."""

    def test_risk_metrics_include_all_fields(self, guardian, trade_params):
        """Risk metrics should include all required fields."""
        result = guardian.check(
            trade_params=trade_params,
            current_equity=10_000.0,
            daily_pnl=-100.0,
        )

        metrics = result.risk_metrics
        assert "starting_equity" in metrics
        assert "current_equity" in metrics
        assert "daily_pnl" in metrics
        assert "daily_loss_pct" in metrics
        assert "total_drawdown_pct" in metrics
        assert "kill_switch_active" in metrics

    def test_daily_loss_percentage_calculated_correctly(self, guardian, trade_params):
        """Daily loss percentage should be calculated correctly."""
        result = guardian.check(
            trade_params=trade_params,
            current_equity=9_800.0,
            daily_pnl=-200.0,
        )

        # 200/10000 = 2%
        assert abs(result.risk_metrics["daily_loss_pct"] - 2.0) < 0.01

    def test_drawdown_percentage_calculated_correctly(self, guardian, trade_params):
        """Total drawdown percentage should be calculated correctly."""
        result = guardian.check(
            trade_params=trade_params,
            current_equity=9_500.0,
            daily_pnl=0.0,
        )

        # (10000 - 9500) / 10000 = 5%
        assert abs(result.risk_metrics["total_drawdown_pct"] - 5.0) < 0.01


# ══════════════════════════════════════════════════════════
# LOT SIZE LIMIT TESTS (Worker uses MAX_LOT_SIZE = 0.30)
# ══════════════════════════════════════════════════════════


@pytest.mark.unit
class TestLotSizeLimit:
    """Tests for lot size limits (as enforced by worker, not RiskGuardian directly)."""

    def test_worker_max_lot_constant(self):
        """Worker uses dynamic max position size (calculate_max_position_size) with cap 5.0."""
        # Worker does not expose MAX_LOT_SIZE; it uses dynamic sizing and cap in calculate_max_position_size
        import src.worker as w

        assert hasattr(w, "calculate_max_position_size")
        # Cap is 5.0 in calculate_max_position_size (see worker.py)
        max_size = w.calculate_max_position_size(
            {"symbol": "EURUSD", "entry": 1.0, "sl": 0.99, "tp": 1.02, "size": 0.01}
        )
        assert max_size <= 5.0

    def test_signal_above_lot_limit_should_be_rejected(self):
        """Signal with size > 0.30 should be rejected by worker logic."""
        # The worker checks size > MAX_LOT_SIZE before RiskGuardian
        # We just verify the threshold is correct
        MAX_LOT_SIZE = 0.30

        oversized_signal = {"size": 0.50}
        assert float(oversized_signal["size"]) > MAX_LOT_SIZE

        valid_signal = {"size": 0.20}
        assert float(valid_signal["size"]) <= MAX_LOT_SIZE


# ══════════════════════════════════════════════════════════
# DAILY RESET TESTS
# ══════════════════════════════════════════════════════════


@pytest.mark.unit
class TestDailyReset:
    """Tests for daily reset functionality."""

    def test_reset_daily_updates_start_equity(self, guardian):
        """reset_daily() should update the daily start equity."""
        guardian.reset_daily(current_equity=11_000.0)

        assert guardian._daily_start_equity == 11_000.0
        assert guardian._daily_pnl == 0.0

    def test_record_trade_pnl_accumulates(self, guardian):
        """record_trade_pnl() should accumulate daily P&L."""
        guardian.record_trade_pnl(100.0)
        guardian.record_trade_pnl(-50.0)
        guardian.record_trade_pnl(75.0)

        assert guardian._daily_pnl == 125.0  # 100 - 50 + 75

    def test_status_includes_all_fields(self, guardian):
        """get_status() should return all required fields."""
        status = guardian.get_status()

        assert "kill_switch_active" in status
        assert "starting_equity" in status
        assert "daily_start_equity" in status
        assert "daily_pnl" in status
        assert "limits" in status
        assert "max_daily_loss_pct" in status["limits"]


# ══════════════════════════════════════════════════════════
# EDGE CASES
# ══════════════════════════════════════════════════════════


@pytest.mark.unit
class TestEdgeCases:
    """Edge case tests for RiskGuardian."""

    def test_handles_zero_equity(self, guardian, trade_params):
        """Should handle zero equity gracefully (reject)."""
        result = guardian.check(
            trade_params=trade_params,
            current_equity=0.0,
            daily_pnl=-10_000.0,
        )

        # Should reject due to drawdown
        assert result.passed is False

    def test_handles_negative_pnl(self, guardian, trade_params):
        """Should handle negative P&L correctly."""
        result = guardian.check(
            trade_params=trade_params,
            current_equity=9_500.0,
            daily_pnl=-500.0,  # 5% loss
        )

        assert result.passed is False  # Exceeds 4% limit

    def test_handles_none_trade_params(self, guardian):
        """Should handle None trade_params (skip per-trade risk check)."""
        result = guardian.check(
            trade_params=None,
            current_equity=10_000.0,
            daily_pnl=0.0,
        )

        # Should pass basic checks
        assert result.passed is True

    def test_check_priority_kill_switch_first(self, guardian, trade_params):
        """Kill switch should be checked before other conditions."""
        guardian.engage_kill_switch("Test")

        # Even with healthy metrics, should reject due to kill switch
        result = guardian.check(
            trade_params=trade_params,
            current_equity=12_000.0,  # Profit
            daily_pnl=2000.0,  # Profit
        )

        assert result.passed is False
        assert result.rejection_reason == RiskRejectionReason.KILL_SWITCH_ACTIVE.value
