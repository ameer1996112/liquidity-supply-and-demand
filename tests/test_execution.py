"""
Test Suite: Execution Adapters (MetaApi & Edge Cases)
=====================================================

Tests the execution adapter layer:
- MetaApi order submission
- Broker rejection handling
- Relative pricing (SL/TP recalculation)
- Network timeout handling
- Order validation

These tests mock the MetaApi HTTP calls to verify logic without
real broker connections.
"""

import pytest
import requests
from unittest.mock import patch, MagicMock
from typing import Dict, Any

# Import modules upfront so patches work correctly
import src.adapters.execution.meta_api_adapter as meta_api_module
from src.adapters.execution.interfaces import OrderRequest, CloseRequest, ExecutionResult


# ══════════════════════════════════════════════════════════
# TEST: SUBMIT ORDER SUCCESS
# ══════════════════════════════════════════════════════════


class TestSubmitOrderSuccess:
    """Test successful order submission scenarios."""

    def test_submit_order_success_buy(
        self,
        order_request_buy,
        mock_metaapi_success,
        mock_metaapi_price,
        mock_settings,
    ):
        """
        Test: MetaApi returns 200 OK with orderId.

        Expected: result.status == "filled", broker_order_id populated.
        """
        def mock_get(*args, **kwargs):
            return mock_metaapi_price

        def mock_post(*args, **kwargs):
            return mock_metaapi_success

        with patch.object(meta_api_module, "get_settings", return_value=mock_settings), \
             patch("requests.get", side_effect=mock_get), \
             patch("requests.post", side_effect=mock_post):

            adapter = meta_api_module.MetaApiAdapter(
                token="test-token",
                account_id="test-account-id",
            )

            result = adapter.submit_order(order_request_buy)

            assert result.status == "filled"
            assert result.broker_order_id == "12345678"
            assert result.client_order_id == order_request_buy.client_order_id

    def test_submit_order_success_sell(
        self,
        order_request_sell,
        mock_settings,
    ):
        """
        Test: Sell order submission success.

        Expected: result.status == "filled".
        """
        mock_price_resp = MagicMock()
        mock_price_resp.status_code = 200
        mock_price_resp.json.return_value = {"bid": 1.2648, "ask": 1.2652}

        mock_order_resp = MagicMock()
        mock_order_resp.status_code = 200
        mock_order_resp.json.return_value = {"orderId": "87654321"}

        with patch.object(meta_api_module, "get_settings", return_value=mock_settings), \
             patch("requests.get", return_value=mock_price_resp), \
             patch("requests.post", return_value=mock_order_resp):

            adapter = meta_api_module.MetaApiAdapter(
                token="test-token",
                account_id="test-account-id",
            )

            result = adapter.submit_order(order_request_sell)

            assert result.status == "filled"
            assert result.broker_order_id == "87654321"


# ══════════════════════════════════════════════════════════
# TEST: BROKER REJECTION
# ══════════════════════════════════════════════════════════


class TestBrokerRejection:
    """Test broker rejection scenarios."""

    def test_broker_rejection_invalid_stops(
        self,
        order_request_buy,
        mock_settings,
    ):
        """
        Test: MetaApi returns 400 Invalid Stops.

        Expected: result.status == "failed", error message logged.
        """
        mock_price_resp = MagicMock()
        mock_price_resp.status_code = 200
        mock_price_resp.json.return_value = {"bid": 1.0848, "ask": 1.0852}

        mock_rejection_resp = MagicMock()
        mock_rejection_resp.status_code = 400
        mock_rejection_resp.text = "Invalid SL/TP levels for current price"

        with patch.object(meta_api_module, "get_settings", return_value=mock_settings), \
             patch("requests.get", return_value=mock_price_resp), \
             patch("requests.post", return_value=mock_rejection_resp):

            adapter = meta_api_module.MetaApiAdapter(
                token="test-token",
                account_id="test-account-id",
            )

            result = adapter.submit_order(order_request_buy)

            assert result.status == "failed"
            assert "400" in result.message
            assert result.broker_order_id is None

    def test_broker_rejection_insufficient_margin(
        self,
        order_request_buy,
        mock_settings,
    ):
        """
        Test: Broker rejects due to insufficient margin.

        Expected: result.status == "failed".
        """
        mock_price_resp = MagicMock()
        mock_price_resp.status_code = 200
        mock_price_resp.json.return_value = {"bid": 1.0848, "ask": 1.0852}

        mock_margin_resp = MagicMock()
        mock_margin_resp.status_code = 400
        mock_margin_resp.text = "Not enough margin"

        with patch.object(meta_api_module, "get_settings", return_value=mock_settings), \
             patch("requests.get", return_value=mock_price_resp), \
             patch("requests.post", return_value=mock_margin_resp):

            adapter = meta_api_module.MetaApiAdapter(
                token="test-token",
                account_id="test-account-id",
            )

            result = adapter.submit_order(order_request_buy)

            assert result.status == "failed"
            assert result.broker_order_id is None

    def test_broker_rejection_market_closed(
        self,
        order_request_buy,
        mock_settings,
    ):
        """
        Test: Broker rejects because market is closed.

        Expected: result.status == "failed".
        """
        mock_price_resp = MagicMock()
        mock_price_resp.status_code = 200
        mock_price_resp.json.return_value = {"bid": 1.0848, "ask": 1.0852}

        mock_closed_resp = MagicMock()
        mock_closed_resp.status_code = 400
        mock_closed_resp.text = "Market is closed"

        with patch.object(meta_api_module, "get_settings", return_value=mock_settings), \
             patch("requests.get", return_value=mock_price_resp), \
             patch("requests.post", return_value=mock_closed_resp):

            adapter = meta_api_module.MetaApiAdapter(
                token="test-token",
                account_id="test-account-id",
            )

            result = adapter.submit_order(order_request_buy)

            assert result.status == "failed"


# ══════════════════════════════════════════════════════════
# TEST: RELATIVE PRICING (SL/TP RECALCULATION)
# ══════════════════════════════════════════════════════════


class TestRelativePricing:
    """Test SL/TP recalculation based on current price."""

    def test_relative_pricing_buy_order(
        self,
        order_request_buy,
        mock_settings,
    ):
        """
        Test: Adapter converts absolute SL/TP to relative distances for BUY.

        Input: entry=1.0850, sl=1.0800, tp=1.0950
        Current ask: 1.0860 (price moved up)

        Expected: SL/TP recalculated from current ask:
        - SL distance: 0.0050 (entry - sl)
        - TP distance: 0.0100 (tp - entry)
        - New SL: 1.0860 - 0.0050 = 1.0810
        - New TP: 1.0860 + 0.0100 = 1.0960
        """
        mock_price_resp = MagicMock()
        mock_price_resp.status_code = 200
        mock_price_resp.json.return_value = {"bid": 1.0858, "ask": 1.0860}

        mock_order_resp = MagicMock()
        mock_order_resp.status_code = 200
        mock_order_resp.json.return_value = {"orderId": "12345"}

        captured_payload = {}

        def capture_post(url, json=None, **kwargs):
            captured_payload.update(json or {})
            return mock_order_resp

        with patch.object(meta_api_module, "get_settings", return_value=mock_settings), \
             patch("requests.get", return_value=mock_price_resp), \
             patch("requests.post", side_effect=capture_post):

            adapter = meta_api_module.MetaApiAdapter(
                token="test-token",
                account_id="test-account-id",
            )

            result = adapter.submit_order(order_request_buy)

            # Verify recalculated values
            assert result.status == "filled"
            # SL should be current ask - original distance
            expected_sl = round(1.0860 - 0.0050, 5)  # 1.0810
            expected_tp = round(1.0860 + 0.0100, 5)  # 1.0960

            assert captured_payload.get("stopLoss") == expected_sl
            assert captured_payload.get("takeProfit") == expected_tp

    def test_relative_pricing_sell_order(
        self,
        order_request_sell,
        mock_settings,
    ):
        """
        Test: Adapter converts absolute SL/TP to relative distances for SELL.

        Input: entry=1.2650, sl=1.2700, tp=1.2550
        Current bid: 1.2640 (price moved down)

        Expected: SL/TP recalculated from current bid:
        - SL distance: 0.0050 (sl - entry)
        - TP distance: 0.0100 (entry - tp)
        - New SL: 1.2640 + 0.0050 = 1.2690
        - New TP: 1.2640 - 0.0100 = 1.2540
        """
        mock_price_resp = MagicMock()
        mock_price_resp.status_code = 200
        mock_price_resp.json.return_value = {"bid": 1.2640, "ask": 1.2644}

        mock_order_resp = MagicMock()
        mock_order_resp.status_code = 200
        mock_order_resp.json.return_value = {"orderId": "54321"}

        captured_payload = {}

        def capture_post(url, json=None, **kwargs):
            captured_payload.update(json or {})
            return mock_order_resp

        with patch.object(meta_api_module, "get_settings", return_value=mock_settings), \
             patch("requests.get", return_value=mock_price_resp), \
             patch("requests.post", side_effect=capture_post):

            adapter = meta_api_module.MetaApiAdapter(
                token="test-token",
                account_id="test-account-id",
            )

            result = adapter.submit_order(order_request_sell)

            assert result.status == "filled"
            expected_sl = round(1.2640 + 0.0050, 5)  # 1.2690
            expected_tp = round(1.2640 - 0.0100, 5)  # 1.2540

            assert captured_payload.get("stopLoss") == expected_sl
            assert captured_payload.get("takeProfit") == expected_tp

    def test_relative_pricing_price_fetch_failure_uses_original(
        self,
        order_request_buy,
        mock_settings,
    ):
        """
        Test: If price fetch fails, adapter uses original SL/TP values.

        Expected: Original SL/TP used as fallback.
        """
        mock_price_error = MagicMock()
        mock_price_error.status_code = 500
        mock_price_error.text = "Internal Server Error"

        mock_order_resp = MagicMock()
        mock_order_resp.status_code = 200
        mock_order_resp.json.return_value = {"orderId": "12345"}

        captured_payload = {}

        def capture_post(url, json=None, **kwargs):
            captured_payload.update(json or {})
            return mock_order_resp

        with patch.object(meta_api_module, "get_settings", return_value=mock_settings), \
             patch("requests.get", return_value=mock_price_error), \
             patch("requests.post", side_effect=capture_post):

            adapter = meta_api_module.MetaApiAdapter(
                token="test-token",
                account_id="test-account-id",
            )

            result = adapter.submit_order(order_request_buy)

            assert result.status == "filled"
            # Should fall back to original values
            assert captured_payload.get("stopLoss") == order_request_buy.sl
            assert captured_payload.get("takeProfit") == order_request_buy.tp


# ══════════════════════════════════════════════════════════
# TEST: NETWORK TIMEOUT
# ══════════════════════════════════════════════════════════


class TestNetworkTimeout:
    """Test network timeout handling."""

    def test_network_timeout_on_submit(
        self,
        order_request_buy,
        mock_settings,
    ):
        """
        Test: requests.Timeout on order submission.

        Expected: result.status == "failed", doesn't crash.
        """
        mock_price_resp = MagicMock()
        mock_price_resp.status_code = 200
        mock_price_resp.json.return_value = {"bid": 1.0848, "ask": 1.0852}

        with patch.object(meta_api_module, "get_settings", return_value=mock_settings), \
             patch("requests.get", return_value=mock_price_resp), \
             patch("requests.post", side_effect=requests.Timeout("Connection timed out")):

            adapter = meta_api_module.MetaApiAdapter(
                token="test-token",
                account_id="test-account-id",
            )

            result = adapter.submit_order(order_request_buy)

            assert result.status == "failed"
            assert "timed out" in result.message.lower() or "timeout" in result.message.lower()
            assert result.broker_order_id is None

    def test_network_timeout_on_price_fetch(
        self,
        order_request_buy,
        mock_settings,
    ):
        """
        Test: requests.Timeout on price fetch.

        Expected: Adapter continues with original prices.
        """
        mock_order_resp = MagicMock()
        mock_order_resp.status_code = 200
        mock_order_resp.json.return_value = {"orderId": "12345"}

        def mock_get(*args, **kwargs):
            raise requests.Timeout("Price fetch timed out")

        captured_payload = {}

        def capture_post(url, json=None, **kwargs):
            captured_payload.update(json or {})
            return mock_order_resp

        with patch.object(meta_api_module, "get_settings", return_value=mock_settings), \
             patch("requests.get", side_effect=mock_get), \
             patch("requests.post", side_effect=capture_post):

            adapter = meta_api_module.MetaApiAdapter(
                token="test-token",
                account_id="test-account-id",
            )

            result = adapter.submit_order(order_request_buy)

            # Should still succeed with fallback prices
            assert result.status == "filled"
            assert captured_payload.get("stopLoss") == order_request_buy.sl
            assert captured_payload.get("takeProfit") == order_request_buy.tp

    def test_connection_error_on_submit(
        self,
        order_request_buy,
        mock_settings,
    ):
        """
        Test: Connection error (network down) on submission.

        Expected: result.status == "failed", graceful handling.
        """
        mock_price_resp = MagicMock()
        mock_price_resp.status_code = 200
        mock_price_resp.json.return_value = {"bid": 1.0848, "ask": 1.0852}

        with patch.object(meta_api_module, "get_settings", return_value=mock_settings), \
             patch("requests.get", return_value=mock_price_resp), \
             patch("requests.post", side_effect=requests.ConnectionError("Network unreachable")):

            adapter = meta_api_module.MetaApiAdapter(
                token="test-token",
                account_id="test-account-id",
            )

            result = adapter.submit_order(order_request_buy)

            assert result.status == "failed"
            assert result.broker_order_id is None


# ══════════════════════════════════════════════════════════
# TEST: INVALID JSON RESPONSE
# ══════════════════════════════════════════════════════════


class TestInvalidJsonResponse:
    """Test handling of invalid JSON responses from broker."""

    def test_invalid_json_response(
        self,
        order_request_buy,
        mock_settings,
    ):
        """
        Test: Broker returns non-JSON response.

        Expected: result.status == "failed".
        """
        mock_price_resp = MagicMock()
        mock_price_resp.status_code = 200
        mock_price_resp.json.return_value = {"bid": 1.0848, "ask": 1.0852}

        mock_invalid_resp = MagicMock()
        mock_invalid_resp.status_code = 200
        mock_invalid_resp.text = "Not a JSON response"
        mock_invalid_resp.json.side_effect = ValueError("Invalid JSON")

        with patch.object(meta_api_module, "get_settings", return_value=mock_settings), \
             patch("requests.get", return_value=mock_price_resp), \
             patch("requests.post", return_value=mock_invalid_resp):

            adapter = meta_api_module.MetaApiAdapter(
                token="test-token",
                account_id="test-account-id",
            )

            result = adapter.submit_order(order_request_buy)

            assert result.status == "failed"
            assert "json" in result.message.lower()

    def test_missing_order_id_in_response(
        self,
        order_request_buy,
        mock_settings,
    ):
        """
        Test: Broker returns valid JSON but missing orderId.

        Expected: result.status == "failed".
        """
        mock_price_resp = MagicMock()
        mock_price_resp.status_code = 200
        mock_price_resp.json.return_value = {"bid": 1.0848, "ask": 1.0852}

        mock_no_id_resp = MagicMock()
        mock_no_id_resp.status_code = 200
        mock_no_id_resp.json.return_value = {"status": "success", "message": "Order placed"}
        mock_no_id_resp.text = '{"status": "success", "message": "Order placed"}'

        with patch.object(meta_api_module, "get_settings", return_value=mock_settings), \
             patch("requests.get", return_value=mock_price_resp), \
             patch("requests.post", return_value=mock_no_id_resp):

            adapter = meta_api_module.MetaApiAdapter(
                token="test-token",
                account_id="test-account-id",
            )

            result = adapter.submit_order(order_request_buy)

            assert result.status == "failed"
            assert "missing" in result.message.lower() or "orderid" in result.message.lower()


# ══════════════════════════════════════════════════════════
# TEST: CLOSE ORDER
# ══════════════════════════════════════════════════════════


class TestCloseOrder:
    """Test order closing functionality."""

    def test_close_order_success(
        self,
        close_request,
        mock_settings,
    ):
        """
        Test: Successful position close.

        Expected: result.status == "filled".
        """
        mock_close_resp = MagicMock()
        mock_close_resp.status_code = 200
        mock_close_resp.json.return_value = {"orderId": "close-123"}

        with patch.object(meta_api_module, "get_settings", return_value=mock_settings), \
             patch("requests.post", return_value=mock_close_resp):

            adapter = meta_api_module.MetaApiAdapter(
                token="test-token",
                account_id="test-account-id",
            )

            result = adapter.close_order(close_request)

            assert result.status == "filled"

    def test_close_order_missing_broker_order_id(
        self,
        mock_settings,
    ):
        """
        Test: Close order without broker_order_id fails.

        Expected: result.status == "failed".
        """
        close_req = CloseRequest(
            client_order_id="test-close",
            symbol="EURUSD",
            side="buy",
            size=0.10,
            # broker_order_id is None
        )

        with patch.object(meta_api_module, "get_settings", return_value=mock_settings):

            adapter = meta_api_module.MetaApiAdapter(
                token="test-token",
                account_id="test-account-id",
            )

            result = adapter.close_order(close_req)

            assert result.status == "failed"
            assert "broker_order_id" in result.message.lower() or "positionid" in result.message.lower()


# ══════════════════════════════════════════════════════════
# TEST: ADAPTER VALIDATION
# ══════════════════════════════════════════════════════════


class TestAdapterValidation:
    """Test adapter initialization and validation."""

    def test_adapter_invalid_side(
        self,
        mock_settings,
    ):
        """
        Test: Invalid side value in order request.

        Expected: result.status == "failed".
        """
        invalid_request = OrderRequest(
            client_order_id="test",
            symbol="EURUSD",
            side="long",  # Invalid - should be "buy" or "sell"
            size=0.10,
        )

        with patch.object(meta_api_module, "get_settings", return_value=mock_settings):

            adapter = meta_api_module.MetaApiAdapter(
                token="test-token",
                account_id="test-account-id",
            )

            result = adapter.submit_order(invalid_request)

            assert result.status == "failed"
            assert "side" in result.message.lower() or "invalid" in result.message.lower()

    def test_adapter_empty_credentials_raises(
        self,
        mock_settings,
    ):
        """
        Test: Empty token or account_id raises ValueError.

        Expected: ValueError raised.
        """
        with patch.object(meta_api_module, "get_settings", return_value=mock_settings):

            with pytest.raises(ValueError):
                meta_api_module.MetaApiAdapter(token="", account_id="test-account")

            with pytest.raises(ValueError):
                meta_api_module.MetaApiAdapter(token="test-token", account_id="")


# ══════════════════════════════════════════════════════════
# TEST: DIGIT PRECISION
# ══════════════════════════════════════════════════════════


class TestDigitPrecision:
    """Test decimal precision handling for different symbols."""

    def test_digit_inference_forex(self, mock_settings):
        """Test: FX pairs use 5 decimal digits."""
        digits = meta_api_module.MetaApiAdapter._infer_digits(1.08523, "EURUSD")
        assert digits == 5

    def test_digit_inference_gold(self, mock_settings):
        """Test: Gold uses 2 decimal digits."""
        digits = meta_api_module.MetaApiAdapter._infer_digits(None, "XAUUSD")
        assert digits == 2

    def test_digit_inference_indices(self, mock_settings):
        """Test: Indices use 2 decimal digits."""
        assert meta_api_module.MetaApiAdapter._infer_digits(None, "NAS100") == 2
        assert meta_api_module.MetaApiAdapter._infer_digits(None, "US30") == 2
        assert meta_api_module.MetaApiAdapter._infer_digits(None, "DE40") == 2

    def test_digit_inference_jpy_pairs(self, mock_settings):
        """Test: JPY pairs infer from price (3 decimal places)."""
        # JPY pairs typically have 3 decimals
        digits = meta_api_module.MetaApiAdapter._infer_digits(150.123, "USDJPY")
        assert digits >= 3
