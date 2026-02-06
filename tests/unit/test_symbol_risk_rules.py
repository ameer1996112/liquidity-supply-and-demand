"""
Tests for per-symbol risk rules integration.

Covers:
1. calculate_max_position_size with symbol_overrides
2. Worker _lookup_symbol_overrides and _max_position_size
3. logic.py passing symbol_overrides to risk calc
"""

from unittest.mock import MagicMock, patch

import pytest

from src.core.risk_engine import calculate_max_position_size


# ──────────────────────────────────────────────────────
# 1. Risk engine: symbol_overrides parameter
# ──────────────────────────────────────────────────────


class TestSymbolOverrides:
    """calculate_max_position_size respects symbol_overrides."""

    def test_xauusd_with_overrides(self):
        """XAUUSD: pip_size=0.01, pip_value_per_lot=100, max_lot=1.0."""
        overrides = {
            "symbol": "XAUUSD",
            "pip_size": 0.01,
            "pip_value_per_lot": 100.0,
            "risk_percent": 1.0,
            "max_lot_size": 1.0,
            "enabled": True,
        }
        payload = {"symbol": "XAUUSD", "entry": 2650.00, "sl": 2649.50}
        # SL distance = $0.50 → 50 pips → risk_usd = $100
        # max_lots = $100 / (50 * $100) = 0.02
        result = calculate_max_position_size(
            payload, account_balance=10_000, risk_percent=1.0, symbol_overrides=overrides
        )
        assert result == pytest.approx(0.02, abs=0.005)

    def test_eurusd_with_overrides(self):
        """EURUSD: pip_size=0.0001, pip_value_per_lot=10."""
        overrides = {
            "symbol": "EURUSD",
            "pip_size": 0.0001,
            "pip_value_per_lot": 10.0,
            "risk_percent": 1.0,
            "max_lot_size": 5.0,
            "enabled": True,
        }
        payload = {"symbol": "EURUSD", "entry": 1.0850, "sl": 1.0830}
        # SL = 0.0020 → 20 pips → max_lots = $100 / (20 * $10) = 0.5
        result = calculate_max_position_size(
            payload, account_balance=10_000, risk_percent=1.0, symbol_overrides=overrides
        )
        assert result == pytest.approx(0.5, abs=0.05)

    def test_usdjpy_with_overrides(self):
        """USDJPY: pip_size=0.01, pip_value_per_lot=6.67 (1000/150)."""
        overrides = {
            "symbol": "USDJPY",
            "pip_size": 0.01,
            "pip_value_per_lot": 6.67,
            "risk_percent": 1.0,
            "max_lot_size": 5.0,
            "enabled": True,
        }
        payload = {"symbol": "USDJPY", "entry": 150.00, "sl": 149.50}
        # SL = 0.50 → 50 pips → max_lots = $100 / (50 * $6.67) = 0.30
        result = calculate_max_position_size(
            payload, account_balance=10_000, risk_percent=1.0, symbol_overrides=overrides
        )
        assert result == pytest.approx(0.30, abs=0.05)

    def test_overrides_cap_at_max_lot_size(self):
        """Result is capped by max_lot_size from overrides."""
        overrides = {
            "symbol": "EURUSD",
            "pip_size": 0.0001,
            "pip_value_per_lot": 10.0,
            "risk_percent": 2.0,
            "max_lot_size": 0.1,  # Very tight cap
            "enabled": True,
        }
        payload = {"symbol": "EURUSD", "entry": 1.0850, "sl": 1.0849}
        # SL = 0.0001 → 1 pip → uncapped lots = $200 / (1 * $10) = 20.0
        # Capped to 0.1
        result = calculate_max_position_size(
            payload, account_balance=10_000, risk_percent=1.0, symbol_overrides=overrides
        )
        assert result == 0.1

    def test_overrides_risk_percent_takes_precedence(self):
        """risk_percent in overrides overrides the function parameter."""
        overrides = {
            "symbol": "EURUSD",
            "pip_size": 0.0001,
            "pip_value_per_lot": 10.0,
            "risk_percent": 2.0,  # 2% instead of 1%
            "max_lot_size": 5.0,
            "enabled": True,
        }
        payload = {"symbol": "EURUSD", "entry": 1.0850, "sl": 1.0830}
        # With 2% risk: $200 / (20 pips * $10) = 1.0 lots
        result = calculate_max_position_size(
            payload, account_balance=10_000, risk_percent=1.0, symbol_overrides=overrides
        )
        assert result == pytest.approx(1.0, abs=0.05)

    def test_disabled_overrides_fallback_to_hardcoded(self):
        """When enabled=False, overrides are ignored and hardcoded values are used."""
        overrides = {
            "symbol": "XAUUSD",
            "pip_size": 0.01,
            "pip_value_per_lot": 100.0,
            "risk_percent": 1.0,
            "max_lot_size": 1.0,
            "enabled": False,
        }
        payload = {"symbol": "XAUUSD", "entry": 2650.00, "sl": 2649.50}
        result_with_disabled = calculate_max_position_size(
            payload, account_balance=10_000, risk_percent=1.0, symbol_overrides=overrides
        )
        result_without = calculate_max_position_size(
            payload, account_balance=10_000, risk_percent=1.0, symbol_overrides=None
        )
        assert result_with_disabled == result_without

    def test_none_overrides_backward_compatible(self):
        """Passing symbol_overrides=None uses original hardcoded logic."""
        payload = {"symbol": "EURUSD", "entry": 1.0850, "sl": 1.0830}
        result = calculate_max_position_size(
            payload, account_balance=10_000, risk_percent=1.0, symbol_overrides=None
        )
        # Hardcoded: pip_size=0.0001, pip_value=10 → 20 pips → $100/(20*10) = 0.5
        assert result == pytest.approx(0.5, abs=0.05)


# ──────────────────────────────────────────────────────
# 2. Worker symbol rules lookup
# ──────────────────────────────────────────────────────


class TestWorkerSymbolLookup:
    """Worker _lookup_symbol_overrides queries Supabase."""

    @patch("src.worker.supabase")
    def test_lookup_returns_overrides_when_found(self, mock_sb):
        from src.worker import _lookup_symbol_overrides

        mock_result = MagicMock()
        mock_result.data = [{"symbol": "XAUUSD", "pip_size": 0.01, "enabled": True}]
        mock_sb.table.return_value.select.return_value.eq.return_value.limit.return_value.execute.return_value = (
            mock_result
        )
        result = _lookup_symbol_overrides("XAUUSD")
        assert result is not None
        assert result["symbol"] == "XAUUSD"

    @patch("src.worker.supabase")
    def test_lookup_returns_none_when_not_found(self, mock_sb):
        from src.worker import _lookup_symbol_overrides

        mock_result = MagicMock()
        mock_result.data = []
        mock_sb.table.return_value.select.return_value.eq.return_value.limit.return_value.execute.return_value = (
            mock_result
        )
        result = _lookup_symbol_overrides("UNKNOWN_SYMBOL")
        assert result is None

    def test_lookup_returns_none_without_supabase(self):
        from src.worker import _lookup_symbol_overrides

        with patch("src.worker.supabase", None):
            result = _lookup_symbol_overrides("XAUUSD")
            assert result is None

    @patch("src.worker.supabase")
    def test_lookup_returns_none_on_exception(self, mock_sb):
        from src.worker import _lookup_symbol_overrides

        mock_sb.table.side_effect = Exception("DB error")
        result = _lookup_symbol_overrides("XAUUSD")
        assert result is None
