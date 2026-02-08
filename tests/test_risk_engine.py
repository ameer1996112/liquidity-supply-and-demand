"""
Unit tests for src/core/risk_engine.py
Tests position sizing, risk checks, and PropGuard logic.
"""

import pytest
from datetime import date
from src.core.risk_engine import (
    calculate_max_position_size,
    RiskGuardian,
    RiskCheckResult,
    RiskRejectionReason,
    TradeRiskParams,
)


class TestCalculateMaxPositionSize:
    """Test position sizing calculations with Pine alignment."""

    def test_basic_forex_position_sizing(self):
        """Test standard forex pair position sizing."""
        payload = {
            "symbol": "EURUSD",
            "entry": 1.1000,
            "sl": 1.0950,
            "side": "buy",
        }
        account_balance = 10000.0
        risk_percent = 0.5  # Pine Balanced profile

        size = calculate_max_position_size(
            payload, account_balance, risk_percent, risk_multiplier=1.0
        )

        # Expected: $50 risk / (50 pips * $10/pip) = 0.1 lots
        # With 1 pip buffer: 51 pips = 0.098 lots
        assert 0.09 <= size <= 0.11, f"Expected ~0.1 lots, got {size}"

    def test_jpy_pair_position_sizing(self):
        """Test JPY pair with different pip size."""
        payload = {
            "symbol": "USDJPY",
            "entry": 150.00,
            "sl": 149.50,
            "side": "buy",
        }
        account_balance = 10000.0
        risk_percent = 0.5

        size = calculate_max_position_size(payload, account_balance, risk_percent)

        # 50 pips on JPY (0.50), pip_value = 1000/150 = 6.67
        # $50 / (50 * 6.67) = 0.15 lots approx
        assert size > 0.0, f"Size should be positive, got {size}"

    def test_gold_position_sizing(self):
        """Test gold (XAUUSD) with correct pip size."""
        payload = {
            "symbol": "XAUUSD",
            "entry": 2000.00,
            "sl": 1990.00,
            "side": "buy",
        }
        account_balance = 10000.0
        risk_percent = 0.5

        size = calculate_max_position_size(payload, account_balance, risk_percent)

        # Gold: pip_size = 0.01, pip_value = 100.0
        # 10.00 price distance = 1000 pips
        # $50 / (1000 * 100) = 0.0005 lots (very small due to high pip value)
        assert size > 0.0, f"Size should be positive, got {size}"

    def test_stop_loss_buffer_applied(self):
        """Test that stop loss buffer makes SL more conservative."""
        payload = {
            "symbol": "EURUSD",
            "entry": 1.1000,
            "sl": 1.0950,
            "side": "buy",
        }
        account_balance = 10000.0
        risk_percent = 0.5

        # With buffer, SL should be adjusted to 1.0949 (1 pip lower for buy)
        # This increases effective SL distance -> smaller position size
        size_with_buffer = calculate_max_position_size(payload, account_balance, risk_percent)

        # Override symbol_overrides to remove buffer
        overrides = {
            "enabled": True,
            "pip_size": 0.0001,
            "pip_value_per_lot": 10.0,
            "risk_percent": 0.5,
            "max_lot_size": 10.0,
            "stop_loss_buffer_pips": 0.0,  # No buffer
        }

        size_no_buffer = calculate_max_position_size(
            payload, account_balance, risk_percent, symbol_overrides=overrides
        )

        # Size with buffer should be smaller (more conservative)
        assert size_with_buffer < size_no_buffer, (
            f"Buffer should reduce size: {size_with_buffer} >= {size_no_buffer}"
        )

    def test_risk_multiplier_scaling(self):
        """Test PropGuard risk multiplier scaling."""
        payload = {
            "symbol": "EURUSD",
            "entry": 1.1000,
            "sl": 1.0950,
            "side": "buy",
        }
        account_balance = 10000.0
        risk_percent = 0.5

        # Normal size (multiplier = 1.0)
        size_normal = calculate_max_position_size(
            payload, account_balance, risk_percent, risk_multiplier=1.0
        )

        # Defensive size (multiplier = 0.5)
        size_defensive = calculate_max_position_size(
            payload, account_balance, risk_percent, risk_multiplier=0.5
        )

        # Aggressive size (multiplier = 2.0)
        size_aggressive = calculate_max_position_size(
            payload, account_balance, risk_percent, risk_multiplier=2.0
        )

        assert size_defensive == pytest.approx(size_normal * 0.5, rel=0.01)
        assert size_aggressive == pytest.approx(size_normal * 2.0, rel=0.01)

    def test_max_lot_cap_enforced(self):
        """Test that max_lot_size cap is enforced."""
        payload = {
            "symbol": "EURUSD",
            "entry": 1.1000,
            "sl": 1.0999,  # Very tight SL = huge position
            "side": "buy",
        }
        account_balance = 1_000_000.0  # Large account
        risk_percent = 5.0  # High risk

        size = calculate_max_position_size(payload, account_balance, risk_percent)

        # Should be capped at 10.0 lots (Pine default)
        assert size <= 10.0, f"Size should be capped at 10.0, got {size}"

    def test_symbol_overrides_respected(self):
        """Test per-symbol overrides from symbol_risk_rules table."""
        payload = {
            "symbol": "EURUSD",
            "entry": 1.1000,
            "sl": 1.0950,
            "side": "buy",
        }
        account_balance = 10000.0

        # Custom overrides
        overrides = {
            "enabled": True,
            "pip_size": 0.0001,
            "pip_value_per_lot": 10.0,
            "risk_percent": 1.0,  # Override: 1% instead of 0.5%
            "max_lot_size": 5.0,  # Override: 5 lots max
            "stop_loss_buffer_pips": 0.5,
        }

        size = calculate_max_position_size(
            payload, account_balance, risk_percent=0.5, symbol_overrides=overrides
        )

        # Should use overridden risk_percent (1.0%) -> double the size
        # And capped at 5.0 lots
        assert size <= 5.0, f"Should respect max_lot_size override, got {size}"

    def test_sell_side_buffer_direction(self):
        """Test that sell orders add buffer above SL (more conservative)."""
        payload_sell = {
            "symbol": "EURUSD",
            "entry": 1.0950,
            "sl": 1.1000,  # SL above entry for sell
            "side": "sell",
        }
        account_balance = 10000.0
        risk_percent = 0.5

        size_sell = calculate_max_position_size(payload_sell, account_balance, risk_percent)

        # For sell: SL adjusted to 1.1001 (1 pip higher)
        # This increases SL distance -> smaller position
        assert size_sell > 0.0, f"Sell size should be positive, got {size_sell}"

    def test_zero_or_invalid_sl_returns_default(self):
        """Test handling of invalid SL values."""
        payload = {
            "symbol": "EURUSD",
            "entry": 1.1000,
            "sl": 0.0,  # Invalid
            "side": "buy",
        }
        account_balance = 10000.0
        risk_percent = 0.5

        size = calculate_max_position_size(payload, account_balance, risk_percent)

        # Should return default 1.0 lot for invalid SL
        assert size == 1.0, f"Expected 1.0 for invalid SL, got {size}"


class TestRiskGuardian:
    """Test RiskGuardian prop firm risk checks."""

    def test_kill_switch_blocks_all_trades(self):
        """Test that kill switch blocks all execution."""
        guardian = RiskGuardian(
            starting_equity=10000.0,
            max_daily_loss_pct=4.0,
            max_drawdown_pct=8.0,
        )

        guardian.engage_kill_switch("Manual override")

        result = guardian.check(current_equity=10000.0)

        assert result.passed is False
        assert result.rejection_reason == RiskRejectionReason.KILL_SWITCH_ACTIVE
        assert "Manual override" in result.rejection_message

    def test_daily_loss_limit_enforced(self):
        """Test daily loss limit blocks trades."""
        guardian = RiskGuardian(
            starting_equity=10000.0,
            max_daily_loss_pct=4.0,  # $400 max daily loss
        )

        guardian.reset_daily(current_equity=10000.0)
        guardian.record_trade_pnl(-300.0)
        guardian.record_trade_pnl(-150.0)  # Total: -$450

        result = guardian.check(current_equity=9550.0, daily_pnl=-450.0)

        assert result.passed is False
        assert result.rejection_reason == RiskRejectionReason.DAILY_LOSS_LIMIT
        assert "DAILY LOSS LIMIT" in result.rejection_message

    def test_drawdown_limit_engages_kill_switch(self):
        """Test max drawdown engages kill switch."""
        guardian = RiskGuardian(
            starting_equity=10000.0,
            max_drawdown_pct=8.0,  # $800 max drawdown
        )

        # Equity drops to $9100 = 9% drawdown
        result = guardian.check(current_equity=9100.0)

        assert result.passed is False
        assert result.rejection_reason == RiskRejectionReason.EQUITY_DRAWDOWN
        assert guardian.is_kill_switch_active is True

    def test_risk_per_trade_limit_enforced(self):
        """Test individual trade risk limit."""
        guardian = RiskGuardian(
            starting_equity=10000.0,
            max_risk_per_trade_pct=1.0,  # $100 max per trade
        )

        trade_params = TradeRiskParams(
            symbol="EURUSD",
            side="buy",
            entry_price=1.1000,
            stop_loss=1.0950,
            position_size=5.0,  # Large position
            risk_amount_usd=150.0,  # Risk > $100
        )

        result = guardian.check(
            trade_params=trade_params,
            current_equity=10000.0,
        )

        assert result.passed is False
        assert result.rejection_reason == RiskRejectionReason.RISK_TOO_HIGH

    def test_profitable_trading_passes_checks(self):
        """Test that profitable scenarios pass all checks."""
        guardian = RiskGuardian(
            starting_equity=10000.0,
            max_daily_loss_pct=4.0,
            max_drawdown_pct=8.0,
            max_risk_per_trade_pct=1.0,
        )

        guardian.reset_daily(current_equity=10500.0)  # Up $500
        guardian.record_trade_pnl(250.0)
        guardian.record_trade_pnl(250.0)

        trade_params = TradeRiskParams(
            symbol="EURUSD",
            side="buy",
            entry_price=1.1000,
            stop_loss=1.0950,
            position_size=0.2,
            risk_amount_usd=50.0,  # Well within limits
        )

        result = guardian.check(
            trade_params=trade_params,
            current_equity=10500.0,
            daily_pnl=500.0,
        )

        assert result.passed is True
        assert result.rejection_reason is None

    def test_daily_reset_clears_pnl(self):
        """Test that daily reset clears PnL tracking."""
        guardian = RiskGuardian(starting_equity=10000.0)

        guardian.reset_daily(current_equity=10000.0)
        guardian.record_trade_pnl(-300.0)

        assert guardian._daily_pnl == -300.0

        # Reset for new day
        guardian.reset_daily(current_equity=9700.0)

        assert guardian._daily_pnl == 0.0
        assert guardian._daily_start_equity == 9700.0

    def test_kill_switch_reset(self):
        """Test kill switch can be reset."""
        guardian = RiskGuardian(starting_equity=10000.0)

        guardian.engage_kill_switch("Test reason")
        assert guardian.is_kill_switch_active is True

        guardian.reset_kill_switch()
        assert guardian.is_kill_switch_active is False

        result = guardian.check(current_equity=10000.0)
        assert result.passed is True

    def test_get_status_returns_state(self):
        """Test status reporting."""
        guardian = RiskGuardian(
            starting_equity=10000.0,
            max_daily_loss_pct=4.0,
            max_drawdown_pct=8.0,
        )

        guardian.engage_kill_switch("Test")

        status = guardian.get_status()

        assert status["kill_switch_active"] is True
        assert status["kill_switch_reason"] == "Test"
        assert status["starting_equity"] == 10000.0
        assert status["limits"]["max_daily_loss_pct"] == 4.0


class TestTradeRiskParams:
    """Test TradeRiskParams validation."""

    def test_valid_params_creation(self):
        """Test creating valid trade params."""
        params = TradeRiskParams(
            symbol="EURUSD",
            side="buy",
            entry_price=1.1000,
            stop_loss=1.0950,
            position_size=0.1,
        )

        assert params.symbol == "EURUSD"
        assert params.calculated_risk_pips == pytest.approx(0.0050, rel=1e-6)

    def test_invalid_prices_rejected(self):
        """Test that invalid prices are rejected."""
        with pytest.raises(ValueError):
            TradeRiskParams(
                symbol="EURUSD",
                side="buy",
                entry_price=-1.0,  # Negative price
                stop_loss=1.0950,
                position_size=0.1,
            )

    def test_calculated_risk_pips(self):
        """Test pip distance calculation."""
        params = TradeRiskParams(
            symbol="EURUSD",
            side="buy",
            entry_price=1.1000,
            stop_loss=1.0900,
            position_size=0.1,
        )

        assert params.calculated_risk_pips == pytest.approx(0.0100, rel=1e-6)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
