from src.services.bybit_streaming_service import _extract_realized_pnl_and_order_id


def test_extract_realized_pnl_and_order_id_from_execution_event():
    evt = {
        "topic": "execution",
        "data": [
            {"symbol": "BTCUSDT", "orderId": "abc123", "execPnl": "5.5"}
        ],
    }
    assert _extract_realized_pnl_and_order_id(evt) == (5.5, "abc123")

