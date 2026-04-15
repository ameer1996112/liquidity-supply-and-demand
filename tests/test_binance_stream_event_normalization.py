from src.services.binance_streaming_service import _extract_realized_pnl_and_order_id


def test_extract_realized_pnl_and_order_id_from_order_trade_update():
    evt = {
        "e": "ORDER_TRADE_UPDATE",
        "o": {
            "x": "TRADE",
            "X": "FILLED",
            "rp": "12.34",
            "i": 123456,
        },
    }
    assert _extract_realized_pnl_and_order_id(evt) == (12.34, "123456")

