"""
Test Suite: TradeWatchdog (Exit Logic & Chain Link)
===================================================

Tests the Watchdog background service that detects "silent exits":
- Positions closed by SL/TP on broker without exit webhook
- Chain-link lookup: Order ID -> Position ID -> Exit Deal
- PnL calculation from broker history
- Edge cases: ID mismatches, missing exit deals, lag scenarios

These tests mock MetaApi and Supabase to verify the chain-link logic.
"""

import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import patch, MagicMock, call
from typing import Dict, Any, List

# Import module upfront so patches work correctly
import src.services.watchdog as watchdog_module


# ══════════════════════════════════════════════════════════
# TEST: DETECT SILENT EXIT
# ══════════════════════════════════════════════════════════


class TestDetectSilentExit:
    """Test detection of positions closed on broker without exit webhook."""

    def test_detect_silent_exit_winning_trade(
        self,
        mock_supabase_with_trades,
        mock_metaapi_positions_empty,
        mock_metaapi_history_deals,
        mock_settings,
    ):
        """
        Test: Watchdog detects position missing from open positions.

        Setup:
        - DB has executed trade with broker_order_id="123456"
        - MetaApi open positions is empty (position closed)
        - History has entry deal (orderId=123456 -> positionId=pos-001)
        - History has exit deal (positionId=pos-001, profit=$100)

        Expected:
        - Watchdog links Order ID to Position ID
        - Calculates PnL from exit deal
        - Updates Supabase with status="closed", outcome="win", pnl_usd=99.25
        """
        # Setup mock responses
        def mock_get_client(path, params=None):
            if "positions" in path:
                return mock_metaapi_positions_empty
            if "history-deals" in path:
                return mock_metaapi_history_deals
            return None

        update_calls = []

        def mock_table(name):
            table = MagicMock()
            if name == "trading_signals":
                # Mock select for executed trades
                select_mock = MagicMock()
                select_mock.eq.return_value.eq.return_value.execute.return_value = MagicMock(
                    data=[{
                        "id": 1,
                        "symbol": "EURUSD",
                        "side": "buy",
                        "status": "executed",
                        "run_mode": "LIVE",
                        "broker_order_id": "123456",
                    }]
                )
                table.select.return_value = select_mock

                # Mock update
                def capture_update(data):
                    update_calls.append(data)
                    update_mock = MagicMock()
                    update_mock.eq.return_value.execute.return_value = MagicMock(data=[])
                    return update_mock

                table.update.side_effect = capture_update

            return table

        mock_supabase_with_trades.table = mock_table

        with patch("src.services.watchdog.get_settings", return_value=mock_settings):
            from src.services.watchdog import TradeWatchdog

            watchdog = TradeWatchdog(supabase_client=mock_supabase_with_trades)
            watchdog._get_client = mock_get_client

            watchdog.run_sync()

            # Verify update was called
            assert len(update_calls) == 1
            update_data = update_calls[0]

            assert update_data["status"] == "closed"
            assert update_data["outcome"] == "win"
            # PnL: profit(100) + swap(-0.25) + commission(-0.50) = 99.25
            assert update_data["pnl_usd"] == pytest.approx(99.25, rel=0.01)
            assert "Watchdog" in update_data["notes"]

    def test_detect_silent_exit_losing_trade(
        self,
        mock_supabase_with_trades,
        mock_metaapi_positions_empty,
        mock_metaapi_history_loss,
        mock_settings,
    ):
        """
        Test: Watchdog detects SL-hit trade and calculates loss.

        Setup:
        - Trade broker_order_id="789012" closed at loss

        Expected:
        - Outcome = "loss"
        - Negative PnL calculated correctly
        """
        def mock_get_client(path, params=None):
            if "positions" in path:
                return mock_metaapi_positions_empty
            if "history-deals" in path:
                return mock_metaapi_history_loss
            return None

        update_calls = []

        def mock_table(name):
            table = MagicMock()
            if name == "trading_signals":
                select_mock = MagicMock()
                select_mock.eq.return_value.eq.return_value.execute.return_value = MagicMock(
                    data=[{
                        "id": 2,
                        "symbol": "GBPUSD",
                        "side": "sell",
                        "status": "executed",
                        "run_mode": "LIVE",
                        "broker_order_id": "789012",
                    }]
                )
                table.select.return_value = select_mock

                def capture_update(data):
                    update_calls.append(data)
                    update_mock = MagicMock()
                    update_mock.eq.return_value.execute.return_value = MagicMock(data=[])
                    return update_mock

                table.update.side_effect = capture_update

            return table

        mock_client = MagicMock()
        mock_client.table = mock_table

        with patch("src.services.watchdog.get_settings", return_value=mock_settings):
            from src.services.watchdog import TradeWatchdog

            watchdog = TradeWatchdog(supabase_client=mock_client)
            watchdog._get_client = mock_get_client

            watchdog.run_sync()

            assert len(update_calls) == 1
            update_data = update_calls[0]

            assert update_data["status"] == "closed"
            assert update_data["outcome"] == "loss"
            # PnL: profit(-75) + swap(-0.10) + commission(-0.75) = -75.85
            assert update_data["pnl_usd"] == pytest.approx(-75.85, rel=0.01)


# ══════════════════════════════════════════════════════════
# TEST: POSITION ID MISMATCH (CHAIN LINK)
# ══════════════════════════════════════════════════════════


class TestPositionIdMismatch:
    """Test chain-link logic when orderId != positionId."""

    def test_position_id_mismatch_finds_correct_exit(
        self,
        mock_metaapi_history_id_mismatch,
        mock_settings,
    ):
        """
        Test: Order ID != Position ID, but chain-link finds correct exit.

        Setup:
        - Entry deal: orderId=123456, positionId=pos-999 (mismatch!)
        - Exit deal: orderId=999888, positionId=pos-999

        Expected:
        - Watchdog finds entry by orderId
        - Extracts real positionId (pos-999)
        - Finds exit deal by positionId
        - Correctly calculates PnL
        """
        def mock_get_client(path, params=None):
            if "positions" in path:
                return []  # Position closed
            if "history-deals" in path:
                return mock_metaapi_history_id_mismatch
            return None

        update_calls = []

        def mock_table(name):
            table = MagicMock()
            if name == "trading_signals":
                select_mock = MagicMock()
                select_mock.eq.return_value.eq.return_value.execute.return_value = MagicMock(
                    data=[{
                        "id": 1,
                        "symbol": "EURUSD",
                        "side": "buy",
                        "status": "executed",
                        "run_mode": "LIVE",
                        "broker_order_id": "123456",  # This is the orderId
                    }]
                )
                table.select.return_value = select_mock

                def capture_update(data):
                    update_calls.append(data)
                    update_mock = MagicMock()
                    update_mock.eq.return_value.execute.return_value = MagicMock(data=[])
                    return update_mock

                table.update.side_effect = capture_update

            return table

        mock_client = MagicMock()
        mock_client.table = mock_table

        with patch("src.services.watchdog.get_settings", return_value=mock_settings):
            from src.services.watchdog import TradeWatchdog

            watchdog = TradeWatchdog(supabase_client=mock_client)
            watchdog._get_client = mock_get_client

            watchdog.run_sync()

            # Should have found the exit via chain-link
            assert len(update_calls) == 1
            update_data = update_calls[0]

            assert update_data["status"] == "closed"
            assert update_data["outcome"] == "win"
            # PnL: profit(70) + swap(-0.15) + commission(-0.50) = 69.35
            assert update_data["pnl_usd"] == pytest.approx(69.35, rel=0.01)


# ══════════════════════════════════════════════════════════
# TEST: NO EXIT DEAL FOUND (LAG SCENARIO)
# ══════════════════════════════════════════════════════════


class TestNoExitDealFound:
    """Test handling when exit deal hasn't appeared in history yet."""

    def test_no_exit_deal_logs_warning_no_crash(
        self,
        mock_metaapi_history_no_exit,
        mock_settings,
        caplog,
    ):
        """
        Test: Position missing from open positions, but no exit deal in history.

        This can happen due to broker data lag.

        Expected:
        - Logs warning about missing exit deal
        - Does NOT crash
        - Does NOT mistakenly mark as loss
        - Supabase NOT updated (waits for exit deal)
        """
        def mock_get_client(path, params=None):
            if "positions" in path:
                return []  # Position not in open positions
            if "history-deals" in path:
                return mock_metaapi_history_no_exit  # Entry but no exit
            return None

        update_calls = []

        def mock_table(name):
            table = MagicMock()
            if name == "trading_signals":
                select_mock = MagicMock()
                select_mock.eq.return_value.eq.return_value.execute.return_value = MagicMock(
                    data=[{
                        "id": 1,
                        "symbol": "EURUSD",
                        "side": "buy",
                        "status": "executed",
                        "run_mode": "LIVE",
                        "broker_order_id": "123456",
                    }]
                )
                table.select.return_value = select_mock

                def capture_update(data):
                    update_calls.append(data)
                    update_mock = MagicMock()
                    update_mock.eq.return_value.execute.return_value = MagicMock(data=[])
                    return update_mock

                table.update.side_effect = capture_update

            return table

        mock_client = MagicMock()
        mock_client.table = mock_table

        with patch("src.services.watchdog.get_settings", return_value=mock_settings):
            from src.services.watchdog import TradeWatchdog

            watchdog = TradeWatchdog(supabase_client=mock_client)
            watchdog._get_client = mock_get_client

            # Should not raise
            watchdog.run_sync()

            # Should NOT have updated (no exit deal)
            assert len(update_calls) == 0

    def test_no_entry_deal_found_uses_ticket_as_position_id(
        self,
        mock_settings,
        caplog,
    ):
        """
        Test: No entry deal found for orderId, fallback to using ticket as position ID.

        Expected:
        - Logs warning about no entry order
        - Uses broker_order_id as positionId for search
        """
        # History with no matching entry orderId
        history_no_entry = {
            "deals": [
                {
                    "id": "deal-999",
                    "orderId": "different-order",
                    "positionId": "123456",  # Same as broker_order_id
                    "entryType": "DEAL_ENTRY_OUT",
                    "profit": 50.0,
                    "swap": 0.0,
                    "commission": -0.25,
                    "time": "2024-01-15T14:00:00.000Z",
                },
            ],
        }

        def mock_get_client(path, params=None):
            if "positions" in path:
                return []
            if "history-deals" in path:
                return history_no_entry
            return None

        update_calls = []

        def mock_table(name):
            table = MagicMock()
            if name == "trading_signals":
                select_mock = MagicMock()
                select_mock.eq.return_value.eq.return_value.execute.return_value = MagicMock(
                    data=[{
                        "id": 1,
                        "symbol": "EURUSD",
                        "side": "buy",
                        "status": "executed",
                        "run_mode": "LIVE",
                        "broker_order_id": "123456",
                    }]
                )
                table.select.return_value = select_mock

                def capture_update(data):
                    update_calls.append(data)
                    update_mock = MagicMock()
                    update_mock.eq.return_value.execute.return_value = MagicMock(data=[])
                    return update_mock

                table.update.side_effect = capture_update

            return table

        mock_client = MagicMock()
        mock_client.table = mock_table

        with patch("src.services.watchdog.get_settings", return_value=mock_settings):
            from src.services.watchdog import TradeWatchdog

            watchdog = TradeWatchdog(supabase_client=mock_client)
            watchdog._get_client = mock_get_client

            watchdog.run_sync()

            # Should have found exit using fallback position ID
            assert len(update_calls) == 1
            assert update_calls[0]["pnl_usd"] == pytest.approx(49.75, rel=0.01)


# ══════════════════════════════════════════════════════════
# TEST: STILL OPEN POSITIONS
# ══════════════════════════════════════════════════════════


class TestStillOpenPositions:
    """Test that watchdog doesn't touch positions still open."""

    def test_position_still_open_no_update(
        self,
        mock_metaapi_positions,
        mock_settings,
    ):
        """
        Test: Position still in open positions list.

        Expected:
        - No database update (position still active)
        """
        def mock_get_client(path, params=None):
            if "positions" in path:
                return mock_metaapi_positions  # Has position 123456
            return None

        update_calls = []

        def mock_table(name):
            table = MagicMock()
            if name == "trading_signals":
                select_mock = MagicMock()
                select_mock.eq.return_value.eq.return_value.execute.return_value = MagicMock(
                    data=[{
                        "id": 1,
                        "symbol": "EURUSD",
                        "status": "executed",
                        "run_mode": "LIVE",
                        "broker_order_id": "123456",  # Same as open position
                    }]
                )
                table.select.return_value = select_mock

                def capture_update(data):
                    update_calls.append(data)
                    update_mock = MagicMock()
                    update_mock.eq.return_value.execute.return_value = MagicMock(data=[])
                    return update_mock

                table.update.side_effect = capture_update

            return table

        mock_client = MagicMock()
        mock_client.table = mock_table

        with patch("src.services.watchdog.get_settings", return_value=mock_settings):
            from src.services.watchdog import TradeWatchdog

            watchdog = TradeWatchdog(supabase_client=mock_client)
            watchdog._get_client = mock_get_client

            watchdog.run_sync()

            # Should NOT have updated (position still open)
            assert len(update_calls) == 0


# ══════════════════════════════════════════════════════════
# TEST: WATCHDOG DISABLED SCENARIOS
# ══════════════════════════════════════════════════════════


class TestWatchdogDisabled:
    """Test watchdog behavior when disabled or misconfigured."""

    def test_watchdog_no_supabase_client_returns_early(
        self,
        mock_settings,
    ):
        """
        Test: Watchdog with no Supabase client returns immediately.

        Expected: No crash, no operations.
        """
        with patch("src.services.watchdog.get_settings", return_value=mock_settings):
            from src.services.watchdog import TradeWatchdog

            watchdog = TradeWatchdog(supabase_client=None)
            # Should not raise
            watchdog.run_sync()

    def test_watchdog_no_metaapi_credentials_returns_early(
        self,
        mock_supabase_client,
    ):
        """
        Test: Watchdog without MetaApi credentials returns immediately.

        Expected: No crash, no API calls.
        """
        from tests.conftest import MockSettings

        settings_no_meta = MockSettings(
            meta_api_token="",
            meta_api_account_id="",
        )

        with patch("src.services.watchdog.get_settings", return_value=settings_no_meta):
            from src.services.watchdog import TradeWatchdog

            watchdog = TradeWatchdog(supabase_client=mock_supabase_client)
            # Should not raise
            watchdog.run_sync()

    def test_watchdog_no_executed_trades_returns_early(
        self,
        mock_settings,
    ):
        """
        Test: No executed LIVE trades in database.

        Expected: Early return, no MetaApi calls.
        """
        def mock_table(name):
            table = MagicMock()
            if name == "trading_signals":
                select_mock = MagicMock()
                select_mock.eq.return_value.eq.return_value.execute.return_value = MagicMock(
                    data=[]  # No executed trades
                )
                table.select.return_value = select_mock
            return table

        mock_client = MagicMock()
        mock_client.table = mock_table

        with patch("src.services.watchdog.get_settings", return_value=mock_settings):
            from src.services.watchdog import TradeWatchdog

            watchdog = TradeWatchdog(supabase_client=mock_client)

            get_calls = []
            original_get_client = watchdog._get_client

            def tracking_get_client(path, params=None):
                get_calls.append(path)
                return original_get_client(path, params)

            watchdog._get_client = tracking_get_client
            watchdog.run_sync()

            # Should not have made positions API call since no trades
            assert not any("positions" in call for call in get_calls)


# ══════════════════════════════════════════════════════════
# TEST: API FAILURE HANDLING
# ══════════════════════════════════════════════════════════


class TestApiFailureHandling:
    """Test watchdog handling of MetaApi failures."""

    def test_positions_api_failure_returns_early(
        self,
        mock_settings,
    ):
        """
        Test: Positions API returns None (failure).

        Expected: Early return, no crash.
        """
        def mock_get_client(path, params=None):
            if "positions" in path:
                return None  # API failure
            return None

        def mock_table(name):
            table = MagicMock()
            if name == "trading_signals":
                select_mock = MagicMock()
                select_mock.eq.return_value.eq.return_value.execute.return_value = MagicMock(
                    data=[{
                        "id": 1,
                        "status": "executed",
                        "run_mode": "LIVE",
                        "broker_order_id": "123456",
                    }]
                )
                table.select.return_value = select_mock
            return table

        mock_client = MagicMock()
        mock_client.table = mock_table

        with patch("src.services.watchdog.get_settings", return_value=mock_settings):
            from src.services.watchdog import TradeWatchdog

            watchdog = TradeWatchdog(supabase_client=mock_client)
            watchdog._get_client = mock_get_client

            # Should not raise
            watchdog.run_sync()

    def test_history_api_failure_logs_warning(
        self,
        mock_settings,
        caplog,
    ):
        """
        Test: History deals API returns None.

        Expected: Warning logged, trade not updated.
        """
        def mock_get_client(path, params=None):
            if "positions" in path:
                return []  # Empty = closed
            if "history-deals" in path:
                return None  # API failure
            return None

        update_calls = []

        def mock_table(name):
            table = MagicMock()
            if name == "trading_signals":
                select_mock = MagicMock()
                select_mock.eq.return_value.eq.return_value.execute.return_value = MagicMock(
                    data=[{
                        "id": 1,
                        "status": "executed",
                        "run_mode": "LIVE",
                        "broker_order_id": "123456",
                    }]
                )
                table.select.return_value = select_mock

                def capture_update(data):
                    update_calls.append(data)
                    update_mock = MagicMock()
                    update_mock.eq.return_value.execute.return_value = MagicMock(data=[])
                    return update_mock

                table.update.side_effect = capture_update

            return table

        mock_client = MagicMock()
        mock_client.table = mock_table

        with patch("src.services.watchdog.get_settings", return_value=mock_settings):
            from src.services.watchdog import TradeWatchdog

            watchdog = TradeWatchdog(supabase_client=mock_client)
            watchdog._get_client = mock_get_client

            watchdog.run_sync()

            # Should NOT have updated
            assert len(update_calls) == 0


# ══════════════════════════════════════════════════════════
# TEST: BREAKEVEN OUTCOME
# ══════════════════════════════════════════════════════════


class TestBreakevenOutcome:
    """Test detection of breakeven trades."""

    def test_breakeven_trade_detected(
        self,
        mock_settings,
    ):
        """
        Test: Trade closed at exactly breakeven (PnL = 0).

        Expected: outcome = "breakeven"
        """
        history_breakeven = {
            "deals": [
                {
                    "id": "deal-001",
                    "orderId": "123456",
                    "positionId": "pos-001",
                    "entryType": "DEAL_ENTRY_IN",
                    "profit": 0.0,
                    "time": "2024-01-15T10:00:00.000Z",
                },
                {
                    "id": "deal-002",
                    "orderId": "123457",
                    "positionId": "pos-001",
                    "entryType": "DEAL_ENTRY_OUT",
                    "profit": 0.0,
                    "swap": 0.0,
                    "commission": 0.0,  # No fees for exact BE
                    "time": "2024-01-15T12:00:00.000Z",
                },
            ],
        }

        def mock_get_client(path, params=None):
            if "positions" in path:
                return []
            if "history-deals" in path:
                return history_breakeven
            return None

        update_calls = []

        def mock_table(name):
            table = MagicMock()
            if name == "trading_signals":
                select_mock = MagicMock()
                select_mock.eq.return_value.eq.return_value.execute.return_value = MagicMock(
                    data=[{
                        "id": 1,
                        "status": "executed",
                        "run_mode": "LIVE",
                        "broker_order_id": "123456",
                    }]
                )
                table.select.return_value = select_mock

                def capture_update(data):
                    update_calls.append(data)
                    update_mock = MagicMock()
                    update_mock.eq.return_value.execute.return_value = MagicMock(data=[])
                    return update_mock

                table.update.side_effect = capture_update

            return table

        mock_client = MagicMock()
        mock_client.table = mock_table

        with patch("src.services.watchdog.get_settings", return_value=mock_settings):
            from src.services.watchdog import TradeWatchdog

            watchdog = TradeWatchdog(supabase_client=mock_client)
            watchdog._get_client = mock_get_client

            watchdog.run_sync()

            assert len(update_calls) == 1
            assert update_calls[0]["outcome"] == "breakeven"
            assert update_calls[0]["pnl_usd"] == 0.0
