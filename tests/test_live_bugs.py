"""
Regression tests for production bugs.

1. Risk Rejection: XAUUSD 0.02 lots rejected because balance was stale/zero,
   producing a tiny max_lots (0.0003). With a $10,000 balance and 1% risk,
   calculate_max_position_size must return a sensible lot size.

2. Watchdog Chain Link: orderId != positionId should still resolve correctly.
"""

from unittest.mock import MagicMock, patch

import pytest

from src.core.risk_engine import calculate_max_position_size


# ──────────────────────────────────────────────────────────
# 1. Risk Rejection Reproduction
# ──────────────────────────────────────────────────────────


class TestRiskRejectionBug:
    """Reproduce the bug where XAUUSD 0.02 lots was rejected as 0.0003."""

    def test_xauusd_position_size_with_10k_balance(self):
        """With $10k balance, 1% risk, 50-pip SL on XAUUSD -> allows 0.02 lots.

        XAU pip_size=0.01, pip_value_per_lot=$100.
        SL $0.50 = 50 pips -> max_lots = $100 / (50 * $100) = 0.02
        """
        payload = {
            "symbol": "XAUUSD",
            "entry": 2350.00,
            "sl": 2349.50,  # $0.50 SL = 50 pips at 0.01 pip size
            "tp": 2351.00,
            "side": "buy",
            "size": 0.02,
        }
        max_lots = calculate_max_position_size(
            payload=payload,
            account_balance=10_000.0,
            risk_percent=1.0,
        )
        # $100 risk / (50 pips * $100/pip/lot) = 0.02 lots
        assert max_lots >= 0.01, (
            f"Max lots {max_lots} is too small — stale/zero balance bug"
        )
        assert max_lots >= 0.02, (
            f"Max lots {max_lots} should allow 0.02 lots with 50-pip SL"
        )

    def test_xauusd_zero_balance_returns_tiny_size(self):
        """With zero balance the max lot size should be near zero (the original bug)."""
        payload = {
            "symbol": "XAUUSD",
            "entry": 2350.00,
            "sl": 2349.50,
            "tp": 2351.00,
            "side": "buy",
            "size": 0.02,
        }
        max_lots = calculate_max_position_size(
            payload=payload,
            account_balance=0.0,
            risk_percent=1.0,
        )
        # Zero balance -> zero risk budget -> near-zero lots
        assert max_lots < 0.01, (
            f"Zero balance should yield tiny max_lots, got {max_lots}"
        )

    def test_eurusd_position_size_with_10k_balance(self):
        """Standard FX pair sanity check."""
        payload = {
            "symbol": "EURUSD",
            "entry": 1.0850,
            "sl": 1.0800,
            "tp": 1.0950,
            "side": "buy",
            "size": 0.10,
        }
        max_lots = calculate_max_position_size(
            payload=payload,
            account_balance=10_000.0,
            risk_percent=1.0,
        )
        # $100 risk / (50 pips * $10/pip) = 0.20 lots
        assert max_lots >= 0.10, (
            f"Max lots {max_lots} too small for EURUSD with $10k"
        )

    @patch("src.logic.get_settings")
    @patch("src.logic.get_adapter")
    @patch("src.logic.init_supabase")
    @patch("src.logic.save_alert", return_value=42)
    @patch("src.logic.send_discord")
    @patch("src.logic.send_telegram")
    def test_process_trade_fetches_live_balance(
        self,
        _tg,
        _dc,
        _save,
        _init_sb,
        mock_get_adapter,
        mock_get_settings,
    ):
        """process_trade should call get_account_information on the adapter."""
        from src.logic import process_trade
        from src.adapters.execution.interfaces import ExecutionResult

        # Configure mock settings for live trading
        settings = MagicMock()
        settings.live_trading_enabled = True
        settings.run_mode = "LIVE"
        settings.paper_trading_enabled = False
        settings.paper_auto_execute = False
        settings.paper_symbols = ""
        settings.min_rr_ratio = 1.0
        settings.account_balance = 10_000.0
        settings.risk_percent = 1.0
        settings.execution_mode = "METAAPI"
        settings.volatility_targeting = False
        mock_get_settings.return_value = settings

        # Configure mock adapter with get_account_information
        mock_adapter = MagicMock()
        mock_adapter.get_account_information.return_value = {
            "balance": 10_000.0,
            "equity": 9_800.0,
        }
        mock_adapter.submit_order.return_value = ExecutionResult(
            status="filled",
            broker_order_id="999",
            client_order_id="test",
            message="ok",
        )
        mock_get_adapter.return_value = mock_adapter

        payload = {
            "symbol": "XAUUSD",
            "side": "buy",
            "entry": 2350.00,
            "sl": 2348.00,
            "tp": 2354.00,
            "size": 0.02,
            "zone_id": 1,
            "trade_key": "test-risk-001",
        }
        process_trade(payload, dry_run=False)

        # Adapter should have been asked for fresh balance
        mock_adapter.get_account_information.assert_called_once()

        # Order should have been submitted (not rejected)
        mock_adapter.submit_order.assert_called_once()
        submitted_req = mock_adapter.submit_order.call_args[0][0]
        assert submitted_req.size > 0, "Order size must be positive"
        assert submitted_req.size <= 0.50, "Order size must respect risk cap"


# ──────────────────────────────────────────────────────────
# 2. Watchdog Chain Link
# ──────────────────────────────────────────────────────────


class TestWatchdogChainLink:
    """Verify the chain-link orderId -> positionId lookup handles mismatches."""

    def test_resolve_with_id_mismatch(self, mock_metaapi_history_id_mismatch):
        """orderId=123456 maps to positionId=pos-999; exit deal should still resolve."""
        from src.services.watchdog import TradeWatchdog

        mock_sb = MagicMock()
        wd = TradeWatchdog(supabase_client=mock_sb)

        # Patch _get_client to return the fixture data
        wd._get_client = MagicMock(return_value=mock_metaapi_history_id_mismatch)
        wd.token = "test"
        wd.account_id = "test"

        trade = {"id": 1, "broker_order_id": "123456", "symbol": "EURUSD"}
        wd._resolve_closed_trade(trade, "123456")

        # Should have called Supabase update with resolved PnL
        mock_sb.table.assert_called_with("trading_signals")
        update_call = mock_sb.table("trading_signals").update
        update_call.assert_called_once()
        update_data = update_call.call_args[0][0]
        assert update_data["status"] == "closed"
        assert update_data["outcome"] == "win"  # profit=70 - 0.15 - 0.50 > 0
        assert update_data["pnl_usd"] == pytest.approx(69.35, abs=0.01)

    def test_resolve_with_matching_ids(self, mock_metaapi_history_deals):
        """Standard case: orderId=123456 -> positionId=pos-001, exit found."""
        from src.services.watchdog import TradeWatchdog

        mock_sb = MagicMock()
        wd = TradeWatchdog(supabase_client=mock_sb)
        wd._get_client = MagicMock(return_value=mock_metaapi_history_deals)
        wd.token = "test"
        wd.account_id = "test"

        trade = {"id": 1, "broker_order_id": "123456", "symbol": "EURUSD"}
        wd._resolve_closed_trade(trade, "123456")

        mock_sb.table.assert_called_with("trading_signals")
        update_call = mock_sb.table("trading_signals").update
        update_call.assert_called_once()
        update_data = update_call.call_args[0][0]
        assert update_data["status"] == "closed"
        assert update_data["outcome"] == "win"
        # profit=100 + swap=-0.25 + commission=-0.50 = 99.25
        assert update_data["pnl_usd"] == pytest.approx(99.25, abs=0.01)

    def test_resolve_no_exit_deal(self, mock_metaapi_history_no_exit):
        """If position has no exit deal yet, watchdog should skip (not crash)."""
        from src.services.watchdog import TradeWatchdog

        mock_sb = MagicMock()
        wd = TradeWatchdog(supabase_client=mock_sb)
        wd._get_client = MagicMock(return_value=mock_metaapi_history_no_exit)
        wd.token = "test"
        wd.account_id = "test"

        trade = {"id": 1, "broker_order_id": "123456", "symbol": "EURUSD"}
        wd._resolve_closed_trade(trade, "123456")

        # Should NOT have updated Supabase (no exit deal found)
        mock_sb.table("trading_signals").update.assert_not_called()
